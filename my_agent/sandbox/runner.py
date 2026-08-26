from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from my_agent.sandbox.model import (
    SandboxPolicy,
    SandboxProcess,
    SandboxRequest,
    SandboxUnavailableError,
)


class SandboxBackend(Protocol):
    """平台沙箱后端的最小接口。"""

    def is_available(self) -> bool: ...

    def start(self, request: SandboxRequest, policy: SandboxPolicy) -> SandboxProcess: ...


@dataclass(slots=True)
class SandboxRunner:
    """所有模型触发型子进程的唯一启动入口。"""

    policy: SandboxPolicy
    backends: list[SandboxBackend]

    def start(self, argv: Sequence[str], *, cwd: Path) -> SandboxProcess:
        request = SandboxRequest(argv=tuple(argv), cwd=cwd).validated(self.policy)
        backend = next((item for item in self.backends if item.is_available()), None)
        if backend is None:
            raise SandboxUnavailableError("没有可用的沙箱后端；拒绝执行命令")
        return backend.start(request, self.policy)
