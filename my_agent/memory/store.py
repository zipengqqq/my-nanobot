from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from my_agent.tools.filesystem_tool import EditFileTool, FileStateStore, ReadFileTool
from my_agent.tools.patch_tool import ApplyPatchTool
from my_agent.tools.registry import ToolRegistry

_DEFAULT_MEMORY = "# Long-term Memory\n\n"
_MAX_TURN_TEXT_CHARS = 4_000
_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)\b(openai_api_key|api[_-]?key|access[_-]?token|token|authorization)\b"
    r"\s*(?:=|:)\s*(?:bearer\s+)?[^\s,;]+|\bbearer\s+[^\s,;]+"
)


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    cursor: int
    timestamp: str
    content: str


class DreamToolRegistry(ToolRegistry):
    """记录 Dream 工具错误，避免模型忽略错误后仍被视为成功。"""

    def __init__(self) -> None:
        super().__init__()
        self.had_execution_error = False

    def execute(self, name: str, arguments: dict[str, object]) -> str:
        result = super().execute(name, arguments)
        if result.startswith(("ERROR:", "Error:", "Error applying patch:")):
            self.had_execution_error = True
        return result


class _DreamPathGuard:
    def __init__(self, *args, allowed_files: set[Path], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._allowed_files = {path.resolve() for path in allowed_files}

    def _ensure_allowed(self, path: Path) -> Path:
        if path.resolve() not in self._allowed_files:
            raise PermissionError(f"Dream cannot modify or read this path: {path}")
        return path


class _DreamReadFileTool(_DreamPathGuard, ReadFileTool):
    def _resolve(self, raw_path: str) -> Path:
        return self._ensure_allowed(super()._resolve(raw_path))


class _DreamEditFileTool(_DreamPathGuard, EditFileTool):
    def _resolve(self, raw_path: str) -> Path:
        return self._ensure_allowed(super()._resolve(raw_path))


class _DreamApplyPatchTool(_DreamPathGuard, ApplyPatchTool):
    def _resolve(self, rel_path: str) -> Path:
        return self._ensure_allowed(super()._resolve(rel_path))


class MemoryStore:
    """持久化 Dream 归档与长期记忆，不负责模型调用。"""

    def __init__(self, workspace: Path | str, template_path: Path | str | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.memory_dir = self.workspace / "memory"
        self.memory_dir.mkdir(exist_ok=True)
        self.soul_file = self.workspace / "SOUL.md"
        self.user_file = self.workspace / "USER.md"
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "history.jsonl"
        self._cursor_file = self.memory_dir / ".cursor"
        self._dream_cursor_file = self.memory_dir / ".dream_cursor"
        self._ensure_template(self.soul_file, "SOUL.md")
        self._ensure_template(self.user_file, "USER.md")
        if not self.memory_file.exists():
            self._atomic_write(self.memory_file, self._read_template(template_path, "MEMORY.md"))

    def read_memory(self) -> str:
        return self._read_file(self.memory_file)

    def read_soul(self) -> str:
        return self._read_file(self.soul_file)

    def read_user(self) -> str:
        return self._read_file(self.user_file)

    def append_turn(self, user_text: str, assistant_text: str) -> int:
        cursor = self._next_cursor()
        content = "\n".join(
            (
                f"USER: {self._sanitize(user_text)}",
                f"ASSISTANT: {self._sanitize(assistant_text)}",
            )
        )
        record = {
            "cursor": cursor,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "content": content,
        }
        with self.history_file.open("a", encoding="utf-8") as history_file:
            history_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._atomic_write(self._cursor_file, str(cursor))
        return cursor

    def get_unprocessed_entries(self, max_entries: int) -> tuple[list[MemoryEntry], int]:
        entries = [
            entry
            for entry in self._read_entries()
            if entry.cursor > self.get_last_dream_cursor()
        ][:max_entries]
        return entries, entries[-1].cursor if entries else self.get_last_dream_cursor()

    def get_last_dream_cursor(self) -> int:
        return self._read_cursor(self._dream_cursor_file)

    def set_last_dream_cursor(self, cursor: int) -> None:
        if cursor < 0:
            raise ValueError("Dream cursor must not be negative")
        self._atomic_write(self._dream_cursor_file, str(cursor))

    def build_dream_tools(self) -> DreamToolRegistry:
        """创建只可操作长期记忆目录的 Dream 工具集。"""
        file_states = FileStateStore()
        tools = DreamToolRegistry()
        allowed_files = {self.soul_file, self.user_file, self.memory_file}
        tools.register(
            _DreamReadFileTool(
                root=self.workspace,
                file_states=file_states,
                allowed_files=allowed_files,
            )
        )
        tools.register(
            _DreamEditFileTool(
                root=self.workspace,
                file_states=file_states,
                allowed_files=allowed_files,
            )
        )
        tools.register(
            _DreamApplyPatchTool(
                root=self.workspace,
                file_states=file_states,
                allowed_files=allowed_files,
            )
        )
        return tools

    def _next_cursor(self) -> int:
        return self._read_cursor(self._cursor_file) + 1

    def _read_entries(self) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        try:
            lines = self.history_file.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return entries
        except OSError:
            return entries

        for line in lines:
            try:
                payload = json.loads(line)
                cursor = payload["cursor"]
                timestamp = payload["timestamp"]
                content = payload["content"]
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
            if isinstance(cursor, int) and isinstance(timestamp, str) and isinstance(content, str):
                entries.append(MemoryEntry(cursor=cursor, timestamp=timestamp, content=content))
        return entries

    def _ensure_template(self, path: Path, template_name: str) -> None:
        if not path.exists():
            self._atomic_write(path, self._read_template(None, template_name))

    @staticmethod
    def _read_template(template_path: Path | str | None, template_name: str) -> str:
        if template_path is None:
            template_path = (
                Path(__file__).resolve().parent.parent / "templates" / "memory" / template_name
            )
        try:
            return Path(template_path).read_text(encoding="utf-8")
        except OSError:
            return _DEFAULT_MEMORY

    @staticmethod
    def _read_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    @staticmethod
    def _read_cursor(path: Path) -> int:
        try:
            value = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return 0
        return max(0, value)

    @staticmethod
    def _sanitize(text: str) -> str:
        clipped = text[:_MAX_TURN_TEXT_CHARS]
        return _SENSITIVE_VALUE_RE.sub("[REDACTED]", clipped)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_name(f"{path.name}.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
