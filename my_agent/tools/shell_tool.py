from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from my_agent.tools.base import ToolSchema


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
        command = shlex.split(str(arguments["command"]))
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=_resolve_cwd(self.root, arguments.get("cwd")),
            timeout=self.timeout_seconds,
            check=False,
        )
        sections = [f"exit_code={completed.returncode}"]
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if stdout:
            sections.append(f"stdout:\n{stdout}")
        if stderr:
            sections.append(f"stderr:\n{stderr}")
        return "\n".join(sections)
