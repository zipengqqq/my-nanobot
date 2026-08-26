from pathlib import Path

from my_agent.app import build_app
from my_agent.sandbox.wsl import WslBubblewrapBackend
from my_agent.tools.shell_tool import ExecTool


def test_build_app_injects_the_configured_wsl_sandbox(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_BASE_URL=https://example.com/v1",
                "OPENAI_API_KEY=test-key",
                "OPENAI_MODEL=test-model",
                "MY_AGENT_SESSION_ID=test",
                "MY_AGENT_HISTORY_LIMIT=5",
                "MY_AGENT_SANDBOX_WSL_DISTRO=Ubuntu",
                "MY_AGENT_SANDBOX_WSL_USER=penn",
            ]
        ),
        encoding="utf-8",
    )

    app_state = build_app(env_file)
    exec_tool = app_state.loop.runner.tool_registry.get("exec")

    assert isinstance(exec_tool, ExecTool)
    assert isinstance(exec_tool.sandbox_runner.backends[0], WslBubblewrapBackend)
