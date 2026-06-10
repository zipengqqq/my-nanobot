from __future__ import annotations

from typing import Any

from my_agent.session.models import ChatMessage


class ContextBuilder:
    """为单轮请求组装面向模型的消息列表。"""

    def __init__(self, system_prompt: str = "你是一个命令行 agent 助手。") -> None:
        self._system_prompt = system_prompt

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    def build_messages(
        self,
        history: list[ChatMessage],
        user_text: str,
    ) -> list[dict[str, Any]]:
        messages = [{"role": "system", "content": self._system_prompt}]
        messages.extend(message.to_model_message() for message in history)
        messages.append({"role": "user", "content": user_text})
        return messages
