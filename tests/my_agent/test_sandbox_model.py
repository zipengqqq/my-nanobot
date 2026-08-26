from pathlib import Path

import pytest

from my_agent.sandbox import (
    SandboxPolicy,
    SandboxRequest,
    SandboxUnavailableError,
    UnavailableBackend,
)


def test_required_policy_rejects_an_unavailable_backend(tmp_path: Path) -> None:
    policy = SandboxPolicy.required(workspace_root=tmp_path)
    request = SandboxRequest(argv=("python", "--version"), cwd=tmp_path)

    with pytest.raises(SandboxUnavailableError, match="没有可用的沙箱后端"):
        UnavailableBackend().start(request, policy)


def test_request_rejects_a_cwd_outside_the_workspace(tmp_path: Path) -> None:
    policy = SandboxPolicy.required(workspace_root=tmp_path)
    request = SandboxRequest(argv=("python", "--version"), cwd=tmp_path.parent)

    with pytest.raises(PermissionError, match="工作区外"):
        request.validated(policy)
