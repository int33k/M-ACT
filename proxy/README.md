# MACT Public Routing Proxy - Unit 2

This **Starlette/ASGI** application acts as the public-facing reverse proxy for MACT rooms. It queries the coordination backend to determine the active developer and relays their tunnel without issuing HTTP redirects.

**NEW in v2.0**: Full WebSocket/HTTP Upgrade support via ASGI architecture.

## Running the Proxy

```bash
BACKEND_BASE_URL=http://localhost:5000 PROXY_PORT=9000 python proxy/app.py
```

**Or with uvicorn directly:**
```bash
uvicorn proxy.app:app --host 0.0.0.0 --port 9000
```

- `BACKEND_BASE_URL` (optional): Base URL of the coordination backend. Defaults to `http://localhost:5000` for local development.
- `PROXY_PORT` (optional): Port to serve the proxy. Defaults to `9000`.
- `FRPS_BIN` (optional): Path to the `frps` binary. When provided, the proxy will launch and supervise the process.
- `FRPS_CONFIG` (optional): Path to the `frps` configuration file passed via `-c`.
	- The repository ships with `third_party/frp/frps`; set `FRPS_BIN=$(pwd)/third_party/frp/frps` to reuse it locally.
- `FRPC_CONFIGS` (optional): Comma-separated list of frpc config paths launched alongside the proxy via the supervisor. Override `FRPC_BIN` to point to an alternate binary.
- `FRPC_BIN` / `FRPC_CONFIG` can be used with `scripts/run_frp_local.sh` to spin up a demo tunnel exposing the backend health endpoint on `localhost:35100`.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/rooms/<room_code>/mirror` | GET | Mirrors the active developer's tunnel for the requested room |
| `/rooms/<room_code>/mirror/<path>` | GET | Mirrors nested paths scoped to the active developer |
| `/rooms/<room_code>/ws` | WebSocket | **NEW**: Forwards WebSocket connections to active developer tunnel |
| `/rooms/<room_code>/ws/<path>` | WebSocket | **NEW**: Forwards WebSocket connections with nested paths |
| `/rooms/<room_code>/dashboard` | GET | Renders a simple HTML dashboard summarizing room state |
| `/health` | GET | Health/diagnostic endpoint |

## Behavior Overview

- **HTTP Mirroring**: Looks up the active developer via `GET /get-active-url` on the backend.
- Streams upstream responses chunk-by-chunk (async/await), preserving content-types and supporting SSE/long-polling flows.
- **WebSocket Support**: Accepts WebSocket upgrade requests and forwards bidirectionally to the active developer's tunnel.
  - Automatically converts HTTP URLs to WebSocket URLs (http → ws, https → wss)
  - Handles text and binary WebSocket messages
  - Graceful disconnect handling
- **Use Cases**: Vite HMR, Next.js Fast Refresh, Socket.IO, native WebSocket apps
- Renders dashboard data by combining `GET /rooms/status` and `GET /rooms/<room_code>/commits`.
- Returns a `503` JSON response when no developers are currently active in a room.
- Propagates `404` when the backend reports an unknown room.
- Returns a `502` when either the backend or the active developer tunnel cannot be reached.

## Testing

```bash
pytest tests/test_proxy.py -v
```

The proxy test suite (7 tests) validates mirror success, inactive-room, backend failure, upstream failure, and dashboard rendering scenarios using Starlette's TestClient. Additional integration tests (`tests/test_integration_unit1_unit2.py`) spin up both backend and proxy to exercise the full request path.

For manual testing, run `./scripts/run_frp_local.sh` to start the bundled frps/frpc pair and access the backend health check through `localhost:35100`.

## Architecture Notes

- **Framework**: Migrated from Flask (WSGI) to Starlette (ASGI) to support WebSocket connections
- **HTTP Client**: Uses `httpx.AsyncClient` for async HTTP requests
- **WebSocket Library**: Uses `websockets` for upstream WebSocket connections
- **Server**: Runs on `uvicorn` ASGI server (replaces Flask's development server)
- **Backwards Compatible**: All existing HTTP endpoints maintain the same API contract
