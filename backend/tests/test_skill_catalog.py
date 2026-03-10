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
