# 🚀 Deploy MACT to Production - Step by Step

**Server IP:** `68.183.89.184`  
**Domain:** `m-act.live`  
**Date:** 2025-11-08

---

## 📋 Quick Deployment Checklist

Follow these steps in order. Each step includes the exact commands to run.

---

## Step 1: Configure Git Locally (5 minutes)

### 1.1 Set Git User Config (if not already done)
```bash
# Check current config
git config --global user.email
git config --global user.name

# If empty, set them:
git config --global user.email "your-email@example.com"
git config --global user.name "Your Name"
```

### 1.2 Commit All Changes
```bash
cd /home/int33k/Desktop/M-ACT

# Add all files
git add .

# Create initial commit
git commit -m "feat: complete MACT implementation with deployment infrastructure

- Units 1-6 complete (33 tests passing)
- Full deployment automation
- Comprehensive documentation
- Production-ready configuration"
```

### 1.3 Create GitHub Repository
1. Go to https://github.com/new
2. Repository name: `M-ACT`
3. Description: "Mirrored Active Collaborative Tunnel - Real-time collaborative development preview system"
4. Keep it **Public** (or Private if you prefer)
5. Don't initialize with README (we already have code)
6. Click "Create repository"

### 1.4 Push to GitHub
```bash
# Add your GitHub remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/M-ACT.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**✅ Checkpoint:** Your code should now be on GitHub!

---

## Step 2: Update Deployment Configuration (5 minutes)

### 2.1 Update setup.sh with Your GitHub URL
```bash
cd /home/int33k/Desktop/M-ACT

# Edit the setup script
nano deployment/scripts/setup.sh
```

**Find line 22 and update:**
```bash
# Change this:
MACT_REPO="https://github.com/yourusername/M-ACT.git"

# To this (with YOUR GitHub username):
MACT_REPO="https://github.com/YOUR_USERNAME/M-ACT.git"
```

**Find line 24 and update:**
```bash
# Change this:
ADMIN_EMAIL="admin@example.com"

# To your email:
ADMIN_EMAIL="your-email@example.com"
```

Save and exit (Ctrl+O, Enter, Ctrl+X)

### 2.2 Generate Admin Authentication Token
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**⚠️ IMPORTANT:** Copy this token and save it somewhere safe! You'll need it in Step 5.

Example output: `Ab12Cd34Ef56Gh78Ij90Kl12Mn34Op56Qr78St90Uv12Wx34`

### 2.3 Commit and Push Changes
```bash
git add deployment/scripts/setup.sh
git commit -m "chore: configure deployment for production server 68.183.89.184"
git push origin main
```

**✅ Checkpoint:** setup.sh is now configured with your GitHub URL!

---

## Step 3: Configure DNS Records (10 minutes)

You need to add DNS records for your domain `m-act.live` to point to your server.

### 3.1 Add DNS A Records

Go to your DNS provider (Name.com, Cloudflare, DigitalOcean DNS, etc.) and add:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | m-act.live | 68.183.89.184 | 300 |
| A | *.m-act.live | 68.183.89.184 | 300 |

**Note:** The wildcard record `*.m-act.live` enables subdomains like `testapp.m-act.live`, `dev-user1.m-act.live`, etc.

### 3.2 Verify DNS Propagation

Wait a few minutes, then verify:
```bash
# Check main domain
dig m-act.live +short
# Should return: 68.183.89.184

# Check wildcard
dig testapp.m-act.live +short
# Should return: 68.183.89.184
```

**⚠️ IMPORTANT:** Don't proceed until DNS is resolving correctly!

**✅ Checkpoint:** DNS records are configured and resolving!

---

## Step 4: Initial Server Setup (15-20 minutes)

### 4.1 SSH to Your Server
```bash
ssh root@68.183.89.184
```

**Note:** You'll need your server password or SSH key. If first time connecting, you'll see a fingerprint warning - type `yes`.

### 4.2 Download and Run Setup Script

Once logged in to the server:
```bash
# Download setup script (replace YOUR_USERNAME)
curl -L https://raw.githubusercontent.com/YOUR_USERNAME/M-ACT/main/deployment/scripts/setup.sh -o setup.sh

# Make it executable
chmod +x setup.sh

# Run the setup (this will take 10-15 minutes)
sudo ./setup.sh
```

**What this does:**
- Installs Python 3.12, Nginx, Git, Certbot, etc.
- Creates `mact` user
- Clones your repository to `/opt/mact`
- Sets up Python virtual environment
- Installs dependencies
- Configures systemd services
- Sets up Nginx
- Configures firewall (UFW)

**⚠️ During SSL Certificate Setup:**

The script will ask about SSL certificates. For wildcard support, you'll need to complete a DNS challenge:

1. Certbot will provide a TXT record to add
2. Add it to your DNS: `_acme-challenge.m-act.live` with the provided value
3. Wait for DNS propagation (check with `dig -t txt _acme-challenge.m-act.live`)
4. Press Enter in certbot to verify

**Alternative (simpler but no wildcard):**
You can skip this for now and just use HTTP, or get a certificate later.

**✅ Checkpoint:** Server is set up with all dependencies installed!

---

## Step 5: Configure Environment Files (5 minutes)

Still on the server:

### 5.1 Configure Backend Environment
```bash
cd /opt/mact/deployment

# Edit backend environment file
sudo nano mact-backend.env
```

**Update these values:**
```bash
# Change this line:
ADMIN_AUTH_TOKEN=changeme-in-production-REPLACE-WITH-SECURE-TOKEN

# To your generated token from Step 2.2:
ADMIN_AUTH_TOKEN=<paste_your_token_here>

# Verify CORS is set correctly:
CORS_ORIGINS=http://m-act.live,https://m-act.live,http://*.m-act.live,https://*.m-act.live
```

Save and exit (Ctrl+O, Enter, Ctrl+X)

### 5.2 Verify Other Environment Files
```bash
# Check proxy config (usually defaults are fine)
cat mact-proxy.env

# Check FRP config (usually defaults are fine)
cat mact-frps.env
```

**✅ Checkpoint:** Environment files are configured!

---

## Step 6: Start Services (5 minutes)

### 6.1 Start All Services
```bash
# Start FRP server (tunnel infrastructure)
sudo systemctl start mact-frps
sleep 2

# Start backend API
sudo systemctl start mact-backend
sleep 2

# Start proxy service
sudo systemctl start mact-proxy
sleep 2

# Reload Nginx
sudo nginx -t && sudo systemctl reload nginx
```

### 6.2 Check Service Status
```bash
# Check all services
sudo systemctl status mact-frps mact-backend mact-proxy nginx
```

All should show "active (running)" in green!

### 6.3 Run Verification Script
```bash
/opt/mact/deployment/scripts/verify_deployment.sh
```

This will run a comprehensive 10-point health check. All checks should pass!

**✅ Checkpoint:** All services are running and healthy!

---

## Step 7: Test from Local Machine (10 minutes)

Now back on your **local machine** (not the server):

### 7.1 Configure CLI for Production
```bash
# Set environment variables
export BACKEND_BASE_URL="http://m-act.live"  # Use https if you set up SSL
export FRP_SERVER_ADDR="m-act.live"
export FRP_SERVER_PORT="7100"
```

### 7.2 Initialize Developer ID
```bash
mact init --name yourname
```

### 7.3 Create a Test Room

First, start a simple web server in a test directory:
```bash
# Create test directory
mkdir -p ~/test-mact-deploy
cd ~/test-mact-deploy

# Initialize git
git init

# Create a simple HTML file
echo "<h1>Hello from MACT!</h1><p>Deployed to production!</p>" > index.html

# Start a local web server
python3 -m http.server 3000 &
```

Now create a MACT room:
```bash
mact create --project TestApp --local-port 3000
```

**Expected output:**
```
✓ Room created: testapp -> http://testapp.m-act.live
✓ Room membership saved
✓ Tunnel started: dev-yourname-testapp -> localhost:3000
✓ Git post-commit hook installed

✓ Room 'testapp' is ready!
  Public URL: http://testapp.m-act.live
  Local dev: http://localhost:3000
```

### 7.4 Visit Your Room!
```bash
# Open in browser
xdg-open http://testapp.m-act.live

# Or visit manually:
# http://testapp.m-act.live
# http://testapp.m-act.live/dashboard
```

You should see your "Hello from MACT!" page!

### 7.5 Test Git Commit Trigger
```bash
# Make a change
echo "<h1>Updated!</h1>" > index.html

# Commit (this will trigger the hook)
git add index.html
git commit -m "test: update page"

# Refresh your browser - the change should appear!
```

**✅ Checkpoint:** MACT is working in production! 🎉

---

## Step 8: Verify Everything Works

### 8.1 Check Health Endpoints
```bash
# Backend health
curl http://m-act.live/health

# Proxy health  
curl http://m-act.live:9000/health

# Mirror endpoint (should show your content)
curl http://testapp.m-act.live
```

### 8.2 Check Dashboard
Visit: `http://testapp.m-act.live/dashboard`

You should see:
- Active developer: yourname
- Participant list
- Commit history
- Room status

### 8.3 Check Logs (on server)
```bash
# Backend logs
sudo journalctl -u mact-backend -n 50

# Proxy logs
sudo journalctl -u mact-proxy -n 50

# FRP logs
sudo journalctl -u mact-frps -n 50
```

**✅ Checkpoint:** Everything is working! 🎉

---

## 🎉 Deployment Complete!

Your MACT instance is now live at:
- **Main site:** http://m-act.live
- **Test room:** http://testapp.m-act.live
- **Dashboard:** http://testapp.m-act.live/dashboard

### Next Steps

1. **Set up HTTPS** (if not done yet):
   - Follow SSL section in `deployment/DEPLOYMENT_GUIDE.md`
   
2. **Create more rooms:**
   ```bash
   mact create --project MyProject --local-port 3001
   ```

3. **Invite team members:**
   - Share the CLI setup instructions
   - They can join with: `mact join --room <room-code> --local-port 3000`

4. **Monitor services:**
   - Use `deployment/RUNBOOK.md` for daily operations
   - Check logs regularly
   - Set up monitoring/alerts

### Useful Commands

**On Server:**
```bash
# View logs
sudo journalctl -u mact-backend -f

# Restart services
sudo systemctl restart mact-backend mact-proxy

# Check status
sudo systemctl status mact-frps mact-backend mact-proxy

# Run verification
/opt/mact/deployment/scripts/verify_deployment.sh
```

**On Local Machine:**
```bash
# Check active rooms
mact status

# Leave a room
mact leave --room testapp

# Create new room
mact create --project NewProject --local-port 3002
```

### Documentation

- **Operations:** `/opt/mact/deployment/RUNBOOK.md` (on server)
- **Full Guide:** `deployment/DEPLOYMENT_GUIDE.md`
- **Project Info:** `.docs/PROJECT_CONTEXT.md`

---

## 🆘 Troubleshooting

### Services Won't Start
```bash
# Check logs
sudo journalctl -xe

# Check if ports are in use
sudo netstat -tlnp | grep -E '5000|9000|7100'

# Restart everything
sudo systemctl restart mact-frps mact-backend mact-proxy nginx
```

### Can't Connect to Room
```bash
# Check backend is reachable
curl http://m-act.live/health

# Check active URL for room
curl "http://m-act.live/get-active-url?room=testapp"

# Check FRP tunnel
sudo journalctl -u mact-frps -n 50
```

### DNS Not Resolving
```bash
# Check DNS
dig m-act.live +short

# Wait for propagation (can take 5-30 minutes)
# Or flush local DNS cache:
sudo systemd-resolve --flush-caches
```

---

**🎉 Congratulations! MACT is deployed and running!** 🚀
