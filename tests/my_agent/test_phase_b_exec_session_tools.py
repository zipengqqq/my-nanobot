import sys
from pathlib import Path

import my_agent.tools.exec_session_tool as exec_session_tool
from my_agent.app import build_app


def test_exec_session_tools_support_interactive_command(tmp_path: Path) -> None:
    assert hasattr(exec_session_tool, "StartExecSessionTool")
    assert hasattr(exec_session_tool, "WriteStdinTool")
    assert hasattr(exec_session_tool, "ListExecSessionsTool")

    start_tool = exec_session_tool.StartExecSessionTool(root=tmp_path)
    write_tool = exec_session_tool.WriteStdinTool(root=tmp_path)
    list_tool = exec_session_tool.ListExecSessionsTool(root=tmp_path)

    command = (
        f"{sys.executable} -c "
        "\"import sys; "
        "print('ready', flush=True); "
        "line = sys.stdin.readline().strip(); "
        "print('echo:' + line, flush=True)\""
    )

    started = start_tool.run(
        {
            "command": command,
            "yield_time_ms": 100,
        }
    )

    assert "session_id=1" in started
    assert "status=running" in started
    assert "stdout:\nready" in started
    assert "session_id=1 status=running command=" in list_tool.run({})

    continued = write_tool.run(
        {
            "session_id": 1,
            "chars": "hello\n",
            "yield_time_ms": 100,
        }
    )

    assert "session_id=1" in continued
    assert "status=exited" in continued
    assert "exit_code=0" in continued
    assert "stdout:\necho:hello" in continued
    assert "session_id=1 status=exited exit_code=0 command=" in list_tool.run({})


def test_write_stdin_returns_clear_error_for_unknown_session(tmp_path: Path) -> None:
    assert hasattr(exec_session_tool, "WriteStdinTool")

    write_tool = exec_session_tool.WriteStdinTool(root=tmp_path)

    result = write_tool.run({"session_id": 999, "chars": "hello\n"})

    assert result == "Error: exec session 999 not found"


def test_write_stdin_can_terminate_running_session(tmp_path: Path) -> None:
    start_tool = exec_session_tool.StartExecSessionTool(root=tmp_path)
    write_tool = exec_session_tool.WriteStdinTool(root=tmp_path)

    command = f"{sys.executable} -c \"import time; time.sleep(30)\""
    started = start_tool.run({"command": command, "yield_time_ms": 10})

    assert "session_id=1" in started
    assert "status=running" in started

    terminated = write_tool.run(
        {
            "session_id": 1,
            "terminate": True,
            "yield_time_ms": 100,
        }
    )

    assert "session_id=1" in terminated
    assert "status=exited" in terminated
    assert "exit_code=" in terminated


def test_build_app_registers_exec_session_default_tools(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://example.com/v1",
                "OPENAI_API_KEY=test-key",
                "OPENAI_MODEL=gpt-4o-mini",
                "MY_AGENT_SESSION_ID=lesson",
                "MY_AGENT_HISTORY_LIMIT=12",
            ]
        ),
        encoding="utf-8",
    )

    app_state = build_app(env_file=env_file)
    tool_names = [
        schema["function"]["name"]
        for schema in app_state.loop.runner.tool_registry.list_schemas()
    ]

    assert tool_names == [
        "read_file",
        "list_dir",
        "exec",
        "write_file",
        "edit_file",
        "find_files",
        "grep",
        "apply_patch",
        "start_exec_session",
        "write_stdin",
        "list_exec_sessions",
    ]
