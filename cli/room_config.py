"""Room configuration management for MACT CLI.

Tracks active room memberships and tunnel configurations.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class RoomMembership:
    """Represents a developer's membership in a room."""
    
    room_code: str
    developer_id: str
    subdomain_url: str
    local_port: Optional[int] = None
    backend_url: str = "http://localhost:5000"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "RoomMembership":
        return cls(**data)


class RoomConfig:
    """Manages room membership configuration."""
    
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            home = Path.home()
            config_path = home / ".mact_rooms.json"
        self.config_path = config_path
        self._rooms: Dict[str, RoomMembership] = {}
        self.load()
    
    def load(self) -> None:
        """Load room configurations from disk."""
        if not self.config_path.exists():
            self._rooms = {}
            return
        
        try:
            with self.config_path.open("r") as fh:
                data = json.load(fh)
                self._rooms = {
                    room_code: RoomMembership.from_dict(room_data)
                    for room_code, room_data in data.items()
                }
        except Exception:
            self._rooms = {}
    
    def save(self) -> None:
        """Save room configurations to disk."""
        data = {
            room_code: room.to_dict()
            for room_code, room in self._rooms.items()
        }
        with self.config_path.open("w") as fh:
            json.dump(data, fh, indent=2)
    
    def add_room(self, room: RoomMembership) -> None:
        """Add or update a room membership."""
        self._rooms[room.room_code] = room
        self.save()
    
    def remove_room(self, room_code: str) -> bool:
        """Remove a room membership."""
        if room_code in self._rooms:
            del self._rooms[room_code]
            self.save()
            return True
        return False
    
    def get_room(self, room_code: str) -> Optional[RoomMembership]:
        """Get room membership by room code."""
        return self._rooms.get(room_code)
    
    def list_rooms(self) -> List[RoomMembership]:
        """List all room memberships."""
        return list(self._rooms.values())
    
    def has_room(self, room_code: str) -> bool:
        """Check if developer is a member of a room."""
        return room_code in self._rooms
