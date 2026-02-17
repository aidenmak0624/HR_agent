#!/usr/bin/env bash
# ============================================
# AWS ECS Fargate — One-Click Deploy Script
# HR Intelligence Platform
# ============================================
#
# Prerequisites:
#   1. Install AWS CLI v2: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
#   2. Run: aws configure  (enter your Access Key, Secret Key, region)
#   3. Install Docker (for local image build)
#
# Usage:
#   chmod +x deploy/aws/deploy.sh
#   ./deploy/aws/deploy.sh
#
# ============================================

set -euo pipefail

# ── Configuration (override via environment) ──
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text 2>/dev/null)}"
SERVICE_NAME="${AWS_SERVICE_NAME:-hr-platform}"
CLUSTER_NAME="${AWS_CLUSTER_NAME:-hr-platform-cluster}"
ECR_REPO="${AWS_ECR_REPO:-hr-platform}"

# Database (set to "skip" to use SQLite)
DB_INSTANCE="${AWS_DB_INSTANCE:-hr-platform-db}"
DB_NAME="${AWS_DB_NAME:-hr_platform}"
DB_USER="${AWS_DB_USER:-hr_user}"
DB_PASSWORD="${AWS_DB_PASSWORD:-}"

# ── Colors ────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# ── Preflight checks ─────────────────────────
echo ""
echo "============================================"
echo "  AWS ECS Fargate — Deployment"
echo "  Account: ${AWS_ACCOUNT_ID}"
echo "  Region:  ${AWS_REGION}"
echo "  Service: ${SERVICE_NAME}"
echo "============================================"
echo ""

[ -z "$AWS_ACCOUNT_ID" ] && fail "Cannot determine AWS account. Run: aws configure"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

cd "$(dirname "$0")/../.."   # Navigate to project root

# ── Step 1: Create ECR repository ─────────────
info "Setting up ECR repository..."
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" &>/dev/null || \
    aws ecr create-repository \
        --repository-name "$ECR_REPO" \
        --region "$AWS_REGION" \
        --image-scanning-configuration scanOnPush=true \
        --query 'repository.repositoryUri' --output text
ok "ECR repository ready: ${ECR_URI}"

# ── Step 2: Build & push Docker image ─────────
info "Logging into ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

info "Building Docker image..."
docker build -t "${ECR_REPO}:latest" .
docker tag "${ECR_REPO}:latest" "${ECR_URI}:latest"

info "Pushing image to ECR..."
docker push "${ECR_URI}:latest"
ok "Image pushed to ${ECR_URI}:latest"

# ── Step 3: Create ECS cluster ────────────────
info "Setting up ECS cluster..."
aws ecs describe-clusters --clusters "$CLUSTER_NAME" --region "$AWS_REGION" \
    --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE" || \
    aws ecs create-cluster --cluster-name "$CLUSTER_NAME" --region "$AWS_REGION" \
        --capacity-providers FARGATE --default-capacity-provider-strategy \
        capacityProvider=FARGATE,weight=1 --query 'cluster.clusterArn' --output text
ok "ECS cluster ready"

# ── Step 4: Create IAM roles ─────────────────
info "Setting up IAM roles..."

# Task execution role (for ECS to pull images and write logs)
EXEC_ROLE_NAME="${SERVICE_NAME}-ecs-exec-role"
if ! aws iam get-role --role-name "$EXEC_ROLE_NAME" &>/dev/null; then
    aws iam create-role \
        --role-name "$EXEC_ROLE_NAME" \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' --query 'Role.Arn' --output text

    aws iam attach-role-policy \
        --role-name "$EXEC_ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
fi

EXEC_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${EXEC_ROLE_NAME}"
ok "IAM roles ready"

# ── Step 5: Create CloudWatch log group ───────
info "Setting up CloudWatch logging..."
aws logs create-log-group \
    --log-group-name "/ecs/${SERVICE_NAME}" \
    --region "$AWS_REGION" 2>/dev/null || true
ok "Log group ready"

# ── Step 6: Create VPC & Security Group (if needed)
info "Setting up networking..."

# Use default VPC
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
    --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")

if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
    warn "No default VPC found. Creating one..."
    VPC_ID=$(aws ec2 create-default-vpc --query 'Vpc.VpcId' --output text --region "$AWS_REGION" 2>/dev/null || echo "")
    [ -z "$VPC_ID" ] && fail "Could not create default VPC. Create one manually in the AWS console."
fi

# Get subnets
SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters Name=vpc-id,Values="$VPC_ID" \
    --query 'Subnets[*].SubnetId' --output text --region "$AWS_REGION" | tr '\t' ',')

# Create security group for the service
SG_NAME="${SERVICE_NAME}-sg"
SG_ID=$(aws ec2 describe-security-groups \
    --filters Name=group-name,Values="$SG_NAME" Name=vpc-id,Values="$VPC_ID" \
    --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION" 2>/dev/null)

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$SG_NAME" \
        --description "HR Platform ECS service" \
        --vpc-id "$VPC_ID" \
        --query 'GroupId' --output text --region "$AWS_REGION")

    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp --port 5050 --cidr 0.0.0.0/0 --region "$AWS_REGION"

    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp --port 80 --cidr 0.0.0.0/0 --region "$AWS_REGION"
fi
ok "Networking ready (VPC: ${VPC_ID})"

# ── Step 7: Store secrets in SSM ──────────────
info "Storing secrets in SSM Parameter Store..."

JWT_SECRET="${JWT_SECRET:-$(openssl rand -base64 32)}"

store_param() {
    aws ssm put-parameter \
        --name "/hr-platform/$1" \
        --value "$2" \
        --type SecureString \
        --overwrite \
        --region "$AWS_REGION" --query 'Version' --output text
}

store_param "jwt-secret" "$JWT_SECRET"

if [ -n "${OPENAI_API_KEY:-}" ]; then
    store_param "openai-api-key" "$OPENAI_API_KEY"
fi

ok "Secrets stored in SSM"

# ── Step 8: Register task definition ──────────
info "Registering ECS task definition..."

# Build environment variables
ENV_VARS='[
    {"name":"PORT","value":"5050"},
    {"name":"WORKERS","value":"2"},
    {"name":"TIMEOUT","value":"120"},
    {"name":"ENVIRONMENT","value":"production"},
    {"name":"LOG_LEVEL","value":"INFO"},
    {"name":"DATABASE_URL","value":"sqlite:///hr_platform.db"}
]'

cat > /tmp/task-def.json <<EOF
{
    "family": "${SERVICE_NAME}",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "512",
    "memory": "1024",
    "executionRoleArn": "${EXEC_ROLE_ARN}",
    "containerDefinitions": [
        {
            "name": "${SERVICE_NAME}",
            "image": "${ECR_URI}:latest",
            "portMappings": [
                {"containerPort": 5050, "protocol": "tcp"}
            ],
            "environment": ${ENV_VARS},
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/${SERVICE_NAME}",
                    "awslogs-region": "${AWS_REGION}",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "healthCheck": {
                "command": ["CMD-SHELL", "curl -f http://localhost:5050/api/v2/health || exit 1"],
                "interval": 30,
                "timeout": 10,
                "retries": 3,
                "startPeriod": 30
            },
            "essential": true
        }
    ]
}
EOF

aws ecs register-task-definition \
    --cli-input-json file:///tmp/task-def.json \
    --region "$AWS_REGION" --query 'taskDefinition.taskDefinitionArn' --output text
ok "Task definition registered"

# ── Step 9: Create or update ECS service ──────
info "Deploying ECS service..."

# Pick first 2 subnets for multi-AZ
SUBNET_ARR=(${SUBNET_IDS//,/ })
SUBNETS="${SUBNET_ARR[0]}"
[ ${#SUBNET_ARR[@]} -gt 1 ] && SUBNETS="${SUBNET_ARR[0]},${SUBNET_ARR[1]}"

if aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" \
    --region "$AWS_REGION" --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    # Update existing service
    aws ecs update-service \
        --cluster "$CLUSTER_NAME" \
        --service "$SERVICE_NAME" \
        --task-definition "$SERVICE_NAME" \
        --force-new-deployment \
        --region "$AWS_REGION" --query 'service.serviceArn' --output text
else
    # Create new service
    aws ecs create-service \
        --cluster "$CLUSTER_NAME" \
        --service-name "$SERVICE_NAME" \
        --task-definition "$SERVICE_NAME" \
        --desired-count 1 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}" \
        --region "$AWS_REGION" --query 'service.serviceArn' --output text
fi
ok "ECS service deployed"

# ── Step 10: Wait & get public IP ─────────────
info "Waiting for task to start (this may take 1-2 minutes)..."
sleep 30

TASK_ARN=$(aws ecs list-tasks --cluster "$CLUSTER_NAME" --service-name "$SERVICE_NAME" \
    --region "$AWS_REGION" --query 'taskArns[0]' --output text)

if [ "$TASK_ARN" != "None" ] && [ -n "$TASK_ARN" ]; then
    ENI_ID=$(aws ecs describe-tasks --cluster "$CLUSTER_NAME" --tasks "$TASK_ARN" \
        --region "$AWS_REGION" \
        --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)

    PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids "$ENI_ID" \
        --region "$AWS_REGION" \
        --query 'NetworkInterfaces[0].Association.PublicIp' --output text 2>/dev/null || echo "pending")
else
    PUBLIC_IP="pending (task still starting)"
fi

echo ""
echo "============================================"
echo -e "  ${GREEN}Deployment complete!${NC}"
echo ""
echo "  Public IP: ${PUBLIC_IP}"
echo "  URL: http://${PUBLIC_IP}:5050"
echo "  Cluster: ${CLUSTER_NAME}"
echo "  Service: ${SERVICE_NAME}"
echo ""
echo "  Test it:"
echo "    curl http://${PUBLIC_IP}:5050/api/v2/health"
echo ""
echo "  View logs:"
echo "    aws logs tail /ecs/${SERVICE_NAME} --follow --region ${AWS_REGION}"
echo ""
echo "  Update later:"
echo "    ./deploy/aws/deploy.sh"
echo ""
echo "  Add a load balancer + custom domain:"
echo "    See deploy/DEPLOY_GUIDE.md for ALB setup"
echo "============================================"
