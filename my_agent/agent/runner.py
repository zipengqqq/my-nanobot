from __future__ import annotations

from dataclasses import dataclass

from my_agent.agent.provider import ProviderAdapter
from my_agent.tools.registry import ToolRegistry


@dataclass(slots=True)
class AgentRunner:
    """执行当前这轮请求对应的一次 provider 调用。"""

    provider: ProviderAdapter
    tool_registry: ToolRegistry

    def run(self, messages: list[dict[str, str]]) -> str:
        _ = self.tool_registry
        return self.provider.generate(messages)
