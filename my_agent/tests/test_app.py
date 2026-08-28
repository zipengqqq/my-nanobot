from __future__ import annotations

from pathlib import Path

import my_agent.app as app_module
from my_agent.tools.image_generation_tool import ImageGenerationTool


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
