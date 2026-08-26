from pathlib import Path

from my_agent.tools.exec_session_tool import StartExecSessionTool, WriteStdinTool
from my_agent.tools.shell_tool import ExecTool
from tests.my_agent.sandbox_fakes import FakeSandboxRunner


def test_exec_delegates_to_the_injected_sandbox_runner(tmp_path: Path) -> None:
    runner = FakeSandboxRunner(stdout="sandboxed\n")

    result = ExecTool(root=tmp_path, sandbox_runner=runner).run({"command": "python3 --version"})

    assert runner.requests == [(("python3", "--version"), tmp_path.resolve())]
    assert "stdout:\nsandboxed" in result


def test_terminating_a_session_terminates_the_sandbox_process_tree(tmp_path: Path) -> None:
    runner = FakeSandboxRunner(exit_code=None)
    start_tool = StartExecSessionTool(root=tmp_path, sandbox_runner=runner)
    write_tool = WriteStdinTool(root=tmp_path, sandbox_runner=runner)

    started = start_tool.run({"command": "python3 -c pass", "yield_time_ms": 0})
    session_id = int(started.splitlines()[0].split("=", 1)[1])
    write_tool.run({"session_id": session_id, "terminate": True, "yield_time_ms": 0})

    assert runner.processes[0].terminate_tree_called is True
