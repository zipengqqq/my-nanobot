from __future__ import annotations

from pathlib import Path

from my_agent.agent.provider import ModelResponse, ProviderAdapter, ToolCall
from my_agent.agent.runner import AgentRunner
from my_agent.agent.subagent import SUBAGENT_SYSTEM_PROMPT, SubagentManager
from my_agent.sandbox import SandboxPolicy, SandboxRunner
from my_agent.tools.registry import ToolRegistry
from my_agent.tools.spawn_subagent_tool import SpawnSubagentTool


class _RecordingProvider(ProviderAdapter):
    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = iter(responses)
        self.requests: list[list[dict[str, object]]] = []

    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> ModelResponse:
        self.requests.append(messages)
        return next(self._responses)


class _RaisingProvider(ProviderAdapter):
    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> ModelResponse:
        raise ValueError("provider unavailable")


class _StubManager:
    def __init__(self, result: str) -> None:
        self._result = result
        self.tasks: list[str] = []

    def run(self, task: str) -> str:
        self.tasks.append(task)
        return self._result


def test_manager_runs_task_with_isolated_context_and_truncates_result(tmp_path: Path) -> None:
    provider = _RecordingProvider([ModelResponse(text="x" * 12)])
    manager = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        sandbox_runner=SandboxRunner(
            policy=SandboxPolicy.required(tmp_path),
            backends=[],
        ),
        max_iterations=2,
        max_result_chars=8,
    )

    assert manager.run("检查代码") == "xxxxxxxx..."
    assert provider.requests == [
        [
            {"role": "system", "content": SUBAGENT_SYSTEM_PROMPT},
            {"role": "user", "content": "检查代码"},
        ]
    ]


def test_manager_converts_runner_error_to_limited_tool_result(tmp_path: Path) -> None:
    manager = SubagentManager(
        provider=_RaisingProvider(),
        workspace=tmp_path,
        sandbox_runner=SandboxRunner(
            policy=SandboxPolicy.required(tmp_path),
            backends=[],
        ),
        max_iterations=2,
        max_result_chars=80,
    )

    result = manager.run("检查代码")

    assert result == "ERROR: 子 agent 执行失败。"


def test_spawn_tool_passes_task_to_manager() -> None:
    manager = _StubManager(result="子任务结论")
    tool = SpawnSubagentTool(manager)

    assert tool.run({"task": "分析测试失败"}) == "子任务结论"
    assert manager.tasks == ["分析测试失败"]
    assert tool.schema.name == "spawn_subagent"


def test_main_runner_uses_subagent_result_in_same_turn() -> None:
    provider = _RecordingProvider(
        [
            ModelResponse(
                tool_call=ToolCall(
                    id="call_1",
                    name="spawn_subagent",
                    arguments={"task": "列出风险"},
                )
            ),
            ModelResponse(text="已根据子任务结论完成回答。"),
        ]
    )
    registry = ToolRegistry()
    registry.register(SpawnSubagentTool(_StubManager(result="风险：缺少回归测试")))

    result = AgentRunner(provider=provider, tool_registry=registry).run([])

    assert result.final_text == "已根据子任务结论完成回答。"
    assert provider.requests[1][-1]["content"] == "风险：缺少回归测试"
