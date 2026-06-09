from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from my_agent.agent.provider import ModelResponse, ProviderAdapter
from my_agent.session.models import ChatMessage
from my_agent.tools.registry import ToolRegistry


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

    def run(self, messages: list[dict[str, Any]]) -> RunnerResult:
        tool_schemas = self.tool_registry.list_schemas()
        # 复制一份当前上下文，后续工具循环只在这份工作副本上持续追加消息。
        follow_up_messages = list(messages)
        new_messages: list[ChatMessage] = []

        for _ in range(self.max_iterations):
            response = self.provider.generate(list(follow_up_messages), tools=tool_schemas)
            if response.tool_call is None:
                final_text = self._require_text(response)
                new_messages.append(ChatMessage(role="assistant", content=final_text))
                return RunnerResult(final_text=final_text, new_messages=new_messages)

            assistant_message = self._build_tool_call_message(response)
            tool_result = self.tool_registry.execute(
                response.tool_call.name,
                response.tool_call.arguments,
            )
            tool_message = ChatMessage(
                role="tool",
                content=tool_result,
                tool_call_id=response.tool_call.id,
            )

            new_messages.extend([assistant_message, tool_message])
            follow_up_messages.append(assistant_message.to_model_message())
            follow_up_messages.append(tool_message.to_model_message())

        raise ValueError(
            f"Agent exceeded max_iterations={self.max_iterations} before producing a final response."
        )

    @staticmethod
    def _require_text(response: ModelResponse) -> str:
        if response.text is None:
            raise ValueError("模型没有返回最终文本回复")
        return response.text

    @staticmethod
    def _build_tool_call_message(response: ModelResponse) -> ChatMessage:
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
                        "arguments": json.dumps(
                            response.tool_call.arguments,
                            ensure_ascii=False,
                        ),
                    },
                }
            ],
        )
