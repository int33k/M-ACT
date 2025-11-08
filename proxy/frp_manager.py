"""Utility for managing the frps (Fast Reverse Proxy server) process.

The public routing proxy optionally launches and supervises `frps` so that
clients using `frpc` can connect. For local development the binary and config
path are provided via environment variables and the manager gracefully no-ops
if configuration is incomplete.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class FrpsLaunchResult:
    """Represents the outcome of a launch attempt."""

    started: bool
    reason: Optional[str] = None


class FrpsManager:
    """Thin wrapper for starting and stopping an frps process."""

    def __init__(
        self,
        binary_path: Optional[str],
        config_path: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.binary_path = binary_path
        self.config_path = config_path
        self.env = env or os.environ.copy()
        self._process: Optional[subprocess.Popen] = None

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "FrpsManager":
        env = env or os.environ
        binary_path = env.get("FRPS_BIN") or env.get("FRPS_BINARY")
        if not binary_path:
            maybe_local = os.path.join(os.path.dirname(__file__), "..", "third_party", "frp", "frps")
            binary_path = os.path.abspath(maybe_local)
        config_path = env.get("FRPS_CONFIG")
        return cls(binary_path=binary_path, config_path=config_path, env=env.copy())

    def is_configured(self) -> bool:
        if not self.binary_path:
            return False
        if shutil.which(self.binary_path) is None and not os.path.isfile(self.binary_path):
            return False
        return True

    def start(self) -> FrpsLaunchResult:
        if self._process and self._process.poll() is None:
            return FrpsLaunchResult(started=True)

        if not self.is_configured():
            return FrpsLaunchResult(started=False, reason="frps binary not configured")

        cmd = [self.binary_path]
        if self.config_path:
            cmd.extend(["-c", self.config_path])

        try:
            self._process = subprocess.Popen(  # noqa: S603, S607 - user-provided binary
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self.env,
            )
        except OSError as exc:
            return FrpsLaunchResult(started=False, reason=str(exc))

        return FrpsLaunchResult(started=True)

    def stop(self) -> None:
        if not self._process:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._process = None

    def running(self) -> bool:
        return bool(self._process and self._process.poll() is None)


__all__ = ["FrpsManager", "FrpsLaunchResult"]
