from pathlib import Path

from agent_profiles import get_agent_profile
from skill_catalog import load_skill_catalog, list_skills, resolve_skill_paths


def read_backend_text(*parts: str) -> str:
    backend_dir = Path(__file__).resolve().parents[1]
    return (backend_dir.joinpath(*parts)).read_text(encoding="utf-8")


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
    skill_text = read_backend_text(
        "skills", "volcengine-rds-report-summarizer", "SKILL.md"
    )
    template_text = read_backend_text(
        "skills",
        "volcengine-rds-report-summarizer",
        "assets",
        "summary_report_template.md",
    )

    assert "25 GiB / 32 GiB" in skill_text
    assert "25 GiB / 32 GiB" in template_text
    assert "/memories/reports/" in skill_text
    assert "volcengine-rds-summary-<YYYYMMDD>.md" not in skill_text
    assert "<topic>-volcengine-rds-summary-<YYYYMMDD>.md" not in skill_text
    assert "{{instance_analysis_sections}}" not in template_text
    assert "{{capacity_patterns}}" not in template_text
    assert "{{stability_patterns}}" not in template_text
    assert "{{availability_patterns}}" not in template_text
    assert "### 2.1" in template_text
    assert "### 2.2" not in template_text
    assert "### 2.3" not in template_text
    assert "### 3.1" in template_text
    assert "### 3.2" not in template_text
    assert "### 3.3" not in template_text
    assert "### 3.4" not in template_text


def test_volcengine_rds_report_summarizer_locks_template_heading_order():
    skill_text = read_backend_text(
        "skills", "volcengine-rds-report-summarizer", "SKILL.md"
    )
    template_text = read_backend_text(
        "skills",
        "volcengine-rds-report-summarizer",
        "assets",
        "summary_report_template.md",
    )

    assert "summary_report_template.md" in skill_text
    assert "instance_summary_rows" in skill_text
    assert "{{instance_summary_rows}}" in template_text
    assert "## 二" in template_text
    assert "### 2.1" in template_text
    assert "### 2.2" not in template_text
    assert "### 2.3" not in template_text
    assert "### 3.1" in template_text
    assert "### 3.2" not in template_text
    assert "### 3.3" not in template_text
    assert "### 3.4" not in template_text


def test_volcengine_rds_health_analyzer_locks_template_heading_order():
    skill_text = read_backend_text(
        "skills", "volcengine-rds-health-analyzer", "SKILL.md"
    )
    template_text = read_backend_text(
        "skills",
        "volcengine-rds-health-analyzer",
        "assets",
        "inspection_report_template.md",
    )

    assert "inspection_report_template.md" in skill_text
    assert "{{cpu_node_breakdown}}" in skill_text
    assert "{{memory_node_breakdown}}" in skill_text
    assert "{{disk_node_breakdown}}" in skill_text
    assert "{{replication_node_breakdown}}" in skill_text
    assert "{{iops_network_node_breakdown}}" in skill_text
    assert "`Node | Avg | Median | Max | 风险级别 | 说明`" in skill_text
    assert "`weighted = 0.5 * avg + 0.5 * median`" in skill_text

    assert "{{cpu_node_breakdown}}" in template_text
    assert "{{memory_node_breakdown}}" in template_text
    assert "{{disk_node_breakdown}}" in template_text
    assert "{{replication_node_breakdown}}" in template_text
    assert "{{iops_network_node_breakdown}}" in template_text
    assert "Node | Avg | Median | Max | 风险级别 | 说明" in template_text
    assert "{{cpu_median}}" in template_text
    assert "{{memory_median}}" in template_text
    assert "{{disk_median}}" in template_text
    assert "{{qps_median}}" in template_text
    assert "{{tps_median}}" in template_text
    assert "{{replication_median}}" in template_text
    assert "{{iops_median}}" in template_text
    assert "{{network_in_median}}" in template_text
    assert "{{network_out_median}}" in template_text


def test_volcengine_rds_health_analyzer_forbids_modifying_source_data():
    skill_text = read_backend_text(
        "skills", "volcengine-rds-health-analyzer", "SKILL.md"
    )
    template_text = read_backend_text(
        "skills",
        "volcengine-rds-health-analyzer",
        "assets",
        "inspection_report_template.md",
    )

    assert "AK/SK" in skill_text
    assert "`instance_id`" in skill_text
    assert "`instance_name`" in skill_text
    assert "`Node ID`" in skill_text
    assert "{{instance_id}}" in template_text
    assert "{{instance_name}}" in template_text
    assert "{{report_time}}" in template_text
    assert "{{cpu_avg}}" in template_text
    assert "{{cpu_median}}" in template_text


def test_volcengine_rds_health_analyzer_uses_recent_3d_aux_window_for_long_ranges():
    skill_text = read_backend_text(
        "skills", "volcengine-rds-health-analyzer", "SKILL.md"
    )
    template_text = read_backend_text(
        "skills",
        "volcengine-rds-health-analyzer",
        "assets",
        "inspection_report_template.md",
    )

    assert "time_range >= 7d" in skill_text
    assert "instance_data.json" in skill_text
    assert "instance_data_recent3d.json" in skill_text
    assert "instance_data_*.json" in skill_text
    assert "instance_data_recent3d_*.json" in skill_text
    assert "`3d`" in skill_text
    assert "主窗口统一使用 `5m` 粒度采集" in skill_text
    assert "最近 `3d` 辅助窗口也使用 `5m` 粒度" in skill_text
    assert "| `1d - <7d` | `1h` |" not in skill_text
    assert "| `>= 7d` | `6h` |" not in skill_text
    assert "time_range >= 7d" in template_text


def test_volcengine_rds_health_analyzer_documents_metric_data_retention_cleanup():
    skill_text = read_backend_text(
        "skills", "volcengine-rds-health-analyzer", "SKILL.md"
    )

    assert "metric_data retention" in skill_text
    assert "./metric_data/" in skill_text
    assert "`30`" in skill_text
    assert "`--retention-days <days>`" in skill_text
    assert "`--skip-cleanup`" in skill_text


def test_volcengine_rds_health_analyzer_documents_median_and_weighted_analysis():
    skill_text = read_backend_text(
        "skills", "volcengine-rds-health-analyzer", "SKILL.md"
    )
    template_text = read_backend_text(
        "skills",
        "volcengine-rds-health-analyzer",
        "assets",
        "inspection_report_template.md",
    )

    assert "`summary.median`" in skill_text
    assert "`node_summaries[*].median`" in skill_text
    assert "`summary.weighted`" in skill_text
    assert "`node_summaries[*].weighted`" in skill_text
    assert "`summary.range`" in skill_text
    assert "`node_summaries[*].range`" in skill_text
    assert "`evidence.distribution`" in skill_text
    assert "`evidence.variability`" in skill_text
    assert "`evidence.spikes.sliding_mad`" in skill_text
    assert "`node_summaries[*].evidence`" in skill_text
    assert "先读 `summary`" in skill_text
    assert "再读 `evidence`" in skill_text
    assert "sliding_mad" in skill_text
    assert "6 x MAD" in skill_text
    assert "`weighted = 0.5 * avg + 0.5 * median`" in skill_text
    assert "按加权值" in skill_text
    assert "{{cpu_range}}" in template_text
    assert "{{memory_range}}" in template_text
    assert "{{disk_range}}" in template_text
    assert "{{qps_range}}" in template_text
    assert "{{tps_range}}" in template_text
    assert "{{replication_range}}" in template_text
    assert "{{iops_range}}" in template_text
    assert "{{network_in_range}}" in template_text
    assert "{{network_out_range}}" in template_text


def test_volcengine_rds_health_analyzer_documents_spike_risk_tiers():
    skill_text = read_backend_text(
        "skills", "volcengine-rds-health-analyzer", "SKILL.md"
    )

    assert "`evidence.spikes.risk_tier`" in skill_text
    assert "`evidence.spikes.risk_reason`" in skill_text
    assert "`none`" in skill_text
    assert "`low`" in skill_text
    assert "`high`" in skill_text
    assert "CPU" in skill_text
    assert "70%" in skill_text
    assert "qps" in skill_text
    assert "capacity model" in skill_text
    assert "`risk_tier = high`" in skill_text
