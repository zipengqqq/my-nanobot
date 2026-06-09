from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ModelResponse:
    text: str | None = None
    tool_call: ToolCall | None = None


class ProviderAdapter(ABC):
    """Provider 抽象接口，方便后续替换具体模型实现。"""

    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        """根据当前消息列表返回文本回复或一次工具调用请求。"""


class OpenAICompatProvider(ProviderAdapter):
    """最小 OpenAI-compatible provider，支持一次工具调用请求解析。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._client = client or OpenAI(base_url=base_url, api_key=api_key)

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            request["tools"] = tools

        response = self._client.chat.completions.create(
            **request,
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            tool_call = tool_calls[0]
            return ModelResponse(
                tool_call=ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments),
                )
            )

        content = message.content
        if not content:
            raise ValueError("模型返回了空内容")
        return ModelResponse(text=content)
