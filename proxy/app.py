"""Starlette/ASGI application for the MACT Public Routing Proxy (Unit 2 - Complete).

This proxy looks up the active developer for a room via the coordination
backend and mirrors their tunnel without issuing HTTP redirects. It also
serves a lightweight dashboard that surfaces room status and recent commits.

NEW: Full WebSocket/HTTP Upgrade support via ASGI.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
import websockets
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from .frp_manager import FrpsManager
from .frp_supervisor import FrpSupervisor

load_dotenv()

DEFAULT_BACKEND_URL = "http://localhost:5000"
DEFAULT_TIMEOUT_SECONDS = 5
IGNORED_UPSTREAM_HEADERS = {"content-encoding", "transfer-encoding", "connection"}
MAX_DASHBOARD_COMMITS = 10
STREAM_BUFFER_SIZE = 8192

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MACT Dashboard - {{ room_code }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: Verdana, Arial, sans-serif;
            font-size: 13px;
            background-color: #f5f5f5;
            color: #333;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: #fff;
            padding: 20px;
            border: 1px solid #ddd;
        }
        
        h1 {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #333;
        }
        
        .room-code {
            color: #0066cc;
        }
        
        .section {
            margin-bottom: 25px;
        }
        
        .section-title {
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #555;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            border: 1px solid #ccc;
            background-color: #fff;
        }
        
        th {
            background-color: #e8e8e8;
            padding: 8px;
            text-align: left;
            font-weight: bold;
            border: 1px solid #ccc;
        }
        
        td {
            padding: 8px;
            border: 1px solid #ccc;
        }
        
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        tr:hover {
            background-color: #ffffcc;
        }
        
        .active-row {
            background-color: #e8f4e8 !important;
            font-weight: bold;
        }
        
        .status-badge {
            padding: 2px 6px;
            font-size: 11px;
            border-radius: 2px;
        }
        
        .status-active {
            background-color: #c8e6c9;
            color: #2e7d32;
        }
        
        .status-connected {
            background-color: #e0e0e0;
            color: #616161;
        }
        
        .status-disconnected {
            background-color: #ffccbc;
            color: #d84315;
        }
        
        .commit-hash {
            font-family: monospace;
            font-size: 12px;
            color: #0066cc;
        }
        
        .auto-refresh {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background-color: #fff;
            border: 1px solid #ccc;
            padding: 10px 15px;
            font-size: 12px;
            border-radius: 3px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: none; /* Hidden by default, shown only when disconnected */
        }
        
        .auto-refresh.show {
            display: block;
        }
        
        a {
            color: #0066cc;
            text-decoration: none;
        }
        
        a:hover {
            text-decoration: underline;
        }
        
        .status-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 5px;
        }
        
        .status-disconnected {
            background-color: #f44336;
        }
        
        .search-box {
            margin-bottom: 10px;
        }
        
        .search-box input {
            width: 100%;
            padding: 8px;
            border: 1px solid #ccc;
            font-family: Verdana, Arial, sans-serif;
            font-size: 13px;
        }
        
        .no-data {
            padding: 20px;
            text-align: center;
            color: #999;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Room: <span class="room-code">{{ room_code }}</span></h1>
        
        <div class="section">
            <div class="section-title">Active Participants</div>
            <table>
                <thead>
                    <tr>
                        <th style="width: 50px;">#</th>
                        <th>Developer ID</th>
                        <th>Dev Tunnel</th>
                        <th style="width: 100px;">Status</th>
                    </tr>
                </thead>
                <tbody id="participants-body">
                    {{ participants_html }}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <div class="section-title">Commit History</div>
            <div class="search-box">
                <input type="text" id="commit-search" placeholder="Search commits by hash, message, developer, or branch...">
            </div>
            <table id="commit-table">
                <thead>
                    <tr>
                        <th style="width: 50px;">#</th>
                        <th style="width: 100px;">Hash</th>
                        <th>Message</th>
                        <th style="width: 150px;">Developer</th>
                        <th style="width: 120px;">Branch</th>
                        <th style="width: 150px;">Timestamp</th>
                    </tr>
                </thead>
                <tbody id="commits-body">
                    {{ commits_html }}
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="auto-refresh" id="auto-refresh-indicator">
        <span class="status-dot status-disconnected" id="ws-status-dot"></span>
        <span id="ws-status-text">Connecting...</span>
    </div>
    
    <script>
        // WebSocket connection for auto-refresh
        const roomCode = "{{ room_code }}";
        let ws = null;
        let reconnectTimeout = null;
        
        function connectWebSocket() {
            const wsUrl = `ws://localhost:9000/notifications`;
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                updateStatus('connected', 'Auto-refresh active');
                
                // Subscribe to this room
                ws.send(JSON.stringify({
                    type: 'subscribe',
                    room: roomCode
                }));
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                console.log('Received notification:', data);
                
                // Reload dashboard on any room update
                // Types: 'commit' (new commit), 'room_update' (participant joined/left)
                if (data.type === 'commit' || data.type === 'room_update') {
                    console.log('Room update detected, reloading dashboard...');
                    location.reload();
                }
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                updateStatus('disconnected', 'Connection error');
            };
            
            ws.onclose = () => {
                console.log('WebSocket closed');
                updateStatus('disconnected', 'Reconnecting...');
                
                // Attempt to reconnect after 5 seconds
                reconnectTimeout = setTimeout(connectWebSocket, 5000);
            };
        }
        
        function updateStatus(status, text) {
            const dot = document.getElementById('ws-status-dot');
            const statusText = document.getElementById('ws-status-text');
            const indicator = document.getElementById('auto-refresh-indicator');
            
            dot.className = 'status-dot status-' + status;
            statusText.textContent = text;
            
            // Only show indicator when disconnected
            if (status === 'disconnected') {
                indicator.classList.add('show');
            } else {
                indicator.classList.remove('show');
            }
        }
        
        // Initialize WebSocket connection
        connectWebSocket();
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (ws) {
                ws.close();
            }
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
            }
        });
        
        // Search functionality
        const searchInput = document.getElementById('commit-search');
        const commitRows = document.querySelectorAll('.commit-row');
        
        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            
            commitRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    </script>
</body>
</html>
"""

DASHBOARD_ERROR_TEMPLATE = """
<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>MACT Dashboard - {{ room_code }}</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            
            body {
                font-family: Verdana, Arial, sans-serif;
                font-size: 13px;
                background-color: #f5f5f5;
                color: #333;
                padding: 20px;
            }
            
            .error-container {
                max-width: 600px;
                margin: 50px auto;
                background: #fff;
                border: 1px solid #ddd;
                padding: 30px;
            }
            
            .error-icon {
                font-size: 3rem;
                margin-bottom: 15px;
                text-align: center;
            }
            
            h1 {
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 2px solid #333;
            }
            
            .room-code {
                color: #0066cc;
                font-family: monospace;
            }
            
            .message {
                color: #d32f2f;
                font-size: 14px;
                line-height: 1.6;
                margin: 20px 0;
                padding: 15px;
                background-color: #ffebee;
                border: 1px solid #ef5350;
            }
            
            .back-link {
                display: inline-block;
                margin-top: 20px;
                padding: 8px 16px;
                background-color: #0066cc;
                color: white;
                text-decoration: none;
                border: 1px solid #0052a3;
                font-weight: bold;
            }
            
            .back-link:hover {
                background-color: #0052a3;
            }
        </style>
    </head>
</html>
"""


@dataclass
class BackendLookupError(Exception):
    """Represents a failure when fetching data from the coordination backend."""

    message: str
    status_code: int = 502

    def __str__(self) -> str:
        return self.message


# Global logger and backend URL
logger = logging.getLogger("mact.proxy")
backend_base_url = os.getenv("BACKEND_BASE_URL", DEFAULT_BACKEND_URL).rstrip("/")


def _simple_template_render(template: str, **context: Any) -> str:
    """Ultra-simple template rendering (replaces {{ var }} and {% if/for %})."""
    import re
    result = template
    
    # Handle {% for item in items %} ... {% endfor %} FIRST (before if blocks)
    for_pattern = r'\{% for (\w+) in (\w+) %\}(.*?)\{% endfor %\}'
    for match in re.finditer(for_pattern, result, re.DOTALL):
        item_name = match.group(1)
        list_name = match.group(2)
        loop_body = match.group(3)
        items = context.get(list_name, [])
        rendered_items = []
        for item in items:
            item_html = loop_body
            if isinstance(item, dict):
                # Handle {{ item.key or "default" }} expressions
                or_pattern = r'\{\{ ' + item_name + r'\.(\w+) or "(.*?)" \}\}'
                for or_match in re.finditer(or_pattern, item_html):
                    key = or_match.group(1)
                    default = or_match.group(2)
                    value = item.get(key) or default
                    item_html = item_html.replace(or_match.group(0), str(value))
                # Handle simple {{ item.key }} expressions
                for key, value in item.items():
                    item_html = item_html.replace(f"{{{{ {item_name}.{key} }}}}", str(value or ""))
            else:
                item_html = item_html.replace(f"{{{{ {item_name} }}}}", str(item))
            rendered_items.append(item_html)
        result = result.replace(match.group(0), "".join(rendered_items))
    
    # Handle {% if var %} ... {% elif var2 %} ... {% else %} ... {% endif %}
    if_pattern = r'\{% if (\w+) %\}(.*?)(?:\{% elif (\w+) %\}(.*?))?(?:\{% else %\}(.*?))?\{% endif %\}'
    for match in re.finditer(if_pattern, result, re.DOTALL):
        var_name = match.group(1)
        true_block = match.group(2)
        elif_var = match.group(3)
        elif_block = match.group(4)
        else_block = match.group(5)
        
        if context.get(var_name):
            result = result.replace(match.group(0), true_block)
        elif elif_var and context.get(elif_var):
            result = result.replace(match.group(0), elif_block or "")
        elif else_block:
            result = result.replace(match.group(0), else_block)
        else:
            result = result.replace(match.group(0), "")
    
    # Handle filters like {{ var|length }}
    filter_pattern = r'\{\{ (\w+)\|(\w+) \}\}'
    for match in re.finditer(filter_pattern, result):
        var_name = match.group(1)
        filter_name = match.group(2)
        value = context.get(var_name)
        
        if filter_name == 'length':
            filtered_value = len(value) if value is not None else 0
        else:
            filtered_value = value
        
        result = result.replace(match.group(0), str(filtered_value))
    
    # Replace simple variables
    for key, value in context.items():
        if value is None:
            value = ""
        result = result.replace(f"{{{{ {key} }}}}", str(value))
    
    return result


async def _get_backend_json(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Perform a GET request to the coordination backend and return JSON."""
    lookup_url = f"{backend_base_url}/{path.lstrip('/')}"
    
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        try:
            response = await client.get(lookup_url, params=params)
        except httpx.RequestError as exc:
            logger.error("Failed to contact coordination backend: %s", exc)
            raise BackendLookupError("Failed to contact coordination backend") from exc
        
        if response.status_code == 404:
            raise BackendLookupError("Room not found", status_code=404)
        if response.status_code >= 500:
            logger.error(
                "Coordination backend error %s while resolving room %s",
                response.status_code,
                params.get("room") if params else "unknown",
            )
            raise BackendLookupError("Coordination backend error", status_code=502)
        if response.status_code != 200:
            raise BackendLookupError(
                f"Unexpected response {response.status_code} from coordination backend",
                status_code=502,
            )
        
        try:
            return response.json()
        except ValueError as exc:
            logger.error("Invalid JSON from coordination backend: %s", exc)
            raise BackendLookupError("Invalid response from coordination backend") from exc


async def _fetch_active_url(room_code: str) -> Optional[str]:
    """Fetch the active developer tunnel URL for the given room."""
    payload = await _get_backend_json("get-active-url", params={"room": room_code})
    return payload.get("active_url")


async def _fetch_room_status(room_code: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Optional[str]]:
    """Fetch room status and commit history for dashboard rendering."""
    status_payload = await _get_backend_json("rooms/status", params={"room": room_code})
    commits: List[Dict[str, Any]] = []
    commit_error: Optional[str] = None
    
    try:
        commits_payload = await _get_backend_json(f"rooms/{room_code}/commits")
        commits = commits_payload.get("commits", []) or []
    except BackendLookupError as err:
        commit_error = str(err)
        logger.warning("Commit history unavailable for %s: %s", room_code, err)
    
    return status_payload, commits, commit_error


def _build_target_url(base_url: str, path: str) -> str:
    """Build the target URL by combining base and path."""
    trimmed_base = base_url.rstrip("/")
    if path:
        return f"{trimmed_base}/{path}"
    return trimmed_base


def _mirror_headers(upstream_headers: Dict[str, str]) -> Dict[str, str]:
    """Filter headers for mirroring response."""
    mirrored: Dict[str, str] = {}
    for header, value in upstream_headers.items():
        if header.lower() in IGNORED_UPSTREAM_HEADERS:
            continue
        mirrored[header] = value
    return mirrored


def _forward_headers(request_headers: Any) -> Dict[str, str]:
    """Filter request headers for forwarding."""
    hop_by_hop = {
        "host",
        "content-length",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
    headers: Dict[str, str] = {}
    for header, value in request_headers.items():
        if header.lower() in hop_by_hop:
            continue
        headers[header] = value
    return headers


async def health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "healthy", "backend_base_url": backend_base_url})


def _extract_room_code(request: Request) -> Optional[str]:
    """Extract room code from path params or Host header subdomain."""
    # Try path params first (legacy routes: /rooms/{room_code}/...)
    room_code = request.path_params.get("room_code")
    if room_code:
        return room_code.lower()
    
    # Try Host header subdomain (e.g., mact-demo-e2e.m-act.live or mact-demo-e2e.localhost)
    host = request.headers.get("host", "")
    if host:
        # Remove port if present
        host_without_port = host.split(":")[0]
        # Extract subdomain (everything before .m-act.live or .localhost)
        if ".m-act.live" in host_without_port:
            subdomain = host_without_port.replace(".m-act.live", "")
            return subdomain.lower() if subdomain else None
        elif ".localhost" in host_without_port:
            subdomain = host_without_port.replace(".localhost", "")
            return subdomain.lower() if subdomain else None
    
    return None


async def mirror(request: Request) -> StreamingResponse:
    """HTTP mirror endpoint - streams content from active developer tunnel with auto-refresh."""
    room_code = _extract_room_code(request)
    if not room_code:
        return JSONResponse(
            {"error": "invalid_request", "message": "Could not determine room from URL"},
            status_code=400,
        )
    
    path = request.path_params.get("path", "")
    
    try:
        active_url = await _fetch_active_url(room_code)
        logger.info(f"[MIRROR DEBUG] Room: {room_code}, Active URL from backend: {active_url}")
    except BackendLookupError as err:
        return JSONResponse(
            {"error": "backend_unavailable", "message": str(err)},
            status_code=err.status_code,
        )
    
    if not active_url:
        logger.warning(f"[MIRROR DEBUG] Room: {room_code}, No active URL returned")
        return JSONResponse(
            {
                "error": "no_active_developer",
                "message": "No active developer is currently mirrored for this room.",
            },
            status_code=503,
        )
    
    # WORKAROUND: Parse special format from backend: "http://127.0.0.1:7101|Host:room.m-act.live"
    # This allows backend to specify both the FRP endpoint and the Host header to use
    custom_host_header = None
    if "|Host:" in active_url:
        base_url, host_part = active_url.split("|Host:", 1)
        active_url = base_url
        custom_host_header = host_part
        logger.info(f"[MIRROR DEBUG] Using FRP endpoint {active_url} with Host: {custom_host_header}")
    
    target_url = _build_target_url(active_url, path)
    logger.info(f"[MIRROR DEBUG] Fetching from: {target_url}")
    
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        try:
            # Prepare headers for the upstream request
            upstream_headers = _forward_headers(request.headers)
            
            # Override Host header if backend specified one (for FRP vhost routing)
            if custom_host_header:
                upstream_headers["host"] = custom_host_header
            
            # Fetch the complete response
            response = await client.get(
                url=target_url,
                params=dict(request.query_params),
                headers=upstream_headers,
                follow_redirects=False,
            )
            
            # Inject auto-refresh WebSocket script for HTML responses
            content = response.content
            content_type = response.headers.get("content-type", "")
            
            if "text/html" in content_type:
                # Inject WebSocket auto-refresh script before </body>
                auto_refresh_script = f"""
<script>
(function() {{
    const roomCode = window.location.hostname.split('.')[0];
    const ws = new WebSocket('ws://' + window.location.host + '/notifications');
    
    ws.onopen = function() {{
        // Subscribe to room updates
        ws.send(JSON.stringify({{
            type: 'subscribe',
            room: roomCode
        }}));
    }};
    
    ws.onmessage = function(event) {{
        const data = JSON.parse(event.data);
        // Reload on any room update (commit or room_update)
        if (data.type === 'commit' || data.type === 'room_update') {{
            console.log('Active developer changed, reloading...');
            window.location.reload();
        }}
    }};
    ws.onerror = function(error) {{
        console.error('WebSocket error:', error);
    }};
    ws.onclose = function() {{
        console.log('WebSocket closed, reconnecting in 3 seconds...');
        setTimeout(() => window.location.reload(), 3000);
    }};
}})();
</script>
</body>
"""
                try:
                    html_content = content.decode("utf-8")
                    if "</body>" in html_content:
                        html_content = html_content.replace("</body>", auto_refresh_script)
                        content = html_content.encode("utf-8")
                except (UnicodeDecodeError, Exception) as e:
                    logger.warning("Could not inject auto-refresh script: %s", e)
            
            # Get headers and update content-length if content was modified
            response_headers = _mirror_headers(dict(response.headers))
            if len(content) != len(response.content):
                # Content was modified, update content-length
                response_headers["content-length"] = str(len(content))
            
            # Add cache-control headers to prevent browser caching
            # This ensures users always see the latest active developer's content
            response_headers["cache-control"] = "no-cache, no-store, must-revalidate"
            response_headers["pragma"] = "no-cache"
            response_headers["expires"] = "0"
            
            # Return the content (possibly modified)
            return Response(
                content=content,
                status_code=response.status_code,
                headers=response_headers,
            )
        except httpx.RequestError as exc:
            logger.error("Failed to contact active developer tunnel: %s", exc)
            return JSONResponse(
                {
                    "error": "upstream_unreachable",
                    "message": "Could not contact the active developer tunnel.",
                },
                status_code=502,
            )


async def websocket_mirror(websocket: WebSocket) -> None:
    """WebSocket mirror endpoint - forwards WebSocket connections to active developer tunnel."""
    await websocket.accept()
    
    # Extract room code from path params or Host header
    room_code = websocket.path_params.get("room_code")
    if not room_code:
        host = websocket.headers.get("host", "")
        if host:
            host_without_port = host.split(":")[0]
            if ".m-act.live" in host_without_port:
                room_code = host_without_port.replace(".m-act.live", "")
            elif ".localhost" in host_without_port:
                room_code = host_without_port.replace(".localhost", "")
    
    if not room_code:
        await websocket.close(code=1011, reason="Could not determine room")
        return
    
    room_code = room_code.lower()
    
    try:
        # Get active developer URL
        active_url = await _fetch_active_url(room_code)
        if not active_url:
            await websocket.close(code=1011, reason="No active developer")
            return
        
        # Convert HTTP URL to WebSocket URL
        ws_url = active_url.replace("http://", "ws://").replace("https://", "wss://")
        
        # Extract path from original request
        path = websocket.url.path.replace(f"/rooms/{room_code}/ws", "")
        if path and not path.startswith("/"):
            path = "/" + path
        target_ws_url = f"{ws_url}{path}"
        
        logger.info("WebSocket mirror: connecting to %s", target_ws_url)
        
        # Connect to upstream WebSocket
        async with websockets.connect(target_ws_url) as upstream_ws:
            # Bidirectional forwarding
            async def forward_client_to_upstream():
                try:
                    while True:
                        data = await websocket.receive()
                        if "text" in data:
                            await upstream_ws.send(data["text"])
                        elif "bytes" in data:
                            await upstream_ws.send(data["bytes"])
                except WebSocketDisconnect:
                    logger.info("Client WebSocket disconnected")
                except Exception as e:
                    logger.error("Error forwarding client to upstream: %s", e)
            
            async def forward_upstream_to_client():
                try:
                    async for message in upstream_ws:
                        if isinstance(message, str):
                            await websocket.send_text(message)
                        elif isinstance(message, bytes):
                            await websocket.send_bytes(message)
                except Exception as e:
                    logger.error("Error forwarding upstream to client: %s", e)
            
            # Run both directions concurrently
            await asyncio.gather(
                forward_client_to_upstream(),
                forward_upstream_to_client(),
                return_exceptions=True,
            )
    
    except BackendLookupError as err:
        logger.warning("WebSocket mirror backend lookup failed: %s", err)
        await websocket.close(code=1011, reason=str(err))
    except Exception as e:
        logger.error("WebSocket mirror error: %s", e)
        await websocket.close(code=1011, reason="Internal error")


# Global storage for active developer tracking (PoC - in-memory)
_active_developer_cache: Dict[str, str] = {}  # room_code -> active_developer_id
_notification_clients: Dict[str, List[WebSocket]] = {}  # room_code -> [websocket, ...]


async def notify_room_clients(room_code: str, active_developer: str):
    """Broadcast active developer change (commit) to all connected WebSocket clients for a room."""
    if room_code not in _notification_clients:
        return
    
    # Update cache
    _active_developer_cache[room_code] = active_developer
    
    # Broadcast to all connected clients
    disconnected = []
    for ws in _notification_clients[room_code]:
        try:
            await ws.send_json({
                "type": "commit",  # Changed from "active_developer_changed" to match JS expectations
                "room": room_code,
                "active_developer": active_developer
            })
        except Exception as e:
            logger.error("Failed to send notification to client: %s", e)
            disconnected.append(ws)
    
    # Clean up disconnected clients
    for ws in disconnected:
        try:
            _notification_clients[room_code].remove(ws)
        except ValueError:
            pass


async def notify_room_update(room_code: str):
    """Broadcast general room update (e.g., new participant) to all connected clients."""
    if room_code not in _notification_clients:
        return
    
    # Broadcast to all connected clients
    disconnected = []
    for ws in _notification_clients[room_code]:
        try:
            await ws.send_json({
                "type": "room_update",
                "room": room_code,
                "message": "Room participants updated"
            })
        except Exception as e:
            logger.error("Failed to send room update to client: %s", e)
            disconnected.append(ws)
    
    # Clean up disconnected clients
    for ws in disconnected:
        try:
            _notification_clients[room_code].remove(ws)
        except ValueError:
            pass


async def internal_notify_commit(request: Request) -> JSONResponse:
    """Internal endpoint called by backend when a commit is reported or room is updated."""
    try:
        data = await request.json()
        room_code = data.get("room_code")
        event_type = data.get("event_type")  # Can be "room_update" for participant join
        
        if not room_code:
            return JSONResponse({"error": "Missing room_code"}, status_code=400)
        
        # If it's a room update (new participant joined), send general room update
        if event_type == "room_update":
            await notify_room_update(room_code)
        else:
            # Active developer change notification
            active_developer = data.get("active_developer")
            if not active_developer:
                return JSONResponse({"error": "Missing active_developer"}, status_code=400)
            await notify_room_clients(room_code, active_developer)
        
        return JSONResponse({"status": "notified"}, status_code=200)
    except Exception as e:
        logger.error("Error processing notification: %s", e)
        return JSONResponse({"error": "Internal error"}, status_code=500)


async def websocket_notifications(websocket: WebSocket) -> None:
    """WebSocket endpoint that notifies clients when active developer changes."""
    await websocket.accept()
    
    room_code = None
    
    try:
        # Wait for client to send subscription message with room code
        subscription_msg = await websocket.receive_json()
        room_code = subscription_msg.get("room")
        
        if not room_code:
            await websocket.close(code=1011, reason="No room specified in subscription")
            return
        
        room_code = room_code.lower()
        
        # Register this client
        if room_code not in _notification_clients:
            _notification_clients[room_code] = []
        _notification_clients[room_code].append(websocket)
        
        logger.info(f"WebSocket client subscribed to room: {room_code}")
        
        # Send confirmation
        await websocket.send_json({
            "type": "subscribed",
            "room": room_code,
            "message": "Successfully subscribed to room updates"
        })
        
        # Keep connection alive - notifications are pushed via notify_room_clients/notify_room_update
        while True:
            try:
                # Keep connection alive, allow client to send ping messages
                msg = await websocket.receive_text()
                # Echo back to keep alive
                await websocket.send_json({"type": "pong"})
            except Exception:
                break
    
    except WebSocketDisconnect:
        logger.info("Notification WebSocket disconnected for room %s", room_code)
    except Exception as e:
        logger.error("Notification WebSocket error for room %s: %s", room_code, e)
    finally:
        # Unregister this client
        if room_code in _notification_clients:
            try:
                _notification_clients[room_code].remove(websocket)
                if not _notification_clients[room_code]:
                    del _notification_clients[room_code]
            except ValueError:
                pass


async def dashboard(request: Request) -> HTMLResponse:
    """Dashboard endpoint - displays room status and commit history."""
    room_code = _extract_room_code(request)
    if not room_code:
        return HTMLResponse(
            "<html><body><h1>Error</h1><p>Could not determine room from URL</p></body></html>",
            status_code=400,
        )
    
    try:
        status_payload, commits, commit_error = await _fetch_room_status(room_code)
    except BackendLookupError as err:
        logger.warning("Dashboard request failed for %s: %s", room_code, err)
        html = _simple_template_render(
            DASHBOARD_ERROR_TEMPLATE,
            room_code=room_code,
            message=str(err),
        )
        return HTMLResponse(html, status_code=err.status_code)
    
    participants = status_payload.get("participants", [])
    active_dev = status_payload.get("active_developer")
    
    # Generate participants HTML
    participants_html = ""
    if participants:
        for idx, p in enumerate(participants, start=1):
            dev_id = p.get("developer_id", "")
            subdomain = p.get("subdomain_url", "")
            is_connected = p.get("connected", True)
            is_active = dev_id == active_dev
            
            # Determine status: ACTIVE (green), CONNECTED (grey), DISCONNECTED (red)
            if is_active:
                row_class = ' class="active-row"'
                status_class = "status-active"
                status_text = "ACTIVE"
            elif is_connected:
                row_class = ''
                status_class = "status-connected"
                status_text = "CONNECTED"
            else:
                row_class = ''
                status_class = "status-disconnected"
                status_text = "DISCONNECTED"
            
            subdomain_link = f'<a href="{subdomain}" target="_blank" style="color: #0066cc; text-decoration: none;">{subdomain}</a>' if subdomain else "(no tunnel)"
            participants_html += f'''
                        <tr{row_class}>
                            <td>{idx}</td>
                            <td>{dev_id}</td>
                            <td>{subdomain_link}</td>
                            <td><span class="status-badge {status_class}">{status_text}</span></td>
                        </tr>'''
    else:
        participants_html = '<tr><td colspan="4" class="no-data">No participants yet</td></tr>'
    
    # Generate commits HTML
    commits_html = ""
    reversed_commits = list(reversed(commits))[:MAX_DASHBOARD_COMMITS]
    if reversed_commits:
        for idx, commit in enumerate(reversed_commits, start=1):
            commit_hash = commit.get("commit_hash", "")[:7]
            commit_msg = commit.get("commit_message", "")
            commit_dev = commit.get("developer_id", "")
            commit_branch = commit.get("branch", "")
            commit_time_raw = commit.get("timestamp", "")
            
            # Convert timestamp to human-readable format
            try:
                from datetime import datetime
                dt = datetime.fromtimestamp(float(commit_time_raw))
                commit_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                commit_time = commit_time_raw
            
            commits_html += f'''
                        <tr class="commit-row">
                            <td>{idx}</td>
                            <td class="commit-hash">{commit_hash}</td>
                            <td>{commit_msg}</td>
                            <td>{commit_dev}</td>
                            <td>{commit_branch}</td>
                            <td>{commit_time}</td>
                        </tr>'''
    else:
        commits_html = '<tr><td colspan="6" class="no-data">No commits yet</td></tr>'
    
    context = {
        "room_code": status_payload.get("room_code", room_code),
        "active_developer": active_dev or "None",
        "participants_html": participants_html,
        "commits_html": commits_html,
    }
    
    html = _simple_template_render(DASHBOARD_TEMPLATE, **context)
    
    # Add cache-control headers to ensure fresh data
    headers = {
        "cache-control": "no-cache, no-store, must-revalidate",
        "pragma": "no-cache",
        "expires": "0"
    }
    
    return HTMLResponse(html, headers=headers)


def create_app() -> Starlette:
    """Application factory for tests and CLI entry point."""
    
    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/internal/notify-commit", internal_notify_commit, methods=["POST"]),
        
        # Subdomain-based routes (e.g., mact-demo-e2e.m-act.live or mact-demo-e2e.localhost:9000)
        Route("/dashboard", dashboard, methods=["GET"]),  # Dashboard at /dashboard
        WebSocketRoute("/ws", websocket_mirror),  # WebSocket mirror
        WebSocketRoute("/ws/{path:path}", websocket_mirror),
        WebSocketRoute("/notifications", websocket_notifications),  # WebSocket notifications
        Route("/", mirror, methods=["GET"]),  # Root serves mirror
        Route("/{path:path}", mirror, methods=["GET"]),  # Paths serve mirror content
    ]
    
    middleware = [
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    ]
    
    return Starlette(debug=True, routes=routes, middleware=middleware)


app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    port = int(os.getenv("PROXY_PORT", "9000"))
    
    # Start FRP supervisor
    frps_manager = FrpsManager.from_env()
    frpc_configs_env = os.getenv("FRPC_CONFIGS", "")
    frpc_configs = [cfg.strip() for cfg in frpc_configs_env.split(",") if cfg.strip()]
    frpc_binary = os.getenv("FRPC_BIN")
    frpc_env = os.environ.copy()
    supervisor = FrpSupervisor(
        frps_manager=frps_manager,
        frpc_configs=frpc_configs,
        frpc_binary=frpc_binary,
        env=frpc_env,
    )
    
    autostart = os.getenv("FRP_AUTOSTART", "1").lower() not in {"0", "false", "no"}
    if autostart:
        supervisor.start(logger=logger)
    else:
        logger.info("FRP autostart disabled; proxy will run without managing frps/frpc")
    
    try:
        uvicorn.run(
            "proxy.app:app",
            host="0.0.0.0",
            port=port,
            log_level="info",
            reload=False,
        )
    finally:
        supervisor.stop()
