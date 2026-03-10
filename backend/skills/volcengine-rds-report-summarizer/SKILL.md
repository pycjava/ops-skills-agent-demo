---
name: volcengine-rds-report-summarizer
description: "汇总多个由 volcengine-rds-health-analyzer 生成的 Markdown 巡检报告并输出跨实例周报式总结。当用户要批量分析多个 RDS 实例巡检报告、做风险总览、归纳共性问题或生成管理摘要时使用。"
---

# Volcengine RDS 巡检报告汇总

读取多个已有巡检 Markdown 报告，做跨实例二次分析。这个 skill 不采集新指标，不调用云 API，不重跑 `volcengine-rds-health-analyzer`。

## 工具边界

- `glob`：只用于枚举用户明确指定范围内的 `.md` 文件
- `read_file`：逐个读取候选报告
- `grep`：只做轻量定位，不替代通读和总结
- `write_file` / `edit_file`：仅在用户明确要求“保存报告”或“生成文件”时写入 `/memories/reports/`

不要：

- 不要扫描整个仓库或默认目录，除非用户明确给出该目录
- 不要调用云 API、数据库、shell 脚本或 `volcengine-rds-health-analyzer` 的采集脚本
- 不要把单实例报告逐段改写成“汇总”，要做跨实例归纳

## 输入规则

- 默认输入是：
  - 一个目录路径，或
  - 多个明确的 Markdown 文件路径
- 只处理用户指定范围内的 `.md`
- 如果范围内没有可用报告，明确告知并说明缺什么
- 如果用户只说“汇总报告”但没给范围，先追问目录或文件列表

## 报告有效性校验

仅纳入由 `volcengine-rds-health-analyzer` 生成的 Markdown 报告。优先检查这些特征：

- 标题或正文包含“火山引擎RDS MySQL巡检报告”
- 存在这些核心章节中的大部分：`巡检概要`、`健康评分`、`核心指标分析`、`异常发现`、`行动建议`
- 文末或正文明确表明这是 `volcengine-rds-health-analyzer` Skill 的输出

满足明显特征则纳入；明显不符则跳过，并在最终结果里列出“未纳入统计”的原因。

## 标准流程

1. 用 `glob` 找到用户指定范围内的 `.md`
2. 用 `read_file` 逐个读取候选报告
3. 对每份有效报告至少提取这些信息：
   - `instance_id`
   - `instance_name`
   - `report_time`
   - `time_range_label`
   - `health_score`
   - `health_rating`
   - `health_summary`
   - 高 / 中 / 低优先级异常
   - `立即处理`、`需要关注`、`长期建议`
4. 先做单报告摘要，再做跨实例汇总，不要边读边下全局结论
5. 按风险优先级排序实例：
   - 先按风险级别：高 > 中 > 低
   - 再按健康评分从低到高
   - 再按高优先级异常数量从多到少
6. 汇总时突出：
   - 总体风险分布
   - 最需要关注的实例 Top N
   - 跨实例重复出现的问题
   - 可执行行动建议
   - 数据质量或覆盖范围不足

## 风险归类

优先复用报告中的 `health_rating` 和 `health_score`，不要重算底层监控评分。

- 若 `health_rating` 已明确表示高风险 / 警告 / 健康 / 优秀，直接沿用其语义
- 若只有 `health_score`：
  - `< 70` 视为高风险
  - `70-84` 视为中风险
  - `>= 85` 视为低风险
- 若评分缺失：
  - 存在明确“立即处理”事项或高优先级异常，视为高风险
  - 否则若存在中优先级异常或“需要关注”事项，视为中风险
  - 否则视为低风险，但要标记“基于不完整数据推断”

## 共性问题归纳

优先把问题归到这几类，再总结重复出现的实例：

- CPU 持续偏高或波动明显
- 内存压力偏高
- 磁盘使用率偏高
- 复制延迟异常
- QPS / TPS 波动或突刺明显
- IOPS 或网络负载异常

只写跨实例重复出现、且对容量、性能或稳定性有意义的模式。没有明确证据时，不要把根因写成确定结论。

## 默认输出结构

保存 Markdown 时，默认按线下巡检报告风格输出这个顺序：

1. `封面信息`
2. `环境巡检说明`
3. `MySQL巡检分析`
4. `巡检汇总及问题建议`
5. `附录`

写作要求：

- 整体风格面向正式巡检报告，同时保留跨实例汇总的管理视角
- 每个实例只保留最关键的 `1-3` 个风险点，不要逐实例复述全部指标
- 如果所有实例都较健康，也要明确写出“本批次未发现需要立即升级处理的共性风险”

## 聊天回复格式

建议直接给出：

- 报告总数、纳入数、跳过数
- 风险分布
- Top 风险实例列表
- `3` 条以内最重要的共性问题
- 按“立即处理 / 近期跟进 / 长期治理”分组的建议

## 保存 Markdown

只有用户明确要求“保存报告”或“生成文件”时才写文件。

保存前：

- 先读取 `./skills/volcengine-rds-report-summarizer/assets/summary_report_template.md`
- 按模板结构填充，不要改一级、二级标题顺序
- 模板中的 `customer_name`、`inspector_name`、`instance_summary_rows` 也需要补齐；无法判断时写“未获取”或“无”
- 没有数据的字段写“未获取”或“无”

保存路径：

- `/memories/reports/volcengine-rds-summary-<YYYYMMDD>.md`
- 若用户给了主题，可用 `/memories/reports/<topic>-volcengine-rds-summary-<YYYYMMDD>.md`

保存成功后，明确说明这是由 `volcengine-rds-report-summarizer` Skill 生成的汇总报告，可在页面中直接下载。
