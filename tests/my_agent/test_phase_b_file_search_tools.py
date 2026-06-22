from pathlib import Path

from my_agent.app import build_app
from my_agent.tools.filesystem_tool import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from my_agent.tools.patch_tool import ApplyPatchTool
from my_agent.tools.search_tool import FindFilesTool, GrepTool


def test_build_app_registers_file_and_search_default_tools(tmp_path: Path) -> None:
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
    ]


def test_write_edit_find_and_grep_tools_support_basic_coding_flow(tmp_path: Path) -> None:
    write_tool = WriteFileTool(root=tmp_path)
    edit_tool = EditFileTool(root=tmp_path)
    find_tool = FindFilesTool(root=tmp_path)
    grep_tool = GrepTool(root=tmp_path)
    read_tool = ReadFileTool(root=tmp_path)
    list_tool = ListDirTool(root=tmp_path)

    write_result = write_tool.run({"path": "src/demo.py", "content": "print('hello')\n"})
    initial_read = read_tool.run({"path": "src/demo.py"})
    edit_result = edit_tool.run(
        {
            "path": "src/demo.py",
            "old_text": "hello",
            "new_text": "phase-b",
        }
    )
    found = find_tool.run(
        {
            "path": ".",
            "query": "demo",
            "glob": "src/**",
            "type": "py",
        }
    )
    grep_result = grep_tool.run({"path": ".", "pattern": "phase-b"})

    assert write_result == f"Successfully wrote 15 characters to {tmp_path / 'src' / 'demo.py'}"
    assert initial_read == "print('hello')\n"
    assert edit_result == f"Successfully edited {tmp_path / 'src' / 'demo.py'}"
    assert found == "src/demo.py"
    assert grep_result == "src/demo.py"
    assert read_tool.run({"path": "src/demo.py"}) == "print('phase-b')\n"
    assert list_tool.run({"path": "src"}) == "demo.py"


def test_edit_file_can_create_new_file_with_empty_old_text(tmp_path: Path) -> None:
    edit_tool = EditFileTool(root=tmp_path)

    result = edit_tool.run(
        {
            "path": "pkg/new_file.py",
            "old_text": "",
            "new_text": "VALUE = 1\n",
        }
    )

    assert result == f"Successfully created {tmp_path / 'pkg' / 'new_file.py'}"
    assert (tmp_path / "pkg" / "new_file.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_apply_patch_supports_add_replace_and_dry_run(tmp_path: Path) -> None:
    patch_tool = ApplyPatchTool(root=tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "main.py").write_text("print('old')\n", encoding="utf-8")

    dry_run = patch_tool.run(
        {
            "edits": [
                {
                    "path": "pkg/main.py",
                    "action": "replace",
                    "old_text": "old",
                    "new_text": "preview",
                },
                {
                    "path": "pkg/helper.py",
                    "action": "add",
                    "new_text": "VALUE = 1\n",
                },
            ],
            "dry_run": True,
        }
    )

    result = patch_tool.run(
        {
            "edits": [
                {
                    "path": "pkg/main.py",
                    "action": "replace",
                    "old_text": "old",
                    "new_text": "new",
                },
                {
                    "path": "pkg/helper.py",
                    "action": "add",
                    "new_text": "VALUE = 1\n",
                },
            ]
        }
    )

    assert dry_run == "Patch dry-run succeeded:\n- update pkg/main.py (+1/-1)\n- add pkg/helper.py (+1/-0)"
    assert result == "Patch applied:\n- update pkg/main.py (+1/-1)\n- add pkg/helper.py (+1/-0)"
    assert (tmp_path / "pkg" / "main.py").read_text(encoding="utf-8") == "print('new')\n"
    assert (tmp_path / "pkg" / "helper.py").read_text(encoding="utf-8") == "VALUE = 1\n"
