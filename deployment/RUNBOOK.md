# MACT Production Operations Runbook

Quick reference for common production operations.

---

## 🚀 Service Management

### Start/Stop/Restart Services
```bash
# Individual services
sudo systemctl start mact-backend
sudo systemctl stop mact-backend
sudo systemctl restart mact-backend

# All MACT services
sudo systemctl restart mact-backend mact-proxy mact-frps

# Reload Nginx (zero downtime)
sudo nginx -t && sudo systemctl reload nginx
```

### Check Service Status
```bash
# All MACT services
sudo systemctl status mact-backend mact-proxy mact-frps

# With live logs
sudo systemctl status mact-backend -l --no-pager
```

### Enable/Disable Auto-Start
```bash
# Enable (start on boot)
sudo systemctl enable mact-backend mact-proxy mact-frps

# Disable
sudo systemctl disable mact-backend
```

---

## 📊 Monitoring & Logs

### View Logs
```bash
# Live tail (all services)
sudo journalctl -f -u mact-backend -u mact-proxy -u mact-frps

# Individual service logs
sudo journalctl -u mact-backend -f
sudo journalctl -u mact-proxy -f
sudo journalctl -u mact-frps -f

# Last 100 lines
sudo journalctl -u mact-backend -n 100

# Since specific time
sudo journalctl -u mact-backend --since "1 hour ago"
sudo journalctl -u mact-backend --since "2024-11-08 10:00:00"

# Filter by log level
sudo journalctl -u mact-backend -p err  # errors only
sudo journalctl -u mact-backend -p warning  # warnings and above
```

### Nginx Logs
```bash
# Access logs
sudo tail -f /var/log/nginx/mact-access.log

# Error logs
sudo tail -f /var/log/nginx/mact-error.log

# Search for errors
sudo grep -i error /var/log/nginx/mact-error.log | tail -20
```

### Disk Usage
```bash
# Check log sizes
du -sh /opt/mact/logs/*
du -sh /var/log/nginx/*

# Check available space
df -h /opt
df -h /var/log
```

---

## 🔧 Common Fixes

### Service Won't Start
```bash
# Check what's using the port
sudo netstat -tlnp | grep 5000
sudo netstat -tlnp | grep 9000
sudo netstat -tlnp | grep 7100

# Kill process using port
sudo kill <PID>

# Or kill by name
sudo pkill -f gunicorn
sudo pkill -f uvicorn
sudo pkill -f frps

# Restart service
sudo systemctl restart mact-backend
```

### Memory Issues
```bash
# Check memory usage
free -h
top -o %MEM

# Restart memory-heavy service
sudo systemctl restart mact-proxy
```

### Disk Full
```bash
# Find large files
sudo du -ah /opt/mact | sort -rh | head -20
sudo du -ah /var/log | sort -rh | head -20

# Clean old logs
sudo journalctl --vacuum-time=7d  # Keep last 7 days
sudo journalctl --vacuum-size=500M  # Keep max 500MB

# Rotate logs manually
sudo logrotate -f /etc/logrotate.conf
```

---

## 🔄 Deployment & Updates

### Deploy Latest Code
```bash
cd /opt/mact
sudo ./deployment/scripts/deploy.sh
```

### Manual Update (without script)
```bash
cd /opt/mact

# 1. Backup first!
sudo tar -czf /tmp/mact-backup-$(date +%Y%m%d).tar.gz \
  --exclude='.venv' --exclude='__pycache__' .

# 2. Pull code
sudo -u mact git pull origin main

# 3. Update dependencies
sudo -u mact .venv/bin/pip install -r requirements.txt

# 4. Restart services
sudo systemctl restart mact-backend mact-proxy

# 5. Verify
curl http://localhost:5000/health
curl http://localhost:9000/health
```

### Rollback
```bash
# List backups
ls -lh /opt/mact-backups/

# Rollback to specific backup
sudo ./deployment/scripts/rollback.sh /opt/mact-backups/mact_backup_YYYYMMDD_HHMMSS.tar.gz
```

---

## 🔒 Security Operations

### Update Admin Token
```bash
# 1. Generate new token
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Update environment file
sudo nano /opt/mact/deployment/mact-backend.env
# Change ADMIN_AUTH_TOKEN=...

# 3. Restart backend
sudo systemctl restart mact-backend
```

### Check Firewall
```bash
# Status
sudo ufw status verbose

# Add rule
sudo ufw allow 8080/tcp comment 'Custom port'

# Remove rule
sudo ufw delete allow 8080/tcp

# Reset (careful!)
sudo ufw reset
```

### SSL Certificate Management
```bash
# Check certificate expiry
sudo certbot certificates

# Renew certificates (dry run)
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal

# Renew specific certificate
sudo certbot renew --cert-name m-act.live

# After renewal, reload Nginx
sudo systemctl reload nginx
```

---

## 🧪 Testing & Debugging

### Health Checks
```bash
# Internal health checks
curl http://localhost:5000/health
curl http://localhost:9000/health

# Public health checks
curl https://m-act.live/health
curl -k https://testapp.m-act.live/health

# With details
curl -v http://localhost:5000/health
```

### Test Endpoints
```bash
# List all rooms (requires admin token)
curl -H "Authorization: Bearer <TOKEN>" https://m-act.live/admin/rooms

# Get active URL for room
curl "https://m-act.live/get-active-url?room=testapp"

# Create test room
curl -X POST https://m-act.live/rooms/create \
  -H "Content-Type: application/json" \
  -d '{"project_name":"TestApp","developer_id":"admin","subdomain_url":"http://dev-admin-testapp.m-act.live"}'
```

### Test FRP Tunnel
```bash
# Check if frps is listening
sudo netstat -tlnp | grep 7100

# Test connection from outside
telnet m-act.live 7100

# View FRP logs
sudo journalctl -u mact-frps -f
```

### Test Nginx Proxy
```bash
# Test configuration
sudo nginx -t

# Reload config
sudo nginx -s reload

# Test specific site
curl -I https://m-act.live
curl -I https://testapp.m-act.live
```

---

## 📈 Performance Monitoring

### Check Resource Usage
```bash
# CPU and Memory
top
htop  # if installed

# Disk I/O
iostat -x 1

# Network
iftop  # if installed
nethogs  # if installed

# Process-specific
top -p $(pgrep -f mact-backend)
```

### Database Queries (if using PostgreSQL in future)
```bash
# Not applicable for current in-memory implementation
# Placeholder for future Unit 5+ with persistent storage
```

---

## 🗑️ Cleanup Operations

### Clear Old Backups
```bash
# List backups
ls -lh /opt/mact-backups/

# Remove backups older than 30 days
find /opt/mact-backups/ -name "mact_backup_*.tar.gz" -mtime +30 -delete

# Keep only last 10 backups
cd /opt/mact-backups
ls -t mact_backup_*.tar.gz | tail -n +11 | xargs rm -f
```

### Clear Test Rooms
```bash
# Use admin API to list and clean up test rooms
# (Implement cleanup endpoint in future)
```

---

## 🆘 Emergency Procedures

### Total System Restart
```bash
# Stop all services
sudo systemctl stop mact-proxy mact-backend mact-frps nginx

# Wait a moment
sleep 5

# Start in order
sudo systemctl start mact-frps
sleep 2
sudo systemctl start mact-backend
sleep 2
sudo systemctl start mact-proxy
sleep 2
sudo systemctl start nginx

# Verify
sudo systemctl status mact-frps mact-backend mact-proxy nginx
```

### Service Crashes Repeatedly
```bash
# Check what's wrong
sudo journalctl -xe
sudo systemctl status mact-backend -l

# Increase restart delay in systemd
sudo systemctl edit mact-backend
# Add:
# [Service]
# RestartSec=30s

sudo systemctl daemon-reload
sudo systemctl restart mact-backend
```

### Nginx Configuration Error
```bash
# Backup current config
sudo cp /etc/nginx/sites-enabled/m-act.live.conf /tmp/nginx-backup.conf

# Test config
sudo nginx -t

# If broken, restore default
sudo cp /opt/mact/deployment/nginx/m-act.live.conf /etc/nginx/sites-available/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📞 Getting Help

### Collect Diagnostic Information
```bash
# Create diagnostic bundle
cd /tmp
mkdir mact-diagnostic-$(date +%Y%m%d)
cd mact-diagnostic-$(date +%Y%m%d)

# Collect logs
sudo journalctl -u mact-backend -n 500 > backend.log
sudo journalctl -u mact-proxy -n 500 > proxy.log
sudo journalctl -u mact-frps -n 500 > frps.log
sudo cp /var/log/nginx/mact-error.log nginx-error.log

# Collect configs
sudo cp /opt/mact/deployment/*.env .
sudo cp /etc/nginx/sites-enabled/m-act.live.conf .

# System info
systemctl status mact-backend mact-proxy mact-frps > service-status.txt
df -h > disk-usage.txt
free -h > memory-usage.txt
uname -a > system-info.txt

# Package bundle
cd ..
tar -czf mact-diagnostic-$(date +%Y%m%d).tar.gz mact-diagnostic-$(date +%Y%m%d)/
echo "Diagnostic bundle: /tmp/mact-diagnostic-$(date +%Y%m%d).tar.gz"
```

### Contact Points
- **GitHub Issues:** https://github.com/yourusername/M-ACT/issues
- **Documentation:** /opt/mact/deployment/DEPLOYMENT_GUIDE.md
- **Project Context:** /opt/mact/.docs/PROJECT_CONTEXT.md

---

**Last Updated:** 2025-11-08  
**Version:** 1.0
