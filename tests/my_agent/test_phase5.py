from pathlib import Path

from my_agent.agent.provider import ModelResponse
from my_agent.app import build_app
from my_agent.session.manager import SessionManager
from my_agent.session.models import ChatMessage


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, object]] | None = None,
    ) -> ModelResponse:
        _ = tools
        self.calls.append(messages)
        return ModelResponse(text=f"reply-{len(self.calls)}")


def test_session_manager_persists_tool_loop_history_and_reloads_it(tmp_path: Path) -> None:
    storage_dir = tmp_path / "sessions"
    session_manager = SessionManager(history_limit=3, storage_dir=storage_dir)

    session_manager.append_messages(
        "lesson",
        [
            ChatMessage(role="user", content="帮我读取文件"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "/tmp/note.txt"}',
                        },
                    }
                ],
            ),
            ChatMessage(role="tool", content="phase5 file content", tool_call_id="call-1"),
            ChatMessage(role="assistant", content="文件已经读取完成"),
        ],
    )

    reloaded_session_manager = SessionManager(history_limit=3, storage_dir=storage_dir)
    history = reloaded_session_manager.get_history("lesson")

    assert [(message.role, message.content) for message in history] == [
        ("user", "帮我读取文件"),
        ("assistant", ""),
        ("tool", "phase5 file content"),
        ("assistant", "文件已经读取完成"),
    ]
    assert history[1].tool_calls is not None
    assert history[1].tool_calls[0]["function"]["name"] == "read_file"
    assert history[2].tool_call_id == "call-1"
    assert (storage_dir / "lesson.json").exists()


def test_build_app_restores_prior_session_history_after_restart(tmp_path: Path) -> None:
    storage_dir = tmp_path / "sessions"
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://example.com/v1",
                "OPENAI_API_KEY=test-key",
                "OPENAI_MODEL=gpt-4o-mini",
                "MY_AGENT_SESSION_ID=lesson",
                "MY_AGENT_HISTORY_LIMIT=12",
                f"MY_AGENT_SESSION_STORAGE_DIR={storage_dir}",
            ]
        ),
        encoding="utf-8",
    )

    first_app_state = build_app(env_file=env_file)
    first_provider = RecordingProvider()
    first_app_state.loop.runner.provider = first_provider

    first_reply = first_app_state.loop.handle_user_message(
        session_id=first_app_state.settings.session_id,
        user_text="第一问",
    )

    second_app_state = build_app(env_file=env_file)
    second_provider = RecordingProvider()
    second_app_state.loop.runner.provider = second_provider

    second_reply = second_app_state.loop.handle_user_message(
        session_id=second_app_state.settings.session_id,
        user_text="第二问",
    )

    assert first_reply == "reply-1"
    assert second_reply == "reply-1"
    assert second_provider.calls[0] == [
        {"role": "system", "content": "你是一个命令行 agent 助手。"},
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "reply-1"},
        {"role": "user", "content": "第二问"},
    ]
