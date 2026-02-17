# HR Intelligence Platform — Cloud Deployment Guide

## What's in this folder

```
deploy/
├── DEPLOY_GUIDE.md          ← You are here
├── gcp/
│   ├── deploy.sh            ← One-command GCP Cloud Run deploy
│   └── cloudbuild.yaml      ← CI/CD pipeline for auto-deploy on git push
└── aws/
    ├── deploy.sh            ← One-command AWS ECS Fargate deploy
    └── task-definition.json ← ECS task template (for manual setup)
```

The project root also has:
- `Dockerfile` — Multi-stage production image (already built)
- `docker-compose.yml` — Full local stack (Postgres + Redis + App + Nginx)
- `.env.example` — All environment variables documented
- `nginx.conf` — Reverse proxy config

---

## Quick Comparison: GCP vs AWS

| Feature | GCP Cloud Run | AWS ECS Fargate |
|---------|---------------|-----------------|
| **Complexity** | Simpler — fewer moving parts | More setup — VPC, IAM, etc. |
| **Pricing** | Pay per request (scales to zero) | Pay per running task (min ~$0.01/hr) |
| **Free tier** | 2M requests/month free | 750 hours/month for 12 months |
| **Database** | Cloud SQL (managed Postgres) | RDS (managed Postgres) |
| **Custom domain** | Built-in with Cloud Run mapping | Requires ALB + Route53 |
| **Best for** | Side projects, demos, MVPs | Production workloads, enterprise |
| **Auto-scaling** | Automatic (0 to N instances) | Configurable (1 to N tasks) |

**Recommendation**: Start with GCP Cloud Run — it's the fastest path to a working deployment, scales to zero when idle (saves money), and has the simplest setup.

---

## Prerequisites

### For both platforms

1. **Docker** installed locally (for building/testing the image):
   ```bash
   # macOS
   brew install --cask docker

   # or download Docker Desktop: https://www.docker.com/products/docker-desktop
   ```

2. **Test locally first** to make sure the image works:
   ```bash
   # Build the image
   docker build -t hr-platform .

   # Run it (uses SQLite, no external dependencies)
   docker run -p 5050:5050 -e JWT_SECRET=test-secret hr-platform

   # Visit http://localhost:5050 in your browser
   ```

3. **Environment variables** — copy and fill in:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (at minimum: JWT_SECRET)
   ```

### For GCP

```bash
# Install Google Cloud CLI
# macOS:
brew install --cask google-cloud-sdk
# Other: https://cloud.google.com/sdk/docs/install

# Login and set project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable billing (required for Cloud Run)
# Go to: https://console.cloud.google.com/billing
```

### For AWS

```bash
# Install AWS CLI v2
# macOS:
brew install awscli
# Other: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

# Configure credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region (e.g., us-east-1), Output (json)
```

---

## Option A: Deploy to GCP Cloud Run

### One-command deploy

```bash
chmod +x deploy/gcp/deploy.sh
./deploy/gcp/deploy.sh
```

This script will:
1. Enable required GCP APIs
2. Build the Docker image using Cloud Build (no local Docker needed)
3. Create a Cloud SQL PostgreSQL instance (optional — set `GCP_DB_INSTANCE=skip` for SQLite)
4. Store secrets in Secret Manager
5. Deploy to Cloud Run
6. Print the public URL

### What you'll get

```
https://hr-platform-xxxxx-uc.a.run.app
```

The app scales to zero when idle (no cost) and auto-scales up when traffic arrives.

### Configuration options

Override any setting with environment variables:

```bash
# Use a different region
GCP_REGION=europe-west1 ./deploy/gcp/deploy.sh

# Skip Cloud SQL (use SQLite instead)
GCP_DB_INSTANCE=skip ./deploy/gcp/deploy.sh

# Set OpenAI key for AI features
OPENAI_API_KEY=sk-xxx ./deploy/gcp/deploy.sh
```

### Set up auto-deploy from GitHub

```bash
# Connect your GitHub repo to Cloud Build
gcloud builds triggers create github \
  --repo-name=HR_agent \
  --repo-owner=YOUR_GITHUB_USERNAME \
  --branch-pattern="^main$" \
  --build-config=deploy/gcp/cloudbuild.yaml

# Now every push to main automatically deploys!
```

### Custom domain

```bash
# Map a custom domain (requires DNS verification)
gcloud run domain-mappings create \
  --service hr-platform \
  --domain hr.yourdomain.com \
  --region us-central1
```

### View logs

```bash
# Stream live logs
gcloud run services logs read hr-platform --region=us-central1 --follow

# Or in the console: https://console.cloud.google.com/run
```

### Estimated cost

- **Free tier**: 2 million requests/month, 360k vCPU-seconds, 180k GiB-seconds
- **After free tier**: ~$0.00002400 per vCPU-second + $0.00000250 per GiB-second
- **Cloud SQL** (if used): ~$7/month for db-f1-micro
- **For a demo/side project**: Likely $0–5/month

---

## Option B: Deploy to AWS ECS Fargate

### One-command deploy

```bash
chmod +x deploy/aws/deploy.sh
./deploy/aws/deploy.sh
```

This script will:
1. Create an ECR repository and push the Docker image
2. Create an ECS cluster
3. Set up IAM roles and security groups
4. Store secrets in SSM Parameter Store
5. Register an ECS task definition
6. Create and deploy the ECS service
7. Print the public IP

### What you'll get

```
http://54.xxx.xxx.xxx:5050
```

### Configuration options

```bash
# Use a different region
AWS_REGION=us-west-2 ./deploy/aws/deploy.sh

# Set OpenAI key for AI features
OPENAI_API_KEY=sk-xxx ./deploy/aws/deploy.sh
```

### Add a load balancer (for custom domain + HTTPS)

After the initial deploy, add an Application Load Balancer:

```bash
# Create target group
aws elbv2 create-target-group \
  --name hr-platform-tg \
  --protocol HTTP \
  --port 5050 \
  --vpc-id YOUR_VPC_ID \
  --target-type ip \
  --health-check-path /api/v2/health

# Create ALB
aws elbv2 create-load-balancer \
  --name hr-platform-alb \
  --subnets SUBNET_1 SUBNET_2 \
  --security-groups YOUR_SG_ID

# Create listener
aws elbv2 create-listener \
  --load-balancer-arn ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=TG_ARN

# Update ECS service to use the load balancer
aws ecs update-service \
  --cluster hr-platform-cluster \
  --service hr-platform \
  --load-balancers targetGroupArn=TG_ARN,containerName=hr-platform,containerPort=5050
```

For HTTPS, add an ACM certificate and create an HTTPS listener on port 443.

### View logs

```bash
# Stream live logs
aws logs tail /ecs/hr-platform --follow --region us-east-1

# Or in the console: https://console.aws.amazon.com/ecs
```

### Estimated cost

- **Fargate**: ~$0.04048/vCPU/hour + $0.004445/GB/hour
- **For 0.5 vCPU + 1GB (our config)**: ~$15/month running 24/7
- **RDS** (if used): ~$13/month for db.t3.micro
- **Free tier** (first 12 months): 750 hours/month of t3.micro

---

## Using docker-compose (for VMs or local)

If you prefer deploying to a plain VM (GCE or EC2), use docker-compose:

```bash
# SSH into your VM, clone the repo, then:
cp .env.example .env
# Edit .env with your settings

# Start everything (Postgres + Redis + App + Nginx)
docker-compose up -d

# The app is now on port 80 (via Nginx)
# Health check: curl http://localhost/api/v2/health
```

This gives you the full stack: PostgreSQL, Redis cache, the Flask app with Gunicorn, and Nginx as a reverse proxy.

---

## Database Options

| Option | Best for | Setup |
|--------|----------|-------|
| **SQLite** (default) | Demos, single-user | No setup needed — works out of the box |
| **Cloud SQL / RDS** | Production, multi-user | Created by deploy scripts |
| **docker-compose Postgres** | Local dev, VM deploys | `docker-compose up -d` |

The app automatically falls back to SQLite if no `DATABASE_URL` is set.

---

## Troubleshooting

**Image fails to build**
```bash
# Check Docker daemon is running
docker info

# Build with verbose output
docker build --no-cache -t hr-platform . 2>&1 | tail -50
```

**App starts but health check fails**
```bash
# Check the container logs
docker logs CONTAINER_ID

# Common fix: PORT environment variable must be 5050
docker run -e PORT=5050 hr-platform
```

**Cloud Run: "Container failed to start"**
```bash
# Check Cloud Run logs
gcloud run services logs read hr-platform --limit=50

# Common cause: missing environment variable or wrong port
```

**ECS: Task keeps stopping**
```bash
# Check stopped task reason
aws ecs describe-tasks --cluster hr-platform-cluster \
  --tasks $(aws ecs list-tasks --cluster hr-platform-cluster \
    --desired-status STOPPED --query 'taskArns[0]' --output text) \
  --query 'tasks[0].stoppedReason'
```

**Database connection refused**
```bash
# For Cloud SQL: ensure Cloud SQL Auth proxy is connected
# For RDS: check security group allows inbound on port 5432
# Quick test: set DATABASE_URL to SQLite to rule out DB issues
```
