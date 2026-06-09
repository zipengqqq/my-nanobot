from my_agent.agent.provider import ModelResponse


class StubProvider:
    """测试专用的占位 provider，不发起真实网络请求。"""

    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> ModelResponse:
        _ = messages
        _ = tools
        return ModelResponse(text="Phase 0 provider stub response")
