from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import httpx
from collections import OrderedDict

# Import security module
from backend.security import (
    ValidationError,
    validate_room_code,
    validate_developer_id,
    validate_subdomain_url,
    validate_commit_hash,
    validate_branch,
    validate_commit_message,
    validate_project_name,
    validate_request_json,
    require_admin_auth,
    sanitize_html,
    get_client_ip
)

app = Flask(__name__)
CORS(app)  # Enable CORS for dashboard API calls

# In-memory state for PoC
rooms = {}  # room_code -> {"participants": OrderedDict{developer_id: subdomain_url}, "commits": [commit_dict]}

# Proxy notification endpoint (configured via env var)
import os
PROXY_NOTIFICATION_URL = os.getenv("PROXY_NOTIFICATION_URL", "http://localhost:9000/internal/notify-commit")

@app.route('/rooms/create', methods=['POST'])
@validate_request_json('project_name', 'developer_id', 'subdomain_url')
def create_room():
    data = request.get_json()
    
    try:
        # Validate and sanitize inputs
        room_code = validate_project_name(data['project_name'])
        developer_id = validate_developer_id(data['developer_id'])
        subdomain_url = validate_subdomain_url(data['subdomain_url'])
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "message": str(e)}), 400

    if room_code in rooms:
        return jsonify({"error": "Room with this project name already exists"}), 409

    rooms[room_code] = {
        "participants": OrderedDict({developer_id: subdomain_url}),
        "commits": []
    }

    public_url = f"http://{room_code}.m-act.live"
    return jsonify({"room_code": room_code, "public_url": public_url}), 201

@app.route('/rooms/join', methods=['POST'])
@validate_request_json('room_code', 'developer_id', 'subdomain_url')
def join_room():
    data = request.get_json()
    
    try:
        # Validate and sanitize inputs
        room_code = validate_room_code(data['room_code'])
        developer_id = validate_developer_id(data['developer_id'])
        subdomain_url = validate_subdomain_url(data['subdomain_url'])
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "message": str(e)}), 400

    if room_code not in rooms:
        return jsonify({"error": "Room not found"}), 404

    # Check if developer already exists in this room
    if developer_id in rooms[room_code]["participants"]:
        # Update subdomain URL and mark as connected (rejoin/reconnect)
        rooms[room_code]["participants"][developer_id] = {
            "subdomain_url": subdomain_url,
            "connected": True
        }
        # Notify proxy of reconnection
        _notify_proxy_room_update(room_code)
        public_url = f"http://{room_code}.m-act.live"
        return jsonify({"status": "reconnected", "public_url": public_url}), 200

    # New participant - add with connected status
    rooms[room_code]["participants"][developer_id] = {
        "subdomain_url": subdomain_url,
        "connected": True
    }
    
    # Notify proxy of room update (new participant joined)
    _notify_proxy_room_update(room_code)
    
    public_url = f"http://{room_code}.m-act.live"
    return jsonify({"status": "success", "public_url": public_url}), 200

@app.route('/rooms/leave', methods=['POST'])
@validate_request_json('room_code', 'developer_id')
def leave_room():
    data = request.get_json()
    
    try:
        # Validate inputs
        room_code = validate_room_code(data['room_code'])
        developer_id = validate_developer_id(data['developer_id'])
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "message": str(e)}), 400

    if room_code not in rooms:
        return jsonify({"error": "Room not found"}), 404

    if developer_id not in rooms[room_code]["participants"]:
        return jsonify({"error": "Developer not in room"}), 404

    # Mark as disconnected instead of removing
    participant_info = rooms[room_code]["participants"][developer_id]
    if isinstance(participant_info, dict):
        participant_info["connected"] = False
    else:
        # Convert old format to new format
        rooms[room_code]["participants"][developer_id] = {
            "subdomain_url": participant_info,
            "connected": False
        }
    
    # Notify proxy of status change
    _notify_proxy_room_update(room_code)
    
    return jsonify({"status": "success"}), 200

@app.route('/report-commit', methods=['POST'])
@validate_request_json('room_code', 'developer_id', 'commit_hash', 'branch', 'commit_message')
def report_commit():
    data = request.get_json()
    
    try:
        # Validate all inputs
        room_code = validate_room_code(data['room_code'])
        developer_id = validate_developer_id(data['developer_id'])
        commit_hash = validate_commit_hash(data['commit_hash'])
        branch = validate_branch(data['branch'])
        commit_message = validate_commit_message(data['commit_message'])
        
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "message": str(e)}), 400

    if room_code not in rooms:
        return jsonify({"error": "Room not found"}), 404

    # Validate developer is a participant in the room
    if developer_id not in rooms[room_code]["participants"]:
        return jsonify({"error": "Developer not in room"}), 403

    # Check if active developer will change
    commits = rooms[room_code]["commits"]
    previous_active = commits[-1]["developer_id"] if commits else None
    
    commit = {
        "commit_hash": commit_hash,
        "branch": branch,
        "commit_message": commit_message,
        "developer_id": developer_id,
        "timestamp": time.time()
    }
    rooms[room_code]["commits"].append(commit)

    # Notify proxy about the commit
    if previous_active != developer_id:
        # Active developer changed - send active developer change notification (for mirror)
        _notify_proxy_async(room_code, developer_id)
    else:
        # Same developer committed - send room update notification (for dashboard commit history)
        _notify_proxy_room_update(room_code)

    return jsonify({"status": "success"}), 200


def _notify_proxy_async(room_code: str, developer_id: str):
    """Send async notification to proxy about active developer change."""
    try:
        # Non-blocking fire-and-forget notification
        import threading
        def _send():
            try:
                with httpx.Client(timeout=1.0) as client:
                    client.post(
                        PROXY_NOTIFICATION_URL,
                        json={"room_code": room_code, "active_developer": developer_id}
                    )
            except Exception:
                pass  # Silently fail if proxy is unavailable
        
        thread = threading.Thread(target=_send, daemon=True)
        thread.start()
    except Exception:
        pass  # Fail silently - notification is best-effort


def _notify_proxy_room_update(room_code: str):
    """Send async notification to proxy about room update (e.g., new participant)."""
    try:
        # Non-blocking fire-and-forget notification
        import threading
        def _send():
            try:
                with httpx.Client(timeout=1.0) as client:
                    client.post(
                        PROXY_NOTIFICATION_URL,
                        json={"room_code": room_code, "event_type": "room_update"}
                    )
            except Exception:
                pass  # Silently fail if proxy is unavailable
        
        thread = threading.Thread(target=_send, daemon=True)
        thread.start()
    except Exception:
        pass  # Fail silently - notification is best-effort

@app.route('/get-active-url', methods=['GET'])
def get_active_url():
    room_code = request.args.get('room')
    
    try:
        # Validate room_code if provided
        if room_code:
            room_code = validate_room_code(room_code)
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "message": str(e)}), 400
    
    if not room_code or room_code not in rooms:
        return jsonify({"active_url": None}), 200

    room = rooms[room_code]
    commits = room["commits"]
    participants = room["participants"]

    # If no participants, return null
    if not participants:
        return jsonify({"active_url": None}), 200

    # Determine active developer with fallback chain (same logic as get_room_status)
    active_developer = None
    
    if commits:
        # Try to find the latest connected developer from commit history (newest to oldest)
        for commit in reversed(commits):
            dev_id = commit['developer_id']
            if dev_id in participants:
                info = participants[dev_id]
                # Handle both old format (string) and new format (dict)
                is_connected = info.get("connected", True) if isinstance(info, dict) else True
                if is_connected:
                    active_developer = dev_id
                    break
    
    # Fallback to first connected participant if no commits or all committers disconnected
    if not active_developer and participants:
        for dev_id, info in participants.items():
            # Handle both old format (string) and new format (dict)
            is_connected = info.get("connected", True) if isinstance(info, dict) else True
            if is_connected:
                active_developer = dev_id
                break
    
    # Last resort: use first participant regardless of connection status
    if not active_developer and participants:
        active_developer = next(iter(participants.keys()))
    
    # Get the subdomain for the active developer
    if active_developer:
        info = participants[active_developer]
        # Handle both old format (string) and new format (dict)
        subdomain_url = info.get("subdomain_url") if isinstance(info, dict) else info
        
        # WORKAROUND: Convert public subdomain to FRP internal endpoint
        # The proxy needs to fetch from the FRP vhost (port 7101), not the public URL
        # Each developer has their own FRP tunnel with subdomain: dev-{developer}-{room}.m-act.live
        if subdomain_url:
            # Extract the full subdomain from the public URL
            # Format: http://dev-{developer}-{room}.m-act.live
            # We need to use this exact subdomain as the Host header for FRP vhost routing
            try:
                # Parse the subdomain from the URL (e.g., "dev-rahba-hospital.m-act.live")
                from urllib.parse import urlparse
                parsed = urlparse(subdomain_url)
                frp_host = parsed.netloc  # e.g., "dev-rahba-hospital.m-act.live"
                
                # The FRP internal endpoint is always http://127.0.0.1:7101 with the developer's Host header
                active_url = f"http://127.0.0.1:7101|Host:{frp_host}"
            except Exception as e:
                print(f"[ERROR] Failed to parse subdomain URL '{subdomain_url}': {e}")
                active_url = None
        else:
            active_url = None
    else:
        active_url = None

    # DEBUG: Log what we're returning
    print(f"[DEBUG] get_active_url for room '{room_code}': returning '{active_url}'")
    print(f"[DEBUG] Active developer: {active_developer}")
    print(f"[DEBUG] Participants: {dict(participants)}")
    print(f"[DEBUG] Commits count: {len(commits)}")

    return jsonify({"active_url": active_url}), 200

@app.route('/rooms/status', methods=['GET'])
def get_room_status():
    room_code = request.args.get('room')
    
    try:
        # Validate room_code
        if room_code:
            room_code = validate_room_code(room_code)
        else:
            return jsonify({"error": "Missing room parameter"}), 400
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "message": str(e)}), 400
    
    if room_code not in rooms:
        return jsonify({"error": "Room not found"}), 404

    room = rooms[room_code]
    commits = room["commits"]
    participants = room["participants"]
    
    # Determine active developer with fallback chain:
    # 1. Latest committer (if connected)
    # 2. Previous committer (if connected)
    # 3. ... continue through commit history
    # 4. First participant (room creator) as base case
    active_developer = None
    
    if commits:
        # Try to find the latest connected developer from commit history (newest to oldest)
        for commit in reversed(commits):
            dev_id = commit['developer_id']
            if dev_id in participants:
                info = participants[dev_id]
                # Handle both old format (string) and new format (dict)
                is_connected = info.get("connected", True) if isinstance(info, dict) else True
                if is_connected:
                    active_developer = dev_id
                    break
    
    # Fallback to first connected participant if no commits or all committers disconnected
    if not active_developer and participants:
        for dev_id, info in participants.items():
            # Handle both old format (string) and new format (dict)
            is_connected = info.get("connected", True) if isinstance(info, dict) else True
            if is_connected:
                active_developer = dev_id
                break
    
    # Last resort: use first participant regardless of connection status
    if not active_developer and participants:
        active_developer = next(iter(participants.keys()))
    
    latest_commit = commits[-1] if commits else None
    latest_commit_hash = latest_commit['commit_hash'] if latest_commit else None
    
    # Build participants list with connection status
    participants_list = []
    for dev_id, info in participants.items():
        # Handle both old format (string) and new format (dict with connected status)
        if isinstance(info, dict):
            participants_list.append({
                "developer_id": dev_id,
                "subdomain_url": info.get("subdomain_url", ""),
                "connected": info.get("connected", False)
            })
        else:
            # Legacy format: just subdomain URL string
            participants_list.append({
                "developer_id": dev_id,
                "subdomain_url": info,
                "connected": True  # Assume connected for legacy data
            })

    return jsonify({
        "room_code": room_code,
        "active_developer": active_developer,
        "latest_commit": latest_commit_hash,
        "participants": participants_list
    }), 200

@app.route('/rooms/<room_code>/commits', methods=['GET'])
def get_room_commits(room_code):
    try:
        # Validate room_code from URL path
        room_code = validate_room_code(room_code)
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "message": str(e)}), 400
    
    if room_code not in rooms:
        return jsonify({"error": "Room not found"}), 404

    commits = rooms[room_code]["commits"]
    return jsonify({"room_code": room_code, "commits": commits}), 200

@app.route('/admin/rooms', methods=['GET'])
@require_admin_auth
def list_all_rooms():
    """List all rooms with details (admin only)."""
    room_list = []
    for room_code, room_data in rooms.items():
        # Get active developer
        active_dev = None
        if room_data["commits"]:
            active_dev = room_data["commits"][-1]["developer_id"]
        
        room_list.append({
            "room_code": room_code,
            "participants": list(room_data["participants"].keys()),
            "commit_count": len(room_data["commits"]),
            "active_developer": active_dev
        })
    return jsonify({"rooms": room_list}), 200

@app.route('/admin/rooms/<room_code>', methods=['DELETE'])
@require_admin_auth
def delete_room(room_code):
    """Delete a specific room (admin only)."""
    try:
        room_code = validate_room_code(room_code)
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "message": str(e)}), 400
    
    if room_code not in rooms:
        return jsonify({"error": "Room not found"}), 404
    
    # Delete room and notify proxy
    del rooms[room_code]
    _notify_proxy_room_update(room_code)
    
    return jsonify({
        "status": "success",
        "message": f"Room '{room_code}' deleted successfully"
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "rooms_count": len(rooms)}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)