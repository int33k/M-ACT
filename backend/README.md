# MACT Coordination Backend - Unit 1

This is the Flask API for the Coordination Backend (Unit 1). It manages rooms and tracks active developers based on Git commits.

## Running the App

```bash
cd /home/int33k/Desktop/M-ACT
/home/int33k/Desktop/M-ACT/.venv/bin/python backend/app.py
```

The app will run on http://localhost:5000

## API Endpoints

### POST /rooms/create
Creates a new room.

**Request:**
```bash
curl -X POST http://localhost:5000/rooms/create \
  -H "Content-Type: application/json" \
  -d '{"project_name": "MyApp", "developer_id": "rahbar", "subdomain_url": "http://dev-rahbar.m-act.live"}'
```

**Response:**
```json
{"room_code": "myapp", "public_url": "http://myapp.m-act.live"}
```

### POST /rooms/join
Joins an existing room.

**Request:**
```bash
curl -X POST http://localhost:5000/rooms/join \
  -H "Content-Type: application/json" \
  -d '{"room_code": "myapp", "developer_id": "sanaullah", "subdomain_url": "http://dev-sanaullah.m-act.live"}'
```

**Response:**
```json
{"status": "success", "public_url": "http://myapp.m-act.live"}
```

### POST /report-commit
Reports a Git commit (simulates post-commit hook).

**Request:**
```bash
curl -X POST http://localhost:5000/report-commit \
  -H "Content-Type: application/json" \
  -d '{"room_code": "myapp", "developer_id": "rahbar", "commit_hash": "abc123", "branch": "main", "commit_message": "Add login"}'
```

**Response:**
```json
{"status": "success"}
```

### GET /get-active-url
Gets the active developer's tunnel URL.

**Active URL Logic:**
- **Always returns a URL** (never null if room has participants)
- No commits: Returns first developer who joined (by join order)
- With commits: Returns developer with latest commit
- If active developer leaves: Falls back to next participant

**Request:**
```bash
curl "http://localhost:5000/get-active-url?room=myapp"
```

**Response:**
```json
{"active_url": "http://dev-rahbar.m-act.live"}
```

### GET /rooms/status
Gets room status for the dashboard.

**Request:**
```bash
curl "http://localhost:5000/rooms/status?room=myapp"
```

**Response:**
```json
{"room_code": "myapp", "active_developer": "rahbar", "latest_commit": "abc123", "participants": ["rahbar", "sanaullah"]}
```

## Running Tests

```bash
cd /home/int33k/Desktop/M-ACT
pytest tests/test_app.py -v
```

All 13 backend tests pass, covering room creation, joining, leaving, commit tracking, active URL logic, and validation rules.

## New Endpoints (Unit 1 - Complete)

```

### POST /rooms/leave
Removes a developer from a room.

**Request:**
```bash
curl -X POST http://localhost:5000/rooms/leave \
  -H "Content-Type: application/json" \
  -d '{"room_code": "myapp", "developer_id": "rahbar"}'
```

**Response:**
```json
{"status": "success"}
```

### GET /rooms/<room_code>/commits
Gets commit history for a room.

**Request:**
```bash
curl "http://localhost:5000/rooms/myapp/commits"
```

**Response:**
```json
{
  "room_code": "myapp",
  "commits": [
    {
      "commit_hash": "abc123",
      "branch": "main",
      "commit_message": "Add login",
      "developer_id": "rahbar",
      "timestamp": 1729512345.67
    }
  ]
}
```

### GET /admin/rooms
Lists all rooms (admin endpoint).

**Request:**
```bash
curl "http://localhost:5000/admin/rooms"
```

**Response:**
```json
{
  "rooms": [
    {
      "room_code": "myapp",
      "participants": ["rahbar", "sanaullah"],
      "commit_count": 5
    }
  ]
}
```

### GET /health
Health check endpoint.

**Request:**
```bash
curl "http://localhost:5000/health"
```

**Response:**
```json
{"status": "healthy", "rooms_count": 2}
```

## Validation Rules

- **Duplicate room creation**: Returns 409 if room with same project name exists
- **Duplicate join**: Returns 409 if developer already in room
- **Commit without membership**: Returns 403 if developer not in room
- **CORS enabled**: Dashboard can make cross-origin API calls
- **Active URL always available**: Never returns null if room has participants (uses join order fallback)