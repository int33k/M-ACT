"""FRPC tunnel management for MACT CLI.

This module handles starting, stopping, and managing frpc tunnel client processes
for developer rooms.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TunnelConfig:
    """Configuration for a single frpc tunnel."""
    
    room_code: str
    developer_id: str
    local_port: int
    remote_subdomain: str
    server_addr: str = "127.0.0.1"
    server_port: int = 7100


class FrpcManager:
    """Manages frpc tunnel client processes."""
    
    def __init__(self, frpc_binary: Optional[str] = None):
        self.frpc_binary = frpc_binary or self._find_frpc_binary()
        self._processes: dict[str, subprocess.Popen] = {}
        self._config_files: dict[str, Path] = {}
    
    def _find_frpc_binary(self) -> str:
        """Find frpc binary in vendored location or PATH."""
        import platform
        
        # Determine binary name based on OS
        binary_name = "frpc.exe" if platform.system() == "Windows" else "frpc"
        
        # Try vendored binary first
        vendored = Path(__file__).parent.parent / "third_party" / "frp" / binary_name
        if vendored.exists() and vendored.is_file():
            return str(vendored.absolute())
        
        # Try PATH
        frpc_path = shutil.which(binary_name)
        if frpc_path:
            return frpc_path
        
        raise RuntimeError(f"frpc binary not found. Please download frp from https://github.com/fatedier/frp/releases and place {binary_name} in your PATH.")
    
    def _generate_config(self, tunnel: TunnelConfig) -> str:
        """Generate frpc TOML configuration."""
        return f"""# MACT frpc config for room {tunnel.room_code}
serverAddr = "{tunnel.server_addr}"
serverPort = {tunnel.server_port}

[[proxies]]
name = "{tunnel.room_code}-{tunnel.developer_id}"
type = "http"
localIP = "127.0.0.1"
localPort = {tunnel.local_port}
subdomain = "{tunnel.remote_subdomain}"
"""
    
    def start_tunnel(self, tunnel: TunnelConfig) -> bool:
        """Start an frpc tunnel for the given configuration."""
        key = f"{tunnel.room_code}:{tunnel.developer_id}"
        
        # Check if already running
        if key in self._processes:
            proc = self._processes[key]
            if proc.poll() is None:
                return True  # Already running
        
        # Create temporary config file
        config_content = self._generate_config(tunnel)
        config_file = Path(tempfile.mkdtemp()) / f"frpc_{tunnel.room_code}.toml"
        config_file.write_text(config_content)
        self._config_files[key] = config_file
        
        # Start frpc
        try:
            proc = subprocess.Popen(
                [self.frpc_binary, "-c", str(config_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._processes[key] = proc
            return True
        except Exception as e:
            print(f"Failed to start frpc: {e}")
            return False
    
    def stop_tunnel(self, room_code: str, developer_id: str) -> bool:
        """Stop the frpc tunnel for the given room and developer."""
        key = f"{room_code}:{developer_id}"
        
        if key not in self._processes:
            return True  # Not running
        
        proc = self._processes[key]
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        
        # Clean up
        del self._processes[key]
        if key in self._config_files:
            try:
                self._config_files[key].parent.rmdir()
            except:
                pass
            del self._config_files[key]
        
        return True
    
    def is_running(self, room_code: str, developer_id: str) -> bool:
        """Check if a tunnel is currently running."""
        key = f"{room_code}:{developer_id}"
        if key not in self._processes:
            return False
        proc = self._processes[key]
        return proc.poll() is None
    
    def stop_all(self) -> None:
        """Stop all running tunnels."""
        for key in list(self._processes.keys()):
            room, dev = key.split(":")
            self.stop_tunnel(room, dev)
