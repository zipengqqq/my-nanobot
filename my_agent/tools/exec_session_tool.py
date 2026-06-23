from __future__ import annotations

import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from my_agent.tools.base import ToolSchema
from my_agent.tools.shell_tool import _resolve_cwd


def _read_stream(stream: TextIO, buffer: list[str], lock: threading.Lock) -> None:
    for line in stream:
        with lock:
            buffer.append(line)


@dataclass(slots=True)
class ExecSession:
    id: int
    command: str
    process: subprocess.Popen[str]
    started_at: float
    stdout: list[str]
    stderr: list[str]
    lock: threading.Lock
    stdout_offset: int = 0
    stderr_offset: int = 0

    def status(self) -> str:
        return "running" if self.process.poll() is None else "exited"

    def exit_code(self) -> int | None:
        return self.process.poll()

    def consume_output(self) -> tuple[str, str]:
        with self.lock:
            stdout = "".join(self.stdout[self.stdout_offset :]).strip()
            stderr = "".join(self.stderr[self.stderr_offset :]).strip()
            self.stdout_offset = len(self.stdout)
            self.stderr_offset = len(self.stderr)
        return stdout, stderr


@dataclass(slots=True)
class ExecSessionStore:
    root: Path
    sessions: dict[int, ExecSession]
    next_id: int = 1

    def start(self, command: str, cwd: Path) -> ExecSession:
        process = subprocess.Popen(
            shlex.split(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd,
        )
        session = ExecSession(
            id=self.next_id,
            command=command,
            process=process,
            started_at=time.time(),
            stdout=[],
            stderr=[],
            lock=threading.Lock(),
        )
        self.next_id += 1
        self.sessions[session.id] = session

        if process.stdout is not None:
            threading.Thread(
                target=_read_stream,
                args=(process.stdout, session.stdout, session.lock),
                daemon=True,
            ).start()
        if process.stderr is not None:
            threading.Thread(
                target=_read_stream,
                args=(process.stderr, session.stderr, session.lock),
                daemon=True,
            ).start()
        return session

    def get(self, session_id: int) -> ExecSession | None:
        return self.sessions.get(session_id)

    def list(self) -> list[ExecSession]:
        return [self.sessions[key] for key in sorted(self.sessions)]


_EXEC_SESSION_STORES: dict[Path, ExecSessionStore] = {}


def _store_for(root: Path) -> ExecSessionStore:
    resolved = root.resolve()
    store = _EXEC_SESSION_STORES.get(resolved)
    if store is None:
        store = ExecSessionStore(root=resolved, sessions={})
        _EXEC_SESSION_STORES[resolved] = store
    return store


def _wait_for_output(milliseconds: int | float | None) -> None:
    if milliseconds is None:
        milliseconds = 1000
    time.sleep(max(0, float(milliseconds)) / 1000)


def _format_session_result(session: ExecSession, stdout: str, stderr: str) -> str:
    sections = [f"session_id={session.id}", f"status={session.status()}"]
    exit_code = session.exit_code()
    if exit_code is not None:
        sections.append(f"exit_code={exit_code}")
    if stdout:
        sections.append(f"stdout:\n{stdout}")
    if stderr:
        sections.append(f"stderr:\n{stderr}")
    return "\n".join(sections)


@dataclass(slots=True)
class StartExecSessionTool:
    """启动长运行或交互式命令，并返回后续操作需要的 session_id。"""

    root: Path

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="start_exec_session",
            description=(
                "Start a long-running local command and return a session_id. "
                "Use write_stdin to send input or poll additional output."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to start."},
                    "cwd": {"type": "string", "description": "Optional working directory."},
                    "yield_time_ms": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 30000,
                        "description": "Milliseconds to wait before returning initial output.",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        command = str(arguments["command"])
        cwd = _resolve_cwd(self.root, arguments.get("cwd"))
        session = _store_for(self.root).start(command=command, cwd=cwd)
        _wait_for_output(arguments.get("yield_time_ms"))
        stdout, stderr = session.consume_output()
        return _format_session_result(session, stdout, stderr)


@dataclass(slots=True)
class WriteStdinTool:
    """向已有 exec session 写入 stdin、轮询新输出，或终止运行中的进程。"""

    root: Path

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="write_stdin",
            description=(
                "Send characters to a running exec session, or poll output by "
                "omitting chars / passing an empty string."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Exec session id."},
                    "chars": {"type": "string", "description": "Characters to send to stdin."},
                    "terminate": {
                        "type": "boolean",
                        "description": "Terminate the session process before returning status.",
                    },
                    "yield_time_ms": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 30000,
                        "description": "Milliseconds to wait before returning new output.",
                    },
                },
                "required": ["session_id"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        session_id = int(arguments["session_id"])
        session = _store_for(self.root).get(session_id)
        if session is None:
            return f"Error: exec session {session_id} not found"

        if bool(arguments.get("terminate", False)) and session.process.poll() is None:
            session.process.terminate()

        chars = str(arguments.get("chars", ""))
        if chars and session.process.poll() is None and session.process.stdin is not None:
            session.process.stdin.write(chars)
            session.process.stdin.flush()

        _wait_for_output(arguments.get("yield_time_ms"))
        stdout, stderr = session.consume_output()
        return _format_session_result(session, stdout, stderr)


@dataclass(slots=True)
class ListExecSessionsTool:
    """列出当前工作区内已知 exec session 的状态和原始命令。"""

    root: Path

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="list_exec_sessions",
            description="List known exec sessions and their current status.",
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        sessions = _store_for(self.root).list()
        if not sessions:
            return "No exec sessions"
        lines = []
        for session in sessions:
            exit_code = session.exit_code()
            exit_part = "" if exit_code is None else f" exit_code={exit_code}"
            lines.append(
                f"session_id={session.id} status={session.status()}{exit_part} "
                f"command={session.command}"
            )
        return "\n".join(lines)
