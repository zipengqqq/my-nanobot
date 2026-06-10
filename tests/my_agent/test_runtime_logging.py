import logging
from pathlib import Path

from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.runner import AgentRunner
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry


class LoggingToolLoopProvider:
    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir
        self.calls = 0

    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> object:
        _ = messages
        _ = tools
        self.calls += 1

        from my_agent.agent.provider import ModelResponse, ToolCall

        if self.calls == 1:
            return ModelResponse(
                tool_call=ToolCall(
                    id="call-1",
                    name="read_file",
                    arguments={"path": str(self.working_dir / "note.txt")},
                )
            )
        return ModelResponse(text="文件已经读取完成，内容是 phase logging")


def test_agent_runtime_logs_turn_context_tooling_and_final_reply(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "note.txt").write_text("phase logging", encoding="utf-8")
    log_file = tmp_path / "runtime.log"

    test_logger = logging.getLogger("tests.my_agent.runtime_logging")
    test_logger.handlers.clear()
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    test_logger.addHandler(file_handler)
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False

    monkeypatch.setattr("my_agent.agent.loop.logger", test_logger)
    monkeypatch.setattr("my_agent.agent.runner.logger", test_logger)
    monkeypatch.setattr("my_agent.tools.registry.logger", test_logger)

    loop = AgentLoop(
        session_manager=SessionManager(history_limit=2),
        context_builder=ContextBuilder(system_prompt="你是测试助手，负责解释你正在做什么。"),
        runner=AgentRunner(
            provider=LoggingToolLoopProvider(working_dir=tmp_path),
            tool_registry=ToolRegistry.with_defaults(),
            max_iterations=3,
        ),
    )

    reply = loop.handle_user_message(session_id="lesson", user_text="读取 note.txt")
    file_handler.flush()

    assert reply == "文件已经读取完成，内容是 phase logging"
    log_text = log_file.read_text(encoding="utf-8")
    assert "开始处理本轮 session=lesson" in log_text
    assert "上下文已构建 session=lesson" in log_text
    assert "system_prompt=你是测试助手，负责解释你正在做什么。" in log_text
    assert "Agent 第 1/3 轮" in log_text
    assert '请求工具 iteration=1 name=read_file args={"path":' in log_text
    assert "工具执行完成 name=read_file" in log_text
    assert "最终回复 iteration=2" in log_text
