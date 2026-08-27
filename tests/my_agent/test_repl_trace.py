from __future__ import annotations

from pathlib import Path

from rich.console import Console

from my_agent.agent.provider import ModelResponse, ToolCall
from my_agent.agent.runner import AgentRunner
from my_agent.app import ReplTraceRenderer


class _OneToolProvider:
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> ModelResponse:
        _ = messages
        _ = tools
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                tool_call=ToolCall(
                    id="fetch-weather",
                    name="web_fetch",
                    arguments={"url": "https://wttr.in/Beijing?format=3"},
                )
            )
        return ModelResponse(text="done")


class _LocalToolRegistry:
    def list_schemas(self) -> list[dict[str, object]]:
        return []

    def execute(self, name: str, arguments: dict[str, object]) -> str:
        assert name == "web_fetch"
        assert arguments == {"url": "https://wttr.in/Beijing?format=3"}
        return "weather result"


def test_agent_runner_notifies_before_calling_a_tool(tmp_path: Path) -> None:
    _ = tmp_path
    events: list[tuple[str, dict[str, object]]] = []
    runner = AgentRunner(
        provider=_OneToolProvider(),
        tool_registry=_LocalToolRegistry(),  # type: ignore[arg-type]
        on_tool_call=lambda name, arguments: events.append((name, arguments)),
    )

    runner.run([{"role": "user", "content": "weather"}])

    assert events == [
        ("web_fetch", {"url": "https://wttr.in/Beijing?format=3"}),
    ]


def test_repl_trace_indents_tool_after_reading_a_skill() -> None:
    console = Console(record=True, width=120, force_terminal=False)
    trace = ReplTraceRenderer(console)

    trace.start_turn()
    trace.on_tool_call("read_file", {"path": str(Path("skills/weather/SKILL.md"))})
    trace.on_tool_call("web_fetch", {"url": "https://wttr.in/Beijing?format=3"})

    assert console.export_text() == (
        "[技能] 读取 weather\n"
        "  [工具] 调用 web_fetch\n"
    )


def test_repl_trace_shows_only_tool_name() -> None:
    console = Console(record=True, width=120, force_terminal=False)
    trace = ReplTraceRenderer(console)

    trace.start_turn()
    trace.on_tool_call("exec", {"command": "git status --short", "cwd": "my_agent"})

    assert console.export_text() == "[工具] 调用 exec\n"
