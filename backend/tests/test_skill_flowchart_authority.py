from pathlib import Path


FLOWCHART_AUTHORITY_MARKER = "【DOT流程图权威规则】"
DOT_AUTHORITY_PHRASE = "DOT 决策流程图是权威执行规范"
DOT_PRECEDENCE_PHRASE = "冲突时，以 DOT 流程图为准"


def test_all_local_dot_skills_declare_flowchart_authority():
    backend_dir = Path(__file__).resolve().parents[1]
    dot_skill_paths: list[Path] = []

    for skill_path in sorted((backend_dir / "skills").glob("*/SKILL.md")):
        skill_text = skill_path.read_text(encoding="utf-8")
        if "```dot" not in skill_text:
            continue

        dot_skill_paths.append(skill_path)
        assert FLOWCHART_AUTHORITY_MARKER in skill_text
        assert DOT_AUTHORITY_PHRASE in skill_text
        assert DOT_PRECEDENCE_PHRASE in skill_text

    assert dot_skill_paths
