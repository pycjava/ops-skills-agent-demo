from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from agent_profiles import get_agent_profile
from config import SKILLS_DIR
from utils.logger import logger


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    id: str
    name: str
    description: str
    path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }


def _parse_skill_metadata(skill_dir: Path) -> SkillMetadata:
    name = skill_dir.name
    description = ""
    skill_file = skill_dir / "SKILL.md"

    try:
        content = skill_file.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error(f"读取技能 {skill_dir.name} 时出错: {exc}")
        return SkillMetadata(
            id=skill_dir.name,
            name=skill_dir.name,
            description="",
            path=f"./skills/{skill_dir.name}",
        )

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"').strip("'")

    return SkillMetadata(
        id=skill_dir.name,
        name=name or skill_dir.name,
        description=description,
        path=f"./skills/{skill_dir.name}",
    )


def load_skill_catalog() -> dict[str, SkillMetadata]:
    skills_path = Path(SKILLS_DIR)
    if not skills_path.exists():
        return {}

    catalog: dict[str, SkillMetadata] = {}
    for skill_dir in sorted(skills_path.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue
        metadata = _parse_skill_metadata(skill_dir)
        catalog[metadata.id] = metadata
    return catalog


def list_skills(agent_id: str | None = None) -> list[SkillMetadata]:
    catalog = load_skill_catalog()
    if not agent_id:
        return list(catalog.values())

    profile = get_agent_profile(agent_id)
    return [catalog[skill_id] for skill_id in profile.skills if skill_id in catalog]


def resolve_skill_paths(skill_ids: Iterable[str]) -> list[str]:
    catalog = load_skill_catalog()
    missing = [skill_id for skill_id in skill_ids if skill_id not in catalog]
    if missing:
        raise ValueError(f"未找到以下 Skills: {', '.join(missing)}")
    return [catalog[skill_id].path for skill_id in skill_ids]

