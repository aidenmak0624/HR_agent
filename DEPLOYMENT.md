# HR Intelligence Platform — Deployment Guide

## Prerequisites

- **Docker** & **Docker Compose** (v2+)
- **OpenAI API key** (required for GPT-4 agent)
- A server with at least 2 GB RAM, 2 CPU cores

---

## Quick Start (Docker Compose — Recommended)

### 1. Clone and configure

```bash
git clone <your-repo-url> hr_agent
cd hr_agent
cp .env.example .env
```

### 2. Edit `.env` with your secrets

At minimum, set these values:

```env
OPENAI_API_KEY=sk-your-actual-key
JWT_SECRET=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
POSTGRES_PASSWORD=<strong-password>
DEBUG=false
ENVIRONMENT=production
```

### 3. Launch the stack

```bash
docker compose up -d
```

This starts four services:

| Service | Purpose | Port |
|---------|---------|------|
| **postgres** | PostgreSQL 15 database | 5432 (internal) |
| **redis** | Cache, rate limiting, sessions | 6379 (internal) |
| **app** | Flask + Gunicorn (4 workers) | 5050 (internal) |
| **nginx** | Reverse proxy, static files | **80** (public) |

### 4. Verify

```bash
# Check all containers are healthy
docker compose ps

# Test the health endpoint
curl http://localhost/api/v2/health
```

Expected response: `{"status":"healthy","success":true,...}`

### 5. Access the app

Open `http://your-server-ip` in a browser. You'll see the login page.

Demo accounts are auto-seeded:

| Email | Password | Role |
|-------|----------|------|
| john.smith@company.com | password123 | Employee |
| sarah.chen@company.com | password123 | Manager |
| emily.rodriguez@company.com | password123 | HR Admin |

---

## Production Hardening

### Environment variables

Set these for production:

```env
DEBUG=false
ENVIRONMENT=production
WORKERS=4                # Adjust to CPU cores × 2
TIMEOUT=120
LOG_LEVEL=INFO
CORS_ORIGINS=https://yourdomain.com
```

### HTTPS with Let's Encrypt

Replace the nginx config with an SSL-enabled version:

```bash
# Install certbot
apt install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d yourdomain.com

# Auto-renewal is set up automatically
```

Update `nginx.conf` to redirect HTTP → HTTPS and serve on port 443.

### Database backups

```bash
# Manual backup
docker compose exec postgres pg_dump -U hr_user hr_platform > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres psql -U hr_user hr_platform < backup_20260215.sql
```

### Monitoring

The health endpoint returns component status:

```bash
curl http://localhost/api/v2/health
# {"checks":{"database":"ok","llm":"ok","redis":"ok"},"status":"healthy"}
```

The Docker healthcheck runs every 30 seconds automatically.

---

## Alternative: Manual Deployment (No Docker)

### 1. Install system dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip postgresql redis-server nginx
```

### 2. Set up PostgreSQL

```bash
sudo -u postgres createuser hr_user
sudo -u postgres createdb hr_platform -O hr_user
sudo -u postgres psql -c "ALTER USER hr_user PASSWORD 'your-password';"
```

### 3. Set up the app

```bash
cd hr_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your DATABASE_URL, OPENAI_API_KEY, etc.
```

### 4. Run with Gunicorn

```bash
gunicorn \
  --bind 0.0.0.0:5050 \
  --workers 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  src.app_v2:app
```

### 5. Set up as a systemd service

Create `/etc/systemd/system/hr-agent.service`:

```ini
[Unit]
Description=HR Intelligence Platform
After=network.target postgresql.service redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/hr_agent
Environment="PATH=/opt/hr_agent/venv/bin"
EnvironmentFile=/opt/hr_agent/.env
ExecStart=/opt/hr_agent/venv/bin/gunicorn \
  --bind 0.0.0.0:5050 \
  --workers 4 \
  --timeout 120 \
  src.app_v2:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable hr-agent
sudo systemctl start hr-agent
```

### 6. Configure nginx

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /static/ {
        alias /opt/hr_agent/frontend/static/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:5050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Cloud Platform Deployment

### AWS (ECS / EC2)

1. Push Docker image to ECR: `docker build -t hr-agent . && docker tag hr-agent:latest <account>.dkr.ecr.<region>.amazonaws.com/hr-agent:latest && docker push ...`
2. Create an ECS task definition referencing the image
3. Use RDS for PostgreSQL, ElastiCache for Redis
4. Set environment variables via ECS task definition or Secrets Manager

### Google Cloud Run

```bash
gcloud builds submit --tag gcr.io/<project>/hr-agent
gcloud run deploy hr-agent \
  --image gcr.io/<project>/hr-agent \
  --port 5050 \
  --set-env-vars "DATABASE_URL=...,OPENAI_API_KEY=..." \
  --allow-unauthenticated
```

Use Cloud SQL for PostgreSQL and Memorystore for Redis.

### Railway / Render / Fly.io

These platforms auto-detect the Dockerfile. Just connect your repo, set the environment variables in their dashboard, and deploy. Add a managed PostgreSQL and Redis add-on.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Connection refused` on health check | Server still starting (~20s), or port mismatch |
| `redis: unavailable` in health check | Redis not running or REDIS_URL wrong — app works without it |
| `llm: unavailable` | OPENAI_API_KEY not set or invalid |
| Database tables missing | App auto-creates and seeds on first start |
| Static files 404 | Check nginx `alias` path matches your install |
