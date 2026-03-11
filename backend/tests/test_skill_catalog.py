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
    assert "`二、MySQL巡检分析` 章节只保留 `2.1 整体风险概览`" in skill_text
    assert "### 2.1 整体风险概览" in template_text
    assert "### 2.2 MySQL实例分析" not in template_text
    assert "### 2.3 共性问题分析" not in template_text
    assert "{{instance_analysis_sections}}" not in template_text
    assert "{{capacity_patterns}}" not in template_text
    assert "{{stability_patterns}}" not in template_text
    assert "{{availability_patterns}}" not in template_text
    assert "/memories/reports/皮氏咖啡线上MySQL巡检报告<YYYYMMDD>.md" in skill_text
    assert "volcengine-rds-summary-<YYYYMMDD>.md" not in skill_text
    assert "<topic>-volcengine-rds-summary-<YYYYMMDD>.md" not in skill_text
    assert "分析汇总类请求" in skill_text
    assert "默认生成并保存 Markdown" in skill_text
    assert "不需要用户额外说“保存报告”或“生成文件”" in skill_text
    assert "如果用户表达分析汇总意图但没给范围，先追问目录或文件列表" in skill_text
    assert "范围内没有可用报告，明确告知并说明缺什么" in skill_text
    assert "### 3.1 实例汇总" in template_text
    assert "### 3.2 立即处理" not in template_text
    assert "### 3.3 近期跟进" not in template_text
    assert "### 3.4 长期治理" not in template_text
    assert "{{immediate_actions}}" not in template_text
    assert "{{follow_up_actions}}" not in template_text
    assert "{{long_term_actions}}" not in template_text
    assert "按“立即处理 / 近期跟进 / 长期治理”分组的建议" not in skill_text
    assert "本次汇总面向皮氏咖啡火山引擎生产环境 MySQL PaaS 数据库" in template_text
    assert "统计周期覆盖 {{time_range_summary}} 内生成的 RDS MySQL 巡检报告" in template_text
    assert "共收到 {{report_count}} 份报告，其中纳入本次汇总统计 {{included_count}} 份。" in template_text
    assert "本报告生成时间为 {{report_time}}" in template_text
    assert "默认基于用户指定时间窗口内的巡检结果，输出周报或月报形式的汇总结论。" in template_text
    assert "皮氏咖啡火山引擎上生产环境MySQL PaaS数据库" not in template_text
    assert "本次报告于 {{report_time}} 生成，默认基于用户指定时间窗口内的巡检结果输出周报 / 月报式总结。" not in template_text
    assert "已开启 MySQL 自动巡检的实例，基于火山引擎自动巡检评分结果进行分析" in template_text
    assert "100 分：健康。" in template_text
    assert "80–99 分：良好，存在部分指标需持续关注。" in template_text
    assert "60–79 分：及格，存在至少一项中等及以上风险，建议在两周内完成整改。" in template_text
    assert "60 分以下：不及格，存在多项中等及以上风险，需立即介入处理。" in template_text
    assert "未开启 MySQL 自动巡检的实例，应在本周期内完成自动巡检配置" in template_text
    assert "当前每月巡检一次，将会基于上一个月的巡检报告分析" not in template_text


def test_volcengine_rds_report_summarizer_locks_template_heading_order():
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

    assert "固定章节/标题顺序" in skill_text
    assert "不得新增、删除、改名、重排模板中已存在的固定章节或标题" in skill_text
    assert "只允许在模板已有占位符所在位置填充内容" in skill_text
    assert "`二、MySQL巡检分析` 章节只保留 `2.1 整体风险概览`，不要生成 `2.2`、`2.3` 小节" in skill_text
    assert "`instance_summary_rows` 只允许填充 `3.1 实例汇总` 表格行" in skill_text
    assert "`instance_summary_rows` 必须覆盖所有纳入统计的实例" in skill_text
    assert "`3.1 实例汇总` 中实例顺序必须与排序后的实例列表保持一致" in skill_text

    assert "固定章节/标题顺序，只替换占位符内容" in template_text
    assert "不得新增、删除、改名、重排模板中已存在的一级、二级、三级标题" in template_text
    assert "`二、MySQL巡检分析` 章节只保留 `2.1 整体风险概览`，不要新增 `2.2`、`2.3` 小节" in template_text
    assert "如需填充汇总表格，只能写入 `3.1 实例汇总` 下的 `{{instance_summary_rows}}`，且必须覆盖所有纳入统计的实例" in template_text
    assert "`3.1 实例汇总` 中各实例的展示顺序必须与排序后的实例列表完全一致" in template_text


def test_volcengine_rds_health_analyzer_locks_template_heading_order():
    backend_dir = Path(__file__).resolve().parents[1]
    skill_text = (
        backend_dir / "skills" / "volcengine-rds-health-analyzer" / "SKILL.md"
    ).read_text(encoding="utf-8")
    template_text = (
        backend_dir
        / "skills"
        / "volcengine-rds-health-analyzer"
        / "assets"
        / "inspection_report_template.md"
    ).read_text(encoding="utf-8")

    assert "凡是输出“巡检报告”类内容（无论是在聊天中直接展示，还是保存为 Markdown 文件），都必须先读取模板文件" in skill_text
    assert "`inspection_report_template.md` 是巡检 Markdown 报告的唯一骨架来源，必须固定章节/标题顺序" in skill_text
    assert "固定章节/标题顺序，只允许在模板已有占位符所在位置填充内容" in skill_text
    assert "不得新增、删除、改名、重排模板中已存在的固定章节或标题" in skill_text
    assert "保留模板中现有一级、二级标题顺序，以及 Markdown 表格、callout、分隔线和内部备注块" in skill_text
    assert "`{{cpu_node_breakdown}}`、`{{memory_node_breakdown}}`、`{{disk_node_breakdown}}`、`{{replication_node_breakdown}}`、`{{iops_network_node_breakdown}}` 只允许填充模板已有位置" in skill_text

    assert "固定章节/标题顺序，只替换占位符内容。" in template_text
    assert "不得新增、删除、改名、重排模板中已存在的一级、二级标题。" in template_text
    assert "保留模板中的 Markdown 表格、callout、分隔线和内部备注块。" in template_text
    assert "如果某个占位符对应节点拆分内容，必须填充固定列表头 `Node | Avg | Max | 风险级别 | 说明` 的 Markdown 表格。" in template_text


def test_volcengine_rds_health_analyzer_forbids_modifying_source_data():
    backend_dir = Path(__file__).resolve().parents[1]
    skill_text = (
        backend_dir / "skills" / "volcengine-rds-health-analyzer" / "SKILL.md"
    ).read_text(encoding="utf-8")
    template_text = (
        backend_dir
        / "skills"
        / "volcengine-rds-health-analyzer"
        / "assets"
        / "inspection_report_template.md"
    ).read_text(encoding="utf-8")

    assert "对用户输入、长期记忆命中的实例信息、脚本采集结果、以及最终写入报告的字段值，都必须按原值使用，不对任何数据做修改" in skill_text
    assert "不得改写、猜测修正、补全、截断、拼接、重新编码、改变大小写、四舍五入、格式化美化、单位换算、乘除换算、百分比折算或用估算值覆盖原值" in skill_text
    assert "分析结论、健康评分、风险等级可以新增，但它们属于派生内容，不得反向覆盖、替换或伪装成原始采集数据" in skill_text
    assert "所有填入占位符的实例 ID、实例名称、节点 ID、时间、配置值、监控值都必须来自原始输入或采集结果原文" in skill_text
    assert "无法确认时写“未获取”，不要估算、脑补或生成近似值" in skill_text

    assert "占位符内的实例信息、时间、配置值、监控值需按来源原值填写，不对任何数据做修改。" in template_text
    assert "无法确认时写“未获取”或“无异常”，不要估算、换算、四舍五入或生成近似值。" in template_text


def test_volcengine_rds_health_analyzer_uses_recent_3d_aux_window_for_long_ranges():
    backend_dir = Path(__file__).resolve().parents[1]
    skill_text = (
        backend_dir / "skills" / "volcengine-rds-health-analyzer" / "SKILL.md"
    ).read_text(encoding="utf-8")
    template_text = (
        backend_dir
        / "skills"
        / "volcengine-rds-health-analyzer"
        / "assets"
        / "inspection_report_template.md"
    ).read_text(encoding="utf-8")

    assert "当主窗口 `time_range >= 7d` 时，除主窗口采集外，必须额外执行一次最近 `3d` 的辅助采集" in skill_text
    assert "最近 `3d` 辅助窗口固定使用 `1h` 粒度，不跟随主窗口 `>= 7d` 时的 `6h` 粒度" in skill_text
    assert "`analysis_depth` 不影响这条双窗口规则；只要主窗口达到 `7d` 及以上，就执行最近 `3d` 辅助采集" in skill_text
    assert "主窗口继续写到 `./metric_data/instance_data.json`" in skill_text
    assert "最近 `3d` 辅助窗口写到 `./metric_data/instance_data_recent3d.json`" in skill_text
    assert "分析阶段按同一指标成对读取：先读主窗口结果，再读最近 `3d` 辅助窗口结果" in skill_text
    assert "如果用户显式要求只分析 `3d` 或更短时间范围，则不再追加第二个 `3d` 辅助窗口" in skill_text
    assert "如果最近 `3d` 辅助采集失败但主窗口成功，仍可输出主窗口分析，但必须明确写“最近 3 天辅助判断未获取”" in skill_text

    assert "主窗口异常 + 最近 `3d` 异常：判定为“持续性 / 当前仍存在的问题”" in skill_text
    assert "主窗口异常 + 最近 `3d` 正常：判定为“历史波动或阶段性问题”" in skill_text
    assert "主窗口正常 + 最近 `3d` 异常：判定为“最近新出现或近期加剧的问题”" in skill_text
    assert "主窗口正常 + 最近 `3d` 正常：维持健康 / 低风险结论" in skill_text

    assert "所有双窗口判断只能填入模板现有占位符位置" in skill_text
    assert "必须显式区分“主窗口（用户请求范围）”与“最近 3 天辅助窗口”" in skill_text
    assert "不允许用最近 `3d` 的数据覆盖主窗口数据，也不允许把主窗口数据改写成最近 `3d` 结论" in skill_text

    assert "当主窗口 `time_range >= 7d` 时，各指标分析说明需同时交代主窗口与最近 3 天辅助窗口的判断，但只能写在现有占位符位置，不得新增标题。" in template_text
