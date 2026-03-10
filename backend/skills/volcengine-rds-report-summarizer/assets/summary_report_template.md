# {{customer_name}}

## 线上 MySQL 资源巡检报告

- 巡检区间：{{time_range_summary}}
- 巡检日期：{{report_time}}
- 巡检人：{{inspector_name}}

> 使用说明：
> - 按本模板的章节顺序输出，保留一级、二级标题及编号结构。
> - 将 `{{...}}` 占位符替换为实际汇总结果；没有数据时写“未获取”或“无”。
> - 内存、磁盘相关描述需同时给出百分比和实际数值，例如 `78%（约 25 GiB / 32 GiB）`、`85%（约 850 GiB / 1 TiB）`；无法换算时写“未获取”。
> - 这是基于多个 `volcengine-rds-health-analyzer` 单实例 Markdown 巡检报告的二次汇总，格式参考线下巡检报告样式。

## 目录

1. 一、环境巡检说明
2. 二、MySQL巡检分析
3. 三、巡检汇总及问题建议
4. 四、附录

---

## 一、环境巡检说明

### 1.1 巡检范围

本次汇总覆盖 {{time_range_summary}} 内生成的 RDS MySQL 巡检报告，共收到 {{report_count}} 份报告，纳入统计 {{included_count}} 份，未纳入统计 {{excluded_count}} 份。

### 1.2 巡检周期

本次报告于 {{report_time}} 生成，默认基于用户指定时间窗口内的巡检结果输出周报 / 月报式总结。

### 1.3 巡检方式

基于火山引擎提供的 RDS MySQL 自动巡检结果，对多个实例报告进行二次分析，重点归纳健康评分、风险分布、异常项与行动建议，不重新采集底层监控数据。

---

## 二、MySQL巡检分析

### 2.1 整体风险概览

#### 风险分布

| 风险级别 | 实例数 | 实例 |
|------|------|------|
| 高风险 | {{high_risk_count}} | {{high_risk_instances}} |
| 中风险 | {{medium_risk_count}} | {{medium_risk_instances}} |
| 低风险 | {{low_risk_count}} | {{low_risk_instances}} |

#### 整体结论

{{overall_summary}}

### 2.2 实例分析

{{instance_analysis_sections}}

### 2.3 共性问题分析

#### 容量与资源

{{capacity_patterns}}

#### 稳定性与流量

{{stability_patterns}}

#### 复制与高可用

{{availability_patterns}}

---

## 三、巡检汇总及问题建议

### 3.1 实例汇总

| 实例名 | 健康评分 | 风险级别 | 建议 |
|------|------|------|------|
{{instance_summary_rows}}

### 3.2 立即处理

{{immediate_actions}}

### 3.3 近期跟进

{{follow_up_actions}}

### 3.4 长期治理

{{long_term_actions}}

---

## 四、附录

### 4.1 未纳入统计

{{excluded_reports}}

### 4.2 数据质量说明

{{data_quality_notes}}

---

**汇总生成时间**: {{report_time}}
**报告版本**: v2.0
**技术支持**: volcengine-rds-report-summarizer
