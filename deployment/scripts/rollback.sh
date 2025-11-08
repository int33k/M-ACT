#!/bin/bash
# MACT Rollback Script
# Restores a previous backup
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MACT_HOME="/opt/mact"
MACT_USER="mact"

echo -e "${RED}=================================================${NC}"
echo -e "${RED}   MACT Rollback${NC}"
echo -e "${RED}=================================================${NC}\n"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (use sudo)${NC}"
    exit 1
fi

# Check for backup file argument
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: sudo ./rollback.sh <backup_file>${NC}"
    echo -e "\nAvailable backups:"
    ls -lh /opt/mact-backups/mact_backup_*.tar.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}Rollback from: $BACKUP_FILE${NC}"
echo -e "${RED}This will restore the previous version of MACT${NC}"
echo -e "${YELLOW}Continue? (yes/no)${NC}"
read -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Rollback cancelled${NC}"
    exit 0
fi

echo -e "${YELLOW}Step 1/5: Stopping services...${NC}"
systemctl stop mact-proxy
systemctl stop mact-backend

echo -e "${YELLOW}Step 2/5: Backing up current state (just in case)...${NC}"
EMERGENCY_BACKUP="/opt/mact-backups/emergency_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "$EMERGENCY_BACKUP" \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='logs/*' \
    "$MACT_HOME" 2>/dev/null || true
echo -e "${GREEN}Emergency backup: $EMERGENCY_BACKUP${NC}"

echo -e "${YELLOW}Step 3/5: Extracting backup...${NC}"
# Clear current installation (except .venv and logs)
cd "$MACT_HOME"
find . -mindepth 1 -maxdepth 1 \
    ! -name '.venv' \
    ! -name 'logs' \
    ! -name '.' \
    ! -name '..' \
    -exec rm -rf {} +

# Extract backup
tar -xzf "$BACKUP_FILE" -C / --strip-components=2

echo -e "${YELLOW}Step 4/5: Restoring dependencies...${NC}"
cd "$MACT_HOME"
sudo -u "$MACT_USER" .venv/bin/pip install -r requirements.txt

echo -e "${YELLOW}Step 5/5: Starting services...${NC}"
systemctl start mact-backend
sleep 2
systemctl start mact-proxy
sleep 3

# Health checks
echo -e "${YELLOW}Running health checks...${NC}"

if curl -f -s http://localhost:5000/health > /dev/null; then
    echo -e "${GREEN}Backend health check: OK${NC}"
else
    echo -e "${RED}Backend health check: FAILED${NC}"
fi

if curl -f -s http://localhost:9000/health > /dev/null; then
    echo -e "${GREEN}Proxy health check: OK${NC}"
else
    echo -e "${RED}Proxy health check: FAILED${NC}"
fi

echo -e "\n${GREEN}=================================================${NC}"
echo -e "${GREEN}   Rollback Complete${NC}"
echo -e "${GREEN}=================================================${NC}\n"

systemctl status mact-backend --no-pager -l
systemctl status mact-proxy --no-pager -l

echo -e "\n${YELLOW}Emergency backup saved at: $EMERGENCY_BACKUP${NC}"
echo -e "${YELLOW}Check logs if services are not running correctly:${NC}"
echo "  sudo journalctl -u mact-backend -n 50"
echo "  sudo journalctl -u mact-proxy -n 50"
