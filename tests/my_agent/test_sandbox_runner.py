from pathlib import Path

import pytest

from my_agent.sandbox import SandboxPolicy, SandboxRunner, SandboxUnavailableError


def test_required_runner_rejects_execution_without_a_backend(tmp_path: Path) -> None:
    runner = SandboxRunner(policy=SandboxPolicy.required(workspace_root=tmp_path), backends=[])

    with pytest.raises(SandboxUnavailableError, match="没有可用的沙箱后端"):
        runner.start(("python", "--version"), cwd=tmp_path)
