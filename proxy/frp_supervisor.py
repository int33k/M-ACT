"""Supervisor for orchestrating frps and any supporting frpc processes."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .frp_manager import FrpsLaunchResult, FrpsManager


@dataclass
class FrpcProcess:
    """Holds state for a managed frpc process."""

    config_path: str
    process: subprocess.Popen


class FrpSupervisor:
    """Coordinates the lifecycle of frps and optional frpc sidecars."""

    def __init__(
        self,
        frps_manager: FrpsManager,
        frpc_configs: Optional[Iterable[str]] = None,
        frpc_binary: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self._frps_manager = frps_manager
        self._frpc_configs: List[str] = list(frpc_configs or [])
        self._frpc_binary = frpc_binary or self._default_frpc_binary()
        self._env = env or os.environ.copy()
        self._frpc_processes: Dict[str, FrpcProcess] = {}
        self._frps_launch_result: Optional[FrpsLaunchResult] = None

    @staticmethod
    def _default_frpc_binary() -> str:
        local_path = os.path.join(os.path.dirname(__file__), "..", "third_party", "frp", "frpc")
        return os.path.abspath(local_path)

    def _frpc_available(self) -> bool:
        binary = self._frpc_binary
        if shutil.which(binary):
            return True
        return os.path.isfile(binary)

    def start(self, logger=None) -> None:
        """Start frps and any configured frpc processes."""

        self._frps_launch_result = self._frps_manager.start()
        if logger and self._frps_launch_result and not self._frps_launch_result.started:
            logger.warning("frps failed to start: %s", self._frps_launch_result.reason)

        if not self._frpc_configs:
            return

        if not self._frpc_available():
            if logger:
                logger.warning("frpc binary not found at %s; skipping frpc startup", self._frpc_binary)
            return

        for config_path in self._frpc_configs:
            self._start_frpc(config_path, logger=logger)

    def _start_frpc(self, config_path: str, logger=None) -> None:
        normalized = os.path.abspath(config_path)
        if not os.path.isfile(normalized):
            if logger:
                logger.warning("frpc config %s not found; skipping", normalized)
            return

        if normalized in self._frpc_processes:
            return

        cmd = [self._frpc_binary, "-c", normalized]
        try:
            process = subprocess.Popen(  # noqa: S603, S607 - controlled binary
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self._env,
            )
        except OSError as exc:
            if logger:
                logger.error("Failed to start frpc for %s: %s", normalized, exc)
            return

        self._frpc_processes[normalized] = FrpcProcess(config_path=normalized, process=process)

        if logger:
            logger.info("frpc started for %s (pid=%s)", normalized, process.pid)

    def stop(self) -> None:
        """Terminate all child processes and stop frps."""

        for proc_data in list(self._frpc_processes.values()):
            process = proc_data.process
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            self._frpc_processes.pop(proc_data.config_path, None)

        self._frps_manager.stop()

    @property
    def frpc_processes(self) -> Dict[str, FrpcProcess]:
        return self._frpc_processes

    @property
    def frps_launch_result(self) -> Optional[FrpsLaunchResult]:
        return self._frps_launch_result