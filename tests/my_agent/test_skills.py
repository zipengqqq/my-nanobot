from __future__ import annotations

from pathlib import Path

from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.provider import ModelResponse, ToolCall
from my_agent.agent.runner import AgentRunner
from my_agent.agent.skills import BUILTIN_SKILLS_DIR, SkillsLoader
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry


def _write_skill(root: Path, name: str, description: str, body: str) -> Path:
    skill_file = root / name / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return skill_file


def test_workspace_skill_overrides_builtin_skill(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    builtin_skills = tmp_path / "builtin"
    _write_skill(builtin_skills, "weather", "builtin weather", "builtin instructions")
    workspace_skill = _write_skill(
        workspace / "skills",
        "weather",
        "workspace weather",
        "workspace instructions",
    )

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin_skills)

    assert loader.list_skills() == [
        {"name": "weather", "path": "skills/weather/SKILL.md", "source": "workspace"}
    ]
    assert loader.load_skill("weather") == workspace_skill.read_text(encoding="utf-8")


def test_context_lists_skills_and_instructs_agent_to_read_them(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write_skill(
        workspace / "skills",
        "weather",
        "Get weather without an API key.",
        "Use web_fetch for a public weather service.",
    )
    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=tmp_path / "builtin")
    context = ContextBuilder(system_prompt="You are a test agent.", skills=loader)

    messages = context.build_messages(history=[], user_text="What is the weather?")

    system_prompt = messages[0]["content"]
    assert "# Skills" in system_prompt
    assert "weather" in system_prompt
    assert "Get weather without an API key." in system_prompt
    assert "skills/weather/SKILL.md" in system_prompt
    assert "read_file" in system_prompt


def test_skills_summary_reads_description_from_crlf_frontmatter(tmp_path: Path) -> None:
    skill_file = tmp_path / "skills" / "weather" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text(
        "---\r\nname: weather\r\ndescription: CRLF weather description\r\n---\r\n\r\n# Weather\r\n",
        encoding="utf-8",
        newline="",
    )
    loader = SkillsLoader(workspace=tmp_path, builtin_skills_dir=None)

    assert "CRLF weather description" in loader.build_summary()


class _SkillReadingProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, object]]] = []

    def generate(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
    ) -> ModelResponse:
        _ = tools
        self.calls.append(messages)
        if len(self.calls) == 1:
            return ModelResponse(
                tool_call=ToolCall(
                    id="read-weather-skill",
                    name="read_file",
                    arguments={"path": "skills/weather/SKILL.md"},
                )
            )
        return ModelResponse(text="Weather skill loaded.")


def test_agent_can_read_discovered_skill_during_tool_loop(tmp_path: Path) -> None:
    _write_skill(
        tmp_path / "skills",
        "weather",
        "Get weather without an API key.",
        "Use web_fetch for a public weather service.",
    )
    provider = _SkillReadingProvider()
    loop = AgentLoop(
        session_manager=SessionManager(history_limit=3),
        context_builder=ContextBuilder(
            system_prompt="You are a test agent.",
            skills=SkillsLoader(workspace=tmp_path, builtin_skills_dir=tmp_path / "builtin"),
        ),
        runner=AgentRunner(
            provider=provider,
            tool_registry=ToolRegistry.with_defaults(root=tmp_path),
        ),
    )

    reply = loop.handle_user_message(session_id="skill-test", user_text="What is the weather?")

    assert reply == "Weather skill loaded."
    assert "weather" in provider.calls[0][0]["content"]
    assert provider.calls[1][-1] == {
        "role": "tool",
        "tool_call_id": "read-weather-skill",
        "content": "---\nname: weather\ndescription: Get weather without an API key.\n---\n\n"
        "Use web_fetch for a public weather service.\n",
    }


def test_builtin_weather_skill_is_discoverable() -> None:
    loader = SkillsLoader(workspace=Path.cwd())

    assert any(skill["name"] == "weather" for skill in loader.list_skills())


def test_builtin_skill_can_be_read_outside_the_workspace(tmp_path: Path) -> None:
    loader = SkillsLoader(workspace=tmp_path)
    weather = next(skill for skill in loader.list_skills() if skill["name"] == "weather")
    registry = ToolRegistry.with_defaults(
        root=tmp_path,
        extra_read_roots=[BUILTIN_SKILLS_DIR],
    )

    result = registry.execute("read_file", {"path": weather["path"]})

    assert result.startswith("---\nname: weather\n")


def test_read_file_rejects_paths_outside_the_workspace(tmp_path: Path) -> None:
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_text("private", encoding="utf-8")
    registry = ToolRegistry.with_defaults(root=tmp_path)

    result = registry.execute("read_file", {"path": str(outside_file)})

    assert "Path escapes allowed read directories" in result
