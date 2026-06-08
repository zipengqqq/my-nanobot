from __future__ import annotations

from dataclasses import dataclass, field

from my_agent.tools.base import Tool


@dataclass
class ToolRegistry:
    """负责注册工具，并向 runner 暴露工具集合。"""

    _tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self._tools[tool.schema.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_schemas(self) -> list[dict[str, str]]:
        return [
            {
                "name": tool.schema.name,
                "description": tool.schema.description,
            }
            for tool in self._tools.values()
        ]
