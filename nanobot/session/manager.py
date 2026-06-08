"""对话历史的 session 管理。"""

import json
import os
import re
import shutil
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.config.paths import get_legacy_sessions_dir
from nanobot.utils.helpers import (
    ensure_dir,
    estimate_message_tokens,
    find_legal_message_start,
    image_placeholder_text,
    safe_filename,
    strip_think,
)
from nanobot.utils.subagent_channel_display import scrub_subagent_announce_body

FILE_MAX_MESSAGES = 2000
_MESSAGE_TIME_PREFIX_RE = re.compile(r"^\[Message Time: [^\]]+\]\n?")
_LOCAL_IMAGE_BREADCRUMB_RE = re.compile(r"^\[image: (?:/|~)[^\]]+\]\s*$")
_TOOL_CALL_ECHO_RE = re.compile(r'^\s*(?:generate_image|message)\([^)]*\)\s*$')
_SESSION_PREVIEW_MAX_CHARS = 120
_SESSION_LIST_PREVIEW_MAX_RECORDS = 200
_SESSION_LIST_PREVIEW_MAX_CHARS = 1_000_000


def _sanitize_assistant_replay_text(content: str) -> str:
    """移除模型可能已经学会复述的内部回放痕迹。

    这些字符串作为运行时或 session 元数据是有价值的，但一旦出现在
    assistant 示例里，就会变成模型继续模仿输出的“示范文本”。
    """
    content = _MESSAGE_TIME_PREFIX_RE.sub("", content, count=1)
    lines = [
        line
        for line in content.splitlines()
        if not _LOCAL_IMAGE_BREADCRUMB_RE.match(line)
        and not _TOOL_CALL_ECHO_RE.match(line)
    ]
    return "\n".join(lines).strip()


def _text_preview(content: Any) -> str:
    """返回用于 session 列表展示的紧凑文本。"""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                value = block.get("text")
                if isinstance(value, str):
                    parts.append(value)
        text = " ".join(parts)
    else:
        return ""
    text = _sanitize_assistant_replay_text(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > _SESSION_PREVIEW_MAX_CHARS:
        text = text[: _SESSION_PREVIEW_MAX_CHARS - 1].rstrip() + "…"
    return text


def _message_preview_text(message: dict[str, Any]) -> str:
    """生成 session 列表预览文本；subagent 注入内容会先压缩再展示。"""
    content: Any = message.get("content")
    if message.get("injected_event") == "subagent_result" and isinstance(content, str):
        content = scrub_subagent_announce_body(content)
    return _text_preview(content)


def _metadata_title(metadata: Any) -> str:
    if not isinstance(metadata, dict):
        return ""
    title = metadata.get("title")
    if not isinstance(title, str):
        return ""
    if metadata.get("title_user_edited") is True:
        return title
    return strip_think(title)


@dataclass
class Session:
    """一段对话 session。"""

    key: str  # channel:chat_id 形式的会话键
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0  # 已经归档到文件中的消息数量

    def __post_init__(self) -> None:
        # 偏移越界通常说明 metadata 已损坏；若不重置会导致整段历史被隐藏。
        if (
            isinstance(self.last_consolidated, bool)
            or not isinstance(self.last_consolidated, int)
            or not 0 <= self.last_consolidated <= len(self.messages)
        ):
            self.last_consolidated = 0

    @staticmethod
    def _annotate_message_time(message: dict[str, Any], content: Any) -> Any:
        """向模型暴露已持久化的 turn 时间戳，便于相对日期推理。

        如果给 *每一条* assistant 消息都加时间戳，模型会在上下文学习中把
        ``[Message Time: ...]`` 当成回复模板，从而把内部元数据泄漏给用户。
        因此这里只标注 user turn。用户侧时间戳已经足够让模型推断相邻的
        assistant 回复时间，包括用户稍后再回复的主动消息。
        """
        timestamp = message.get("timestamp")
        if not timestamp or not isinstance(content, str):
            return content
        role = message.get("role")
        if role != "user":
            return content
        return f"[Message Time: {timestamp}]\n{content}"

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """向 session 追加一条消息。"""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(
        self,
        max_messages: int = 120,
        *,
        max_tokens: int = 0,
        include_timestamps: bool = False,
    ) -> list[dict[str, Any]]:
        """返回供 LLM 输入使用的、尚未归档压缩的消息。

        历史会先按消息数（``max_messages``）裁剪，再在提供 ``max_tokens`` 时
        从尾部按 token 预算继续收缩。
        """
        unconsolidated = self.messages[self.last_consolidated:]
        max_messages = max_messages if max_messages > 0 else 120
        sliced = unconsolidated[-max_messages:]

        # 尽量不要从一个 turn 的中间开始回放，除非前一条是用户正在回复的
        # 主动 assistant 投递消息。
        for i, message in enumerate(sliced):
            if message.get("role") == "user":
                start = i
                if i > 0 and sliced[i - 1].get("_channel_delivery"):
                    start = i - 1
                sliced = sliced[start:]
                break

        # 丢弃开头没有对应 tool_call 的孤儿 tool result。
        start = find_legal_message_start(sliced)
        if start:
            sliced = sliced[start:]

        out: list[dict[str, Any]] = []
        for message in sliced:
            if message.get("_command"):
                continue
            content = message.get("content", "")
            role = message.get("role")
            if role == "assistant" and isinstance(content, str):
                content = _sanitize_assistant_replay_text(content)
            # 根据持久化的 ``media`` 参数补出 ``[image: path]`` 面包屑，
            # 让 LLM 回放时至少还能看到“这里原本有张图”。否则纯图片的
            # 用户消息会回放成空白消息，assistant 的回答看起来就像
            # 在对着空气回复。
            media = message.get("media")
            if role == "user" and isinstance(media, list) and media and isinstance(content, str):
                breadcrumbs = "\n".join(
                    image_placeholder_text(p) for p in media if isinstance(p, str) and p
                )
                content = f"{content}\n{breadcrumbs}" if content else breadcrumbs
            cli_apps = message.get("cli_apps")
            if role == "user" and isinstance(cli_apps, list) and cli_apps and isinstance(content, str):
                cli_lines: list[str] = []
                for item in cli_apps[:8]:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip().lower()
                    if not name:
                        continue
                    entry = str(item.get("entry_point") or "unknown").strip() or "unknown"
                    cli_lines.append(
                        f"[CLI App Attachment: @{name}; tool=run_cli_app; entry_point={entry}; "
                        f"skill=skills/cli-app-{name}/SKILL.md]"
                    )
                if cli_lines:
                    breadcrumbs = "\n".join(cli_lines)
                    content = f"{content}\n{breadcrumbs}" if content else breadcrumbs
            mcp_presets = message.get("mcp_presets")
            if (
                role == "user"
                and isinstance(mcp_presets, list)
                and mcp_presets
                and isinstance(content, str)
            ):
                mcp_lines: list[str] = []
                for item in mcp_presets[:8]:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip().lower()
                    if not name:
                        continue
                    transport = str(item.get("transport") or "mcp").strip() or "mcp"
                    mcp_lines.append(
                        f"[MCP Preset Attachment: @{name}; tool_prefix=mcp_{name}_; "
                        f"transport={transport}]"
                    )
                if mcp_lines:
                    breadcrumbs = "\n".join(mcp_lines)
                    content = f"{content}\n{breadcrumbs}" if content else breadcrumbs
            if include_timestamps:
                content = self._annotate_message_time(message, content)
            if role == "assistant" and isinstance(content, str) and not content.strip():
                if not any(key in message for key in ("tool_calls", "reasoning_content", "thinking_blocks")):
                    continue
            entry: dict[str, Any] = {"role": message["role"], "content": content}
            for key in ("tool_calls", "tool_call_id", "name", "reasoning_content", "thinking_blocks"):
                if key in message:
                    entry[key] = message[key]
            out.append(entry)

        if max_tokens > 0 and out:
            kept: list[dict[str, Any]] = []
            used = 0
            for message in reversed(out):
                tokens = estimate_message_tokens(message)
                if kept and used + tokens > max_tokens:
                    break
                kept.append(message)
                used += tokens
            kept.reverse()

            # 让历史回放尽量从第一个可见的 user turn 开始。
            first_user = next((i for i, m in enumerate(kept) if m.get("role") == "user"), None)
            if first_user is not None:
                kept = kept[first_user:]
            else:
                # token 预算很紧时，尾部可能只剩 assistant 消息。
                # 如果未裁剪输出里存在 user turn，就尽量找回最近的一条，
                # 即便会略微超出预算也比上下文不合法更好。
                recovered_user = next(
                    (i for i in range(len(out) - 1, -1, -1) if out[i].get("role") == "user"),
                    None,
                )
                if recovered_user is not None:
                    kept = out[recovered_user:]

            # 同时确保开头仍然处于合法的 tool-call 边界上。
            start = find_legal_message_start(kept)
            if start:
                kept = kept[start:]
            out = kept
        return out

    def clear(self) -> None:
        """清空全部消息，并把 session 重置到初始状态。"""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()
        self.metadata.pop("_last_summary", None)

    def retain_recent_legal_suffix(self, max_messages: int) -> tuple[list[dict], int]:
        """在硬消息上限下，保留一段“合法”的最近后缀。

        返回 ``(dropped, already_consolidated_count)``。
        其中 *dropped* 是被移除的消息列表（保持原顺序），
        *already_consolidated_count* 表示这些消息里有多少原本就在
        ``last_consolidated`` 前缀中，因此不需要再做 raw archive。
        """
        if max_messages <= 0:
            dropped = list(self.messages)
            lc = self.last_consolidated
            self.clear()
            return dropped, min(lc, len(dropped))
        if len(self.messages) <= max_messages:
            return [], 0

        original = list(self.messages)
        before_lc = self.last_consolidated

        retained = list(self.messages[-max_messages:])

        # 如果尾部存在 user turn，优先从它开始。
        first_user = next((i for i, m in enumerate(retained) if m.get("role") == "user"), None)
        if first_user is not None:
            retained = retained[first_user:]
        else:
            # 如果尾部只有 assistant/tool，就回退到整段会话里最近的 user，
            # 再从那里截取一个受上限约束的前向窗口。
            latest_user = next(
                (i for i in range(len(self.messages) - 1, -1, -1)
                 if self.messages[i].get("role") == "user"),
                None,
            )
            if latest_user is not None:
                retained = list(self.messages[latest_user: latest_user + max_messages])

        # 与 get_history() 保持一致：避免前面保留孤儿 tool result。
        start = find_legal_message_start(retained)
        if start:
            retained = retained[start:]

        # 强约束：保留的消息数绝不超过 max_messages。
        if len(retained) > max_messages:
            retained = retained[-max_messages:]
            start = find_legal_message_start(retained)
            if start:
                retained = retained[start:]

        # 通过对象身份计算“真正被丢弃”的消息。这样即便 retained 不是
        # 原列表的连续切片（例如上面的 else 分支），也不会重复或漏掉消息。
        retained_ids = set(id(m) for m in retained)
        dropped = [m for m in original if id(m) not in retained_ids]

        # 统计 dropped 中有多少原本位于已归档前缀里。这里不能简单用 min()，
        # 因为 dropped 里可能混入归档前缀之后的消息（例如 else 分支）。
        already_consolidated = sum(
            1 for i, m in enumerate(original)
            if i < before_lc and id(m) not in retained_ids
        )

        # 新的 last_consolidated 等于“仍被保留、且原本位于旧归档前缀内”的消息数。
        new_lc = sum(
            1 for i, m in enumerate(original)
            if i < before_lc and id(m) in retained_ids
        )

        self.messages = retained
        self.last_consolidated = new_lc
        self.updated_at = datetime.now()
        return dropped, already_consolidated

    def enforce_file_cap(
        self,
        on_archive: Any = None,
        limit: int = FILE_MAX_MESSAGES,
    ) -> None:
        """通过归档和裁剪旧前缀，限制 session 消息持续膨胀。"""
        if limit <= 0 or len(self.messages) <= limit:
            return

        dropped, already_consolidated = self.retain_recent_legal_suffix(limit)
        if not dropped:
            return

        archive_chunk = dropped[already_consolidated:]
        if archive_chunk and on_archive:
            on_archive(archive_chunk)
        logger.info(
            "Session file cap hit for {}: dropped {}, raw-archived {}, kept {}",
            self.key,
            len(dropped),
            len(archive_chunk),
            len(self.messages),
        )


class SessionManager:
    """
    管理对话 session。

    每个 session 都以 JSONL 文件形式保存在 sessions 目录中。
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(self.workspace / "sessions")
        self.legacy_sessions_dir = get_legacy_sessions_dir()
        self._cache: dict[str, Session] = {}

    @staticmethod
    def safe_key(key: str) -> str:
        """供 HTTP 处理器使用：把任意 key 映射为稳定的文件名主体。"""
        return safe_filename(key.replace(":", "_"))

    def _get_session_path(self, key: str) -> Path:
        """返回某个 session 对应的文件路径。"""
        return self.sessions_dir / f"{self.safe_key(key)}.jsonl"

    def _get_legacy_session_path(self, key: str) -> Path:
        """旧版全局 session 路径（~/.nanobot/sessions/）。"""
        return self.legacy_sessions_dir / f"{self.safe_key(key)}.jsonl"

    def get_or_create(self, key: str) -> Session:
        """
        获取已有 session；若不存在则创建一个新的。

        Args:
            key: session key，通常形如 ``channel:chat_id``。

        Returns:
            对应的 session 对象。
        """
        if key in self._cache:
            return self._cache[key]

        session = self._load(key)
        if session is None:
            session = Session(key=key)

        self._cache[key] = session
        return session

    def _load(self, key: str) -> Session | None:
        """从磁盘加载 session。"""
        path = self._get_session_path(key)
        if not path.exists():
            legacy_path = self._get_legacy_session_path(key)
            if legacy_path.exists():
                try:
                    shutil.move(str(legacy_path), str(path))
                    logger.info("Migrated session {} from legacy path", key)
                except Exception:
                    logger.exception("Failed to migrate session {}", key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None
            updated_at = None
            last_consolidated = 0

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                        updated_at = datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                updated_at=updated_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated
            )
        except Exception as e:
            logger.warning("Failed to load session {}: {}", key, e)
            repaired = self._repair(key)
            if repaired is not None:
                logger.info("Recovered session {} from corrupt file ({} messages)", key, len(repaired.messages))
            return repaired

    def _repair(self, key: str) -> Session | None:
        """尝试从损坏的 JSONL 文件中恢复 session。"""
        path = self._get_session_path(key)
        if not path.exists():
            return None

        try:
            messages: list[dict[str, Any]] = []
            metadata: dict[str, Any] = {}
            created_at: datetime | None = None
            updated_at: datetime | None = None
            last_consolidated = 0
            skipped = 0

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        if data.get("created_at"):
                            with suppress(ValueError, TypeError):
                                created_at = datetime.fromisoformat(data["created_at"])
                        if data.get("updated_at"):
                            with suppress(ValueError, TypeError):
                                updated_at = datetime.fromisoformat(data["updated_at"])
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)

            if skipped:
                logger.warning("Skipped {} corrupt lines in session {}", skipped, key)

            if not messages and not metadata:
                return None

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                updated_at=updated_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated
            )
        except Exception as e:
            logger.warning("Repair failed for session {}: {}", key, e)
            return None

    @staticmethod
    def _session_payload(session: Session) -> dict[str, Any]:
        return {
            "key": session.key,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "metadata": session.metadata,
            "messages": session.messages,
        }

    def save(self, session: Session, *, fsync: bool = False) -> None:
        """以原子方式把 session 保存到磁盘。

        当 *fsync* 为 ``True`` 时，最终文件及其父目录都会显式刷入持久存储。
        默认关闭是有意为之，因为常规运行依赖操作系统页缓存已足够；但在优雅关停时
        应开启，以避免带写回缓存的文件系统（例如 rclone VFS、NFS、FUSE 挂载）
        丢失最近一次写入。
        """
        path = self._get_session_path(session.key)
        tmp_path = path.with_suffix(".jsonl.tmp")

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                metadata_line = {
                    "_type": "metadata",
                    "key": session.key,
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "metadata": session.metadata,
                    "last_consolidated": session.last_consolidated
                }
                f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
                for msg in session.messages:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")
                if fsync:
                    f.flush()
                    os.fsync(f.fileno())

            os.replace(tmp_path, path)

            if fsync:
                # 对目录执行 fsync，保证 rename 本身也真正落盘。
                # Windows 上以 O_RDONLY 打开目录会抛出 PermissionError，
                # 因此那里跳过目录同步（NTFS 会同步记录元数据日志）。
                with suppress(PermissionError):
                    fd = os.open(str(path.parent), os.O_RDONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        self._cache[session.key] = session

    def flush_all(self) -> int:
        """对所有缓存中的 session 执行带 fsync 的重新保存，用于可靠关停。

        返回成功 flush 的 session 数量。单个 session 出错会记录日志，
        但不会阻止其他 session 继续 flush。
        """
        flushed = 0
        for key, session in list(self._cache.items()):
            try:
                self.save(session, fsync=True)
                flushed += 1
            except Exception:
                logger.warning("Failed to flush session {}", key, exc_info=True)
        return flushed

    def invalidate(self, key: str) -> None:
        """从内存缓存中移除某个 session。"""
        self._cache.pop(key, None)

    def delete_session(self, key: str) -> bool:
        """从磁盘和内存缓存中删除某个 session。

        如果找到并删除了 JSONL 文件，则返回 True。
        """
        path = self._get_session_path(key)
        self.invalidate(key)
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except OSError as e:
            logger.warning("Failed to delete session file {}: {}", path, e)
            return False

    def read_session_file(self, key: str) -> dict[str, Any] | None:
        """直接从磁盘读取 session，但不写入缓存；主要用于只读 HTTP 接口。

        成功时返回 ``{"key", "created_at", "updated_at", "metadata", "messages"}``，
        如果文件不存在或解析失败，则返回 ``None``。
        """
        path = self._get_session_path(key)
        if not path.exists():
            return None
        try:
            messages: list[dict[str, Any]] = []
            metadata: dict[str, Any] = {}
            created_at: str | None = None
            updated_at: str | None = None
            stored_key: str | None = None
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = data.get("created_at")
                        updated_at = data.get("updated_at")
                        stored_key = data.get("key")
                    else:
                        messages.append(data)
            return {
                "key": stored_key or key,
                "created_at": created_at,
                "updated_at": updated_at,
                "metadata": metadata,
                "messages": messages,
            }
        except Exception as e:
            logger.warning("Failed to read session {}: {}", key, e)
            repaired = self._repair(key)
            if repaired is not None:
                logger.info("Recovered read-only session view {} from corrupt file", key)
                return self._session_payload(repaired)
            return None

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        列出所有 session。

        Returns:
            session 信息字典列表。
        """
        sessions = []

        for path in self.sessions_dir.glob("*.jsonl"):
            fallback_key = path.stem.replace("_", ":", 1)
            try:
                # 只读取 metadata 行和少量预览文本，供 WebUI/session 列表使用。
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            key = data.get("key") or path.stem.replace("_", ":", 1)
                            metadata = data.get("metadata", {})
                            title = _metadata_title(metadata)
                            preview = ""
                            fallback_preview = ""
                            scanned_records = 0
                            scanned_chars = 0
                            for line in f:
                                if not line.strip():
                                    continue
                                scanned_records += 1
                                scanned_chars += len(line)
                                if (
                                    scanned_records > _SESSION_LIST_PREVIEW_MAX_RECORDS
                                    or scanned_chars > _SESSION_LIST_PREVIEW_MAX_CHARS
                                ):
                                    break
                                item = json.loads(line)
                                if item.get("_type") == "metadata":
                                    continue
                                text = _message_preview_text(item)
                                if not text:
                                    continue
                                if item.get("role") == "user":
                                    preview = text
                                    break
                                if not fallback_preview and item.get("role") == "assistant":
                                    fallback_preview = text
                            preview = preview or fallback_preview
                            sessions.append({
                                "key": key,
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "title": title,
                                "preview": preview,
                                "path": str(path)
                            })
            except Exception:
                repaired = self._repair(fallback_key)
                if repaired is not None:
                    sessions.append({
                        "key": repaired.key,
                        "created_at": repaired.created_at.isoformat(),
                        "updated_at": repaired.updated_at.isoformat(),
                        "title": _metadata_title(repaired.metadata),
                        "preview": next(
                            (
                                text
                                for msg in repaired.messages
                                if (text := _message_preview_text(msg))
                            ),
                            "",
                        ),
                        "path": str(path)
                    })
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
