from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from my_agent.tools.base import ToolSchema
from my_agent.tools.filesystem_tool import FileStateStore

_ABSOLUTE_WINDOWS_RE = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(slots=True)
class _PatchSummary:
    action: str
    path: str
    added: int = 0
    deleted: int = 0


class _PatchError(ValueError):
    pass


def _validate_relative_path(path: str) -> str:
    normalized = path.strip()
    if not normalized:
        raise _PatchError("patch path cannot be empty")
    if "\0" in normalized:
        raise _PatchError(f"patch path contains a null byte: {path!r}")
    if normalized.startswith(("~", "/", "\\")) or _ABSOLUTE_WINDOWS_RE.match(normalized):
        raise _PatchError(f"patch path must be relative: {path}")
    if any(part == ".." for part in re.split(r"[\\/]+", normalized)):
        raise _PatchError(f"patch path must not contain '..': {path}")
    return normalized


def _text_line_count(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def _line_diff_stats(before: str, after: str) -> tuple[int, int]:
    before_lines = before.replace("\r\n", "\n").splitlines()
    after_lines = after.replace("\r\n", "\n").splitlines()
    added = 0
    deleted = 0
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in {"replace", "delete"}:
            deleted += i2 - i1
        if tag in {"replace", "insert"}:
            added += j2 - j1
    return added, deleted


def _format_summary(summary: _PatchSummary) -> str:
    return f"- {summary.action} {summary.path} (+{summary.added}/-{summary.deleted})"


@dataclass(slots=True)
class ApplyPatchTool:
    """多文件结构化补丁工具：按 edits 批量新增或替换文件内容，并支持 dry_run。"""

    root: Path
    file_states: FileStateStore = field(default_factory=FileStateStore)

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="apply_patch",
            description=(
                "Default tool for code edits. Supports multi-file changes in a single call. "
                "Provide a list of structured edits with relative paths and use dry_run=true "
                "to validate without writing files. Use edit_file only for small exact replacements."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "edits": {
                        "type": "array",
                        "description": "List of edits to apply.",
                        "minItems": 1,
                        "maxItems": 20,
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "action": {"type": "string", "enum": ["replace", "add"]},
                                "old_text": {"type": "string"},
                                "new_text": {"type": "string"},
                            },
                            "required": ["path", "action"],
                            "additionalProperties": False,
                        },
                    },
                    "dry_run": {"type": "boolean"},
                },
                "required": ["edits"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        edits = arguments.get("edits")
        dry_run = bool(arguments.get("dry_run", False))
        try:
            if not edits:
                raise _PatchError("must provide edits")

            writes: dict[Path, str] = {}
            summaries: list[_PatchSummary] = []

            for edit in edits:
                if not isinstance(edit, dict):
                    raise _PatchError("each edit must be an object")
                raw_path = edit.get("path")
                if not isinstance(raw_path, str):
                    raise _PatchError("path required for edit")
                rel_path = _validate_relative_path(raw_path)
                action = edit.get("action")
                if not isinstance(action, str):
                    raise _PatchError(f"action required for edit: {rel_path}")
                source = self._resolve(rel_path)

                if action == "add":
                    new_text = edit.get("new_text")
                    if new_text is None:
                        raise _PatchError(f"new_text required for add: {rel_path}")
                    pending = writes.get(source)
                    if pending is not None:
                        content = pending
                        exists = True
                    elif source.exists():
                        content = source.read_text(encoding="utf-8")
                        exists = True
                    else:
                        content = ""
                        exists = False

                    if exists:
                        new_content = content.replace("\r\n", "\n") + str(new_text).replace("\r\n", "\n")
                        if new_content and not new_content.endswith("\n"):
                            new_content += "\n"
                        added, deleted = _line_diff_stats(content, new_content)
                        writes[source] = new_content
                        summaries.append(_PatchSummary(action="update", path=rel_path, added=added, deleted=deleted))
                    else:
                        new_content = str(new_text).replace("\r\n", "\n")
                        if new_content and not new_content.endswith("\n"):
                            new_content += "\n"
                        writes[source] = new_content
                        summaries.append(
                            _PatchSummary(
                                action="add",
                                path=rel_path,
                                added=_text_line_count(new_content),
                                deleted=0,
                            )
                        )
                elif action == "replace":
                    old_text = edit.get("old_text")
                    if not old_text:
                        raise _PatchError(f"old_text required for replace: {rel_path}")
                    new_text = edit.get("new_text")
                    if new_text is None:
                        raise _PatchError(f"new_text required for replace: {rel_path}")

                    pending = writes.get(source)
                    if pending is not None:
                        content = pending
                    elif source.exists():
                        content = source.read_text(encoding="utf-8")
                    else:
                        raise _PatchError(f"file to update does not exist: {rel_path}")

                    norm_content = content.replace("\r\n", "\n")
                    norm_old = str(old_text).replace("\r\n", "\n")
                    pos = norm_content.find(norm_old)
                    if pos < 0:
                        raise _PatchError(f"old_text not found in {rel_path}")
                    if norm_content.find(norm_old, pos + 1) >= 0:
                        raise _PatchError(f"old_text appears multiple times in {rel_path}")

                    new_content = (
                        norm_content[:pos]
                        + str(new_text).replace("\r\n", "\n")
                        + norm_content[pos + len(norm_old) :]
                    )
                    if new_content and not new_content.endswith("\n"):
                        new_content += "\n"
                    writes[source] = new_content
                    added, deleted = _line_diff_stats(content, new_content)
                    summaries.append(_PatchSummary(action="update", path=rel_path, added=added, deleted=deleted))
                else:
                    raise _PatchError(f"unknown action: {action}")

            if dry_run:
                return "Patch dry-run succeeded:\n" + "\n".join(_format_summary(summary) for summary in summaries)

            backups: dict[Path, bytes | None] = {
                path: path.read_bytes() if path.exists() else None for path in writes
            }
            try:
                for path, content in writes.items():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8", newline="")
            except Exception:
                for path, data in backups.items():
                    if data is None:
                        if path.exists():
                            path.unlink()
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                raise

            for path in writes:
                self.file_states.record_write(path)
            return "Patch applied:\n" + "\n".join(_format_summary(summary) for summary in summaries)
        except PermissionError as exc:
            return f"Error: {exc}"
        except _PatchError as exc:
            return f"Error applying patch: {exc}"
        except Exception as exc:
            return f"Error applying patch: {exc}"

    def _resolve(self, rel_path: str) -> Path:
        resolved = (self.root / rel_path).resolve()
        root_resolved = self.root.resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise PermissionError(f"Path escapes workspace: {rel_path}") from exc
        return resolved
