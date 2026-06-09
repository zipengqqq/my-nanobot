from pathlib import Path
from types import SimpleNamespace

from my_agent.agent.provider import OpenAICompatProvider, ProviderAdapter
from my_agent.app import build_app


def test_openai_provider_explicitly_inherits_provider_adapter() -> None:
    assert issubclass(OpenAICompatProvider, ProviderAdapter)


def test_openai_provider_calls_chat_completions_and_returns_text() -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="真实模型回复"),
                    )
                ]
            )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
    )

    provider = OpenAICompatProvider(
        base_url="https://example.com/v1",
        api_key="test-key",
        model="gpt-4o-mini",
        client=fake_client,
    )

    reply = provider.generate(
        [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"},
        ]
    )

    assert reply == "真实模型回复"
    assert captured["model"] == "gpt-4o-mini"
    assert captured["messages"][1]["content"] == "你好"


def test_build_app_uses_openai_provider(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://example.com/v1",
                "OPENAI_API_KEY=test-key",
                "OPENAI_MODEL=gpt-4o-mini",
                "MY_AGENT_SESSION_ID=lesson",
                "MY_AGENT_HISTORY_LIMIT=12",
            ]
        ),
        encoding="utf-8",
    )

    app_state = build_app(env_file=env_file)

    assert isinstance(app_state.loop.runner.provider, OpenAICompatProvider)
