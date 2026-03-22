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

5. **Default credentials**
   - Email: `founder@demo.local`
   - Password: `ChangeMe123!`

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
   - Add `COMPLIANCE_JWT_SECRET` and `COMPLIANCE_DB_PATH`
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
COMPLIANCE_DB_PATH=/data/compliance.db
COMPLIANCE_DB_TYPE=sqlite  # or postgres
COMPLIANCE_PORT=8000
COMPLIANCE_CORS_ORIGINS=http://localhost:3000,https://your-domain.com
```

### Frontend (.env.local or Vercel settings)
```
NEXT_PUBLIC_API_BASE=http://localhost:8000  # or your deployed backend URL
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

- [ ] Change default `ChangeMe123!` password
- [ ] Set strong `COMPLIANCE_JWT_SECRET`
- [ ] Enable HTTPS/TLS (Let's Encrypt)
- [ ] Rotate JWT secret monthly
- [ ] Enable audit logging
- [ ] Regular backups (automated)
- [ ] Restrict API rate limits
- [ ] Monitor for suspicious activity
- [ ] Keep dependencies updated
- [ ] Restrict database access

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/your-username/compliance-copilot/issues
- Documentation: See [README.md](README.md) and [API.md](API.md)
