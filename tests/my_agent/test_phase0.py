from pathlib import Path

from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.provider import StubProvider
from my_agent.agent.runner import AgentRunner
from my_agent.app import build_app
from my_agent.config import Settings
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry


def test_phase0_modules_import() -> None:
    assert ContextBuilder is not None
    assert AgentLoop is not None
    assert StubProvider is not None
    assert AgentRunner is not None
    assert SessionManager is not None
    assert ToolRegistry is not None


def test_agent_loop_returns_stub_response_and_saves_history() -> None:
    session_manager = SessionManager()
    runner = AgentRunner(provider=StubProvider(), tool_registry=ToolRegistry())
    loop = AgentLoop(
        session_manager=session_manager,
        context_builder=ContextBuilder(),
        runner=runner,
    )

    reply = loop.handle_user_message(session_id="default", user_text="你好")

    assert reply == "Phase 0 provider stub response"
    history = session_manager.get_history("default")
    assert [message.role for message in history] == ["user", "assistant"]


def test_settings_load_from_env_file(tmp_path: Path) -> None:
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

    settings = Settings.from_env_file(env_file)

    assert settings.openai_base_url == "https://example.com/v1"
    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.session_id == "lesson"
    assert settings.history_limit == 12


def test_build_app_returns_loop_and_settings(tmp_path: Path) -> None:
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

    assert app_state.settings.session_id == "lesson"
    assert app_state.loop is not None
