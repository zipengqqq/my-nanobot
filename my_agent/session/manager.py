from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from my_agent.session.models import ChatMessage


@dataclass
class SessionManager:
    """保存最近会话历史，并可按 session 文件持久化到本地。"""

    history_limit: int = 20
    storage_dir: Path | str | None = None
    _sessions: dict[str, list[ChatMessage]] = field(default_factory=dict)
    _loaded_sessions: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.storage_dir is None:
            return
        self.storage_dir = Path(self.storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def get_history(self, session_id: str) -> list[ChatMessage]:
        self._ensure_loaded(session_id)
        return list(self._sessions.get(session_id, []))

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        """向指定 session 追加单条消息。"""
        self.append_messages(session_id, [message])

    def append_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
        """向指定 session 追加多条消息，并在追加后按最近 N 轮裁剪。"""
        self._ensure_loaded(session_id)
        history = [*self._sessions.get(session_id, []), *messages]
        self._sessions[session_id] = self._trim_to_recent_turns(history)
        self._persist_session(session_id)

    def _trim_to_recent_turns(self, history: list[ChatMessage]) -> list[ChatMessage]:
        """按 user 消息切分对话轮次，只保留最近 history_limit 轮。"""
        user_indices = [index for index, message in enumerate(history) if message.role == "user"]
        if len(user_indices) <= self.history_limit:
            return list(history)

        start_index = user_indices[-self.history_limit]
        return history[start_index:]

    def _ensure_loaded(self, session_id: str) -> None:
        """在首次访问某个 session 时，从磁盘懒加载到内存缓存。"""
        if session_id in self._loaded_sessions:
            return
        self._loaded_sessions.add(session_id)

        if self.storage_dir is None:
            return

        session_file = self._session_file(session_id)
        if not session_file.exists():
            return

        payload = json.loads(session_file.read_text(encoding="utf-8"))
        self._sessions[session_id] = [
            ChatMessage.from_dict(message_payload)
            for message_payload in payload
        ]

    def _persist_session(self, session_id: str) -> None:
        """把指定 session 的当前内存历史原子写回本地文件。"""
        if self.storage_dir is None:
            return

        session_file = self._session_file(session_id)
        tmp_file = session_file.with_name(f"{session_file.name}.tmp")
        payload = [
            message.to_dict()
            for message in self._sessions.get(session_id, [])
        ]
        tmp_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_file.replace(session_file)

    def _session_file(self, session_id: str) -> Path:
        assert self.storage_dir is not None
        safe_session_id = quote(session_id, safe="")
        return self.storage_dir / f"{safe_session_id}.json"
