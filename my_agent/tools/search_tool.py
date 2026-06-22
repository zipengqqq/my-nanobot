from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from my_agent.tools.base import ToolSchema
from my_agent.tools.filesystem_tool import _FsTool


_DEFAULT_HEAD_LIMIT = 250
_DEFAULT_FILE_HEAD_LIMIT = 200
_TYPE_GLOB_MAP = {
    "py": ("*.py", "*.pyi"),
    "python": ("*.py", "*.pyi"),
    "js": ("*.js", "*.jsx", "*.mjs", "*.cjs"),
    "ts": ("*.ts", "*.tsx", "*.mts", "*.cts"),
    "tsx": ("*.tsx",),
    "jsx": ("*.jsx",),
    "json": ("*.json",),
    "md": ("*.md", "*.mdx"),
    "markdown": ("*.md", "*.mdx"),
    "go": ("*.go",),
    "rs": ("*.rs",),
    "rust": ("*.rs",),
    "java": ("*.java",),
    "sh": ("*.sh", "*.bash"),
    "yaml": ("*.yaml", "*.yml"),
    "yml": ("*.yaml", "*.yml"),
    "toml": ("*.toml",),
    "sql": ("*.sql",),
    "html": ("*.html", "*.htm"),
    "css": ("*.css", "*.scss", "*.sass"),
}


def _normalize_pattern(pattern: str) -> str:
    return pattern.strip().replace("\\", "/")


def _match_glob(rel_path: str, name: str, pattern: str) -> bool:
    normalized = _normalize_pattern(pattern)
    if not normalized:
        return False
    if "/" in normalized or normalized.startswith("**"):
        return PurePosixPath(rel_path).match(normalized)
    return fnmatch.fnmatch(name, normalized)


def _is_binary(raw: bytes) -> bool:
    if b"\x00" in raw:
        return True
    sample = raw[:4096]
    if not sample:
        return False
    non_text = sum(byte < 9 or 13 < byte < 32 for byte in sample)
    return (non_text / len(sample)) > 0.2


def _paginate(items: list[str], limit: int | None, offset: int) -> tuple[list[str], bool]:
    if limit is None:
        return items[offset:], False
    sliced = items[offset : offset + limit]
    truncated = len(items) > offset + limit
    return sliced, truncated


def _pagination_note(limit: int | None, offset: int, truncated: bool) -> str | None:
    if truncated:
        if limit is None:
            return f"(pagination: offset={offset})"
        return f"(pagination: limit={limit}, offset={offset})"
    if offset > 0:
        return f"(pagination: offset={offset})"
    return None


def _matches_type(name: str, file_type: str | None) -> bool:
    if not file_type:
        return True
    lowered = file_type.strip().lower()
    if not lowered:
        return True
    patterns = _TYPE_GLOB_MAP.get(lowered, (f"*.{lowered}",))
    return any(fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in patterns)


def _matches_query(rel_path: str, query: str | None) -> bool:
    if not query:
        return True
    haystack = rel_path.lower()
    terms = [part for part in query.lower().split() if part]
    return all(term in haystack for term in terms)


@dataclass(slots=True)
class FindFilesTool(_FsTool):
    """文件发现工具：按 query、glob、type 等条件查找文件或目录。"""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="find_files",
            description=(
                "Find files by path fragment, glob, or file type. Use this before "
                "read_file when you need to locate files, and prefer it over shell find/ls."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory or file to search in (default '.')"},
                    "query": {"type": "string", "description": "Optional case-insensitive path fragment search"},
                    "glob": {"type": "string", "description": "Optional file filter, e.g. '*.py'"},
                    "type": {"type": "string", "description": "Optional file type shorthand, e.g. 'py', 'ts'"},
                    "include_dirs": {"type": "boolean", "description": "Include matching directories as well as files"},
                    "sort": {"type": "string", "enum": ["path", "modified"]},
                    "head_limit": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "offset": {"type": "integer", "minimum": 0, "maximum": 100000},
                },
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        raw_path = str(arguments.get("path", "."))
        query = arguments.get("query")
        glob = arguments.get("glob")
        file_type = arguments.get("type")
        include_dirs = bool(arguments.get("include_dirs", False))
        sort = str(arguments.get("sort", "path"))
        head_limit = arguments.get("head_limit")
        offset = int(arguments.get("offset", 0))

        target = self._resolve(raw_path)
        if not target.exists():
            return f"Error: Path not found: {raw_path}"
        if not (target.is_dir() or target.is_file()):
            return f"Error: Unsupported path: {raw_path}"
        if sort not in {"path", "modified"}:
            return "Error: sort must be 'path' or 'modified'"

        limit = _DEFAULT_FILE_HEAD_LIMIT if head_limit is None else None if int(head_limit) == 0 else int(head_limit)
        root = target if target.is_dir() else target.parent
        matches: list[tuple[str, float]] = []

        candidates = self._iter_paths(target, include_dirs=include_dirs)
        for candidate in candidates:
            if candidate.is_dir() and not include_dirs:
                continue
            rel_path = candidate.relative_to(root).as_posix()
            display_path = self._display_path(candidate, root)
            if glob and not _match_glob(rel_path, candidate.name, str(glob)):
                continue
            if candidate.is_file() and not _matches_type(candidate.name, None if file_type is None else str(file_type)):
                continue
            if candidate.is_dir() and file_type:
                continue
            if not _matches_query(display_path, None if query is None else str(query)):
                continue
            try:
                mtime = candidate.stat().st_mtime
            except OSError:
                mtime = 0.0
            suffix = "/" if candidate.is_dir() else ""
            matches.append((display_path + suffix, mtime))

        if sort == "modified":
            matches.sort(key=lambda item: (-item[1], item[0]))
        else:
            matches.sort(key=lambda item: item[0])

        paths = [item[0] for item in matches]
        paged, truncated = _paginate(paths, limit, offset)
        if not paged:
            return "No files found"
        result = "\n".join(paged)
        note = _pagination_note(limit, offset, truncated)
        if note:
            result += "\n\n" + note
        return result

    def _iter_paths(self, root: Path, *, include_dirs: bool):
        if root.is_file():
            yield root
            return
        if include_dirs:
            yield root
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in self._ignore_dirs())
            current = Path(dirpath)
            if include_dirs and current != root:
                yield current
            for filename in sorted(filenames):
                yield current / filename

    @staticmethod
    def _ignore_dirs() -> set[str]:
        return {
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


@dataclass(slots=True)
class GrepTool(_FsTool):
    """内容搜索工具：在文件内容中按模式查找，并支持多种输出模式。"""

    _MAX_RESULT_CHARS = 128_000
    _MAX_FILE_BYTES = 2_000_000

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="grep",
            description=(
                "Search file contents with a regex pattern. Default output_mode is "
                "files_with_matches (file paths only); use content mode for matching "
                "lines with context. Prefer this over shell grep for ordinary workspace searches."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "minLength": 1},
                    "path": {"type": "string"},
                    "glob": {"type": "string"},
                    "type": {"type": "string"},
                    "case_insensitive": {"type": "boolean"},
                    "fixed_strings": {"type": "boolean"},
                    "output_mode": {
                        "type": "string",
                        "enum": ["content", "files_with_matches", "count"],
                    },
                    "context_before": {"type": "integer", "minimum": 0, "maximum": 20},
                    "context_after": {"type": "integer", "minimum": 0, "maximum": 20},
                    "max_matches": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "head_limit": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "offset": {"type": "integer", "minimum": 0, "maximum": 100000},
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        pattern = str(arguments["pattern"])
        raw_path = str(arguments.get("path", "."))
        glob = arguments.get("glob")
        file_type = arguments.get("type")
        case_insensitive = bool(arguments.get("case_insensitive", False))
        fixed_strings = bool(arguments.get("fixed_strings", False))
        output_mode = str(arguments.get("output_mode", "files_with_matches"))
        context_before = int(arguments.get("context_before", 0))
        context_after = int(arguments.get("context_after", 0))
        max_matches = arguments.get("max_matches")
        max_results = arguments.get("max_results")
        head_limit = arguments.get("head_limit")
        offset = int(arguments.get("offset", 0))

        target = self._resolve(raw_path)
        if not target.exists():
            return f"Error: Path not found: {raw_path}"
        if not (target.is_dir() or target.is_file()):
            return f"Error: Unsupported path: {raw_path}"

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            needle = re.escape(pattern) if fixed_strings else pattern
            regex = re.compile(needle, flags)
        except re.error as exc:
            return f"Error: invalid regex pattern: {exc}"

        if head_limit is not None:
            limit = None if int(head_limit) == 0 else int(head_limit)
        elif output_mode == "content" and max_matches is not None:
            limit = int(max_matches)
        elif output_mode != "content" and max_results is not None:
            limit = int(max_results)
        else:
            limit = _DEFAULT_HEAD_LIMIT

        blocks: list[str] = []
        result_chars = 0
        seen_content_matches = 0
        truncated = False
        size_truncated = False
        skipped_binary = 0
        skipped_large = 0
        matching_files: list[str] = []
        counts: dict[str, int] = {}
        file_mtimes: dict[str, float] = {}
        root = target if target.is_dir() else target.parent

        for file_path in self._iter_files(target):
            rel_path = file_path.relative_to(root).as_posix()
            if glob and not _match_glob(rel_path, file_path.name, str(glob)):
                continue
            if not _matches_type(file_path.name, None if file_type is None else str(file_type)):
                continue

            raw = file_path.read_bytes()
            if len(raw) > self._MAX_FILE_BYTES:
                skipped_large += 1
                continue
            if _is_binary(raw):
                skipped_binary += 1
                continue
            try:
                mtime = file_path.stat().st_mtime
            except OSError:
                mtime = 0.0
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                skipped_binary += 1
                continue

            lines = content.splitlines()
            display_path = self._display_path(file_path, root)
            file_had_match = False
            for index, line in enumerate(lines, start=1):
                if not regex.search(line):
                    continue
                file_had_match = True

                if output_mode == "count":
                    counts[display_path] = counts.get(display_path, 0) + 1
                    continue
                if output_mode == "files_with_matches":
                    if display_path not in matching_files:
                        matching_files.append(display_path)
                        file_mtimes[display_path] = mtime
                    break

                seen_content_matches += 1
                if seen_content_matches <= offset:
                    continue
                if limit is not None and len(blocks) >= limit:
                    truncated = True
                    break
                block = self._format_block(display_path, lines, index, context_before, context_after)
                extra_sep = 2 if blocks else 0
                if result_chars + extra_sep + len(block) > self._MAX_RESULT_CHARS:
                    size_truncated = True
                    break
                blocks.append(block)
                result_chars += extra_sep + len(block)

            if output_mode == "count" and file_had_match and display_path not in matching_files:
                matching_files.append(display_path)
                file_mtimes[display_path] = mtime
            if truncated or size_truncated:
                break

        if output_mode == "files_with_matches":
            if not matching_files:
                result = f"No matches found for pattern '{pattern}' in {raw_path}"
            else:
                ordered_files = sorted(matching_files, key=lambda name: (-file_mtimes.get(name, 0.0), name))
                paged, truncated = _paginate(ordered_files, limit, offset)
                result = "\n".join(paged)
        elif output_mode == "count":
            if not counts:
                result = f"No matches found for pattern '{pattern}' in {raw_path}"
            else:
                ordered_files = sorted(matching_files, key=lambda name: (-file_mtimes.get(name, 0.0), name))
                ordered, truncated = _paginate(ordered_files, limit, offset)
                result = "\n".join(f"{name}: {counts[name]}" for name in ordered)
        else:
            if not blocks:
                result = f"No matches found for pattern '{pattern}' in {raw_path}"
            else:
                result = "\n\n".join(blocks)

        notes: list[str] = []
        if output_mode == "content" and truncated:
            notes.append(f"(pagination: limit={limit}, offset={offset})")
        elif output_mode == "content" and size_truncated:
            notes.append("(output truncated due to size)")
        elif truncated and output_mode in {"count", "files_with_matches"}:
            notes.append(f"(pagination: limit={limit}, offset={offset})")
        elif output_mode in {"count", "files_with_matches"} and offset > 0:
            notes.append(f"(pagination: offset={offset})")
        elif output_mode == "content" and offset > 0 and blocks:
            notes.append(f"(pagination: offset={offset})")
        if skipped_binary:
            notes.append(f"(skipped {skipped_binary} binary/unreadable files)")
        if skipped_large:
            notes.append(f"(skipped {skipped_large} large files)")
        if output_mode == "count" and counts:
            notes.append(f"(total matches: {sum(counts.values())} in {len(counts)} files)")
        if notes:
            result += "\n\n" + "\n".join(notes)
        return result

    @staticmethod
    def _format_block(
        display_path: str,
        lines: list[str],
        match_line: int,
        before: int,
        after: int,
    ) -> str:
        start = max(1, match_line - before)
        end = min(len(lines), match_line + after)
        block = [f"{display_path}:{match_line}"]
        for line_no in range(start, end + 1):
            marker = ">" if line_no == match_line else " "
            block.append(f"{marker} {line_no}| {lines[line_no - 1]}")
        return "\n".join(block)
