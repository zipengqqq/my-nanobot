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

    def to_dict(self) -> dict[str, Any]:
        """把消息转换成统一的 dict 表示，可用于落盘或传给模型。"""
        message: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            message["tool_calls"] = self.tool_calls
        return message

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ChatMessage":
        """从落盘后的 dict 恢复内部消息对象。"""
        return cls(
            role=payload["role"],
            content=payload["content"],
            tool_call_id=payload.get("tool_call_id"),
            tool_calls=payload.get("tool_calls"),
        )

    def to_model_message(self) -> dict[str, Any]:
        """把内部消息对象转换成可直接发给模型的 message dict。"""
        return self.to_dict()
