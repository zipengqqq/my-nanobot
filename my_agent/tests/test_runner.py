from __future__ import annotations

from typing import Any

from my_agent.agent.provider import ModelResponse, ProviderAdapter, ToolCall
from my_agent.agent.runner import AgentRunner
from my_agent.tools.base import ToolSchema
from my_agent.tools.registry import ToolRegistry


class _ImageTool:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="generate_image",
            description="Generate an image.",
            parameters={"type": "object", "properties": {}},
        )

    def run(self, arguments: dict[str, Any]) -> str:
        self.calls.append(arguments)
        return (
            '{"artifacts": [{"path": '
            '"D:\\\\my-nanobot\\\\my_agent\\\\storage\\\\generated-images\\\\poster.png"}]}'
        )


class _SequenceProvider(ProviderAdapter):
    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = iter(responses)

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        return next(self._responses)


def test_runner_appends_absolute_image_path_when_model_uses_relative_path() -> None:
    image_path = r"D:\my-nanobot\my_agent\storage\generated-images\poster.png"
    registry = ToolRegistry()
    registry.register(_ImageTool())
    provider = _SequenceProvider(
        [
            ModelResponse(
                tool_call=ToolCall(
                    id="call_1",
                    name="generate_image",
                    arguments={"prompt": "poster"},
                )
            ),
            ModelResponse(text="已生成海报。\n\n图片文件：storage/generated-images/poster.png"),
        ]
    )

    result = AgentRunner(provider=provider, tool_registry=registry).run([])

    assert image_path in result.final_text


def test_runner_merges_pasted_and_existing_reference_images() -> None:
    pasted_image = r"D:\my-nanobot\my_agent\storage\reference-images\source.png"
    generated_image = r"D:\my-nanobot\my_agent\storage\generated-images\previous.png"
    image_tool = _ImageTool()
    registry = ToolRegistry()
    registry.register(image_tool)
    provider = _SequenceProvider(
        [
            ModelResponse(
                tool_call=ToolCall(
                    id="call_1",
                    name="generate_image",
                    arguments={
                        "prompt": "make this a 2D illustration",
                        "reference_images": [generated_image],
                    },
                )
            ),
            ModelResponse(text="已生成。"),
        ]
    )

    AgentRunner(provider=provider, tool_registry=registry).run(
        [], reference_images=[pasted_image]
    )

    assert image_tool.calls == [
        {
            "prompt": "make this a 2D illustration",
            "reference_images": [pasted_image, generated_image],
        }
    ]
