from pathlib import Path

from agent_profiles import get_agent_profile
from skill_catalog import load_skill_catalog, list_skills, resolve_skill_paths


def test_skill_catalog_loads_volcengine_rds_report_summarizer():
    catalog = load_skill_catalog()

    assert "volcengine-rds-report-summarizer" in catalog

    skill = catalog["volcengine-rds-report-summarizer"]
    assert skill.name == "volcengine-rds-report-summarizer"
    assert skill.description
    assert resolve_skill_paths(["volcengine-rds-report-summarizer"]) == [
        "./skills/volcengine-rds-report-summarizer"
    ]


def test_dba_agent_exposes_volcengine_rds_report_summarizer():
    profile = get_agent_profile("dba")

    assert "volcengine-rds-report-summarizer" in profile.skills
    assert any(
        skill.id == "volcengine-rds-report-summarizer"
        for skill in list_skills("dba")
    )


def test_volcengine_rds_report_summarizer_documents_actual_values():
    backend_dir = Path(__file__).resolve().parents[1]
    skill_text = (
        backend_dir / "skills" / "volcengine-rds-report-summarizer" / "SKILL.md"
    ).read_text(encoding="utf-8")
    template_text = (
        backend_dir
        / "skills"
        / "volcengine-rds-report-summarizer"
        / "assets"
        / "summary_report_template.md"
    ).read_text(encoding="utf-8")

    assert "内存、磁盘相关风险描述需同时给出百分比和实际数值" in skill_text
    assert "78%（约 25 GiB / 32 GiB）" in skill_text
    assert "内存、磁盘相关描述需同时给出百分比和实际数值" in template_text
    assert "`2.2 实例分析` 需要覆盖所有纳入统计的实例" in skill_text
    assert "### 2.2 实例分析" in template_text
