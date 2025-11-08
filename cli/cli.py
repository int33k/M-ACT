"""MACT CLI for Unit 3 - Tunnel Client

Complete implementation with:
- Developer initialization
- Room creation with automatic tunnel and hook setup
- Room joining with automatic tunnel and hook setup
- Room leaving with tunnel cleanup
- Status command to show active rooms

Features:
- Automatic frpc tunnel management
- Git post-commit hook installation
- Room membership tracking
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional
import requests

from .frpc_manager import FrpcManager, TunnelConfig
from .hook import install_post_commit
from .room_config import RoomConfig, RoomMembership

def get_config_path() -> Path:
    # Resolve HOME at runtime so tests can monkeypatch HOME before import
    home = os.getenv("HOME") or str(Path.home())
    return Path(home) / ".mact_config.json"


# Default to production server (users can override with environment variables for local dev)
DEFAULT_BACKEND = os.getenv("BACKEND_BASE_URL", "http://m-act.live")
DEFAULT_FRP_SERVER = os.getenv("FRP_SERVER_ADDR", "m-act.live")
DEFAULT_FRP_PORT = int(os.getenv("FRP_SERVER_PORT", "7100"))


def load_config() -> Dict[str, str]:
    cfg_path = get_config_path()
    if cfg_path.exists():
        try:
            with cfg_path.open("r") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def save_config(cfg: Dict[str, str]) -> None:
    cfg_path = get_config_path()
    with cfg_path.open("w") as fh:
        json.dump(cfg, fh)


def cmd_init(args: argparse.Namespace) -> int:
    cfg = load_config()
    cfg["developer_id"] = args.name
    save_config(cfg)
    print(f"Initialized developer_id={args.name} (saved to {get_config_path()})")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new room with automatic tunnel and hook setup."""
    cfg = load_config()
    developer_id = cfg.get("developer_id")
    if not developer_id:
        print("Error: Developer ID not set. Run 'mact init --name <your_name>' first.")
        return 1
    
    # Support both syntax styles: positional and -project flag
    project_name = args.project or getattr(args, 'project_flag', None)
    if not project_name:
        print("Error: Project name required. Use: mact create TelegramBot -port 5000")
        return 1
    
    # Get local port (support both --local-port and -port)
    local_port = getattr(args, 'port', None) or 3000
    
    # Auto-generate subdomain if not provided
    subdomain = args.subdomain
    if not subdomain:
        # Auto-generate: dev-{developer}-{project}
        subdomain = f"dev-{developer_id}-{project_name.lower()}"
    
    # Construct full subdomain URL for backend
    # If subdomain is already a full URL, use it; otherwise construct it
    if subdomain.startswith("http://") or subdomain.startswith("https://"):
        subdomain_url = subdomain
    else:
        subdomain_url = f"http://{subdomain}.localhost:7101"
    
    # Create room via backend
    payload = {"project_name": project_name, "developer_id": developer_id, "subdomain_url": subdomain_url}
    resp = requests.post(f"{DEFAULT_BACKEND}/rooms/create", json=payload, timeout=5)
    if resp.status_code != 201:
        print(f"Failed to create room: {resp.status_code} {resp.text}")
        return 1
    
    data = resp.json()
    room_code = data['room_code']
    print(f"✓ Room created: {room_code} -> {data['public_url']}")
    
    # Save room membership
    room_config = RoomConfig()
    membership = RoomMembership(
        room_code=room_code,
        developer_id=developer_id,
        subdomain_url=subdomain_url,  # Use the full URL
        local_port=local_port,
        backend_url=DEFAULT_BACKEND
    )
    room_config.add_room(membership)
    print(f"✓ Room membership saved")
    
    # Start frpc tunnel if not in test mode
    if not getattr(args, 'no_tunnel', False):
        try:
            frpc = FrpcManager()
            # Extract subdomain from URL or use the subdomain variable (already computed above)
            # subdomain variable contains the correct value (either user-provided or auto-generated)
            tunnel_subdomain = subdomain
            if "//" in subdomain:
                # Full URL provided: extract subdomain part
                tunnel_subdomain = subdomain.split("//")[-1].split(".")[0]
            
            tunnel = TunnelConfig(
                room_code=room_code,
                developer_id=developer_id,
                local_port=local_port,
                remote_subdomain=tunnel_subdomain,
                server_addr=DEFAULT_FRP_SERVER,
                server_port=DEFAULT_FRP_PORT
            )
            if frpc.start_tunnel(tunnel):
                print(f"✓ Tunnel started: {tunnel_subdomain} -> localhost:{local_port}")
            else:
                print(f"✗ Failed to start tunnel (continuing anyway)")
                print(f"  Tip: Check if frpc binary exists and frps server is running on port {DEFAULT_FRP_PORT}")
        except Exception as e:
            print(f"✗ Tunnel setup failed: {e} (continuing anyway)")
            print(f"  Tip: Run with DEBUG=1 for full traceback")
    
    # Install git hook if in a git repo
    if not getattr(args, 'no_hook', False):
        git_dir = Path.cwd()
        if (git_dir / ".git").exists():
            try:
                install_post_commit(git_dir, developer_id, room_code, DEFAULT_BACKEND)
                print(f"✓ Git post-commit hook installed")
            except Exception as e:
                print(f"✗ Hook installation failed: {e}")
        else:
            print(f"ℹ Not a git repository; skipping hook installation")
    
    print(f"\n✓ Room '{room_code}' is ready!")
    print(f"  Public URL: {data['public_url']}")
    print(f"  Local dev: http://localhost:{local_port}")
    return 0


def cmd_join(args: argparse.Namespace) -> int:
    """Join an existing room with automatic tunnel and hook setup."""
    cfg = load_config()
    developer_id = cfg.get("developer_id") or args.developer
    
    if not developer_id:
        print("Error: Developer ID not set. Run 'mact init --name <your_name>' first or use --developer flag.")
        return 1
    
    # Support both syntax styles: positional and -join flag
    room_code = args.room or getattr(args, 'room_flag', None)
    if not room_code:
        print("Error: Room code required. Use: mact join XXXX-XXXX-XXXX -port 5023")
        return 1
    
    # Get local port (support both styles)
    local_port = getattr(args, 'port', None) or 3000
    
    # Auto-generate subdomain if not provided
    subdomain = args.subdomain
    if not subdomain:
        # Auto-generate: dev-{developer}-{room}
        subdomain = f"dev-{developer_id}-{room_code}"
    
    # Construct full subdomain URL for backend
    if subdomain.startswith("http://") or subdomain.startswith("https://"):
        subdomain_url = subdomain
    else:
        subdomain_url = f"http://{subdomain}.localhost:7101"
    
    # Join room via backend
    payload = {"room_code": room_code, "developer_id": developer_id, "subdomain_url": subdomain_url}
    resp = requests.post(f"{DEFAULT_BACKEND}/rooms/join", json=payload, timeout=5)
    if resp.status_code != 200:
        print(f"Failed to join room: {resp.status_code} {resp.text}")
        return 1
    
    print(f"✓ Joined room: {room_code}")
    
    # Save room membership
    room_config = RoomConfig()
    membership = RoomMembership(
        room_code=room_code,
        developer_id=developer_id,
        subdomain_url=subdomain_url,
        local_port=local_port,
        backend_url=DEFAULT_BACKEND
    )
    room_config.add_room(membership)
    print(f"✓ Room membership saved")
    
    # Start frpc tunnel
    if not getattr(args, 'no_tunnel', False):
        try:
            frpc = FrpcManager()
            # Extract subdomain from URL or use as-is (subdomain variable already computed above)
            tunnel_subdomain = subdomain
            if "//" in subdomain:
                # Full URL provided: extract subdomain part
                tunnel_subdomain = subdomain.split("//")[-1].split(".")[0]
            
            tunnel = TunnelConfig(
                room_code=room_code,
                developer_id=developer_id,
                local_port=local_port,
                remote_subdomain=tunnel_subdomain,
                server_addr=DEFAULT_FRP_SERVER,
                server_port=DEFAULT_FRP_PORT
            )
            if frpc.start_tunnel(tunnel):
                print(f"✓ Tunnel started: {tunnel_subdomain} -> localhost:{local_port}")
            else:
                print(f"✗ Failed to start tunnel (continuing anyway)")
                print(f"  Tip: Check if frpc binary exists and frps server is running on port {DEFAULT_FRP_PORT}")
        except Exception as e:
            print(f"✗ Tunnel setup failed: {e} (continuing anyway)")
            print(f"  Tip: Run with DEBUG=1 for full traceback")
    
    # Install git hook
    if not getattr(args, 'no_hook', False):
        git_dir = Path.cwd()
        if (git_dir / ".git").exists():
            try:
                install_post_commit(git_dir, developer_id, room_code, DEFAULT_BACKEND)
                print(f"✓ Git post-commit hook installed")
            except Exception as e:
                print(f"✗ Hook installation failed: {e}")
        else:
            print(f"ℹ Not a git repository; skipping hook installation")
    
    print(f"\n✓ Successfully joined room '{room_code}'!")
    return 0


def cmd_leave(args: argparse.Namespace) -> int:
    """Leave a room and stop tunnel."""
    cfg = load_config()
    developer_id = cfg.get("developer_id") or args.developer
    
    if not developer_id:
        print("Error: Developer ID not set. Run 'mact init --name <your_name>' first or use --developer flag.")
        return 1
    
    # Leave room via backend
    payload = {"room_code": args.room, "developer_id": developer_id}
    resp = requests.post(f"{DEFAULT_BACKEND}/rooms/leave", json=payload, timeout=5)
    if resp.status_code != 200:
        print(f"Failed to leave room: {resp.status_code} {resp.text}")
        return 1
    
    print(f"✓ Left room: {args.room}")
    
    # Stop tunnel
    try:
        frpc = FrpcManager()
        if frpc.stop_tunnel(args.room, developer_id):
            print(f"✓ Tunnel stopped")
    except Exception as e:
        print(f"✗ Failed to stop tunnel: {e}")
    
    # Remove room membership
    room_config = RoomConfig()
    if room_config.remove_room(args.room):
        print(f"✓ Room membership removed")
    
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show active room memberships."""
    room_config = RoomConfig()
    rooms = room_config.list_rooms()
    
    if not rooms:
        print("No active room memberships.")
        print("Create a room with: mact create --project <name> --subdomain <url>")
        return 0
    
    print(f"Active room memberships ({len(rooms)}):\n")
    for room in rooms:
        print(f"  Room: {room.room_code}")
        print(f"    Developer: {room.developer_id}")
        print(f"    Subdomain: {room.subdomain_url}")
        if room.local_port:
            print(f"    Local port: {room.local_port}")
        
        # Check tunnel status
        try:
            frpc = FrpcManager()
            if frpc.is_running(room.room_code, room.developer_id):
                print(f"    Tunnel: ✓ Running")
            else:
                print(f"    Tunnel: ✗ Not running")
        except:
            print(f"    Tunnel: ? Unknown")
        print()
    
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mact",
        description="MACT - Mirrored Active Collaborative Tunnel CLI"
    )
    sub = parser.add_subparsers(dest="cmd", help="Command to run")

    # init command
    p_init = sub.add_parser("init", help="Initialize MACT with your developer ID")
    p_init.add_argument("--name", required=True, help="Your developer ID/name")
    p_init.set_defaults(func=cmd_init)

    # create command
    p_create = sub.add_parser("create", help="Create a new room")
    p_create.add_argument("project", nargs="?", help="Project name for the room (positional)")
    p_create.add_argument("-project", dest="project_flag", help="Project name (alternative)")
    p_create.add_argument("-port", type=int, default=3000, help="Local port (default: 3000)")
    p_create.add_argument("--subdomain", help="Your subdomain (auto-generated if not provided)")
    p_create.add_argument("--no-tunnel", action="store_true", help="Skip tunnel setup")
    p_create.add_argument("--no-hook", action="store_true", help="Skip git hook installation")
    p_create.set_defaults(func=cmd_create)

    # join command
    p_join = sub.add_parser("join", help="Join an existing room")
    p_join.add_argument("room", nargs="?", help="Room code to join (positional)")
    p_join.add_argument("-join", dest="room_flag", help="Room code (alternative)")
    p_join.add_argument("-port", type=int, default=3000, help="Local port (default: 3000)")
    p_join.add_argument("--developer", help="Developer ID (uses init value if not specified)")
    p_join.add_argument("--subdomain", help="Your subdomain (auto-generated if not provided)")
    p_join.add_argument("--no-tunnel", action="store_true", help="Skip tunnel setup")
    p_join.add_argument("--no-hook", action="store_true", help="Skip git hook installation")
    p_join.set_defaults(func=cmd_join)

    # leave command
    p_leave = sub.add_parser("leave", help="Leave a room")
    p_leave.add_argument("--room", required=True, help="Room code to leave")
    p_leave.add_argument("--developer", help="Developer ID (uses init value if not specified)")
    p_leave.set_defaults(func=cmd_leave)
    
    # status command
    p_status = sub.add_parser("status", help="Show active room memberships")
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
