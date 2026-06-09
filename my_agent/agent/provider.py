from __future__ import annotations

from typing import Any
from typing import Protocol

from openai import OpenAI


class ProviderAdapter(Protocol):
    """Provider 抽象接口，方便后续替换具体模型实现。"""

    def generate(self, messages: list[dict[str, str]]) -> str:
        """根据当前消息列表返回一条 assistant 回复。"""


class OpenAICompatProvider:
    """最小 OpenAI-compatible provider，只处理单轮文本回复。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._client = client or OpenAI(base_url=base_url, api_key=api_key)

    def generate(self, messages: list[dict[str, str]]) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("模型返回了空内容")
        return content
