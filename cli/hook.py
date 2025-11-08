"""Utilities for installing a Git post-commit hook that calls the backend /report-commit endpoint.

This is a minimal helper used by the CLI to install a script into .git/hooks/post-commit
that will POST to the coordination backend with commit info. The actual hook content
is intentionally small and can be improved later.
"""
from __future__ import annotations

import os
from pathlib import Path

HOOK_TEMPLATE = """#!/usr/bin/env bash
# MACT post-commit hook - this script posts commit details to the coordination backend
# Usage: This file is written into .git/hooks/post-commit
BACKEND_URL="__BACKEND_URL__"
DEVELOPER_ID="__DEVELOPER_ID__"
ROOM_CODE="__ROOM_CODE__"

COMMIT_HASH=$(git rev-parse --short HEAD || true)
BRANCH=$(git rev-parse --abbrev-ref HEAD || true)
MSG=$(git log -1 --pretty=%B | tr -d '"' | tr -d "'" | head -c 200)

if [ -z "$ROOM_CODE" ]; then
  echo "MACT: ROOM_CODE not set; skipping report-commit"
  exit 0
fi

curl -s -X POST "$BACKEND_URL/report-commit" \\
  -H "Content-Type: application/json" \\
  -d "{\\"room_code\\": \\"$ROOM_CODE\\", \\"developer_id\\": \\"$DEVELOPER_ID\\", \\"commit_hash\\": \\"$COMMIT_HASH\\", \\"branch\\": \\"$BRANCH\\", \\"commit_message\\": \\"$MSG\\"}" >/dev/null

echo "✓ Commit reported to MACT (Room: $ROOM_CODE)"
"""


def install_post_commit(git_dir: Path, developer_id: str, room_code: str, backend_url: str = "http://localhost:5000") -> None:
    hooks_dir = git_dir / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "post-commit"
    content = HOOK_TEMPLATE.replace("__BACKEND_URL__", backend_url)
    content = content.replace("__DEVELOPER_ID__", developer_id)
    content = content.replace("__ROOM_CODE__", room_code)
    with hook_path.open("w") as fh:
        fh.write(content)
    hook_path.chmod(0o755)
