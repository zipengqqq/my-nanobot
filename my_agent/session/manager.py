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
        history = self._sessions.setdefault(session_id, [])
        history.append(message)
        max_messages = self._max_messages()
        if len(history) > max_messages:
            self._sessions[session_id] = history[-max_messages:]

    def _max_messages(self) -> int:
        return self.history_limit * 2
