#!/bin/bash
# MACT Deployment Script
# Deploys updates to production
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MACT_HOME="/opt/mact"
MACT_USER="mact"

echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}   MACT Deployment${NC}"
echo -e "${GREEN}=================================================${NC}\n"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

# Check if MACT directory exists
if [ ! -d "$MACT_HOME" ]; then
    echo -e "${RED}Error: MACT not found at $MACT_HOME${NC}"
    echo "Run setup.sh first"
    exit 1
fi

cd "$MACT_HOME"

echo -e "${YELLOW}Step 1/8: Creating backup...${NC}"
BACKUP_DIR="/opt/mact-backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/mact_backup_$TIMESTAMP.tar.gz"

tar -czf "$BACKUP_PATH" \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='logs/*' \
    "$MACT_HOME"

echo -e "${GREEN}Backup created: $BACKUP_PATH${NC}"

echo -e "${YELLOW}Step 2/8: Pulling latest code...${NC}"
sudo -u "$MACT_USER" git fetch origin
sudo -u "$MACT_USER" git pull origin main

echo -e "${YELLOW}Step 3/8: Updating dependencies...${NC}"
sudo -u "$MACT_USER" .venv/bin/pip install --upgrade pip
sudo -u "$MACT_USER" .venv/bin/pip install -r requirements.txt

echo -e "${YELLOW}Step 4/8: Running tests...${NC}"
if sudo -u "$MACT_USER" .venv/bin/pytest tests/ -q --tb=line; then
    echo -e "${GREEN}All tests passed${NC}"
else
    echo -e "${RED}Tests failed! Deployment aborted.${NC}"
    echo -e "${YELLOW}To rollback, run: sudo ./deployment/scripts/rollback.sh $BACKUP_PATH${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 5/8: Stopping services...${NC}"
systemctl stop mact-proxy
systemctl stop mact-backend
# Keep frps running (tunnels stay active)

echo -e "${YELLOW}Step 6/8: Reloading systemd...${NC}"
systemctl daemon-reload

echo -e "${YELLOW}Step 7/8: Starting services...${NC}"
systemctl start mact-backend
sleep 2  # Give backend time to start
systemctl start mact-proxy

echo -e "${YELLOW}Step 8/8: Health check...${NC}"
sleep 3

# Check backend health
if curl -f -s http://localhost:5000/health > /dev/null; then
    echo -e "${GREEN}Backend health check: OK${NC}"
else
    echo -e "${RED}Backend health check: FAILED${NC}"
    echo -e "${YELLOW}Rolling back...${NC}"
    ./deployment/scripts/rollback.sh "$BACKUP_PATH"
    exit 1
fi

# Check proxy health
if curl -f -s http://localhost:9000/health > /dev/null; then
    echo -e "${GREEN}Proxy health check: OK${NC}"
else
    echo -e "${RED}Proxy health check: FAILED${NC}"
    echo -e "${YELLOW}Rolling back...${NC}"
    ./deployment/scripts/rollback.sh "$BACKUP_PATH"
    exit 1
fi

echo -e "\n${GREEN}=================================================${NC}"
echo -e "${GREEN}   Deployment Successful!${NC}"
echo -e "${GREEN}=================================================${NC}\n"

echo -e "${YELLOW}Service Status:${NC}"
systemctl status mact-backend --no-pager -l
systemctl status mact-proxy --no-pager -l

echo -e "\n${YELLOW}Backup location: $BACKUP_PATH${NC}"
echo -e "${YELLOW}To rollback: sudo ./deployment/scripts/rollback.sh $BACKUP_PATH${NC}\n"

# Keep only last 10 backups
echo -e "${YELLOW}Cleaning old backups (keeping last 10)...${NC}"
cd "$BACKUP_DIR"
ls -t mact_backup_*.tar.gz | tail -n +11 | xargs -r rm
echo -e "${GREEN}Cleanup complete${NC}\n"
