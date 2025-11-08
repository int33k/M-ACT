# MACT CLI - Tunnel Client

Command-line interface for the MACT (Mirrored Active Collaborative Tunnel) system.

## Overview

The MACT CLI allows developers to:
- Initialize their developer identity
- Create and join collaborative rooms
- Automatically manage frpc tunnel connections
- Install Git hooks for automatic commit reporting
- Track active room memberships

## Installation

The CLI is part of the MACT project. Ensure you have the project installed:

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Initialize Your Developer ID

```bash
python -m cli.cli init --name rahbar
```

This saves your developer ID to `~/.mact_config.json` for use in subsequent commands.

### 2. Create a Room

```bash
python -m cli.cli create \
  --project "MyApp" \
  --subdomain http://dev-rahbar.m-act.live \
  --local-port 3000
```

This will:
- ✓ Create a room on the coordination backend
- ✓ Start an frpc tunnel (localhost:3000 → dev-rahbar.m-act.live)
- ✓ Install a Git post-commit hook (if in a git repo)
- ✓ Save room membership to `~/.mact_rooms.json`

### 3. Join an Existing Room

```bash
python -m cli.cli join \
  --room myapp \
  --subdomain http://dev-sanaullah.m-act.live \
  --local-port 3000
```

Same automatic setup as create (tunnel + hook + config).

### 4. Check Status

```bash
python -m cli.cli status
```

Shows all your active room memberships and tunnel status.

### 5. Leave a Room

```bash
python -m cli.cli leave --room myapp
```

This will:
- ✓ Remove you from the room on the backend
- ✓ Stop the frpc tunnel
- ✓ Remove room membership from config

## Commands

### `init`

Initialize MACT with your developer ID.

```bash
python -m cli.cli init --name <developer_id>
```

**Options**:
- `--name`: Your developer ID/name (required)

**Example**:
```bash
python -m cli.cli init --name rahbar
```

---

### `create`

Create a new collaborative room.

```bash
python -m cli.cli create --project <name> --subdomain <url> [options]
```

**Options**:
- `--project`: Project name for the room (required)
- `--subdomain`: Your subdomain URL (required)
- `--local-port`: Local development server port (default: 3000)
- `--no-tunnel`: Skip automatic tunnel setup
- `--no-hook`: Skip Git hook installation

**Example**:
```bash
python -m cli.cli create \
  --project "WebApp-Beta" \
  --subdomain http://dev-rahbar.m-act.live \
  --local-port 3000
```

---

### `join`

Join an existing room.

```bash
python -m cli.cli join --room <code> --subdomain <url> [options]
```

**Options**:
- `--room`: Room code to join (required)
- `--subdomain`: Your subdomain URL (required)
- `--developer`: Developer ID (uses `init` value if not specified)
- `--local-port`: Local development server port (default: 3000)
- `--no-tunnel`: Skip automatic tunnel setup
- `--no-hook`: Skip Git hook installation

**Example**:
```bash
python -m cli.cli join \
  --room webapp-beta \
  --subdomain http://dev-sanaullah.m-act.live
```

---

### `leave`

Leave a room and clean up.

```bash
python -m cli.cli leave --room <code> [options]
```

**Options**:
- `--room`: Room code to leave (required)
- `--developer`: Developer ID (uses `init` value if not specified)

**Example**:
```bash
python -m cli.cli leave --room webapp-beta
```

---

### `status`

Show active room memberships and tunnel status.

```bash
python -m cli.cli status
```

**Example Output**:
```
Active room memberships (2):

  Room: webapp-beta
    Developer: rahbar
    Subdomain: http://dev-rahbar.m-act.live
    Local port: 3000
    Tunnel: ✓ Running

  Room: api-service
    Developer: rahbar
    Subdomain: http://dev-rahbar-api.m-act.live
    Local port: 8000
    Tunnel: ✗ Not running
```

## Configuration Files

### `~/.mact_config.json`

Stores your developer ID:

```json
{
  "developer_id": "rahbar"
}
```

### `~/.mact_rooms.json`

Tracks your active room memberships:

```json
{
  "webapp-beta": {
    "room_code": "webapp-beta",
    "developer_id": "rahbar",
    "subdomain_url": "http://dev-rahbar.m-act.live",
    "local_port": 3000,
    "backend_url": "http://localhost:5000"
  }
}
```

## Git Hook

The CLI automatically installs a post-commit hook at `.git/hooks/post-commit` that:
- Captures commit hash, branch, and message
- POSTs to the coordination backend `/report-commit` endpoint
- Updates the active developer for the room

**Hook behavior**:
- Runs after every `git commit`
- Only sends data if `ROOM_CODE` is set (set by CLI during create/join)
- Silent operation (doesn't interfere with git workflow)

## Environment Variables

- `BACKEND_BASE_URL`: Coordination backend URL (default: `http://localhost:5000`)
- `FRP_SERVER_ADDR`: FRP server address (default: `127.0.0.1`)
- `FRP_SERVER_PORT`: FRP server port (default: `7100`)
- `FRPC_BIN`: Path to frpc binary (default: vendored `third_party/frp/frpc`)

## Architecture

### Components

1. **cli.py**: Main CLI commands and argument parsing
2. **frpc_manager.py**: Manages frpc tunnel processes
3. **room_config.py**: Tracks room memberships
4. **hook.py**: Git post-commit hook installer

### Tunnel Management

The CLI uses `FrpcManager` to:
- Generate frpc TOML config files on-the-fly
- Start frpc subprocesses with proper configs
- Track running tunnels
- Clean up processes and temp files on leave

### Room Config Tracking

`RoomConfig` maintains a JSON file with:
- Active room memberships
- Subdomain URLs
- Local ports
- Backend URLs

This allows the CLI to:
- Remember which rooms you're in
- Restart tunnels if needed
- Provide status information

## Troubleshooting

### "frpc binary not found"

Ensure frpc is available:
1. Check if vendored: `ls third_party/frp/frpc`
2. Or install frp and add to PATH
3. Or set `FRPC_BIN` environment variable

### "Failed to start tunnel"

Possible causes:
- FRP server not running (start with `scripts/run_frp_local.sh` or deploy frps)
- Port already in use
- Wrong FRP server address/port

### "Not a git repository"

Git hook installation is skipped if not in a git repo. This is normal and doesn't affect other functionality.

### Tunnel shows "Not running" in status

Restart the tunnel manually or leave and rejoin the room.

## Development

Run tests:
```bash
pytest tests/test_cli.py -v
```

Test coverage includes:
- Config initialization
- Room creation/join/leave
- Hook installation
- Room config persistence
- Tunnel config generation

## Next Steps

- [ ] Add `mact restart <room>` to restart tunnels
- [ ] Add `mact logs` to show frpc tunnel logs
- [ ] Support for multiple environments (dev/staging/prod)
- [ ] Auto-reconnect on tunnel failure
- [ ] Interactive mode for room selection

## See Also

- [Project Documentation](../.docs/PROJECT_CONTEXT.md)
- [Validation Report](../.docs/VALIDATION_REPORT.md)
- [Backend README](../backend/README.md)
- [Proxy README](../proxy/README.md)
