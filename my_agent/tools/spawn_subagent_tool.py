from __future__ import annotations

from typing import Any

from my_agent.agent.subagent import SubagentManager
from my_agent.tools.base import ToolSchema


class SpawnSubagentTool:
    def __init__(self, manager: SubagentManager) -> None:
        self._manager = manager

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="spawn_subagent",
            description="将明确且可独立完成的任务委派给子 agent，并返回其结论。",
            parameters={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "minLength": 1,
                        "description": "需要子 agent 独立完成的具体任务。",
                    }
                },
                "required": ["task"],
            },
        )

    def run(self, arguments: dict[str, Any]) -> str:
        task = arguments.get("task")
        if not isinstance(task, str) or not task.strip():
            return "ERROR: 参数 task 必须是非空字符串。"
        return self._manager.run(task.strip())
