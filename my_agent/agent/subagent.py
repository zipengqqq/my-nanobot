from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from my_agent.agent.provider import ProviderAdapter
from my_agent.agent.runner import AgentRunner
from my_agent.sandbox import SandboxRunner
from my_agent.tools.registry import ToolRegistry

SUBAGENT_SYSTEM_PROMPT = (
    "你是被主 agent 委派的子 agent。只完成给定任务，并返回可供主 agent 使用的结论。"
)


@dataclass(slots=True)
class SubagentManager:
    provider: ProviderAdapter
    workspace: Path
    sandbox_runner: SandboxRunner
    max_iterations: int
    max_result_chars: int
    extra_read_roots: Sequence[Path] = ()
    image_api_key: str | None = None
    image_model: str = "gpt-image-2"
    image_draw_url: str = "https://www.rightapi.ai/draw/v1/images/generations"
    image_task_url_template: str = "https://www.rightapi.ai/v1/tasks"
    image_timeout_seconds: float = 120.0
    image_max_images_per_turn: int = 1

    def run(self, task: str) -> str:
        tool_registry = ToolRegistry.with_defaults(
            root=self.workspace,
            sandbox_runner=self.sandbox_runner,
            extra_read_roots=self.extra_read_roots,
            image_api_key=self.image_api_key,
            image_model=self.image_model,
            image_draw_url=self.image_draw_url,
            image_task_url_template=self.image_task_url_template,
            image_timeout_seconds=self.image_timeout_seconds,
            image_max_images_per_turn=self.image_max_images_per_turn,
        )
        try:
            result = AgentRunner(
                provider=self.provider,
                tool_registry=tool_registry,
                max_iterations=self.max_iterations,
            ).run(
                [
                    {"role": "system", "content": SUBAGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": task},
                ]
            )
        except Exception:
            return "ERROR: 子 agent 执行失败。"
        return self._limit(result.final_text)

    def _limit(self, text: str) -> str:
        if len(text) <= self.max_result_chars:
            return text
        return text[: self.max_result_chars] + "..."
