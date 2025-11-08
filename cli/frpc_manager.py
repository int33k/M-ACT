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
        """Find frpc binary in vendored location, PATH, or auto-download."""
        import platform
        import urllib.request
        import zipfile
        import tarfile
        
        system = platform.system()
        binary_name = "frpc.exe" if system == "Windows" else "frpc"
        
        # Try vendored binary first
        vendored = Path(__file__).parent.parent / "third_party" / "frp" / binary_name
        if vendored.exists() and vendored.is_file():
            return str(vendored.absolute())
        
        # Try PATH
        frpc_path = shutil.which(binary_name)
        if frpc_path:
            return frpc_path
        
        # Try user's local cache
        cache_dir = Path.home() / ".mact" / "bin"
        cached_binary = cache_dir / binary_name
        if cached_binary.exists() and cached_binary.is_file():
            return str(cached_binary.absolute())
        
        # Auto-download frpc
        print(f"📦 frpc not found. Downloading from GitHub...")
        try:
            return self._download_frpc(cache_dir, system, binary_name)
        except Exception as e:
            raise RuntimeError(f"Failed to download frpc: {e}. Please download manually from https://github.com/fatedier/frp/releases and place {binary_name} in your PATH.")
    
    def _download_frpc(self, cache_dir: Path, system: str, binary_name: str) -> str:
        """Download frpc binary from GitHub releases."""
        import urllib.request
        import zipfile
        import tarfile
        
        # Determine architecture and download URL
        FRP_VERSION = "0.52.0"
        machine = os.uname().machine.lower() if hasattr(os, 'uname') else 'amd64'
        
        if system == "Windows":
            arch = "amd64" if "64" in machine else "386"
            filename = f"frp_{FRP_VERSION}_windows_{arch}.zip"
            url = f"https://github.com/fatedier/frp/releases/download/v{FRP_VERSION}/{filename}"
        elif system == "Linux":
            arch = "amd64" if "x86_64" in machine or "amd64" in machine else "arm64" if "arm64" in machine or "aarch64" in machine else "386"
            filename = f"frp_{FRP_VERSION}_linux_{arch}.tar.gz"
            url = f"https://github.com/fatedier/frp/releases/download/v{FRP_VERSION}/{filename}"
        elif system == "Darwin":  # macOS
            arch = "arm64" if "arm" in machine else "amd64"
            filename = f"frp_{FRP_VERSION}_darwin_{arch}.tar.gz"
            url = f"https://github.com/fatedier/frp/releases/download/v{FRP_VERSION}/{filename}"
        else:
            raise RuntimeError(f"Unsupported OS: {system}")
        
        # Download
        cache_dir.mkdir(parents=True, exist_ok=True)
        archive_path = cache_dir / filename
        
        print(f"   Downloading {filename}...")
        urllib.request.urlretrieve(url, archive_path)
        
        # Extract
        print(f"   Extracting...")
        if filename.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(cache_dir)
        else:
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                tar_ref.extractall(cache_dir)
        
        # Find and move binary
        extracted_dir = cache_dir / filename.replace('.zip', '').replace('.tar.gz', '')
        source_binary = extracted_dir / binary_name
        target_binary = cache_dir / binary_name
        
        if source_binary.exists():
            shutil.move(str(source_binary), str(target_binary))
            target_binary.chmod(0o755)
        
        # Cleanup
        archive_path.unlink()
        shutil.rmtree(extracted_dir, ignore_errors=True)
        
        print(f"✓ frpc installed to {target_binary}")
        return str(target_binary.absolute())
    
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
