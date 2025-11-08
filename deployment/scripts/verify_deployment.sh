#!/bin/bash
# MACT Deployment Verification Script
# Run this on the production server after deployment
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DOMAIN="${DOMAIN:-m-act.live}"
MACT_HOME="${MACT_HOME:-/opt/mact}"

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}   MACT Deployment Verification${NC}"
echo -e "${BLUE}=================================================${NC}\n"

# Track results
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# 1. Check System Requirements
echo -e "${YELLOW}[1/10] System Requirements${NC}"

if command -v python3.12 &> /dev/null; then
    pass "Python 3.12 installed"
else
    fail "Python 3.12 not found"
fi

if command -v nginx &> /dev/null; then
    pass "Nginx installed"
else
    fail "Nginx not found"
fi

if command -v git &> /dev/null; then
    pass "Git installed"
else
    fail "Git not found"
fi

echo ""

# 2. Check MACT Installation
echo -e "${YELLOW}[2/10] MACT Installation${NC}"

if [ -d "$MACT_HOME" ]; then
    pass "MACT directory exists: $MACT_HOME"
else
    fail "MACT directory not found: $MACT_HOME"
fi

if [ -d "$MACT_HOME/.venv" ]; then
    pass "Python virtual environment exists"
else
    fail "Python virtual environment not found"
fi

if [ -f "$MACT_HOME/backend/app.py" ]; then
    pass "Backend app found"
else
    fail "Backend app not found"
fi

if [ -f "$MACT_HOME/proxy/app.py" ]; then
    pass "Proxy app found"
else
    fail "Proxy app not found"
fi

echo ""

# 3. Check Systemd Services
echo -e "${YELLOW}[3/10] Systemd Services${NC}"

for service in mact-backend mact-proxy mact-frps; do
    if systemctl is-active --quiet $service; then
        pass "$service is running"
    else
        fail "$service is not running"
        info "   Start with: sudo systemctl start $service"
    fi
    
    if systemctl is-enabled --quiet $service; then
        pass "$service is enabled"
    else
        warn "$service is not enabled (won't start on boot)"
        info "   Enable with: sudo systemctl enable $service"
    fi
done

echo ""

# 4. Check Nginx Configuration
echo -e "${YELLOW}[4/10] Nginx Configuration${NC}"

if systemctl is-active --quiet nginx; then
    pass "Nginx is running"
else
    fail "Nginx is not running"
fi

if [ -f "/etc/nginx/sites-enabled/m-act.live.conf" ]; then
    pass "MACT site configuration enabled"
else
    fail "MACT site configuration not enabled"
fi

if nginx -t &> /dev/null; then
    pass "Nginx configuration is valid"
else
    fail "Nginx configuration has errors"
    nginx -t
fi

echo ""

# 5. Check SSL Certificates
echo -e "${YELLOW}[5/10] SSL Certificates${NC}"

if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    pass "SSL certificate exists"
    
    # Check expiry
    EXPIRY=$(openssl x509 -enddate -noout -in "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" 2>/dev/null | cut -d= -f2)
    if [ -n "$EXPIRY" ]; then
        info "   Expires: $EXPIRY"
    fi
else
    warn "SSL certificate not found (may be using HTTP only)"
fi

if systemctl is-active --quiet certbot.timer; then
    pass "Certbot auto-renewal timer is active"
else
    warn "Certbot auto-renewal timer is not active"
fi

echo ""

# 6. Check Firewall
echo -e "${YELLOW}[6/10] Firewall Configuration${NC}"

if command -v ufw &> /dev/null; then
    if ufw status | grep -q "Status: active"; then
        pass "UFW firewall is active"
        
        # Check required ports
        for port in "22/tcp" "80/tcp" "443/tcp" "7100/tcp"; do
            if ufw status | grep -q "$port.*ALLOW"; then
                pass "Port $port is open"
            else
                warn "Port $port is not open"
            fi
        done
    else
        warn "UFW firewall is not active"
    fi
else
    warn "UFW not installed"
fi

echo ""

# 7. Check Ports
echo -e "${YELLOW}[7/10] Port Bindings${NC}"

check_port() {
    local port=$1
    local service=$2
    if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        pass "$service listening on port $port"
    else
        fail "$service not listening on port $port"
    fi
}

check_port 5000 "Backend"
check_port 9000 "Proxy"
check_port 7100 "FRP Server"
check_port 80 "Nginx (HTTP)"
check_port 443 "Nginx (HTTPS)" || warn "Nginx HTTPS not listening (SSL may not be configured)"

echo ""

# 8. Check Health Endpoints
echo -e "${YELLOW}[8/10] Health Endpoints${NC}"

# Backend health (internal)
if curl -f -s http://localhost:5000/health > /dev/null 2>&1; then
    pass "Backend health check (internal)"
else
    fail "Backend health check failed"
fi

# Proxy health (internal)
if curl -f -s http://localhost:9000/health > /dev/null 2>&1; then
    pass "Proxy health check (internal)"
else
    fail "Proxy health check failed"
fi

# Public health (via Nginx)
if curl -f -s -k "https://$DOMAIN/health" > /dev/null 2>&1; then
    pass "Public health check (HTTPS)"
elif curl -f -s "http://$DOMAIN/health" > /dev/null 2>&1; then
    pass "Public health check (HTTP)"
    warn "HTTPS not available (using HTTP fallback)"
else
    fail "Public health check failed"
fi

echo ""

# 9. Check DNS Resolution
echo -e "${YELLOW}[9/10] DNS Resolution${NC}"

if dig +short "$DOMAIN" | grep -q "[0-9]"; then
    SERVER_IP=$(dig +short "$DOMAIN" | head -1)
    pass "Domain resolves: $DOMAIN -> $SERVER_IP"
    
    # Check wildcard
    if dig +short "test.$DOMAIN" | grep -q "[0-9]"; then
        pass "Wildcard subdomain resolves"
    else
        warn "Wildcard subdomain does not resolve"
    fi
else
    fail "Domain does not resolve: $DOMAIN"
fi

echo ""

# 10. Check Environment Configuration
echo -e "${YELLOW}[10/10] Environment Configuration${NC}"

if [ -f "$MACT_HOME/deployment/mact-backend.env" ]; then
    pass "Backend environment file exists"
    
    # Check for default values that should be changed
    if grep -q "changeme-in-production" "$MACT_HOME/deployment/mact-backend.env"; then
        fail "ADMIN_AUTH_TOKEN still has default value!"
        info "   Generate token: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    else
        pass "ADMIN_AUTH_TOKEN appears to be customized"
    fi
else
    fail "Backend environment file not found"
fi

if [ -f "$MACT_HOME/deployment/mact-proxy.env" ]; then
    pass "Proxy environment file exists"
else
    fail "Proxy environment file not found"
fi

echo ""

# Summary
echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}   Summary${NC}"
echo -e "${BLUE}=================================================${NC}"
echo -e "${GREEN}Passed:   $PASSED${NC}"
echo -e "${RED}Failed:   $FAILED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✓ Deployment verification PASSED${NC}"
    echo -e "${GREEN}  Your MACT instance appears to be healthy!${NC}\n"
    
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Test with CLI: mact create --project TestApp --local-port 3000"
    echo "2. Visit your room: https://testapp.$DOMAIN"
    echo "3. Check dashboard: https://testapp.$DOMAIN/dashboard"
    echo "4. Monitor logs: sudo journalctl -u mact-backend -f"
    
    exit 0
else
    echo -e "\n${RED}✗ Deployment verification FAILED${NC}"
    echo -e "${RED}  Please fix the failed checks above.${NC}\n"
    
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "- Check logs: sudo journalctl -xe"
    echo "- Restart services: sudo systemctl restart mact-backend mact-proxy mact-frps"
    echo "- Review guide: $MACT_HOME/deployment/DEPLOYMENT_GUIDE.md"
    
    exit 1
fi
