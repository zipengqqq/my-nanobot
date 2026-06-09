from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from my_agent.agent.provider import ModelResponse, ProviderAdapter
from my_agent.tools.registry import ToolRegistry


@dataclass(slots=True)
class AgentRunner:
    """执行当前这轮请求对应的一次 provider 调用。"""

    provider: ProviderAdapter
    tool_registry: ToolRegistry

    def run(self, messages: list[dict[str, Any]]) -> str:
        tool_schemas = self.tool_registry.list_schemas()
        first_response = self.provider.generate(messages, tools=tool_schemas)
        if first_response.tool_call is None:
            return self._require_text(first_response)

        tool_result = self.tool_registry.execute(
            first_response.tool_call.name,
            first_response.tool_call.arguments,
        )
        follow_up_messages = list(messages)
        follow_up_messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": first_response.tool_call.id,
                        "type": "function",
                        "function": {
                            "name": first_response.tool_call.name,
                            "arguments": json.dumps(
                                first_response.tool_call.arguments,
                                ensure_ascii=False,
                            ),
                        },
                    }
                ],
            }
        )
        follow_up_messages.append(
            {
                "role": "tool",
                "tool_call_id": first_response.tool_call.id,
                "content": tool_result,
            }
        )
        second_response = self.provider.generate(follow_up_messages, tools=tool_schemas)
        if second_response.tool_call is not None:
            raise ValueError("Phase 3 只支持单次工具调用，暂不支持连续 tool loop。")
        return self._require_text(second_response)

    @staticmethod
    def _require_text(response: ModelResponse) -> str:
        if response.text is None:
            raise ValueError("模型没有返回最终文本回复")
        return response.text
