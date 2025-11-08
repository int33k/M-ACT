# 🚀 MACT Installation Guide

MACT (Mirrored Active Collaborative Tunnel) - Git-driven real-time collaboration tool

---

## 📦 For End Users (Install CLI)

### Quick Install

```bash
# Install via pip (easy!)
pip install git+https://github.com/int33k/M-ACT.git
```

### Initialize

```bash
# Set up your developer profile
mact init --name your-name
```

### Create Your First Room

```bash
# Navigate to your project directory
cd ~/your-project

# Create a room (automatically starts tunnel and installs git hook)
mact create --project TelegramBot --local-port 3000
```

### 🎉 Your Room is Live!

```
Mirror:    http://telegrambot.m-act.live/
Dashboard: http://telegrambot.m-act.live/dashboard
```

### Start Your Local Server

```bash
# Make sure your app is running on the port you specified
npm start  # or python app.py, or any other command
```

### Make Commits to Switch Mirror

Every commit automatically updates the active mirror:

```bash
git add .
git commit -m "Updated feature"
# The public URL now mirrors YOUR localhost!
```

---

## 🔧 For Developers (Local Development)

### Clone Repository

```bash
git clone https://github.com/int33k/M-ACT.git
cd M-ACT
```

### Install in Editable Mode

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install MACT in development mode
pip install -e .

# Install development dependencies
pip install -r requirements.txt
```

### Run Tests

```bash
pytest tests/
```

---

## 🖥️ For Server Administrators (Deploy MACT Server)

See **[DEPLOYMENT_GUIDE.md](deployment/DEPLOYMENT_GUIDE.md)** for full server setup instructions.

### Quick Server Setup

```bash
# On your server (Ubuntu 22.04+)
wget https://raw.githubusercontent.com/int33k/M-ACT/main/deployment/scripts/setup.sh
chmod +x setup.sh
sudo ./setup.sh
```

---

## 📋 Requirements

### Client Requirements
- **Python**: 3.8 or higher
- **Git**: Any recent version
- **OS**: Linux, macOS, or Windows (with WSL)
- **Network**: Internet connection to reach m-act.live server

### Server Requirements (for self-hosting)
- **OS**: Ubuntu 22.04+ (recommended)
- **Python**: 3.10 or higher
- **Domain**: DNS configured for wildcard subdomains (*.yourdomain.com)
- **Ports**: 80 (HTTP), 443 (HTTPS), 7100 (FRP server)

---

## 🔍 Verify Installation

### Check CLI Installation

```bash
mact --help
```

**Expected output:**
```
Usage: mact [OPTIONS] COMMAND [ARGS]...

  MACT CLI - Mirrored Active Collaborative Tunnel

Commands:
  init    Initialize MACT configuration
  create  Create a new room
  join    Join an existing room
  leave   Leave a room
  status  Show room status
```

### Check FRP Binary

The FRP client binary is bundled with the package. To verify:

```bash
python -c "from cli.frpc_manager import FrpcManager; print(FrpcManager()._find_frpc_binary())"
```

---

## 🛠️ Troubleshooting

### Issue: `mact: command not found`

**Solution:** Ensure you're using the correct Python environment:
```bash
which python
pip list | grep mact-cli
```

If using a virtual environment, activate it:
```bash
source .venv/bin/activate
```

### Issue: `frpc binary not found`

**Solution:** The FRP binary should be included automatically. If it's missing:

1. **Manual install:**
   ```bash
   # Download FRP for your platform
   wget https://github.com/fatedier/frp/releases/download/v0.52.0/frp_0.52.0_linux_amd64.tar.gz
   tar -xzf frp_0.52.0_linux_amd64.tar.gz
   sudo mv frp_0.52.0_linux_amd64/frpc /usr/local/bin/
   ```

2. **Or reinstall with --force:**
   ```bash
   pip install --force-reinstall git+https://github.com/int33k/M-ACT.git
   ```

### Issue: Cannot connect to server

**Solution:** Verify the server is reachable:
```bash
curl http://m-act.live/health
```

Expected response:
```json
{"status":"healthy","rooms_count":0}
```

### Issue: Port already in use

**Solution:** Check what's using the port:
```bash
lsof -i :3000  # Replace 3000 with your port
```

Kill the process or use a different port.

---

## 🌐 Using Custom Server

If you're running your own MACT server, configure these environment variables:

```bash
export BACKEND_BASE_URL="http://your-server.com"
export FRP_SERVER_ADDR="your-server.com"
export FRP_SERVER_PORT="7100"
```

Add to `~/.bashrc` or `~/.zshrc` to make permanent.

---

## 📚 Next Steps

- **Quick Start:** Check [README.md](README.md) for usage examples
- **Deployment:** See [deployment/DEPLOYMENT_GUIDE.md](deployment/DEPLOYMENT_GUIDE.md)
- **Architecture:** Read [.docs/PROJECT_CONTEXT.md](.docs/PROJECT_CONTEXT.md)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md) (if exists)

---

## 📞 Support

- **Documentation:** https://github.com/int33k/M-ACT
- **Issues:** https://github.com/int33k/M-ACT/issues
- **Website:** https://m-act.live

---

**Happy collaborating! 🎉**
