from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ChatMessage:
    """表示 session 历史中的一条消息。"""

    # 消息角色，例如 user、assistant、tool。
    role: str
    # 这条消息的文本内容。
    content: str
    # tool 消息回指的那次工具调用 id；普通消息为空。
    tool_call_id: str | None = None
    # assistant 发起工具调用时附带的结构化 tool call 数据。
    tool_calls: list[dict[str, Any]] | None = None

    def to_model_message(self) -> dict[str, Any]:
        """把内部消息对象转换成可直接发给模型的 message dict。"""
        message: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            message["tool_calls"] = self.tool_calls
        return message
