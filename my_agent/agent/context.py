from __future__ import annotations

import base64
from typing import Any

from my_agent.agent.media import ImageAttachment
from my_agent.agent.skills import SkillsLoader
from my_agent.session.models import ChatMessage


class ContextBuilder:
    """为单轮请求组装面向模型的消息列表。"""

    def __init__(
        self,
        system_prompt: str = "你是一个命令行 agent 助手。",
        skills: SkillsLoader | None = None,
    ) -> None:
        self._system_prompt = system_prompt
        self._skills = skills

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    def build_system_prompt(self) -> str:
        if self._skills is None:
            return self._system_prompt
        skills_summary = self._skills.build_summary()
        if not skills_summary:
            return self._system_prompt
        return (
            f"{self._system_prompt}\n\n"
            "# Skills\n\n"
            "The following skills extend your capabilities. Before using a skill, "
            "read its SKILL.md with read_file and follow its instructions.\n\n"
            f"{skills_summary}"
        )

    def build_messages(
        self,
        history: list[ChatMessage],
        user_text: str,
        images: list[ImageAttachment] | None = None,
    ) -> list[dict[str, Any]]:
        messages = [{"role": "system", "content": self.build_system_prompt()}]
        messages.extend(message.to_model_message() for message in history)
        messages.append({"role": "user", "content": self._build_user_content(user_text, images)})
        return messages

    @staticmethod
    def _build_user_content(
        user_text: str,
        images: list[ImageAttachment] | None,
    ) -> str | list[dict[str, Any]]:
        if not images:
            return user_text

        image_blocks = [
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:{image.mime_type};base64,"
                        f"{base64.b64encode(image.data).decode('ascii')}"
                    )
                },
            }
            for image in images
        ]
        return [*image_blocks, {"type": "text", "text": user_text}]
