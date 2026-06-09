from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from my_agent.tools.base import ToolSchema


def _resolve_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


@dataclass(slots=True)
class ReadFileTool:
    root: Path

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="read_file",
            description="读取本地文本文件内容。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径，可以是绝对路径或相对路径。",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        path = _resolve_path(self.root, str(arguments["path"]))
        return path.read_text(encoding="utf-8")


@dataclass(slots=True)
class ListDirTool:
    root: Path

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="list_dir",
            description="列出目录下的文件和子目录。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要查看的目录路径，可以是绝对路径或相对路径。",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        path = _resolve_path(self.root, str(arguments["path"]))
        entries = []
        for entry in sorted(path.iterdir(), key=lambda item: item.name):
            suffix = "/" if entry.is_dir() else ""
            entries.append(f"{entry.name}{suffix}")
        return "\n".join(entries) if entries else "(empty directory)"
