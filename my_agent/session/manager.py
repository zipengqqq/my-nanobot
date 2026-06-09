from __future__ import annotations

from dataclasses import dataclass, field

from my_agent.session.models import ChatMessage


@dataclass
class SessionManager:
    """以内存方式保存最近会话历史，并按最近 N 轮对话裁剪。"""

    history_limit: int = 20
    _sessions: dict[str, list[ChatMessage]] = field(default_factory=dict)

    def get_history(self, session_id: str) -> list[ChatMessage]:
        return list(self._sessions.get(session_id, []))

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        """向指定 session 追加单条消息。"""
        self.append_messages(session_id, [message])

    def append_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
        """向指定 session 追加多条消息，并在追加后按最近 N 轮裁剪。"""
        history = self._sessions.setdefault(session_id, [])
        history.extend(messages)
        self._sessions[session_id] = self._trim_to_recent_turns(history)

    def _trim_to_recent_turns(self, history: list[ChatMessage]) -> list[ChatMessage]:
        """按 user 消息切分对话轮次，只保留最近 history_limit 轮。"""
        user_indices = [index for index, message in enumerate(history) if message.role == "user"]
        if len(user_indices) <= self.history_limit:
            return list(history)

        start_index = user_indices[-self.history_limit]
        return history[start_index:]
