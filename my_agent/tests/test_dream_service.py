from __future__ import annotations

from pathlib import Path

from my_agent.agent.provider import ModelResponse, ProviderAdapter, ToolCall
from my_agent.memory.dream import DreamService
from my_agent.memory.store import MemoryStore


class _SequenceProvider(ProviderAdapter):
    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = iter(responses)

    def generate(self, messages, tools=None) -> ModelResponse:
        return next(self._responses)


class _FailingProvider(ProviderAdapter):
    def generate(self, messages, tools=None) -> ModelResponse:
        raise RuntimeError("provider unavailable")


def test_dream_success_edits_memory_and_advances_cursor(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.append_turn("我偏好中文", "收到")
    provider = _SequenceProvider(
        [
            ModelResponse(
                tool_call=ToolCall(
                    id="read-memory",
                    name="read_file",
                    arguments={"path": "memory/MEMORY.md"},
                )
            ),
            ModelResponse(
                tool_call=ToolCall(
                    id="edit-memory",
                    name="edit_file",
                    arguments={
                        "path": "memory/MEMORY.md",
                        "old_text": (
                            "# Long-term Memory\n\n"
                            "此文件由 Dream 自动维护，用于保存跨会话仍然有效的重要信息。\n"
                        ),
                        "new_text": "# Long-term Memory\n\n用户偏好中文回答。\n",
                    },
                )
            ),
            ModelResponse(text="Dream completed."),
        ]
    )

    result = DreamService(store=store, provider=provider).run_once()

    assert result.status == "completed"
    assert store.get_last_dream_cursor() == 1
    assert "用户偏好中文回答。" in store.read_memory()


def test_dream_failure_preserves_cursor(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.append_turn("重要事实", "收到")

    result = DreamService(store=store, provider=_FailingProvider()).run_once()

    assert result.status == "failed"
    assert store.get_last_dream_cursor() == 0


def test_dream_tool_error_preserves_cursor(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.append_turn("重要事实", "收到")
    provider = _SequenceProvider(
        [
            ModelResponse(
                tool_call=ToolCall(
                    id="bad-edit",
                    name="edit_file",
                    arguments={
                        "path": "memory/MEMORY.md",
                        "old_text": "不存在的内容",
                        "new_text": "错误更新",
                    },
                )
            ),
            ModelResponse(text="Dream completed."),
        ]
    )

    result = DreamService(store=store, provider=provider).run_once()

    assert result.status == "failed"
    assert store.get_last_dream_cursor() == 0


def test_dream_reports_empty_when_no_archived_turn_exists(tmp_path: Path) -> None:
    result = DreamService(store=MemoryStore(tmp_path), provider=_FailingProvider()).run_once()

    assert result.status == "empty"


def test_dream_tools_are_limited_to_memory_file_tools(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    tools = store.build_dream_tools()

    assert {schema["function"]["name"] for schema in tools.list_schemas()} == {
        "apply_patch",
        "edit_file",
        "read_file",
    }
    assert tools.execute("read_file", {"path": "SOUL.md"}).startswith("#")
    assert tools.execute("read_file", {"path": "USER.md"}).startswith("#")
    assert tools.execute("read_file", {"path": "memory/history.jsonl"}).startswith("ERROR:")
    assert tools.execute(
        "edit_file",
        {"path": "other.txt", "old_text": "", "new_text": "blocked"},
    ).startswith("ERROR:")
