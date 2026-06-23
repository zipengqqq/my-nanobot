import json
from pathlib import Path

from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.runner import AgentRunner
from my_agent.app import build_app
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry


class SingleToolCallProvider:
    def __init__(self, target_file: Path) -> None:
        self.target_file = target_file
        self.calls: list[tuple[list[dict[str, object]], list[dict[str, object]]]] = []

    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> object:
        self.calls.append((messages, tools or []))
        if len(self.calls) == 1:
            from my_agent.agent.provider import ModelResponse, ToolCall

            return ModelResponse(
                tool_call=ToolCall(
                    id="call-1",
                    name="read_file",
                    arguments={"path": str(self.target_file)},
                )
            )

        from my_agent.agent.provider import ModelResponse

        return ModelResponse(text="工具结果已读取完成")


def test_agent_runner_executes_single_tool_call_before_final_answer(tmp_path: Path) -> None:
    target_file = tmp_path / "note.txt"
    target_file.write_text("phase3 file content", encoding="utf-8")

    provider = SingleToolCallProvider(target_file=target_file)
    loop = AgentLoop(
        session_manager=SessionManager(history_limit=3),
        context_builder=ContextBuilder(system_prompt="你是测试助手"),
        runner=AgentRunner(provider=provider, tool_registry=ToolRegistry.with_defaults()),
    )

    reply = loop.handle_user_message(session_id="lesson", user_text="帮我读取文件")

    assert reply == "工具结果已读取完成"
    assert len(provider.calls) == 2
    assert provider.calls[0][1]

    second_call_messages = provider.calls[1][0]
    assert second_call_messages[-2]["role"] == "assistant"
    assert second_call_messages[-2]["tool_calls"][0]["function"]["name"] == "read_file"
    assert second_call_messages[-2]["tool_calls"][0]["function"]["arguments"] == json.dumps(
        {"path": str(target_file)},
        ensure_ascii=False,
    )
    assert second_call_messages[-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "phase3 file content",
    }


def test_tool_registry_returns_standard_error_for_unknown_tool() -> None:
    registry = ToolRegistry()

    result = registry.execute("missing_tool", {})

    assert result == "ERROR: Tool 'missing_tool' is not registered."


def test_build_app_registers_phase3_default_tools(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://example.com/v1",
                "OPENAI_API_KEY=test-key",
                "OPENAI_MODEL=gpt-4o-mini",
                "MY_AGENT_SESSION_ID=lesson",
                "MY_AGENT_HISTORY_LIMIT=12",
            ]
        ),
        encoding="utf-8",
    )

    app_state = build_app(env_file=env_file)
    tool_names = [
        schema["function"]["name"]
        for schema in app_state.loop.runner.tool_registry.list_schemas()
    ]

    assert tool_names == [
        "read_file",
        "list_dir",
        "exec",
        "write_file",
        "edit_file",
        "find_files",
        "grep",
        "apply_patch",
        "start_exec_session",
        "write_stdin",
        "list_exec_sessions",
    ]
