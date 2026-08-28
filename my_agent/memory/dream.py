from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from my_agent.agent.provider import ProviderAdapter
from my_agent.agent.runner import AgentRunner
from my_agent.config import logger
from my_agent.memory.store import MemoryEntry, MemoryStore

_DEFAULT_BATCH_SIZE = 20
_DEFAULT_MAX_ITERATIONS = 6
_DREAM_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "agent" / "dream.md"


@dataclass(frozen=True, slots=True)
class DreamResult:
    status: Literal["completed", "empty", "failed", "running"]
    message: str


class DreamService:
    """以受限临时 Agent 整理长期记忆。"""

    def __init__(
        self,
        store: MemoryStore,
        provider: ProviderAdapter,
        *,
        max_entries: int = _DEFAULT_BATCH_SIZE,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._store = store
        self._provider = provider
        self._max_entries = max_entries
        self._max_iterations = max_iterations
        self._run_lock = threading.Lock()

    def run_once(self) -> DreamResult:
        if not self._run_lock.acquire(blocking=False):
            return DreamResult(status="running", message="Dream is already running.")
        try:
            return self._run_once()
        finally:
            self._run_lock.release()

    def start(self, on_complete: Callable[[DreamResult], None]) -> DreamResult:
        if not self._run_lock.acquire(blocking=False):
            return DreamResult(status="running", message="Dream is already running.")

        thread = threading.Thread(
            target=self._run_in_background,
            args=(on_complete,),
            name="my-agent-dream",
            daemon=True,
        )
        thread.start()
        return DreamResult(status="running", message="Dreaming...")

    def _run_in_background(self, on_complete: Callable[[DreamResult], None]) -> None:
        try:
            result = self._run_once()
        finally:
            self._run_lock.release()
        on_complete(result)

    def _run_once(self) -> DreamResult:
        entries, last_cursor = self._store.get_unprocessed_entries(self._max_entries)
        if not entries:
            return DreamResult(status="empty", message="Dream: nothing to process.")

        try:
            tools = self._store.build_dream_tools()
            runner = AgentRunner(
                provider=self._provider,
                tool_registry=tools,
                max_iterations=self._max_iterations,
            )
            runner.run(self._build_messages(entries))
            if tools.had_execution_error:
                raise RuntimeError("Dream tool execution failed")
        except Exception as exc:
            logger.warning("Dream 整理失败: %s", exc)
            return DreamResult(status="failed", message=f"Dream failed: {exc}")

        self._store.set_last_dream_cursor(last_cursor)
        return DreamResult(status="completed", message="Dream completed.")

    @staticmethod
    def _build_messages(entries: list[MemoryEntry]) -> list[dict[str, str]]:
        template = _DREAM_TEMPLATE.read_text(encoding="utf-8")
        history = "\n".join(
            f"[{entry.timestamp}] {entry.content}" for entry in entries
        )
        # 提示词构造
        return [
            {"role": "system", "content": template},
            {"role": "user", "content": f"## Conversation History\n{history}"},
        ]


class DreamScheduler:
    """在 REPL 存活期间周期触发 Dream。"""

    def __init__(
        self,
        service: DreamService,
        interval_hours: float,
        on_complete: Callable[[DreamResult], None],
    ) -> None:
        self._service = service
        self._interval_seconds = interval_hours * 3_600
        self._on_complete = on_complete
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="my-agent-dream-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_seconds):
            self._service.start(self._on_complete)
