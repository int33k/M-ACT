# MACT (Mirrored Active Collaborative Tunnel)

A collaborative development platform that provides a single, persistent public URL for project "rooms" that live-mirrors the localhost of the developer with the latest Git commit.

## 🚀 Quick Start

### For End Users (Install CLI)

```bash
# Install via pip (easy!)
pip install git+https://github.com/int33k/M-ACT.git

# Initialize
mact init --name your-name

# Create your first room (from your project directory)
cd ~/your-project
mact create TelegramBot -port 3000

# 🎉 Your room is live!
# Mirror:    https://telegrambot.m-act.live/
# Dashboard: https://telegrambot.m-act.live/dashboard
```

See [.docs/QUICK_START.md](.docs/QUICK_START.md) for complete guide.

### For Administrators (Run Server Locally)

```bash
# 1. Clone and setup
git clone https://github.com/int33k/M-ACT.git
cd M-ACT
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Start services (3 terminals)
python -m backend.app                    # Terminal 1: Backend (port 5000)
./scripts/run_frp_local.sh              # Terminal 2: FRP server (port 7100)
FRP_AUTOSTART=0 python -m proxy.app     # Terminal 3: Proxy (port 9000)
```

See [INSTALL.md](INSTALL.md) for detailed local development setup.  
See [.docs/PRODUCTION_DEPLOYMENT_GUIDE.md](.docs/PRODUCTION_DEPLOYMENT_GUIDE.md) for production deployment.

### For Server Administrators (Manage Production)

Once deployed to DigitalOcean, use the admin CLI to manage rooms and users:

```bash
# SSH into your droplet
ssh root@m-act.live

# List all rooms
mact-admin rooms list

# Delete a specific room
mact-admin rooms delete old-project

# Clean up empty rooms
mact-admin rooms cleanup

# Check system health
mact-admin system health

# View logs
mact-admin system logs backend
```

See [.docs/ADMIN_CLI_GUIDE.md](.docs/ADMIN_CLI_GUIDE.md) for complete admin reference.

## What is MACT?

MACT eliminates deployment delays in collaborative development:

- 🏠 **Room-based collaboration** - Multiple developers share one permanent URL
- 🔄 **Git-driven switching** - Latest commit author becomes "active developer"
- 🪞 **Live mirroring** - Room URL auto-proxies to active developer's localhost
- 🌐 **Subdomain routing** - Clean URLs: `project-name.m-act.live`
- ⚡ **Zero configuration** - One CLI command sets up tunnel + git hooks
- 📊 **Real-time dashboard** - WebSocket-powered status updates

## Architecture

```
┌─────────────┐
│   Browser   │ ← User accesses project-name.m-act.live
└──────┬──────┘
       │
┌──────▼────────────────────────────────────────────┐
│  Proxy (Port 9000)                                │
│  • Subdomain routing                              │
│  • WebSocket auto-refresh                         │
│  • Dashboard UI                                   │
└──────┬───────────────┬────────────────────────────┘
       │               │
┌──────▼──────┐   ┌────▼───────────────────┐
│  Backend    │   │  FRP Server (Port 7100)│
│  Port 5000  │   │  • Tunnel multiplexing │
│  • Rooms    │   │  • Vhost HTTP (7101)   │
│  • Commits  │   └────┬───────────────────┘
└─────────────┘        │
                  ┌────▼─────┐  ┌──────────┐
                  │ Dev A    │  │ Dev B    │
                  │ :3000    │  │ :3001    │
                  │ (Active) │  │ (Idle)   │
                  └──────────┘  └──────────┘
```

**Four Components:**
1. **Backend** - Flask REST API managing rooms, participants, commits
2. **Proxy** - Starlette/ASGI server with subdomain routing + WebSocket support
3. **CLI** - Developer tool for room creation, joining, and tunnel management  
4. **FRP** - Fast Reverse Proxy for localhost tunneling

## Features

### ✅ Core Functionality
- **Subdomain-based routing** - `project-name.localhost:9000` → active developer
- **Git-driven active developer** - Latest commit author gets the spotlight
- **WebSocket auto-refresh** - Dashboard & mirror update instantly on commits
- **Automatic tunnel setup** - One CLI command handles everything
- **Real-time dashboard** - See participants, commits, active developer
- **Production security** - Input validation, auth, XSS prevention

### 🧪 Test Coverage  
**36 tests passing** across all components:
- Backend: 13 tests
- Proxy: 8 tests  
- CLI: 7 tests
- FRP Manager: 5 tests
- Integration: 3 tests

### 📦 Technology Stack
- **Backend**: Python 3.12 + Flask
- **Proxy**: Starlette/ASGI + uvicorn  
- **Tunneling**: frp v0.65.0 (vendored)
- **Testing**: pytest
- **Security**: Flask-Limiter + input validation

## CLI Usage

```bash
# 1. Initialize your developer identity
mact init --name your-name

# 2. Create a room (from your git project directory)
# Simple syntax: mact create PROJECT_NAME -port PORT
mact create TelegramBot -port 5000

# Your room is now accessible at:
# 🪞 Mirror:    https://telegrambot.m-act.live/
# 📊 Dashboard: https://telegrambot.m-act.live/dashboard

# 3. Another developer joins
mact join telegrambot -port 5001

# 4. Make commits - active developer switches automatically!
git commit -m "My feature"  # You become active
# Mirror now shows YOUR localhost:5000

# 5. Check status
mact status

# 6. Leave room
mact leave --room telegrambot
```

**Key Features:**
- ✨ **Simple syntax:** `mact create ProjectName -port 3000`
- 🚀 **Auto-subdomain:** Generates subdomain automatically
- 🔧 **Zero config:** One command does everything
- 📦 **pip install:** No manual setup needed

See [`.docs/QUICK_START.md`](.docs/QUICK_START.md) for complete guide.  
See [`cli/README.md`](cli/README.md) for detailed CLI documentation.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /rooms/create` | Create a new room |
| `POST /rooms/join` | Join an existing room |
| `POST /report-commit` | Report a Git commit (auto-called by git hook) |
| `GET /get-active-url` | Get active developer's tunnel URL |
| `GET /rooms/status` | Get room participants and state |
| `GET /rooms/<room>/commits` | Get commit history |
| `GET /health` | Health check |

**Proxy Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `http://<room>.localhost:9000/` | Mirror - proxies to active developer |
| `http://<room>.localhost:9000/dashboard` | Dashboard - room status UI |
| `ws://<room>.localhost:9000/notifications` | WebSocket - real-time updates |

See [`backend/README.md`](backend/README.md) for API examples.

## Port Configuration

| Service | Port | Purpose |
|---------|------|---------|
| Backend | 5000 | REST API |
| Proxy | 9000 | Public entry point |
| FRP Server | 7100 | Tunnel control |
| FRP VHost | 7101 | HTTP tunnels (subdomain multiplexing) |
| Developer localhost | 3000+ | Your local dev servers |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific component
pytest tests/test_backend.py -v
pytest tests/test_proxy.py -v
pytest tests/test_cli.py -v

# Run with coverage
pytest --cov=. tests/
```

**Test Status**: 36 tests passing (13 backend + 8 proxy + 7 CLI + 5 FRP + 3 integration)

## Production Deployment

MACT is production-ready with:
- ✅ **Systemd services** with auto-restart
- ✅ **Nginx configuration** for SSL/TLS termination
- ✅ **Security hardening** (input validation, auth, XSS prevention)
- ✅ **Deployment scripts** (setup, deploy, rollback)
- ✅ **Wildcard DNS support** for subdomain routing

### Quick Deploy (Ubuntu 22.04)

```bash
# 1. Setup server (as root)
cd deployment/scripts
./setup.sh

# 2. Configure environment
cp deployment/mact-*.env.template /etc/mact/
# Edit env files with your settings

# 3. Deploy
./deploy.sh

# 4. Configure DNS
# Add wildcard DNS: *.m-act.live → YOUR_SERVER_IP

# 5. Setup SSL (Let's Encrypt)
certbot --nginx -d m-act.live -d "*.m-act.live"
```

See [`.docs/DEPLOYMENT.md`](.docs/DEPLOYMENT.md) for complete guide.

### Security Features
- Input validation on all endpoints
- Bearer token authentication for admin endpoints
- XSS prevention with HTML sanitization
- Rate limiting (nginx + Flask-Limiter)
- Security headers (X-Frame-Options, CSP, etc.)

See [`.docs/SECURITY_THREAT_MODEL.md`](.docs/SECURITY_THREAT_MODEL.md) for threat analysis.

## Documentation

### 📚 User Guides
- **[INSTALL.md](INSTALL.md)** - Installation and setup guide
- **[cli/README.md](cli/README.md)** - CLI commands and usage
- **[backend/README.md](backend/README.md)** - API reference
- **[proxy/README.md](proxy/README.md)** - Proxy configuration

### 🔧 Technical Documentation
- **[.docs/PROJECT_CONTEXT.md](.docs/PROJECT_CONTEXT.md)** - Architecture and design decisions
- **[.docs/DEPLOYMENT.md](.docs/DEPLOYMENT.md)** - Production deployment guide
- **[.docs/SECURITY_THREAT_MODEL.md](.docs/SECURITY_THREAT_MODEL.md)** - Security analysis
- **[.docs/WEBSOCKET_DESIGN.md](.docs/WEBSOCKET_DESIGN.md)** - WebSocket implementation
- **[.docs/E2E_TEST_REPORT.md](.docs/E2E_TEST_REPORT.md)** - End-to-end testing results
- **[ARCHITECTURE_NOTES.md](ARCHITECTURE_NOTES.md)** - URL standardization & nginx setup

### 📖 Additional Resources
- **[FRP_AUTOMATION.md](FRP_AUTOMATION.md)** - FRP tunnel automation guide
- **[CLI_QUICKREF.md](CLI_QUICKREF.md)** - Quick CLI reference
- **[.docs/PROGRESS_LOG.md](.docs/PROGRESS_LOG.md)** - Development history

## Contributing

Academic research project. Code follows "Build in Units" methodology with strict adherence to `PROJECT_CONTEXT.md`.

## License

MIT License - See LICENSE file for details.
