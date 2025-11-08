# MACT Production Deployment Guide

**Last Updated:** 2025-11-08  
**Status:** Ready for deployment (Units 1-4 complete, Unit 6 security hardened)

---

## 🎯 Overview

This guide walks you through deploying MACT to production on a DigitalOcean droplet with the domain `m-act.live`.

**What's Included:**
- ✅ Coordination Backend (Flask API with security)
- ✅ Public Routing Proxy (Starlette ASGI with WebSocket support)
- ✅ FRP Server (frps for tunneling)
- ✅ Nginx reverse proxy with SSL
- ✅ Systemd service management
- ✅ Automated deployment scripts
- ✅ Security hardening (input validation, auth, rate limiting)

---

## 📋 Pre-Deployment Checklist

### 1. Local Development Complete
- [ ] All tests passing: `pytest tests/ -v` (33 tests expected)
- [ ] Backend health check works: `http://localhost:5000/health`
- [ ] Proxy health check works: `http://localhost:9000/health`
- [ ] FRP binaries present: `ls -lh third_party/frp/`
- [ ] Environment templates reviewed: `deployment/*.env.template`

### 2. Server Requirements
- [ ] DigitalOcean Droplet (recommended: 2GB RAM, 1 vCPU, Ubuntu 22.04 LTS)
- [ ] Domain registered: `m-act.live` (Name.com or other)
- [ ] SSH access configured
- [ ] Non-root sudo user created (optional but recommended)

### 3. DNS Configuration
Configure these DNS records **BEFORE** running setup:

```
Type    Name                Value               TTL
----    ----                -----               ---
A       m-act.live          <YOUR_SERVER_IP>    300
A       *.m-act.live        <YOUR_SERVER_IP>    300
A       dev-*.m-act.live    <YOUR_SERVER_IP>    300
```

**Verify DNS propagation:** `dig m-act.live +short`

### 4. Prepare Configuration Values
Gather these values before deployment:

```bash
# Server Details
SERVER_IP="<YOUR_DROPLET_IP>"
ADMIN_EMAIL="<YOUR_EMAIL>"  # For Let's Encrypt

# GitHub Repository
MACT_REPO="https://github.com/<USERNAME>/M-ACT.git"

# Admin Auth Token (generate with: python3 -c "import secrets; print(secrets.token_urlsafe(32))")
ADMIN_AUTH_TOKEN="<GENERATE_SECURE_TOKEN>"
```

---

## 🚀 Deployment Steps

### Step 1: Update Deployment Scripts

1. **Edit `deployment/scripts/setup.sh`:**
   ```bash
   # Line 22-24: Update these variables
   MACT_REPO="https://github.com/yourusername/M-ACT.git"  # Your repo!
   ADMIN_EMAIL="your-email@example.com"                    # For SSL
   ```

2. **Generate admin auth token:**
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   # Save this token - you'll need it later
   ```

### Step 2: Push Code to GitHub

```bash
# Commit all changes
git add .
git commit -m "chore: prepare for production deployment"
git push origin main
```

### Step 3: Initial Server Setup

SSH to your server and run the setup script:

```bash
# SSH to server
ssh root@<YOUR_SERVER_IP>

# Download and run setup script
curl -L https://raw.githubusercontent.com/<USERNAME>/M-ACT/main/deployment/scripts/setup.sh -o setup.sh
chmod +x setup.sh
sudo ./setup.sh
```

**What this does:**
- Installs system dependencies (Python, Nginx, Certbot, etc.)
- Creates `mact` system user
- Clones repository to `/opt/mact`
- Sets up Python virtual environment
- Installs systemd services
- Configures Nginx
- Sets up firewall (UFW)
- Initiates SSL certificate request

### Step 4: Configure Environment Files

After setup completes, customize the environment files:

```bash
cd /opt/mact/deployment

# 1. Backend environment
sudo nano mact-backend.env
# Update:
#   ADMIN_AUTH_TOKEN=<paste_your_generated_token>
#   CORS_ORIGINS=http://m-act.live,https://m-act.live,http://*.m-act.live,https://*.m-act.live

# 2. Proxy environment
sudo nano mact-proxy.env
# Usually defaults are fine, but verify:
#   BACKEND_BASE_URL=http://127.0.0.1:5000

# 3. FRP environment (if needed)
sudo nano mact-frps.env
```

### Step 5: SSL Certificate Setup

For wildcard certificates, you'll need to complete DNS challenge:

```bash
# Request wildcard certificate
sudo certbot certonly --manual \
  -d m-act.live \
  -d "*.m-act.live" \
  --preferred-challenges dns \
  --email <YOUR_EMAIL> \
  --agree-tos

# Follow prompts to add DNS TXT records
# Add these to your DNS provider:
#   Name: _acme-challenge.m-act.live
#   Type: TXT
#   Value: <provided_by_certbot>

# Wait for DNS propagation (check with: dig -t txt _acme-challenge.m-act.live)
# Then press Enter in certbot to complete verification
```

**Alternative (easier but less secure):** Use HTTP-01 challenge for non-wildcard:
```bash
# For m-act.live only (no wildcard support)
sudo certbot --nginx -d m-act.live --email <YOUR_EMAIL> --agree-tos
```

### Step 6: Start Services

```bash
# Start FRP server (tunneling infrastructure)
sudo systemctl start mact-frps
sudo systemctl status mact-frps

# Start backend (coordination API)
sudo systemctl start mact-backend
sudo systemctl status mact-backend

# Start proxy (public-facing mirror)
sudo systemctl start mact-proxy
sudo systemctl status mact-proxy

# Reload Nginx
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

### Step 7: Verify Deployment

Run these health checks:

```bash
# Backend health
curl http://localhost:5000/health
# Expected: {"status":"healthy","rooms_count":0}

# Proxy health
curl http://localhost:9000/health
# Expected: {"status":"healthy","backend_reachable":true}

# Public health (via Nginx)
curl https://m-act.live/health

# Check FRP server
sudo netstat -tlnp | grep 7100
# Should show frps listening on port 7100
```

### Step 8: Test with CLI

From your local development machine:

```bash
# 1. Update CLI to use production
export BACKEND_BASE_URL="https://m-act.live"
export FRP_SERVER_ADDR="m-act.live"
export FRP_SERVER_PORT="7100"

# 2. Initialize developer
mact init --name yourname

# 3. Create a test room (in a git repo with a running localhost:3000)
cd test-client-workspace/user1-project
python3 -m http.server 3000 &
mact create --project TestApp --local-port 3000 --subdomain dev-yourname-testapp

# 4. Visit the public URL
# Open: https://testapp.m-act.live (should show your localhost:3000)

# 5. Make a commit
git commit --allow-empty -m "test: verify deployment"
# Should auto-report to backend

# 6. Check dashboard
# Open: https://testapp.m-act.live/dashboard
```

---

## 🔄 Updating Production

After initial deployment, use the deploy script for updates:

```bash
ssh root@<YOUR_SERVER_IP>
cd /opt/mact
sudo ./deployment/scripts/deploy.sh
```

**This will:**
1. Create automatic backup
2. Pull latest code from GitHub
3. Update dependencies
4. Run tests (aborts if tests fail)
5. Restart services with zero downtime
6. Verify health checks
7. Auto-rollback on failure

---

## 🔙 Rollback

If something goes wrong:

```bash
# List available backups
ls -lh /opt/mact-backups/

# Rollback to specific backup
sudo ./deployment/scripts/rollback.sh /opt/mact-backups/mact_backup_YYYYMMDD_HHMMSS.tar.gz
```

---

## 📊 Monitoring & Logs

### View Live Logs

```bash
# Backend logs
sudo journalctl -u mact-backend -f

# Proxy logs
sudo journalctl -u mact-proxy -f

# FRP server logs
sudo journalctl -u mact-frps -f

# Nginx access logs
sudo tail -f /var/log/nginx/mact-access.log

# Nginx error logs
sudo tail -f /var/log/nginx/mact-error.log
```

### Check Service Status

```bash
# All MACT services
sudo systemctl status mact-backend mact-proxy mact-frps

# Nginx
sudo systemctl status nginx

# SSL renewal timer
sudo systemctl status certbot.timer
```

### View Metrics

```bash
# Admin API (requires auth token)
curl -H "Authorization: Bearer <YOUR_ADMIN_TOKEN>" https://m-act.live/admin/rooms
```

---

## 🔒 Security Considerations

**Already Implemented:**
- ✅ Input validation on all endpoints (room codes, developer IDs, URLs, etc.)
- ✅ Admin endpoints protected with Bearer token authentication
- ✅ XSS prevention (HTML sanitization in commit messages)
- ✅ Rate limiting via Nginx (100 req/min general, 200 req/min per developer)
- ✅ CORS configured for m-act.live domain only
- ✅ UFW firewall (only ports 22, 80, 443, 7100 open)
- ✅ Systemd security hardening (NoNewPrivileges, PrivateTmp, ProtectSystem)

**Additional Recommendations:**
- [ ] Enable Fail2Ban for SSH brute force protection (installed but needs config)
- [ ] Set up monitoring/alerting (Prometheus + Grafana, or DigitalOcean monitoring)
- [ ] Regular security updates: `sudo apt update && sudo apt upgrade`
- [ ] Backup strategy for room data (currently in-memory, consider Redis/PostgreSQL for Unit 5+)
- [ ] Rotate admin auth token periodically
- [ ] Consider DDoS protection (Cloudflare or DigitalOcean DDoS)

---

## 🐛 Troubleshooting

### Services won't start

```bash
# Check logs
sudo journalctl -xe

# Check if ports are already in use
sudo netstat -tlnp | grep -E '5000|9000|7100'

# Verify Python environment
sudo -u mact /opt/mact/.venv/bin/python --version
sudo -u mact /opt/mact/.venv/bin/pip list
```

### SSL certificate issues

```bash
# Check certificate validity
sudo certbot certificates

# Renew manually
sudo certbot renew --dry-run

# Check Nginx SSL config
sudo nginx -t
```

### Tunnel connection fails

```bash
# Verify frps is running
sudo systemctl status mact-frps
sudo netstat -tlnp | grep 7100

# Check firewall
sudo ufw status
sudo ufw allow 7100/tcp

# Test from client
telnet m-act.live 7100
```

### Mirror endpoint returns 404

```bash
# Verify backend is reachable from proxy
curl http://localhost:5000/health

# Check get-active-url endpoint
curl "http://localhost:5000/get-active-url?room=testapp"

# Check if developer tunnel is up
curl "http://dev-yourname-testapp.localhost:7101"
```

---

## 📞 Support

- **Documentation:** `/docs/PROJECT_CONTEXT.md`
- **Architecture:** `/.github/instructions/mact.instructions.md`
- **Issues:** GitHub Issues
- **Logs:** Always include relevant logs when reporting issues

---

## ✅ Post-Deployment Checklist

After successful deployment:
- [ ] All services running and healthy
- [ ] SSL certificates valid and auto-renewing
- [ ] DNS resolves correctly for m-act.live and *.m-act.live
- [ ] Test room created and mirror works
- [ ] Dashboard accessible and shows live data
- [ ] Git hook triggers mirror switches
- [ ] Logs are clean (no errors)
- [ ] Monitoring configured
- [ ] Team members can use CLI against production
- [ ] Documentation updated with production URLs
- [ ] Admin token stored securely (password manager)
- [ ] Backup strategy in place

---

**Deployment Prepared By:** MACT Development Team  
**Last Tested:** Local development environment (all 33 tests passing)  
**Next Steps:** Execute deployment on DigitalOcean droplet
