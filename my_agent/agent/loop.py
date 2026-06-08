from __future__ import annotations

from dataclasses import dataclass

from my_agent.agent.context import ContextBuilder
from my_agent.agent.runner import AgentRunner
from my_agent.session.manager import SessionManager
from my_agent.session.models import ChatMessage


@dataclass(slots=True)
class AgentLoop:
    """编排单轮用户请求，串起 session、context 和 runner。"""

    session_manager: SessionManager
    context_builder: ContextBuilder
    runner: AgentRunner

    def handle_user_message(self, session_id: str, user_text: str) -> str:
        history = self.session_manager.get_history(session_id)
        messages = self.context_builder.build_messages(history=history, user_text=user_text)
        reply = self.runner.run(messages)

        self.session_manager.append_message(
            session_id,
            ChatMessage(role="user", content=user_text),
        )
        self.session_manager.append_message(
            session_id,
            ChatMessage(role="assistant", content=reply),
        )
        return reply
