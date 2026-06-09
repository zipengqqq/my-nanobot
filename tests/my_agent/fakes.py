class StubProvider:
    """测试专用的占位 provider，不发起真实网络请求。"""

    def generate(self, messages: list[dict[str, str]]) -> str:
        _ = messages
        return "Phase 0 provider stub response"
