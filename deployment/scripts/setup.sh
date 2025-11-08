#!/bin/bash
# MACT Production Setup Script
# Run this script on a fresh Ubuntu 22.04 server
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}   MACT Production Setup${NC}"
echo -e "${GREEN}=================================================${NC}\n"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

# Configurable variables
MACT_USER="mact"
MACT_HOME="/opt/mact"
MACT_REPO="https://github.com/yourusername/M-ACT.git"  # Update this!
DOMAIN="m-act.live"
ADMIN_EMAIL="admin@example.com"  # For Let's Encrypt

echo -e "${YELLOW}Step 1/10: Updating system packages...${NC}"
apt-get update
apt-get upgrade -y

echo -e "${YELLOW}Step 2/10: Installing dependencies...${NC}"
apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    nginx \
    git \
    certbot \
    python3-certbot-nginx \
    ufw \
    fail2ban

echo -e "${YELLOW}Step 3/10: Creating MACT user...${NC}"
if ! id "$MACT_USER" &>/dev/null; then
    useradd -r -m -d "$MACT_HOME" -s /bin/bash "$MACT_USER"
    echo -e "${GREEN}User $MACT_USER created${NC}"
else
    echo -e "${GREEN}User $MACT_USER already exists${NC}"
fi

echo -e "${YELLOW}Step 4/10: Cloning MACT repository...${NC}"
if [ ! -d "$MACT_HOME/.git" ]; then
    sudo -u "$MACT_USER" git clone "$MACT_REPO" "$MACT_HOME"
    echo -e "${GREEN}Repository cloned${NC}"
else
    echo -e "${GREEN}Repository already exists${NC}"
fi

echo -e "${YELLOW}Step 5/10: Setting up Python virtual environment...${NC}"
cd "$MACT_HOME"
sudo -u "$MACT_USER" python3.12 -m venv .venv
sudo -u "$MACT_USER" .venv/bin/pip install --upgrade pip
sudo -u "$MACT_USER" .venv/bin/pip install -r requirements.txt

echo -e "${YELLOW}Step 6/10: Creating environment files...${NC}"
mkdir -p "$MACT_HOME/logs"
chown "$MACT_USER:$MACT_USER" "$MACT_HOME/logs"

# Copy environment templates if not exists
if [ ! -f "$MACT_HOME/deployment/mact-backend.env" ]; then
    cp "$MACT_HOME/deployment/mact-backend.env.template" "$MACT_HOME/deployment/mact-backend.env"
    echo -e "${YELLOW}Created mact-backend.env (please review and customize)${NC}"
fi

if [ ! -f "$MACT_HOME/deployment/mact-proxy.env" ]; then
    cp "$MACT_HOME/deployment/mact-proxy.env.template" "$MACT_HOME/deployment/mact-proxy.env"
    echo -e "${YELLOW}Created mact-proxy.env (please review and customize)${NC}"
fi

if [ ! -f "$MACT_HOME/deployment/mact-frps.env" ]; then
    cp "$MACT_HOME/deployment/mact-frps.env.template" "$MACT_HOME/deployment/mact-frps.env"
    echo -e "${YELLOW}Created mact-frps.env (please review and customize)${NC}"
fi

echo -e "${YELLOW}Step 7/10: Installing systemd services...${NC}"
cp "$MACT_HOME/deployment/systemd/mact-backend.service" /etc/systemd/system/
cp "$MACT_HOME/deployment/systemd/mact-proxy.service" /etc/systemd/system/
cp "$MACT_HOME/deployment/systemd/mact-frps.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable mact-backend mact-proxy mact-frps

echo -e "${YELLOW}Step 8/10: Configuring Nginx...${NC}"
cp "$MACT_HOME/deployment/nginx/m-act.live.conf" /etc/nginx/sites-available/
cp "$MACT_HOME/deployment/nginx/frp-tunnels.conf" /etc/nginx/sites-available/

# Remove default site
rm -f /etc/nginx/sites-enabled/default

# Enable MACT sites
ln -sf /etc/nginx/sites-available/m-act.live.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/frp-tunnels.conf /etc/nginx/sites-enabled/

# Test nginx configuration
nginx -t

echo -e "${YELLOW}Step 9/10: Configuring firewall...${NC}"
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw allow 7100/tcp comment 'FRP Server'
ufw status

echo -e "${YELLOW}Step 10/10: Obtaining SSL certificate...${NC}"
# Stop nginx temporarily for certbot standalone
systemctl stop nginx

# Obtain certificate
certbot certonly --standalone \
    -d "$DOMAIN" \
    -d "*.$DOMAIN" \
    --email "$ADMIN_EMAIL" \
    --agree-tos \
    --no-eff-email \
    --preferred-challenges dns

# Note: For wildcard certificates, you'll need to add DNS TXT records manually
echo -e "${YELLOW}Note: For wildcard SSL, you may need to complete DNS challenge manually${NC}"
echo -e "${YELLOW}Follow certbot's instructions to add DNS TXT records${NC}"

# Setup auto-renewal
systemctl enable certbot.timer
systemctl start certbot.timer

# Start nginx
systemctl start nginx

echo -e "\n${GREEN}=================================================${NC}"
echo -e "${GREEN}   MACT Setup Complete!${NC}"
echo -e "${GREEN}=================================================${NC}\n"

echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review and customize environment files in $MACT_HOME/deployment/"
echo "2. Update FRP configuration in $MACT_HOME/third_party/frp/mact.frps.toml"
echo "3. Configure DNS records:"
echo "   - A record: m-act.live -> Your server IP"
echo "   - A record: *.m-act.live -> Your server IP"
echo "   - A record: dev-*.m-act.live -> Your server IP"
echo "4. Complete SSL certificate DNS challenge if needed"
echo "5. Start MACT services:"
echo "   sudo systemctl start mact-frps"
echo "   sudo systemctl start mact-backend"
echo "   sudo systemctl start mact-proxy"
echo "6. Check service status:"
echo "   sudo systemctl status mact-frps mact-backend mact-proxy"
echo "7. View logs:"
echo "   sudo journalctl -u mact-backend -f"
echo "   sudo journalctl -u mact-proxy -f"
echo "   sudo journalctl -u mact-frps -f"

echo -e "\n${GREEN}Setup script completed successfully!${NC}\n"
