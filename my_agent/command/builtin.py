from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from my_agent.command.router import CommandResult, CommandRouter
from my_agent.memory.dream import DreamResult


class DreamStarter(Protocol):
    def start(self, on_complete: Callable[[DreamResult], None]) -> DreamResult: ...


def register_builtin_commands(
    router: CommandRouter,
    dream_service: DreamStarter,
    on_dream_complete: Callable[[DreamResult], None],
) -> None:
    def exit_command() -> CommandResult:
        return CommandResult(handled=True, should_exit=True)

    def dream_command() -> CommandResult:
        result = dream_service.start(on_dream_complete)
        return CommandResult(handled=True, reply=result.message)

    for command in ("quit", "exit", "/exit"):
        router.exact(command, exit_command)
    router.exact("/dream", dream_command)
