from __future__ import annotations

from dataclasses import dataclass

from my_agent.agent.context import ContextBuilder
from my_agent.agent.runner import AgentRunner
from my_agent.config import logger
from my_agent.session.manager import SessionManager
from my_agent.session.models import ChatMessage


def _preview_text(text: str, limit: int = 120) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


@dataclass(slots=True)
class AgentLoop:
    """编排单轮用户请求，串起 session、context 和 runner。"""

    session_manager: SessionManager
    context_builder: ContextBuilder
    runner: AgentRunner

    def handle_user_message(self, session_id: str, user_text: str) -> str:
        history = self.session_manager.get_history(session_id)
        logger.info(
            "开始处理本轮 session=%s history_messages=%s user=%s",
            session_id,
            len(history),
            _preview_text(user_text),
        )
        messages = self.context_builder.build_messages(history=history, user_text=user_text)
        logger.info(
            "上下文已构建 session=%s history_messages=%s model_messages=%s system_prompt=%s",
            session_id,
            len(history),
            len(messages),
            _preview_text(self.context_builder.system_prompt),
        )
        result = self.runner.run(messages)

        self.session_manager.append_messages(
            session_id,
            [ChatMessage(role="user", content=user_text), *result.new_messages],
        )
        logger.info(
            "本轮处理完成 session=%s persisted_messages=%s final_reply=%s",
            session_id,
            1 + len(result.new_messages),
            _preview_text(result.final_text),
        )
        return result.final_text
