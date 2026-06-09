from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.runner import AgentRunner
from my_agent.session.manager import SessionManager
from my_agent.session.models import ChatMessage
from my_agent.tools.registry import ToolRegistry


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return f"reply-{len(self.calls)}"


def test_second_turn_includes_previous_turn_history() -> None:
    provider = RecordingProvider()
    loop = AgentLoop(
        session_manager=SessionManager(history_limit=3),
        context_builder=ContextBuilder(system_prompt="你是测试助手"),
        runner=AgentRunner(provider=provider, tool_registry=ToolRegistry()),
    )

    first_reply = loop.handle_user_message(session_id="lesson", user_text="第一问")
    second_reply = loop.handle_user_message(session_id="lesson", user_text="第二问")

    assert first_reply == "reply-1"
    assert second_reply == "reply-2"
    assert provider.calls[1] == [
        {"role": "system", "content": "你是测试助手"},
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "reply-1"},
        {"role": "user", "content": "第二问"},
    ]


def test_session_manager_keeps_recent_complete_turns() -> None:
    session_manager = SessionManager(history_limit=2)

    for turn in range(1, 4):
        session_manager.append_message(
            "lesson",
            ChatMessage(role="user", content=f"user-{turn}"),
        )
        session_manager.append_message(
            "lesson",
            ChatMessage(role="assistant", content=f"assistant-{turn}"),
        )

    history = session_manager.get_history("lesson")

    assert [(message.role, message.content) for message in history] == [
        ("user", "user-2"),
        ("assistant", "assistant-2"),
        ("user", "user-3"),
        ("assistant", "assistant-3"),
    ]
