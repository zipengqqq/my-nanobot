from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from my_agent.sandbox.runner import SandboxRunner
from my_agent.tools.base import ToolSchema


def split_command(command: str) -> list[str]:
    """将命令文本拆成跨平台可执行参数。"""
    if os.name != "nt":
        return shlex.split(command)

    arguments = shlex.split(command, posix=False)
    return [
        argument[1:-1]
        if len(argument) >= 2 and argument[0] == argument[-1] and argument[0] in {"'", '"'}
        else argument
        for argument in arguments
    ]


def _resolve_cwd(root: Path, raw_path: str | None) -> Path:
    if raw_path is None:
        return root.resolve()
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


@dataclass(slots=True)
class ExecTool:
    root: Path
    sandbox_runner: SandboxRunner
    timeout_seconds: float = 10.0

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="exec",
            description="执行一条本地 shell 命令并返回输出。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令，例如 `pwd` 或 `ls my_agent`。",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "可选的工作目录路径。",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        command = split_command(str(arguments["command"]))
        process = self.sandbox_runner.start(
            command,
            cwd=_resolve_cwd(self.root, arguments.get("cwd")),
        )
        try:
            stdout, stderr = process.communicate(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            process.terminate_tree()
            stdout, _ = process.communicate()
            return f"ERROR: command timed out after {self.timeout_seconds} seconds\nstdout:\n{stdout.strip()}"
        sections = [f"exit_code={process.wait()}"]
        stdout = stdout.strip()
        stderr = stderr.strip()
        if stdout:
            sections.append(f"stdout:\n{stdout}")
        if stderr:
            sections.append(f"stderr:\n{stderr}")
        return "\n".join(sections)
