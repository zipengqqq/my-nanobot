from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ToolSchema:
    """提供给后续模型集成使用的最小工具 schema。"""

    name: str
    description: str


class Tool(Protocol):
    """为后续阶段保留的工具接口约定。"""

    @property
    def schema(self) -> ToolSchema:
        """返回暴露给模型侧的工具 schema。"""

    def run(self, arguments: dict[str, Any]) -> str:
        """使用已校验的参数执行工具。"""
