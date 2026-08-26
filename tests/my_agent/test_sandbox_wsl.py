from pathlib import Path

import my_agent.sandbox.wsl as wsl_module
from my_agent.sandbox import SandboxPolicy, SandboxRequest
from my_agent.sandbox.wsl import WslBubblewrapBackend


def test_wsl_backend_mounts_only_the_workspace_and_runtime(tmp_path: Path) -> None:
    backend = WslBubblewrapBackend(
        distro="Ubuntu",
        user="penn",
        path_converter=lambda path: "/mnt/d/workspace" if path == tmp_path else "",
    )
    request = SandboxRequest(argv=("python3", "--version"), cwd=tmp_path)

    command = backend.build_command(request, SandboxPolicy.required(tmp_path))

    assert command[:8] == (
        "wsl.exe",
        "--distribution",
        "Ubuntu",
        "--user",
        "penn",
        "--exec",
        "bwrap",
        "--unshare-all",
    )
    assert "--unshare-net" in command
    assert "--tmpfs" in command
    assert "--ro-bind" in command
    assert "/workspace" in command
    assert "/mnt/d/workspace" in command
    assert ("--ro-bind", "/", "/") not in zip(command, command[1:], command[2:])
    assert command[-3:] == ("--", "python3", "--version")


def test_wsl_backend_logs_the_sandbox_command(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    backend = WslBubblewrapBackend(
        distro="Ubuntu",
        user="penn",
        path_converter=lambda path: "/mnt/d/workspace" if path == tmp_path else "",
    )
    monkeypatch.setattr(wsl_module.subprocess, "Popen", lambda *args, **kwargs: object())
    messages: list[tuple[str, tuple[object, ...]]] = []
    monkeypatch.setattr(
        wsl_module.logger,
        "info",
        lambda message, *args: messages.append((message, args)),
    )

    backend.start(
        SandboxRequest(argv=("python3", "--version"), cwd=tmp_path),
        SandboxPolicy.required(tmp_path),
    )

    assert messages[0][0] == "沙箱 WSL Bubblewrap 执行：%s"
    assert "python3 --version" in str(messages[0][1])
