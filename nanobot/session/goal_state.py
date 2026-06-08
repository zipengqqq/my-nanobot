"""持续性目标的 session 元数据辅助函数（例如 ``long_task`` / ``complete_goal``）。

工具会写入 ``metadata[GOAL_STATE_KEY]``。读取时也兼容旧版 session key ``thread_goal``，
以支持老会话。调用方可以直接使用 ``goal_state_runtime_lines``、
``goal_state_ws_blob`` 和 ``runner_wall_llm_timeout_s``，无需导入具体工具实现。
"""

from __future__ import annotations

import json
from typing import Any, Mapping, MutableMapping

from nanobot.session.manager import SessionManager

GOAL_STATE_KEY = "goal_state"
# 旧版本会把同一份 JSON blob 存在这个 key 下。
_LEGACY_GOAL_STATE_SESSION_KEY = "thread_goal"
_MAX_OBJECTIVE_IN_RUNTIME = 4000
_MAX_OBJECTIVE_WS = 600


def _session_goal_raw(metadata: Mapping[str, Any] | None) -> Any:
    if not metadata:
        return None
    if GOAL_STATE_KEY in metadata:
        return metadata.get(GOAL_STATE_KEY)
    return metadata.get(_LEGACY_GOAL_STATE_SESSION_KEY)


def discard_legacy_goal_state_key(metadata: MutableMapping[str, Any]) -> None:
    """将写入迁移到 :data:`GOAL_STATE_KEY` 后，删除旧版 metadata key。"""
    metadata.pop(_LEGACY_GOAL_STATE_SESSION_KEY, None)


def goal_state_raw(metadata: Mapping[str, Any] | None) -> Any:
    """返回 :data:`GOAL_STATE_KEY` 或旧版 key 下保存的 session goal blob。"""
    return _session_goal_raw(metadata)


def sustained_goal_active(metadata: Mapping[str, Any] | None) -> bool:
    """当该 session 存在激活中的持续性目标时返回 True（``long_task`` 记账信息）。"""
    goal = parse_goal_state(goal_state_raw(metadata))
    return isinstance(goal, dict) and goal.get("status") == "active"


def sustained_goal_turn(
    metadata: Mapping[str, Any] | None,
    *,
    message_metadata: Mapping[str, Any] | None = None,
) -> bool:
    """当本轮应使用持续性目标的运行时限制时返回 True。"""
    if sustained_goal_active(metadata):
        return True
    if not message_metadata:
        return False
    return str(message_metadata.get("original_command") or "").strip() == "/goal"


def parse_goal_state(blob: Any) -> dict[str, Any] | None:
    if blob is None:
        return None
    if isinstance(blob, dict):
        return blob
    if isinstance(blob, str):
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def goal_state_runtime_lines(metadata: Mapping[str, Any] | None) -> list[str]:
    """当目标处于激活状态时，追加到 Runtime Context 块中的文本行。"""
    if not metadata:
        return []
    goal = parse_goal_state(_session_goal_raw(metadata))
    if not isinstance(goal, dict) or goal.get("status") != "active":
        return []
    objective = str(goal.get("objective") or "").strip()
    if not objective:
        return ["Goal: active (no objective text stored)."]
    if len(objective) > _MAX_OBJECTIVE_IN_RUNTIME:
        objective = objective[:_MAX_OBJECTIVE_IN_RUNTIME].rstrip() + "\n… (truncated)"
    out = ["Goal (active):", objective]
    hint = str(goal.get("ui_summary") or "").strip()
    if hint:
        out.append(f"Summary: {hint}")
    return out


def goal_state_ws_blob(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """为 WebSocket ``goal_state`` 事件生成可安全序列化为 JSON 的快照。"""
    goal = parse_goal_state(_session_goal_raw(metadata)) if metadata else None
    if isinstance(goal, dict) and goal.get("status") == "active":
        objective = str(goal.get("objective") or "").strip()
        if len(objective) > _MAX_OBJECTIVE_WS:
            objective = objective[:_MAX_OBJECTIVE_WS].rstrip() + "…"
        summary = str(goal.get("ui_summary") or "").strip()[:120]
        blob: dict[str, Any] = {"active": True}
        if summary:
            blob["ui_summary"] = summary
        if objective:
            blob["objective"] = objective
        return blob
    return {"active": False}


def runner_wall_llm_timeout_s(
    sessions: SessionManager,
    session_key: str | None,
    *,
    metadata: Mapping[str, Any] | None = None,
    message_metadata: Mapping[str, Any] | None = None,
) -> float | None:
    """为 :class:`~nanobot.agent.runner.AgentRunner` 生成流式 LLM 请求的总时长上限。

    如果当前 turn 属于持续性目标，返回 ``0.0``，表示禁用包裹请求的
    ``asyncio.wait_for``；返回 ``None`` 表示沿用 ``NANOBOT_LLM_TIMEOUT_S``。
    当调用方已经持有本轮的
    :attr:`~nanobot.session.manager.Session.metadata` 时，应直接传入内存中的
    ``metadata``，避免重复读取。
    """
    meta: Mapping[str, Any] | None = metadata
    if meta is None and session_key:
        meta = sessions.get_or_create(session_key).metadata
    return 0.0 if sustained_goal_turn(meta, message_metadata=message_metadata) else None
