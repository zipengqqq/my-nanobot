from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from my_agent.agent.provider import ModelResponse, ProviderAdapter
from my_agent.config import logger
from my_agent.session.models import ChatMessage
from my_agent.tools.registry import ToolRegistry


def _preview_text(text: str, limit: int = 160) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


@dataclass(slots=True)
class RunnerResult:
    """封装单轮 agent 执行后的最终回复和新增历史消息。"""

    # 本轮执行结束后，要返回给用户的最终文本。
    final_text: str
    # 本轮执行过程中新增的 assistant/tool 消息，供 AgentLoop 写回 session。
    new_messages: list[ChatMessage] = field(default_factory=list)


@dataclass(slots=True)
class AgentRunner:
    """执行当前这轮请求对应的一次 provider 调用。"""

    provider: ProviderAdapter
    tool_registry: ToolRegistry
    max_iterations: int = 6
    on_tool_call: Callable[[str, dict[str, Any]], None] | None = None

    def run(
        self,
        messages: list[dict[str, Any]],
        reference_images: list[str] | None = None,
    ) -> RunnerResult:
        tool_schemas = self.tool_registry.list_schemas()
        # 复制一份当前上下文，后续工具循环只在这份工作副本上持续追加消息。
        follow_up_messages = list(messages)
        new_messages: list[ChatMessage] = []
        generated_image_paths: list[str] = []

        for iteration in range(1, self.max_iterations + 1):
            logger.info(
                "Agent 第 %s/%s 轮 messages=%s tools=%s",
                iteration,
                self.max_iterations,
                len(follow_up_messages),
                [schema["function"]["name"] for schema in tool_schemas],
            )
            response = self.provider.generate(list(follow_up_messages), tools=tool_schemas)
            if response.tool_call is None:
                final_text = self._require_text(response)
                final_text = self._append_generated_image_paths(
                    final_text, generated_image_paths
                )
                logger.info(
                    "最终回复 iteration=%s preview=%s",
                    iteration,
                    _preview_text(final_text),
                )
                new_messages.append(ChatMessage(role="assistant", content=final_text))
                return RunnerResult(final_text=final_text, new_messages=new_messages)

            logger.info(
                "请求工具 iteration=%s name=%s args=%s",
                iteration,
                response.tool_call.name,
                _preview_text(
                    json.dumps(response.tool_call.arguments, ensure_ascii=False),
                    limit=200,
                ),
            )
            tool_arguments = self._with_reference_images(
                response.tool_call.name,
                response.tool_call.arguments,
                reference_images or [],
            )
            if self.on_tool_call is not None:
                self.on_tool_call(response.tool_call.name, tool_arguments)
            assistant_message = self._build_tool_call_message(response, tool_arguments)
            tool_result = self.tool_registry.execute(
                response.tool_call.name,
                tool_arguments,
            )
            if response.tool_call.name == "generate_image":
                generated_image_paths.extend(self._generated_image_paths(tool_result))
            tool_message = ChatMessage(
                role="tool",
                content=tool_result,
                tool_call_id=response.tool_call.id,
            )

            new_messages.extend([assistant_message, tool_message])
            follow_up_messages.append(assistant_message.to_model_message())
            follow_up_messages.append(tool_message.to_model_message())

        logger.warning("Agent 超出最大迭代次数 max_iterations=%s，仍未得到最终回复", self.max_iterations)
        raise ValueError(
            f"Agent exceeded max_iterations={self.max_iterations} before producing a final response."
        )

    @staticmethod
    def _require_text(response: ModelResponse) -> str:
        if response.text is None:
            raise ValueError("模型没有返回最终文本回复")
        return response.text

    @staticmethod
    def _generated_image_paths(tool_result: str) -> list[str]:
        """从工具结构化结果提取已保存图片，避免依赖模型自行复述路径。"""
        try:
            payload = json.loads(tool_result)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, dict) or not isinstance(payload.get("artifacts"), list):
            return []

        paths: list[str] = []
        for artifact in payload["artifacts"]:
            if isinstance(artifact, dict) and isinstance(artifact.get("path"), str):
                paths.append(artifact["path"])
        return paths

    @staticmethod
    def _append_generated_image_paths(final_text: str, paths: list[str]) -> str:
        missing_paths = list(dict.fromkeys(path for path in paths if path and path not in final_text))
        if not missing_paths:
            return final_text
        rendered_paths = "\n".join(f"图片文件（绝对路径）：`{path}`" for path in missing_paths)
        return f"{final_text.rstrip()}\n\n{rendered_paths}"

    @staticmethod
    def _with_reference_images(
        tool_name: str,
        arguments: dict[str, Any],
        reference_images: list[str],
    ) -> dict[str, Any]:
        if tool_name != "generate_image" or not reference_images:
            return arguments
        existing = arguments.get("reference_images", [])
        if not isinstance(existing, list) or not all(isinstance(path, str) for path in existing):
            return arguments
        paths = [path for path in [*reference_images, *existing] if path]
        return {**arguments, "reference_images": list(dict.fromkeys(paths))}

    @staticmethod
    def _build_tool_call_message(
        response: ModelResponse, arguments: dict[str, Any] | None = None
    ) -> ChatMessage:
        if response.tool_call is None:
            raise ValueError("构造工具调用消息时，response.tool_call 不能为空")
        return ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": response.tool_call.id,
                    "type": "function",
                    "function": {
                        "name": response.tool_call.name,
                        "arguments": json.dumps(arguments or response.tool_call.arguments, ensure_ascii=False),
                    },
                }
            ],
        )
