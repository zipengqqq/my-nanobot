from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.provider import ModelResponse
from my_agent.agent.runner import AgentRunner
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, object]] | None = None,
    ) -> ModelResponse:
        _ = tools
        self.calls.append(messages)
        return ModelResponse(text=f"reply-{len(self.calls)}")


def test_system_prompt_is_rebuilt_each_turn_instead_of_persisted_in_session() -> None:
    provider = RecordingProvider()
    loop = AgentLoop(
        session_manager=SessionManager(history_limit=3),
        context_builder=ContextBuilder(system_prompt="系统提示-v1"),
        runner=AgentRunner(provider=provider, tool_registry=ToolRegistry()),
    )

    first_reply = loop.handle_user_message(session_id="lesson", user_text="第一问")

    # 模拟下一轮启动时 system prompt 发生变化；session 历史里不应残留旧 prompt。
    loop.context_builder = ContextBuilder(system_prompt="系统提示-v2")
    second_reply = loop.handle_user_message(session_id="lesson", user_text="第二问")

    assert first_reply == "reply-1"
    assert second_reply == "reply-2"
    assert provider.calls[0][0] == {"role": "system", "content": "系统提示-v1"}
    assert provider.calls[1] == [
        {"role": "system", "content": "系统提示-v2"},
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "reply-1"},
        {"role": "user", "content": "第二问"},
    ]
