from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from my_agent.config import logger
from my_agent.tools.base import Tool
from my_agent.tools.filesystem_tool import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from my_agent.tools.patch_tool import ApplyPatchTool
from my_agent.tools.search_tool import FindFilesTool, GrepTool
from my_agent.tools.shell_tool import ExecTool


def _preview_text(text: str, limit: int = 160) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


@dataclass
class ToolRegistry:
    """负责注册工具，并向 runner 暴露工具集合。"""

    _tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self._tools[tool.schema.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """执行某个工具"""
        tool = self.get(name)
        if tool is None:
            logger.warning("工具执行失败 name=%s reason=not_registered", name)
            return f"ERROR: Tool '{name}' is not registered."

        try:
            result = tool.run(arguments)
            logger.info("工具执行完成 name=%s preview=%s", name, _preview_text(result))
            return result
        except Exception as exc:
            logger.warning("工具执行失败 name=%s error=%s", name, exc)
            return f"ERROR: Tool '{name}' failed: {exc}"

    def list_schemas(self) -> list[dict[str, Any]]:
        """返回可以发给模型看的工具定义列表"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.schema.name,
                    "description": tool.schema.description,
                    "parameters": tool.schema.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    @classmethod
    def with_defaults(cls, root: Path | None = None) -> "ToolRegistry":
        """
            之所以写成带引号的 "ToolRegistry"，是因为它在类体内部引用了“当前这个类自己”。
            这种写法叫前向引用，避免 Python 在解析这个函数签名时，类名还没完全定义好
        """
        registry = cls()
        tool_root = (root or Path.cwd()).resolve()
        registry.register(ReadFileTool(root=tool_root))
        registry.register(ListDirTool(root=tool_root))
        registry.register(ExecTool(root=tool_root))
        registry.register(WriteFileTool(root=tool_root))
        registry.register(EditFileTool(root=tool_root))
        registry.register(FindFilesTool(root=tool_root))
        registry.register(GrepTool(root=tool_root))
        registry.register(ApplyPatchTool(root=tool_root))
        return registry
