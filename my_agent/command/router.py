from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandResult:
    handled: bool
    should_exit: bool = False
    reply: str | None = None


class CommandRouter:
    """仅处理完全匹配的 REPL 本地命令。"""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[], CommandResult]] = {}

    def exact(self, command: str, handler: Callable[[], CommandResult]) -> None:
        self._handlers[command.lower()] = handler

    def dispatch(self, text: str) -> CommandResult:
        handler = self._handlers.get(text.strip().lower())
        return handler() if handler is not None else CommandResult(handled=False)
