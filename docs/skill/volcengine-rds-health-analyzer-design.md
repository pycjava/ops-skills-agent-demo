# Volcengine RDS 单实例巡检 Skill 设计说明

## 1. Skill 定位

`volcengine-rds-health-analyzer` 用于对单个 Volcengine RDS MySQL 实例进行只读巡检。它的职责包括：

- 采集实例信息和监控指标
- 读取采集结果进行结构化分析
- 生成健康评分、异常结论和行动建议
- 在用户要求时生成标准化巡检 Markdown 报告

它不是数据库 SQL 诊断工具，也不是多实例汇总工具。

## 2. 设计目标

- 把云上单实例巡检流程标准化。
- 把采集与分析解耦：先采集 JSON，再基于 JSON 做分析。
- 把主窗口、最近 `3d`、最近 `24h` 的语义显式化，避免短期波动覆盖长期结论。
- 用模板约束报告结构，确保输出可复用、可下载、可汇总。

## 3. 输入与上下文设计

核心输入包括：

- `instance_id`
- `region`
- `time_range`
- `analysis_depth`
- `credential_ref`

其中：

- `credential_ref` 优先来自长期记忆或凭证注册表。
- 真正的 `AK/SK` 由脚本结合 `backend/.env` 解析，不要求用户在聊天中明文提供。

## 4. 采集与分析分离

### 4.1 采集阶段

采集阶段只负责运行：

- `backend/skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`

采集结果输出为 `backend/metric_data/` 下的 JSON 文件。

### 4.2 分析阶段

分析阶段不再调用云 API，而是读取已有 JSON：

- 先读 `summary`
- 再读 `evidence`
- 只有在异常指标上才回看 `nodes` / `data_points`

设计原因：

- 降低上下文体积
- 让分析基于稳定中间结果
- 便于问题复盘和后续汇总

## 5. 时间窗口语义

该 Skill 特别强调多时间窗口：

- **主窗口**：用户请求的长期窗口，用于长期趋势和容量判断
- **最近 `3d` 辅助窗口**：用于判断问题是否仍在持续
- **最近 `24h` 辅助窗口**：用于识别最新出现的短时异常

窗口解释规则是设计重点：

- 主窗口异常 + 最近 `3d` 异常：持续性问题
- 主窗口异常 + 最近 `3d` 正常：历史或阶段性问题
- 主窗口正常 + 最近 `3d` 异常：近期新发问题
- 主窗口正常 + 最近 `3d` 正常 + 最近 `24h` 异常：最新短时异常

## 6. 指标与评分模型

### 6.1 核心指标

重点覆盖：

- `cpu`
- `memory`
- `disk_util`
- `qps`
- `tps`
- `replication_delay`
- `IOPSRate`
- `network_in`
- `network_out`

### 6.2 分析视角

Skill 使用更平衡的统计视角，而不是只看平均值：

- `avg`
- `median`
- `p95`
- `range`
- `pressure.level`
- `saturation.level`
- `sliding_mad` 尖峰识别

### 6.3 多节点策略

在多节点指标上，既输出实例级结论，也输出节点级热点结论，并禁止臆测节点角色。

## 7. 依赖资产

该 Skill 当前依赖：

- `backend/skills/volcengine-rds-health-analyzer/SKILL.md`
- `backend/skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`
- `backend/skills/volcengine-rds-health-analyzer/assets/inspection_report_template.md`

模板的作用非常关键：报告输出不是自由发挥，而是严格填充固定结构。

## 8. 报告生成设计

在用户要求“保存报告”或“生成文件”时，Skill 会：

1. 读取固定模板
2. 把采集和分析结果填入模板占位符
3. 写入 `/memories/reports/<sanitized_instance_name>-inspection-<YYYYMMDD>.md`

这样设计的价值：

- 前端可直接识别为 Skill 报告并提供下载
- 汇总 Skill 可稳定消费这些单实例报告
- 不同批次报告结构保持一致

## 9. 安全边界

- 只做只读巡检，不直接连接数据库执行 SQL。
- 不在聊天中暴露真实 `AK/SK`。
- 不允许为了分析 JSON 再临时生成额外脚本。
- `execute` 只用于采集脚本或必要非分析目录操作，不用于 ad-hoc 数据分析。

## 10. 与其他 Skill 的边界

- 单条 SQL 慢查询分析应交给 `mysql-sql-analyzer`。
- 多份单实例报告汇总应交给 `volcengine-rds-report-summarizer`。
- 纯 Markdown 排版问题不属于该 Skill 的主职责。

## 11. 失败场景与回退

- 采集失败时应明确说明缺失环节，不输出高置信结论。
- 辅助窗口缺失时，仍可基于主窗口分析，但必须显式说明证据不完整。
- 模板写入失败时，不应伪称报告已成功生成。

## 12. 设计取舍

- 采集与分析分离，可复盘、可复用，但步骤更多。
- 模板强约束保证一致性，但降低了自由表达空间。
- 多窗口分析提高判断质量，但增加了规则复杂度。
