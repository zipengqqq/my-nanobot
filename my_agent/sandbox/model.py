from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, TextIO


class SandboxMode(StrEnum):
    """定义命令执行时是否必须通过沙箱的策略模式。"""

    REQUIRED = "required"
    DISABLED = "disabled"


class SandboxUnavailableError(RuntimeError):
    """表示当前环境没有可满足安全策略的沙箱后端。"""


class SandboxProcess(Protocol):
    """约束沙箱后端返回的进程对象，供同步和交互式命令工具统一使用。"""

    stdin: TextIO | None
    stdout: TextIO | None
    stderr: TextIO | None

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def communicate(self, timeout: float | None = None) -> tuple[str, str]: ...

    def terminate_tree(self) -> None: ...


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    """保存沙箱执行策略，包括运行模式和允许访问的工作区根目录。"""

    mode: SandboxMode
    workspace_root: Path

    @classmethod
    def required(cls, workspace_root: Path) -> SandboxPolicy:
        return cls(mode=SandboxMode.REQUIRED, workspace_root=workspace_root.resolve())


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    """封装待执行命令及其工作目录，并在启动前校验目录边界。"""

    argv: tuple[str, ...]
    cwd: Path

    def validated(self, policy: SandboxPolicy) -> SandboxRequest:
        resolved_cwd = self.cwd.resolve()
        try:
            resolved_cwd.relative_to(policy.workspace_root)
        except ValueError as exc:
            raise PermissionError("工作目录位于工作区外") from exc
        return SandboxRequest(argv=self.argv, cwd=resolved_cwd)


class UnavailableBackend:
    """在没有可用沙箱时拒绝执行的失败关闭占位后端。"""

    def start(self, request: SandboxRequest, policy: SandboxPolicy) -> None:
        _ = request.validated(policy)
        raise SandboxUnavailableError("没有可用的沙箱后端；拒绝执行命令")
