from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from my_agent.config import logger
from my_agent.sandbox.model import SandboxPolicy, SandboxRequest, SandboxUnavailableError


@dataclass(slots=True)
class WslSandboxProcess:
    """承载 WSL 进程句柄，并保证终止时让 Bubblewrap 清理子进程。"""

    process: subprocess.Popen[str]

    @property
    def pid(self) -> int:
        return self.process.pid

    @property
    def stdin(self) -> TextIO | None:
        return self.process.stdin

    @property
    def stdout(self) -> TextIO | None:
        return self.process.stdout

    @property
    def stderr(self) -> TextIO | None:
        return self.process.stderr

    def poll(self) -> int | None:
        return self.process.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self.process.wait(timeout=timeout)

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        return self.process.communicate(timeout=timeout)

    def terminate_tree(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()


@dataclass(slots=True)
class WslBubblewrapBackend:
    """通过 WSL2 在 Linux Bubblewrap 中运行 Windows Agent 命令。"""

    distro: str
    user: str
    wsl_executable: str = "wsl.exe"
    path_converter: Callable[[Path], str] | None = None

    def is_available(self) -> bool:
        if os.name != "nt":
            return False
        try:
            result = subprocess.run(
                [
                    self.wsl_executable,
                    "--distribution",
                    self.distro,
                    "--user",
                    self.user,
                    "--exec",
                    "bwrap",
                    "--version",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def build_command(self, request: SandboxRequest, policy: SandboxPolicy) -> tuple[str, ...]:
        request = request.validated(policy)
        workspace = self._to_linux_path(request.cwd)
        return (
            self.wsl_executable,
            "--distribution",
            self.distro,
            "--user",
            self.user,
            "--exec",
            "bwrap",
            "--unshare-all",
            "--unshare-net",
            "--die-with-parent",
            "--new-session",
            "--tmpfs",
            "/",
            "--dir",
            "/usr",
            "--ro-bind",
            "/usr",
            "/usr",
            "--dir",
            "/lib",
            "--ro-bind",
            "/lib",
            "/lib",
            "--dir",
            "/lib64",
            "--ro-bind-try",
            "/lib64",
            "/lib64",
            "--dir",
            "/workspace",
            "--bind",
            workspace,
            "/workspace",
            "--chdir",
            "/workspace",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
            "--",
            *request.argv,
        )

    def start(self, request: SandboxRequest, policy: SandboxPolicy) -> WslSandboxProcess:
        command = self.build_command(request, policy)
        logger.info("沙箱 WSL Bubblewrap 执行：%s", subprocess.list2cmdline(command))
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise SandboxUnavailableError(f"无法启动 WSL Bubblewrap 沙箱：{exc}") from exc
        return WslSandboxProcess(process)

    def _to_linux_path(self, path: Path) -> str:
        if self.path_converter is not None:
            return self.path_converter(path)
        try:
            result = subprocess.run(
                [
                    self.wsl_executable,
                    "--distribution",
                    self.distro,
                    "--exec",
                    "wslpath",
                    "-u",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SandboxUnavailableError(f"无法转换 WSL 工作区路径：{exc}") from exc
        if result.returncode != 0 or not result.stdout.strip():
            detail = result.stderr.strip() or "wslpath 未返回路径"
            raise SandboxUnavailableError(f"无法转换 WSL 工作区路径：{detail}")
        return result.stdout.strip()
