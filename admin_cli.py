#!/usr/bin/env python3
"""MACT Admin CLI - Server-side administration tool

This tool is for server administrators to manage MACT rooms, users, and system health.
Should be run on the DigitalOcean droplet with direct access to the backend.

Usage:
    mact-admin rooms list                    # List all rooms
    mact-admin rooms delete <room-code>      # Delete a specific room
    mact-admin rooms info <room-code>        # Show room details
    mact-admin rooms cleanup                 # Delete empty/inactive rooms
    
    mact-admin users list                    # List all active users
    mact-admin users kick <developer-id> <room-code>  # Kick user from room
    
    mact-admin system health                 # Check system health
    mact-admin system stats                  # Show usage statistics
    mact-admin system logs [backend|proxy|frps]  # View service logs
"""

import argparse
import json
import os
import sys
import subprocess
from typing import Dict, List, Optional
from datetime import datetime

import requests

# Configuration
DEFAULT_BACKEND = os.getenv("BACKEND_URL", "http://localhost:5000")
ADMIN_TOKEN = os.getenv("ADMIN_AUTH_TOKEN", "")

def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers for admin API calls."""
    if not ADMIN_TOKEN:
        print("⚠️  Warning: ADMIN_AUTH_TOKEN not set. Some commands may fail.")
        print("   Set it in /opt/mact/deployment/mact-backend.env")
        return {}
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def format_timestamp(ts: float) -> str:
    """Format Unix timestamp to readable date."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


# ==================== ROOMS COMMANDS ====================

def cmd_rooms_list(args: argparse.Namespace) -> int:
    """List all rooms in the system."""
    try:
        resp = requests.get(
            f"{DEFAULT_BACKEND}/admin/rooms",
            headers=get_auth_headers(),
            timeout=5
        )
        
        if resp.status_code == 401:
            print("❌ Authentication failed. Check ADMIN_AUTH_TOKEN.")
            return 1
        
        if resp.status_code != 200:
            print(f"❌ Failed to fetch rooms: {resp.status_code} {resp.text}")
            return 1
        
        data = resp.json()
        rooms = data.get("rooms", [])
        
        if not rooms:
            print("📭 No rooms found.")
            return 0
        
        print(f"\n📊 Total Rooms: {len(rooms)}\n")
        print(f"{'Room Code':<20} {'Participants':<15} {'Commits':<10} {'Active Developer':<20}")
        print("=" * 75)
        
        for room in rooms:
            room_code = room.get("room_code", "N/A")
            participants = room.get("participants", [])
            commit_count = room.get("commit_count", 0)
            active_dev = room.get("active_developer", "None")
            
            print(f"{room_code:<20} {len(participants):<15} {commit_count:<10} {active_dev:<20}")
        
        print()
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_rooms_delete(args: argparse.Namespace) -> int:
    """Delete a specific room."""
    room_code = args.room_code
    
    # Confirm deletion
    if not args.force:
        print(f"⚠️  Are you sure you want to delete room '{room_code}'?")
        print("   This will remove all participants and commit history.")
        confirm = input("   Type 'yes' to confirm: ")
        if confirm.lower() != "yes":
            print("❌ Deletion cancelled.")
            return 0
    
    try:
        resp = requests.delete(
            f"{DEFAULT_BACKEND}/admin/rooms/{room_code}",
            headers=get_auth_headers(),
            timeout=5
        )
        
        if resp.status_code == 401:
            print("❌ Authentication failed. Check ADMIN_AUTH_TOKEN.")
            return 1
        
        if resp.status_code == 404:
            print(f"❌ Room '{room_code}' not found.")
            return 1
        
        if resp.status_code != 200:
            print(f"❌ Failed to delete room: {resp.status_code} {resp.text}")
            return 1
        
        print(f"✅ Room '{room_code}' deleted successfully.")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_rooms_info(args: argparse.Namespace) -> int:
    """Show detailed information about a room."""
    room_code = args.room_code
    
    try:
        # Get room status
        resp = requests.get(
            f"{DEFAULT_BACKEND}/rooms/status",
            params={"room": room_code},
            timeout=5
        )
        
        if resp.status_code == 404:
            print(f"❌ Room '{room_code}' not found.")
            return 1
        
        if resp.status_code != 200:
            print(f"❌ Failed to fetch room info: {resp.status_code}")
            return 1
        
        status_data = resp.json()
        
        # Get commit history
        resp = requests.get(
            f"{DEFAULT_BACKEND}/rooms/{room_code}/commits",
            timeout=5
        )
        
        commits_data = resp.json() if resp.status_code == 200 else {"commits": []}
        commits = commits_data.get("commits", [])
        
        # Display room info
        print(f"\n📦 Room: {room_code}")
        print("=" * 60)
        print(f"Active Developer: {status_data.get('active_developer', 'None')}")
        print(f"Latest Commit: {status_data.get('latest_commit', 'None')}")
        print(f"Total Commits: {len(commits)}")
        print(f"\nParticipants ({len(status_data.get('participants', []))}):")
        
        for participant in status_data.get("participants", []):
            marker = "🟢" if participant == status_data.get("active_developer") else "⚪"
            print(f"  {marker} {participant}")
        
        if commits:
            print(f"\nRecent Commits (last 10):")
            print(f"  {'Time':<20} {'Developer':<15} {'Hash':<12} {'Message':<30}")
            print("  " + "-" * 75)
            
            for commit in commits[:10]:
                timestamp = format_timestamp(commit.get("timestamp", 0))
                developer = commit.get("developer_id", "N/A")
                commit_hash = commit.get("commit_hash", "N/A")[:10]
                message = commit.get("commit_message", "N/A")[:28]
                
                print(f"  {timestamp:<20} {developer:<15} {commit_hash:<12} {message:<30}")
        
        print()
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_rooms_cleanup(args: argparse.Namespace) -> int:
    """Delete empty or inactive rooms."""
    try:
        resp = requests.get(
            f"{DEFAULT_BACKEND}/admin/rooms",
            headers=get_auth_headers(),
            timeout=5
        )
        
        if resp.status_code != 200:
            print(f"❌ Failed to fetch rooms: {resp.status_code}")
            return 1
        
        data = resp.json()
        rooms = data.get("rooms", [])
        
        # Find empty rooms (no participants)
        empty_rooms = [r for r in rooms if len(r.get("participants", [])) == 0]
        
        if not empty_rooms:
            print("✅ No empty rooms found. System is clean!")
            return 0
        
        print(f"\n🧹 Found {len(empty_rooms)} empty room(s) to clean up:")
        for room in empty_rooms:
            print(f"   - {room.get('room_code')}")
        
        if not args.force:
            confirm = input("\nProceed with cleanup? (yes/no): ")
            if confirm.lower() != "yes":
                print("❌ Cleanup cancelled.")
                return 0
        
        # Delete empty rooms
        deleted = 0
        for room in empty_rooms:
            room_code = room.get("room_code")
            resp = requests.delete(
                f"{DEFAULT_BACKEND}/admin/rooms/{room_code}",
                headers=get_auth_headers(),
                timeout=5
            )
            
            if resp.status_code == 200:
                print(f"   ✅ Deleted: {room_code}")
                deleted += 1
            else:
                print(f"   ❌ Failed to delete: {room_code}")
        
        print(f"\n✅ Cleanup complete. Deleted {deleted}/{len(empty_rooms)} rooms.")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


# ==================== USERS COMMANDS ====================

def cmd_users_list(args: argparse.Namespace) -> int:
    """List all active users across all rooms."""
    try:
        resp = requests.get(
            f"{DEFAULT_BACKEND}/admin/rooms",
            headers=get_auth_headers(),
            timeout=5
        )
        
        if resp.status_code != 200:
            print(f"❌ Failed to fetch rooms: {resp.status_code}")
            return 1
        
        data = resp.json()
        rooms = data.get("rooms", [])
        
        # Collect unique users
        users_by_room: Dict[str, List[str]] = {}
        all_users = set()
        
        for room in rooms:
            room_code = room.get("room_code")
            participants = room.get("participants", [])
            
            for participant in participants:
                all_users.add(participant)
                if participant not in users_by_room:
                    users_by_room[participant] = []
                users_by_room[participant].append(room_code)
        
        if not all_users:
            print("📭 No active users found.")
            return 0
        
        print(f"\n👥 Total Active Users: {len(all_users)}\n")
        print(f"{'Developer ID':<20} {'Rooms':<10} {'Room Codes':<40}")
        print("=" * 75)
        
        for user in sorted(all_users):
            rooms_list = users_by_room.get(user, [])
            rooms_str = ", ".join(rooms_list[:3])
            if len(rooms_list) > 3:
                rooms_str += f" +{len(rooms_list) - 3} more"
            
            print(f"{user:<20} {len(rooms_list):<10} {rooms_str:<40}")
        
        print()
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_users_kick(args: argparse.Namespace) -> int:
    """Kick a user from a specific room."""
    developer_id = args.developer_id
    room_code = args.room_code
    
    if not args.force:
        print(f"⚠️  Kick user '{developer_id}' from room '{room_code}'?")
        confirm = input("   Type 'yes' to confirm: ")
        if confirm.lower() != "yes":
            print("❌ Operation cancelled.")
            return 0
    
    try:
        resp = requests.post(
            f"{DEFAULT_BACKEND}/rooms/leave",
            json={"room_code": room_code, "developer_id": developer_id},
            headers=get_auth_headers(),
            timeout=5
        )
        
        if resp.status_code == 404:
            print(f"❌ Room '{room_code}' not found or user not in room.")
            return 1
        
        if resp.status_code != 200:
            print(f"❌ Failed to kick user: {resp.status_code} {resp.text}")
            return 1
        
        print(f"✅ User '{developer_id}' kicked from room '{room_code}'.")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


# ==================== SYSTEM COMMANDS ====================

def cmd_system_health(args: argparse.Namespace) -> int:
    """Check system health status."""
    print("\n🏥 MACT System Health Check\n")
    print("=" * 60)
    
    # Check backend
    print("\n1. Backend API (Port 5000)")
    try:
        resp = requests.get(f"{DEFAULT_BACKEND}/health", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ Status: {data.get('status')}")
            print(f"   📊 Rooms: {data.get('rooms_count', 0)}")
        else:
            print(f"   ❌ Status: Unhealthy ({resp.status_code})")
    except Exception as e:
        print(f"   ❌ Status: Unreachable - {e}")
    
    # Check proxy
    print("\n2. Routing Proxy (Port 9000)")
    try:
        resp = requests.get("http://localhost:9000/health", timeout=3)
        if resp.status_code == 200:
            print(f"   ✅ Status: Healthy")
        else:
            print(f"   ❌ Status: Unhealthy ({resp.status_code})")
    except Exception as e:
        print(f"   ❌ Status: Unreachable - {e}")
    
    # Check systemd services
    print("\n3. Systemd Services")
    services = ["mact-backend", "mact-proxy", "mact-frps"]
    
    for service in services:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service],
                capture_output=True,
                text=True,
                timeout=2
            )
            status = result.stdout.strip()
            
            if status == "active":
                print(f"   ✅ {service}: Running")
            else:
                print(f"   ❌ {service}: {status}")
        except Exception as e:
            print(f"   ⚠️  {service}: Cannot check - {e}")
    
    # Check nginx
    print("\n4. Nginx")
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "nginx"],
            capture_output=True,
            text=True,
            timeout=2
        )
        status = result.stdout.strip()
        
        if status == "active":
            print(f"   ✅ nginx: Running")
        else:
            print(f"   ❌ nginx: {status}")
    except Exception as e:
        print(f"   ⚠️  nginx: Cannot check - {e}")
    
    print("\n" + "=" * 60 + "\n")
    return 0


def cmd_system_stats(args: argparse.Namespace) -> int:
    """Show system usage statistics."""
    try:
        resp = requests.get(
            f"{DEFAULT_BACKEND}/admin/rooms",
            headers=get_auth_headers(),
            timeout=5
        )
        
        if resp.status_code != 200:
            print(f"❌ Failed to fetch stats: {resp.status_code}")
            return 1
        
        data = resp.json()
        rooms = data.get("rooms", [])
        
        total_rooms = len(rooms)
        total_participants = sum(len(r.get("participants", [])) for r in rooms)
        total_commits = sum(r.get("commit_count", 0) for r in rooms)
        
        active_rooms = sum(1 for r in rooms if len(r.get("participants", [])) > 0)
        empty_rooms = total_rooms - active_rooms
        
        print("\n📊 MACT System Statistics\n")
        print("=" * 60)
        print(f"Total Rooms:        {total_rooms}")
        print(f"  Active:           {active_rooms}")
        print(f"  Empty:            {empty_rooms}")
        print(f"\nTotal Participants: {total_participants}")
        print(f"Total Commits:      {total_commits}")
        
        if rooms:
            avg_participants = total_participants / total_rooms
            avg_commits = total_commits / total_rooms
            print(f"\nAverage per room:")
            print(f"  Participants:     {avg_participants:.1f}")
            print(f"  Commits:          {avg_commits:.1f}")
        
        print("\n" + "=" * 60 + "\n")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def cmd_system_logs(args: argparse.Namespace) -> int:
    """View service logs using journalctl."""
    service = args.service
    service_name = f"mact-{service}"
    
    lines = args.lines or 50
    follow = args.follow
    
    try:
        cmd = ["journalctl", "-u", service_name, "-n", str(lines)]
        
        if follow:
            cmd.append("-f")
        
        print(f"📋 Showing logs for {service_name} (last {lines} lines)\n")
        
        subprocess.run(cmd)
        return 0
        
    except KeyboardInterrupt:
        print("\n\n✅ Stopped following logs.")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


# ==================== PARSER SETUP ====================

def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        prog="mact-admin",
        description="MACT Admin CLI - Server-side administration tool"
    )
    
    subparsers = parser.add_subparsers(dest="category", help="Command category")
    
    # ===== ROOMS =====
    rooms_parser = subparsers.add_parser("rooms", help="Manage rooms")
    rooms_sub = rooms_parser.add_subparsers(dest="command", help="Rooms commands")
    
    # rooms list
    rooms_list = rooms_sub.add_parser("list", help="List all rooms")
    rooms_list.set_defaults(func=cmd_rooms_list)
    
    # rooms delete
    rooms_delete = rooms_sub.add_parser("delete", help="Delete a room")
    rooms_delete.add_argument("room_code", help="Room code to delete")
    rooms_delete.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    rooms_delete.set_defaults(func=cmd_rooms_delete)
    
    # rooms info
    rooms_info = rooms_sub.add_parser("info", help="Show room details")
    rooms_info.add_argument("room_code", help="Room code to inspect")
    rooms_info.set_defaults(func=cmd_rooms_info)
    
    # rooms cleanup
    rooms_cleanup = rooms_sub.add_parser("cleanup", help="Delete empty rooms")
    rooms_cleanup.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    rooms_cleanup.set_defaults(func=cmd_rooms_cleanup)
    
    # ===== USERS =====
    users_parser = subparsers.add_parser("users", help="Manage users")
    users_sub = users_parser.add_subparsers(dest="command", help="Users commands")
    
    # users list
    users_list = users_sub.add_parser("list", help="List all active users")
    users_list.set_defaults(func=cmd_users_list)
    
    # users kick
    users_kick = users_sub.add_parser("kick", help="Kick user from room")
    users_kick.add_argument("developer_id", help="Developer ID to kick")
    users_kick.add_argument("room_code", help="Room code")
    users_kick.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    users_kick.set_defaults(func=cmd_users_kick)
    
    # ===== SYSTEM =====
    system_parser = subparsers.add_parser("system", help="System administration")
    system_sub = system_parser.add_subparsers(dest="command", help="System commands")
    
    # system health
    system_health = system_sub.add_parser("health", help="Check system health")
    system_health.set_defaults(func=cmd_system_health)
    
    # system stats
    system_stats = system_sub.add_parser("stats", help="Show usage statistics")
    system_stats.set_defaults(func=cmd_system_stats)
    
    # system logs
    system_logs = system_sub.add_parser("logs", help="View service logs")
    system_logs.add_argument("service", choices=["backend", "proxy", "frps"], help="Service to view logs for")
    system_logs.add_argument("-n", "--lines", type=int, help="Number of lines to show (default: 50)")
    system_logs.add_argument("-f", "--follow", action="store_true", help="Follow logs (like tail -f)")
    system_logs.set_defaults(func=cmd_system_logs)
    
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
