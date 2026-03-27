# Deployment Guide

This document provides instructions for deploying the Compliance Copilot system to production environments.

## Quick Start (Local Docker)

### Prerequisites
- Docker & Docker Compose installed
- 2GB RAM available
- Ports 3000 (frontend) and 8000 (backend) available

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/compliance-copilot.git
   cd compliance-copilot
   ```

2. **Set environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your JWT secret and other settings
   ```

3. **Start with Docker Compose**
   ```bash
   docker-compose up --build
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

5. **Create your first admin explicitly**
   - Set `COMPLIANCE_ADMIN_EMAIL`, `COMPLIANCE_ADMIN_PASSWORD`, `COMPLIANCE_ADMIN_TENANT`, and `COMPLIANCE_ADMIN_ROLE=admin`
   - Keep `COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP=false` for real deployments
   - Keep `COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS=false` for real deployments
   - The app no longer relies on insecure default bootstrap credentials
   - If you leave bootstrap vars empty, the first email signup becomes the initial workspace admin

### Quick Start (Local Production Processes)

Use the helper script to launch the hardened backend and frontend without Docker:

```bash
chmod +x scripts/deploy_local.sh
./scripts/deploy_local.sh
```

Component-level helpers are also available:

```bash
bash scripts/start_backend.sh
bash scripts/start_frontend.sh
bash scripts/status_local.sh
bash scripts/logs_local.sh all
bash scripts/stop_local.sh
```

The script:
- runs explicit backend migrations first
- builds the frontend if needed
- starts the backend with `uvicorn --env-file`
- verifies `GET /health` before continuing
- starts the frontend with `next start`
- writes PID files to `.run/` and logs to `logs/`

`/health` and `/ready` now include migration metadata so automated checks can verify both service availability and schema state.

You can also run migrations manually before boot:

```bash
cd backend
PYTHONPATH=. python -m app.cli --env-file .env status
PYTHONPATH=. python -m app.cli --env-file .env migrate
PYTHONPATH=. python -m app.cli --env-file .env health --url http://127.0.0.1:8000/health
PYTHONPATH=. python -m app.cli --env-file .env preflight --url http://127.0.0.1:8000/health
```

---

## Vercel (Frontend Only)

### Setup

1. **Fork/Push to GitHub**
   ```bash
   git remote add origin https://github.com/your-username/compliance-copilot.git
   git branch -M main
   git push -u origin main
   ```

2. **Connect to Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - Select "Next.js" as framework

3. **Configure Environment**
   In Vercel Project Settings → Environment Variables:
   ```
   NEXT_PUBLIC_API_BASE=https://your-backend-url.com
   ```

4. **Deploy**
   - Vercel automatically deploys on git push
   - Your frontend is live!

---

## Railway / Render (Backend Deployment)

### Railway (Recommended for simplicity)

1. **Connect GitHub to Railway**
   - Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub"
   - Select your repository
   - Authorize Railway

2. **Configure Backend Service**
   - Select the `backend` directory
   - Set Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Add Environment Variables:
     ```
   COMPLIANCE_JWT_SECRET=your-secret-key
    COMPLIANCE_WEBHOOK_SECRET=your-webhook-secret
    COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP=false
    COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS=false
   COMPLIANCE_DB_PATH=/tmp/compliance.db
     ```

3. **Deploy**
   - Railway auto-deploys on git push
   - Note your backend URL

4. **Update Frontend**
   - Set Vercel `NEXT_PUBLIC_API_BASE` to Railway backend URL
   - Redeploy frontend

### Render (Alternative)

1. **Create Web Service**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect GitHub repo
   - Select `backend` directory
   - Runtime: Python 3.9
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

2. **Configure Environment**
   - Add `COMPLIANCE_JWT_SECRET`, `COMPLIANCE_WEBHOOK_SECRET`, `COMPLIANCE_DB_PATH`
   - Keep `COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP=false` and `COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS=false`
   - Deploy

---

## AWS EC2 (Self-Hosted)

### Prerequisites
- EC2 instance (t3.micro or larger)
- Ubuntu 20.04 LTS
- Security groups: allow ports 80, 443, 3000, 8000

### Setup

1. **SSH into instance**
   ```bash
   ssh -i your-key.pem ubuntu@your-instance-ip
   ```

2. **Install dependencies**
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose git curl
   sudo usermod -aG docker $USER
   newgrp docker
   ```

3. **Clone and deploy**
   ```bash
   git clone https://github.com/your-username/compliance-copilot.git
   cd compliance-copilot
   docker-compose up -d
   ```

4. **Setup Nginx reverse proxy**
   ```bash
   sudo apt install -y nginx
   ```
   
   Create `/etc/nginx/sites-available/compliance`:
   ```nginx
   upstream backend {
       server localhost:8000;
   }

   upstream frontend {
       server localhost:3000;
   }

   server {
       listen 80 default_server;
       listen [::]:80 default_server;
       server_name _;

       # Frontend
       location / {
           proxy_pass http://frontend;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }

       # Backend API
       location /api/ {
           proxy_pass http://backend;
           proxy_http_version 1.1;
           proxy_set_header Host $host;
       }

       # API Docs
       location /docs {
           proxy_pass http://backend;
       }
       location /openapi.json {
           proxy_pass http://backend;
       }
   }
   ```

5. **Enable SSL with Let's Encrypt**
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

6. **Enable Nginx**
   ```bash
   sudo systemctl enable nginx
   sudo systemctl start nginx
   ```

---

## Environment Variables Reference

### Backend (.env or docker-compose.yml)
```
COMPLIANCE_JWT_SECRET=your-super-secret-key
COMPLIANCE_WEBHOOK_SECRET=your-strong-webhook-secret
COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP=false
COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS=false
COMPLIANCE_DB_PATH=/data/compliance.db
COMPLIANCE_DATABASE_URL=sqlite:////data/compliance.db
COMPLIANCE_PORT=8000
COMPLIANCE_CORS_ORIGINS=http://localhost:3000,https://your-domain.com
```

Local preview note:
- Set `COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP=true` only when you intentionally want the preview workspace admin seeded for demos.
- Set `COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS=true` only when you intentionally want preview OAuth or phone signup flows available.
- If preview bootstrap is off, no preview admin is created and the historical preview password is ignored.
- Keep `NEXT_PUBLIC_ENABLE_PREVIEW_AUTH=false` in launch environments so the signed-out UI shows only the real email/password path.

Current storage note:
- The runtime is still backed by the SQLite implementation in [backend/app/db.py](backend/app/db.py)
- `COMPLIANCE_DATABASE_URL` currently supports `sqlite:///...` URLs only
- Postgres is the next migration target, but is not active in the current persistence layer yet

### Frontend (.env.local or Vercel settings)
```
NEXT_PUBLIC_API_BASE=http://localhost:8000  # or your deployed backend URL
NEXT_PUBLIC_API_KEY=                      # optional; set only if you intentionally use API-key auth from the frontend
```

---

## Health Checks

### Backend Health
```bash
curl http://localhost:8000/health
```

### Frontend Health
```bash
curl http://localhost:3000
```

### API Documentation
- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

---

## Database Backups

### Local SQLite
```bash
# Backup
docker-compose exec backend cp /data/compliance.db /data/backup-$(date +%Y%m%d).db

# Restore
docker-compose exec backend cp /data/backup-20240101.db /data/compliance.db
```

### PostgreSQL (Production)
```bash
# Backup
pg_dump compliance_db > backup.sql

# Restore
psql compliance_db < backup.sql
```

---

## Monitoring & Logs

### Docker Compose
```bash
# View all logs
docker-compose logs -f

# Backend logs only
docker-compose logs -f backend

# Frontend logs only
docker-compose logs -f frontend
```

### Production (systemd)
```bash
journalctl -u docker -f
```

---

## Troubleshooting

### Frontend can't reach backend
- Check `NEXT_PUBLIC_API_BASE` environment variable
- Verify backend is running: `curl http://backend:8000/health`
- Check CORS settings in backend config

### Database locked error
- Backend already running elsewhere: `lsof -i :8000`
- Stop other instances: `kill -9 <PID>`

### High CPU usage
- Check if indexing: `docker-compose logs backend | grep -i index`
- Wait for initial analysis to complete

### Out of disk space
- Clean Docker: `docker system prune -a`
- Check database size: `du -sh /data/compliance.db`

---

## Scaling

### Load Balancing
- Use AWS ALB or Nginx upstream to multiple backend instances
- Ensure shared database (PostgreSQL recommended)

### Caching
- Add Redis for session/analysis caching
- Enable Vercel automatic caching for frontend

### CDN
- Vercel provides built-in CDN
- CloudFlare for additional caching/DDoS protection

---

## Security Checklist

- [ ] Leave `COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP=false`
- [ ] Leave `COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS=false`
- [ ] Leave `NEXT_PUBLIC_ENABLE_PREVIEW_AUTH=false`
- [ ] Set strong `COMPLIANCE_JWT_SECRET`
- [ ] Set strong `COMPLIANCE_WEBHOOK_SECRET`
- [ ] Enable HTTPS/TLS (Let's Encrypt)
- [ ] Rotate JWT secret monthly
- [ ] Enable audit logging
- [ ] Regular backups (automated)
- [ ] Restrict API rate limits
- [ ] Monitor for suspicious activity
- [ ] Keep dependencies updated
- [ ] Restrict database access
- [ ] Do not set `NEXT_PUBLIC_API_KEY` unless browser API-key auth is intentionally required

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/your-username/compliance-copilot/issues
- Documentation: See [README.md](README.md) and [API.md](API.md)
