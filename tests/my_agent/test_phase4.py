import json
from pathlib import Path

import pytest

from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.runner import AgentRunner
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry


class MultiToolLoopProvider:
    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir
        self.calls: list[list[dict[str, object]]] = []

    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> object:
        _ = tools
        self.calls.append(messages)

        from my_agent.agent.provider import ModelResponse, ToolCall

        if len(self.calls) == 1:
            return ModelResponse(
                tool_call=ToolCall(
                    id="call-1",
                    name="list_dir",
                    arguments={"path": str(self.working_dir)},
                )
            )
        if len(self.calls) == 2:
            return ModelResponse(
                tool_call=ToolCall(
                    id="call-2",
                    name="read_file",
                    arguments={"path": str(self.working_dir / "note.txt")},
                )
            )
        return ModelResponse(text="我已经先列目录，再读取文件了。")


class EndlessToolCallProvider:
    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> object:
        _ = messages
        _ = tools

        from my_agent.agent.provider import ModelResponse, ToolCall

        return ModelResponse(
            tool_call=ToolCall(
                id="looping-call",
                name="list_dir",
                arguments={"path": "."},
            )
        )


def test_agent_runner_supports_multiple_tool_calls_and_saves_turn_history(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("phase4 file content", encoding="utf-8")
    provider = MultiToolLoopProvider(working_dir=tmp_path)
    session_manager = SessionManager(history_limit=2)
    loop = AgentLoop(
        session_manager=session_manager,
        context_builder=ContextBuilder(system_prompt="你是测试助手"),
        runner=AgentRunner(
            provider=provider,
            tool_registry=ToolRegistry.with_defaults(),
            max_iterations=4,
        ),
    )

    reply = loop.handle_user_message(session_id="lesson", user_text="先看目录再读文件")

    assert reply == "我已经先列目录，再读取文件了。"
    assert len(provider.calls) == 3

    history = session_manager.get_history("lesson")
    assert [message.role for message in history] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    assert history[1].tool_calls is not None
    assert history[1].tool_calls[0]["function"]["name"] == "list_dir"
    assert history[2].tool_call_id == "call-1"
    assert "note.txt" in history[2].content
    assert history[3].tool_calls is not None
    assert history[3].tool_calls[0]["function"]["name"] == "read_file"
    assert history[4].tool_call_id == "call-2"
    assert history[4].content == "phase4 file content"
    assert history[5].content == "我已经先列目录，再读取文件了。"

    assert provider.calls[1][-2]["tool_calls"][0]["function"]["arguments"] == json.dumps(
        {"path": str(tmp_path)},
        ensure_ascii=False,
    )
    assert provider.calls[2][-1] == {
        "role": "tool",
        "tool_call_id": "call-2",
        "content": "phase4 file content",
    }


def test_agent_runner_stops_when_tool_loop_exceeds_max_iterations() -> None:
    loop = AgentLoop(
        session_manager=SessionManager(history_limit=2),
        context_builder=ContextBuilder(system_prompt="你是测试助手"),
        runner=AgentRunner(
            provider=EndlessToolCallProvider(),
            tool_registry=ToolRegistry.with_defaults(),
            max_iterations=2,
        ),
    )

    with pytest.raises(ValueError, match="max_iterations"):
        loop.handle_user_message(session_id="lesson", user_text="一直调工具")
