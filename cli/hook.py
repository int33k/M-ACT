"""Utilities for installing a Git post-commit hook that calls the backend /report-commit endpoint.

This is a minimal helper used by the CLI to install a script into .git/hooks/post-commit
that will POST to the coordination backend with commit info. The actual hook content
is intentionally small and can be improved later.
"""
from __future__ import annotations

import os
from pathlib import Path

# Python-based hook that works cross-platform (Windows, Linux, Mac)
HOOK_TEMPLATE = """#!/usr/bin/env python3
# MACT post-commit hook - reports commit details to coordination backend
import subprocess
import json
try:
    import requests
except ImportError:
    print("MACT: requests module not found, skipping commit report")
    exit(0)

BACKEND_URL = "__BACKEND_URL__"
DEVELOPER_ID = "__DEVELOPER_ID__"
ROOM_CODE = "__ROOM_CODE__"

try:
    commit_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], text=True).strip()
    branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], text=True).strip()
    msg = subprocess.check_output(['git', 'log', '-1', '--pretty=%B'], text=True).strip()[:200]
    
    payload = {
        "room_code": ROOM_CODE,
        "developer_id": DEVELOPER_ID,
        "commit_hash": commit_hash,
        "branch": branch,
        "commit_message": msg
    }
    
    response = requests.post(f"{BACKEND_URL}/report-commit", json=payload, timeout=5)
    if response.status_code == 200:
        print(f"Commit reported to MACT (Room: {ROOM_CODE})")
    else:
        print(f"MACT: Failed to report commit: {response.status_code}")
except Exception as e:
    print(f"MACT: Error reporting commit: {e}")
"""


def install_post_commit(git_dir: Path, developer_id: str, room_code: str, backend_url: str = "http://localhost:5000") -> None:
    """Install a cross-platform post-commit hook (Python-based, works on Windows/Linux/Mac)."""
    hooks_dir = git_dir / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "post-commit"
    content = HOOK_TEMPLATE.replace("__BACKEND_URL__", backend_url)
    content = content.replace("__DEVELOPER_ID__", developer_id)
    content = content.replace("__ROOM_CODE__", room_code)
    
    # Use UTF-8 encoding to avoid Windows charmap errors
    with hook_path.open("w", encoding="utf-8") as fh:
        fh.write(content)
    
    # Make executable (works on Unix, no-op on Windows)
    try:
        hook_path.chmod(0o755)
    except (OSError, NotImplementedError):
        pass  # Windows doesn't support chmod
