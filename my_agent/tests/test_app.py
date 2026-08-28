from __future__ import annotations

from pathlib import Path
from queue import Queue
from types import SimpleNamespace

import my_agent.app as app_module
from my_agent.command.builtin import register_builtin_commands
from my_agent.command.router import CommandRouter
from my_agent.memory.dream import DreamResult
from my_agent.tools.image_generation_tool import ImageGenerationTool


def test_run_repl_exits_for_slash_exit_without_calling_agent(monkeypatch) -> None:
    class Loop:
        runner = None

        def handle_user_message(self, **_request: object) -> str:
            raise AssertionError("/exit must be handled by the REPL before calling the agent")

    class DreamService:
        def start(self, on_complete) -> DreamResult:
            return DreamResult(status="running", message="Dreaming...")

    router = CommandRouter()
    register_builtin_commands(router, DreamService(), lambda _result: None)
    app_state = SimpleNamespace(
        loop=Loop(),
        session_id="test-session",
        command_router=router,
        background_messages=Queue(),
        dream_scheduler=None,
    )
    monkeypatch.setattr(app_module, "build_app", lambda env_file=None: app_state)
    monkeypatch.setattr(app_module, "prompt_with_images", lambda _prompt: ("/exit", []))

    app_module.run_repl()


def test_run_repl_handles_dream_command_without_calling_agent(monkeypatch) -> None:
    class Loop:
        runner = None

        def handle_user_message(self, **_request: object) -> str:
            raise AssertionError("/dream must be handled by the command router")

    class DreamService:
        def __init__(self) -> None:
            self.started = False

        def start(self, on_complete) -> DreamResult:
            self.started = True
            return DreamResult(status="running", message="Dreaming...")

    service = DreamService()
    router = CommandRouter()
    register_builtin_commands(router, service, lambda _result: None)
    app_state = SimpleNamespace(
        loop=Loop(),
        session_id="test-session",
        command_router=router,
        background_messages=Queue(),
        dream_scheduler=None,
    )
    prompts = iter([("/dream", []), ("/exit", [])])
    monkeypatch.setattr(app_module, "build_app", lambda env_file=None: app_state)
    monkeypatch.setattr(app_module, "prompt_with_images", lambda _prompt: next(prompts))

    app_module.run_repl()

    assert service.started is True


def test_run_repl_stops_dream_scheduler_when_exit_command_is_received(monkeypatch) -> None:
    class Loop:
        runner = None

        def handle_user_message(self, **_request: object) -> str:
            raise AssertionError("/exit must not be sent to the agent")

    class DreamService:
        def start(self, on_complete) -> DreamResult:
            return DreamResult(status="running", message="Dreaming...")

    class Scheduler:
        def __init__(self) -> None:
            self.started = False
            self.stopped = False

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

    router = CommandRouter()
    register_builtin_commands(router, DreamService(), lambda _result: None)
    scheduler = Scheduler()
    app_state = SimpleNamespace(
        loop=Loop(),
        session_id="test-session",
        command_router=router,
        background_messages=Queue(),
        dream_scheduler=scheduler,
    )
    monkeypatch.setattr(app_module, "build_app", lambda env_file=None: app_state)
    monkeypatch.setattr(app_module, "prompt_with_images", lambda _prompt: ("/exit", []))

    app_module.run_repl()

    assert scheduler.started is True
    assert scheduler.stopped is True


def test_build_app_uses_project_root_when_started_from_my_agent_directory(
    tmp_path: Path, monkeypatch
) -> None:
    launch_directory = tmp_path / "my_agent"
    launch_directory.mkdir()
    monkeypatch.chdir(launch_directory)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("MY_AGENT_SESSION_ID", "test-session")
    monkeypatch.setenv("MY_AGENT_HISTORY_LIMIT", "10")
    monkeypatch.setenv("MY_AGENT_IMAGE_API_KEY", "test-image-key")
    monkeypatch.setenv("MY_AGENT_SESSION_STORAGE_DIR", str(tmp_path / "sessions"))

    app_state = app_module.build_app()

    image_tool = app_state.loop.runner.tool_registry.get("generate_image")
    assert isinstance(image_tool, ImageGenerationTool)
    project_root = Path(app_module.__file__).resolve().parent.parent
    assert image_tool.workspace == project_root
    assert image_tool.output_dir == project_root / "my_agent" / "storage" / "generated-images"


def test_build_app_creates_a_new_session_for_each_start(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("MY_AGENT_SESSION_ID", "legacy-session")
    monkeypatch.setenv("MY_AGENT_HISTORY_LIMIT", "10")
    monkeypatch.setenv("MY_AGENT_SESSION_STORAGE_DIR", str(tmp_path / "sessions"))

    first_start = app_module.build_app()
    second_start = app_module.build_app()

    assert first_start.session_id != second_start.session_id
    assert first_start.session_id != "legacy-session"
