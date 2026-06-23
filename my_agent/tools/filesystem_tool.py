from __future__ import annotations

import difflib
import os
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from my_agent.tools.base import ToolSchema

_IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
}
_FILE_STATE_STORES: dict[Path, "FileStateStore"] = {}


def _is_binary(raw: bytes) -> bool:
    if b"\x00" in raw:
        return True
    sample = raw[:4096]
    if not sample:
        return False
    non_text = sum(byte < 9 or 13 < byte < 32 for byte in sample)
    return (non_text / len(sample)) > 0.2


@dataclass(slots=True)
class FileStateEntry:
    mtime: float


@dataclass(slots=True)
class FileStateStore:
    _reads: dict[Path, FileStateEntry] = field(default_factory=dict)

    def record_read(self, path: Path) -> None:
        self._reads[path] = FileStateEntry(mtime=self._mtime(path))

    def record_write(self, path: Path) -> None:
        self._reads[path] = FileStateEntry(mtime=self._mtime(path))

    def check_read(self, path: Path) -> str | None:
        entry = self._reads.get(path)
        if entry is None:
            return (
                f"Warning: {path} has not been read in this session. "
                "Use read_file first to confirm the current content."
            )
        current = self._mtime(path)
        if current != entry.mtime:
            return (
                f"Warning: {path} was modified since it was last read. "
                "Use read_file again to confirm the latest content."
            )
        return None

    @staticmethod
    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0


@dataclass(slots=True)
class _FsTool:
    """文件系统工具共享基座：统一处理路径解析、workspace 边界和读写状态。"""

    root: Path
    file_states: FileStateStore | None = None

    def __post_init__(self) -> None:
        if self.file_states is None:
            key = self.root.resolve()
            store = _FILE_STATE_STORES.get(key)
            if store is None:
                store = FileStateStore()
                _FILE_STATE_STORES[key] = store
            self.file_states = store

    def _resolve(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path.resolve()
        resolved = (self.root / path).resolve()
        root_resolved = self.root.resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise PermissionError(f"Path escapes workspace: {raw_path}") from exc
        return resolved

    def _display_path(self, target: Path, root: Path) -> str:
        workspace = self.root.resolve()
        with suppress(ValueError):
            return target.relative_to(workspace).as_posix()
        return target.relative_to(root).as_posix()

    def _iter_files(self, root: Path):
        if root.is_file():
            yield root
            return

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)
            current = Path(dirpath)
            for filename in sorted(filenames):
                yield current / filename


@dataclass(slots=True)
class ReadFileTool(_FsTool):
    """读取单个 UTF-8 文本文件，并记录“已读”状态供后续编辑工具使用。"""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="read_file",
            description=(
                "Read a UTF-8 text file from the workspace. "
                "Use find_files/list_dir first when the path is uncertain."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to read",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        path = self._resolve(str(arguments["path"]))
        raw = path.read_bytes()
        if _is_binary(raw):
            raise ValueError(f"Cannot read binary file {arguments['path']}")
        text = raw.decode("utf-8")
        assert self.file_states is not None
        self.file_states.record_read(path)
        return text


@dataclass(slots=True)
class WriteFileTool(_FsTool):
    """整文件写入工具：创建文件或直接覆盖整个文件内容。"""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="write_file",
            description=(
                "Create a new file or intentionally replace an entire file with "
                "the provided content. For code changes or partial edits, prefer "
                "apply_patch; use edit_file only for small exact replacements."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        path = self._resolve(str(arguments["path"]))
        content = str(arguments["content"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        assert self.file_states is not None
        self.file_states.record_write(path)
        return f"Successfully wrote {len(content)} characters to {path}"


def _find_matches(content: str, old_text: str) -> list[int]:
    matches: list[int] = []
    start = 0
    while True:
        idx = content.find(old_text, start)
        if idx == -1:
            break
        matches.append(idx)
        start = idx + max(1, len(old_text))
    return matches


@dataclass(slots=True)
class EditFileTool(_FsTool):
    """单文件精确替换工具：用 old_text -> new_text 做小范围文本编辑。"""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="edit_file",
            description=(
                "Perform a small, exact replacement in one file by replacing "
                "old_text with new_text. Use this for narrow text substitutions "
                "with old_text copied from read_file. For multi-file or "
                "structural edits, prefer apply_patch."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file path to edit"},
                    "old_text": {"type": "string", "description": "The text to find and replace"},
                    "new_text": {"type": "string", "description": "The text to replace with"},
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        path = self._resolve(str(arguments["path"]))
        old_text = str(arguments["old_text"])
        new_text = str(arguments["new_text"])

        if not path.exists():
            if old_text == "":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(new_text, encoding="utf-8")
                assert self.file_states is not None
                self.file_states.record_write(path)
                return f"Successfully created {path}"
            return self._file_not_found_msg(str(arguments["path"]), path)

        assert self.file_states is not None
        warning = self.file_states.check_read(path)
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n")

        if old_text == "":
            if content.strip():
                raise ValueError(
                    f"Cannot create file — {arguments['path']} already exists and is not empty."
                )
            path.write_text(new_text, encoding="utf-8")
            self.file_states.record_write(path)
            result = f"Successfully edited {path}"
            return f"{warning}\n{result}" if warning else result

        matches = _find_matches(content, old_text.replace("\r\n", "\n"))
        if not matches:
            raise ValueError(self._not_found_msg(old_text, content, str(arguments["path"])))
        if len(matches) > 1:
            raise ValueError(
                f"old_text appears multiple times in {arguments['path']}. "
                "Provide more context or use apply_patch."
            )

        position = matches[0]
        updated = content[:position] + new_text.replace("\r\n", "\n") + content[position + len(old_text) :]
        path.write_text(updated, encoding="utf-8")
        self.file_states.record_write(path)

        result = f"Successfully edited {path}"
        return f"{warning}\n{result}" if warning else result

    def _file_not_found_msg(self, raw_path: str, path: Path) -> str:
        parent = path.parent
        suggestions: list[str] = []
        if parent.is_dir():
            siblings = [item.name for item in parent.iterdir() if item.is_file()]
            close = difflib.get_close_matches(path.name, siblings, n=3, cutoff=0.6)
            suggestions = [str(parent / name) for name in close]
        parts = [f"Error: File not found: {raw_path}"]
        if suggestions:
            parts.append("Did you mean: " + ", ".join(suggestions) + "?")
        return "\n".join(parts)

    @staticmethod
    def _not_found_msg(old_text: str, content: str, path: str) -> str:
        lines = content.splitlines(keepends=True)
        old_lines = old_text.splitlines(keepends=True)
        window = max(1, len(old_lines))
        best_ratio = -1.0
        best_start = 0
        best_window: list[str] = []
        for index in range(max(1, len(lines) - window + 1)):
            current = lines[index : index + window]
            ratio = difflib.SequenceMatcher(None, old_lines, current).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_start = index
                best_window = current
        if best_ratio > 0.5:
            diff = "\n".join(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    best_window,
                    fromfile="old_text (provided)",
                    tofile=f"{path} (actual, line {best_start + 1})",
                    lineterm="",
                )
            )
            return (
                f"Error: old_text not found in {path}.\n"
                f"Best match ({best_ratio:.0%} similar) at line {best_start + 1}:\n{diff}"
            )
        return f"Error: old_text not found in {path}. No similar text found."


@dataclass(slots=True)
class ListDirTool(_FsTool):
    """目录查看工具：列出目录下的直接子项，并忽略常见噪音目录。"""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="list_dir",
            description=(
                "List the contents of a directory. Common noise directories "
                "(.git, node_modules, __pycache__, etc.) are auto-ignored."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        path = self._resolve(str(arguments["path"]))
        if not path.exists():
            return f"Error: Directory not found: {arguments['path']}"
        if not path.is_dir():
            return f"Error: Not a directory: {arguments['path']}"

        entries = []
        for entry in sorted(path.iterdir(), key=lambda item: item.name):
            if entry.name in _IGNORE_DIRS:
                continue
            entries.append(entry.name)
        return "\n".join(entries) if entries else f"Directory {arguments['path']} is empty"
