from __future__ import annotations

from dataclasses import dataclass, field

from my_agent.session.models import ChatMessage


@dataclass
class SessionManager:
    """在 Phase 0 阶段以内存方式保存最近会话历史。"""

    history_limit: int = 20
    _sessions: dict[str, list[ChatMessage]] = field(default_factory=dict)

    def get_history(self, session_id: str) -> list[ChatMessage]:
        return list(self._sessions.get(session_id, []))

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        history = self._sessions.setdefault(session_id, [])
        history.append(message)
        if len(history) > self.history_limit:
            self._sessions[session_id] = history[-self.history_limit :]
