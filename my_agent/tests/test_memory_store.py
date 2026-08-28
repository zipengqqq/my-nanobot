from __future__ import annotations

from pathlib import Path

from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.provider import ModelResponse, ProviderAdapter
from my_agent.agent.runner import AgentRunner
from my_agent.memory.store import MemoryStore
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry


class _TextProvider(ProviderAdapter):
    def generate(self, messages, tools=None) -> ModelResponse:
        return ModelResponse(text="已记录")


def test_store_creates_template_and_redacts_archived_turn(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)

    cursor = store.append_turn("OPENAI_API_KEY=secret-value", "已记录")
    entries, last_cursor = store.get_unprocessed_entries(max_entries=20)

    assert store.soul_file == tmp_path / "SOUL.md"
    assert store.user_file == tmp_path / "USER.md"
    assert store.memory_file == tmp_path / "memory" / "MEMORY.md"
    assert store.history_file == tmp_path / "memory" / "history.jsonl"
    assert store.soul_file.is_file()
    assert store.user_file.is_file()
    assert store.memory_file.is_file()
    assert cursor == 1
    assert last_cursor == 1
    assert len(entries) == 1
    assert "secret-value" not in entries[0].content
    assert "[REDACTED]" in entries[0].content


def test_store_returns_only_entries_after_dream_cursor(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.append_turn("第一条", "回复一")
    store.append_turn("第二条", "回复二")
    store.set_last_dream_cursor(1)

    entries, last_cursor = store.get_unprocessed_entries(max_entries=20)

    assert [entry.cursor for entry in entries] == [2]
    assert last_cursor == 2


def test_context_includes_soul_user_and_long_term_memory(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.soul_file.write_text("保持直接、准确的表达。", encoding="utf-8")
    store.user_file.write_text("用户偏好中文回答。", encoding="utf-8")
    store.memory_file.write_text("用户偏好中文回答。", encoding="utf-8")

    messages = ContextBuilder(memory_store=store).build_messages([], "你好")

    assert "## SOUL.md\n\n保持直接、准确的表达。" in messages[0]["content"]
    assert "## USER.md\n\n用户偏好中文回答。" in messages[0]["content"]
    assert "# Long-term Memory\n用户偏好中文回答。" in messages[0]["content"]


def test_successful_agent_turn_is_archived_for_dream(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    loop = AgentLoop(
        session_manager=SessionManager(storage_dir=tmp_path / "sessions"),
        context_builder=ContextBuilder(memory_store=store),
        runner=AgentRunner(provider=_TextProvider(), tool_registry=ToolRegistry()),
        memory_store=store,
    )

    assert loop.handle_user_message("session-1", "请记住我偏好简洁回复") == "已记录"
    entries, _ = store.get_unprocessed_entries(max_entries=20)

    assert len(entries) == 1
    assert "请记住我偏好简洁回复" in entries[0].content
    assert "已记录" in entries[0].content
