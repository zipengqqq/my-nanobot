from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


@dataclass(frozen=True, slots=True)
class SkillEntry:
    name: str
    path: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "path": self.path, "source": self.source}


class SkillsLoader:
    """发现磁盘上的 SKILL.md，并为模型生成渐进加载摘要。"""

    def __init__(
        self,
        workspace: Path,
        builtin_skills_dir: Path | None = BUILTIN_SKILLS_DIR,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace_skills_dir = self.workspace / "skills"
        self.builtin_skills_dir = builtin_skills_dir

    def list_skills(self) -> list[dict[str, str]]:
        workspace_entries = self._entries_from_dir(
            self.workspace_skills_dir,
            source="workspace",
            path_prefix="skills",
        )
        workspace_names = {entry.name for entry in workspace_entries}
        builtin_entries = self._entries_from_dir(
            self.builtin_skills_dir,
            source="builtin",
            path_prefix=None,
            skip_names=workspace_names,
        )
        return [entry.to_dict() for entry in [*workspace_entries, *builtin_entries]]

    def load_skill(self, name: str) -> str | None:
        if not self._valid_name(name):
            return None
        for root in (self.workspace_skills_dir, self.builtin_skills_dir):
            skill_file = self._skill_file(root, name)
            if skill_file is not None:
                return skill_file.read_text(encoding="utf-8")
        return None

    def build_summary(self) -> str:
        lines: list[str] = []
        for entry in self.list_skills():
            metadata = self._metadata(entry["name"])
            description = str(metadata.get("description", entry["name"])).strip()
            lines.append(f"- **{entry['name']}**: {description} (`{entry['path']}`)")
        return "\n".join(lines)

    def _entries_from_dir(
        self,
        root: Path | None,
        *,
        source: str,
        path_prefix: str | None,
        skip_names: set[str] | None = None,
    ) -> list[SkillEntry]:
        if root is None or not root.is_dir():
            return []
        entries: list[SkillEntry] = []
        for skill_dir in sorted(root.iterdir(), key=lambda item: item.name):
            if not skill_dir.is_dir() or (skip_names and skill_dir.name in skip_names):
                continue
            skill_file = self._skill_file(root, skill_dir.name)
            if skill_file is None:
                continue
            entries.append(
                SkillEntry(
                    name=skill_dir.name,
                    path=(
                        f"{path_prefix}/{skill_dir.name}/SKILL.md"
                        if path_prefix is not None
                        else str(skill_file)
                    ),
                    source=source,
                )
            )
        return entries

    @staticmethod
    def _skill_file(root: Path | None, name: str) -> Path | None:
        if root is None:
            return None
        skill_file = root / name / "SKILL.md"
        if not skill_file.is_file():
            return None
        resolved_root = root.resolve()
        resolved_file = skill_file.resolve()
        try:
            resolved_file.relative_to(resolved_root)
        except ValueError:
            return None
        return resolved_file

    def _metadata(self, name: str) -> dict[str, object]:
        content = self.load_skill(name)
        if content is None or not content.startswith("---\n"):
            return {}
        header, separator, _ = content[4:].partition("\n---\n")
        if not separator:
            return {}
        try:
            parsed = yaml.safe_load(header)
        except yaml.YAMLError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _valid_name(name: str) -> bool:
        return bool(name) and Path(name).name == name and name not in {".", ".."}
