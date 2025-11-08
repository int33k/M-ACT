# 🚀 MACT Deployment - Quick Start

**Status:** Ready for deployment  
**Date:** 2025-11-08

---

## ✅ What's Ready

All development units are complete and tested:

- **Unit 1:** Coordination Backend (Flask API) - 13 tests passing ✅
- **Unit 2:** Public Routing Proxy (Starlette ASGI) - 8 tests passing ✅
- **Unit 3:** Tunnel Client CLI - 7 tests passing ✅
- **Unit 4:** Dashboard - Complete with modern UI ✅
- **Unit 6:** Security Hardening - Complete ✅

**Total:** 33 tests passing, 1 skipped

---

## 📦 Deployment Package Includes

1. **Backend Service** (`backend/`)
   - Flask API with all endpoints
   - Security validation and authentication
   - CORS configuration
   - Gunicorn production server

2. **Proxy Service** (`proxy/`)
   - Starlette ASGI app with WebSocket support
   - FRP server management
   - Mirror endpoint with streaming
   - Dashboard rendering

3. **FRP Binaries** (`third_party/frp/`)
   - frps (server) and frpc (client)
   - Pre-configured TOML configs

4. **CLI Tool** (`cli/`)
   - Full room management
   - Auto tunnel setup
   - Git hook automation

5. **Deployment Scripts** (`deployment/`)
   - Systemd service files
   - Nginx configurations
   - Setup/deploy/rollback scripts
   - Environment templates

6. **Documentation** (`deployment/`)
   - DEPLOYMENT_GUIDE.md (comprehensive guide)
   - RUNBOOK.md (operations manual)
   - verify_deployment.sh (health checks)

---

## 🎯 Before You Deploy

### 1. Set Up Git Config (One-time)
```bash
git config --global user.email "your-email@example.com"
git config --global user.name "Your Name"
```

### 2. Commit Your Code
```bash
git add .
git commit -m "chore: prepare for production deployment"
```

### 3. Create GitHub Repository
1. Go to GitHub and create a new repository named `M-ACT`
2. Add remote:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/M-ACT.git
   git branch -M main
   git push -u origin main
   ```

### 4. Update Deployment Scripts
Edit `deployment/scripts/setup.sh` and change:
```bash
MACT_REPO="https://github.com/YOUR_USERNAME/M-ACT.git"  # Line 22
ADMIN_EMAIL="your-email@example.com"                     # Line 24
```

### 5. Generate Admin Token
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
**Save this token** - you'll need it when configuring the server.

---

## 🚀 Deploy in 3 Steps

### Step 1: Set Up Server (15 minutes)

```bash
# SSH to your DigitalOcean droplet
ssh root@YOUR_SERVER_IP

# Download and run setup script
curl -L https://raw.githubusercontent.com/YOUR_USERNAME/M-ACT/main/deployment/scripts/setup.sh -o setup.sh
chmod +x setup.sh
sudo ./setup.sh
```

This will:
- Install all dependencies
- Clone your repository
- Set up Python environment
- Configure Nginx and systemd
- Request SSL certificate

### Step 2: Configure Environment (5 minutes)

```bash
cd /opt/mact/deployment

# Update backend config
sudo nano mact-backend.env
# Set ADMIN_AUTH_TOKEN to your generated token

# Review other configs (usually defaults are fine)
sudo nano mact-proxy.env
sudo nano mact-frps.env
```

### Step 3: Start Services (2 minutes)

```bash
# Start all services
sudo systemctl start mact-frps
sudo systemctl start mact-backend
sudo systemctl start mact-proxy

# Verify health
curl http://localhost:5000/health
curl http://localhost:9000/health

# Reload Nginx
sudo nginx -t && sudo systemctl reload nginx
```

---

## 🧪 Test Your Deployment

From your local machine:

```bash
# Configure CLI to use production
export BACKEND_BASE_URL="https://m-act.live"
export FRP_SERVER_ADDR="m-act.live"
export FRP_SERVER_PORT="7100"

# Initialize
mact init --name yourname

# Create a test room (in a project directory with git)
cd my-project
git init
echo "Hello MACT!" > index.html
python3 -m http.server 3000 &

mact create --project TestApp --local-port 3000

# Visit your room
open https://testapp.m-act.live
open https://testapp.m-act.live/dashboard
```

---

## 📚 Documentation Reference

- **Full Guide:** `deployment/DEPLOYMENT_GUIDE.md` (comprehensive step-by-step)
- **Operations Manual:** `deployment/RUNBOOK.md` (daily operations)
- **Project Context:** `.docs/PROJECT_CONTEXT.md` (architecture overview)
- **Pre-Deploy Check:** `./scripts/pre_deploy_check.sh` (run before deployment)
- **Verify Deployment:** Run on server after deployment:
  ```bash
  /opt/mact/deployment/scripts/verify_deployment.sh
  ```

---

## 🆘 Need Help?

### Common Issues

**Tests failing?**
```bash
pytest tests/ -v  # Run with verbose output
```

**Git not configured?**
```bash
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
```

**Missing files?**
```bash
./scripts/pre_deploy_check.sh  # Check what's missing
```

### Get Support

- Check logs: `sudo journalctl -u mact-backend -f`
- Review guide: `cat deployment/DEPLOYMENT_GUIDE.md`
- Rollback: `sudo /opt/mact/deployment/scripts/rollback.sh <backup>`

---

## 🎉 Quick Deploy Checklist

- [ ] Git configured (user.email and user.name)
- [ ] Code committed to git
- [ ] GitHub repository created and pushed
- [ ] setup.sh updated with your repo URL
- [ ] Admin token generated and saved
- [ ] DNS records configured (A records for m-act.live and *.m-act.live)
- [ ] DigitalOcean droplet provisioned (Ubuntu 22.04)
- [ ] Ran setup.sh on server
- [ ] Environment files configured
- [ ] SSL certificate obtained
- [ ] Services started and verified
- [ ] Test room created successfully

---

**Ready to deploy?** Start with Step 1 above! 🚀

**Questions?** Check `DEPLOYMENT_GUIDE.md` for detailed instructions.
