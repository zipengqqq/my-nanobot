from __future__ import annotations

from my_agent.command.builtin import register_builtin_commands
from my_agent.command.router import CommandRouter
from my_agent.memory.dream import DreamResult


class _DreamService:
    def __init__(self) -> None:
        self.started = False

    def start(self, on_complete) -> DreamResult:
        self.started = True
        self.on_complete = on_complete
        return DreamResult(status="running", message="Dreaming...")


def test_dream_command_starts_service_and_returns_immediate_reply() -> None:
    service = _DreamService()
    router = CommandRouter()
    register_builtin_commands(router, service, lambda _result: None)

    result = router.dispatch("/dream")

    assert result.handled is True
    assert result.reply == "Dreaming..."
    assert service.started is True


def test_exit_command_is_handled_without_agent_reply() -> None:
    router = CommandRouter()
    register_builtin_commands(router, _DreamService(), lambda _result: None)

    result = router.dispatch("/exit")

    assert result.handled is True
    assert result.should_exit is True
    assert result.reply is None


def test_unrecognized_text_is_not_handled_as_command() -> None:
    router = CommandRouter()
    register_builtin_commands(router, _DreamService(), lambda _result: None)

    assert router.dispatch("请总结这段对话").handled is False
