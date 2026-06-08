from __future__ import annotations

from typing import Protocol


class ProviderAdapter(Protocol):
    """Provider 抽象接口，方便后续替换具体模型实现。"""

    def generate(self, messages: list[dict[str, str]]) -> str:
        """根据当前消息列表返回一条 assistant 回复。"""


class StubProvider:
    """Phase 0 阶段的占位 provider，不发起真实网络请求。"""

    def generate(self, messages: list[dict[str, str]]) -> str:
        _ = messages
        return "Phase 0 provider stub response"
