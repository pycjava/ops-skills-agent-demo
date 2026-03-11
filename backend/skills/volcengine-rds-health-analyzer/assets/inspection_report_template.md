# 📊 火山引擎RDS MySQL巡检报告

> 使用说明：
> - 固定章节/标题顺序，只替换占位符内容。
> - 不得新增、删除、改名、重排模板中已存在的一级、二级标题。
> - 将 `{{...}}` 占位符替换为实际分析结果；没有数据时写“未获取”或“无异常”。
> - 保留模板中的 Markdown 表格、callout、分隔线和内部备注块。
> - 如果某个占位符对应节点拆分内容，必须填充固定列表头 `Node | Avg | Median | Max | 风险级别 | 说明` 的 Markdown 表格。
> - 占位符内的实例信息、时间、配置值、监控值需按来源原值填写，不对任何数据做修改。
> - 无法确认时写“未获取”或“无异常”，不要估算、换算、四舍五入或生成近似值。
> - 当主窗口 `time_range >= 7d` 时，各指标分析说明需同时交代主窗口与最近 3 天辅助窗口的判断，但只能写在现有占位符位置，不得新增标题。

## 巡检概要

### 实例基本信息

| 项目 | 详情 |
|------|------|
| 实例ID | `{{instance_id}}` |
| 实例名称 | {{instance_name}} |
| 运行状态 | {{instance_status}} |
| 数据库版本 | {{db_version}} |
| 实例类型 | {{instance_type}} |
| 节点规格 | {{node_spec}} |
| 节点数量 | {{node_count}} |
| 存储容量 | {{storage_capacity}} |
| 实际使用 | {{storage_used}} |
| 可用区 | {{zone}} |
| 数据同步模式 | {{sync_mode}} |
| 创建时间 | {{create_time}} |
| 计费方式 | {{charge_type}} |

### 巡检参数

| 参数 | 值 |
|------|-----|
| 巡检时间 | {{report_time}} |
| 分析时间范围 | {{time_range_label}} |
| 数据采集粒度 | {{period}} |
| 数据点数量 | {{data_point_count}} |
| 分析深度 | {{analysis_depth}} |

### 节点拓扑摘要

{{node_topology_summary}}

---

## 健康评分

> [!{{score_callout_type}}] 综合评分: {{health_score}}/100 {{score_stars}}
> **评级**: {{health_rating}} - {{health_summary}}

### 评分明细

| 维度 | 得分 | 满分 | 评价 |
|------|------|------|------|
| CPU使用率 | {{cpu_score}} | 20 | {{cpu_score_comment}} |
| 内存使用率 | {{memory_score}} | 20 | {{memory_score_comment}} |
| 磁盘使用率 | {{disk_score}} | 20 | {{disk_score_comment}} |
| QPS/TPS稳定性 | {{stability_score}} | 15 | {{stability_score_comment}} |
| 主从延迟 | {{replication_score}} | 15 | {{replication_score_comment}} |
| 综合波动 | {{overall_score}} | 10 | {{overall_score_comment}} |

---

## 核心指标分析

### 1️⃣ CPU 使用率

**统计值**（{{cpu_window}}）：

| 指标 | 数值 |
|------|------|
| 最小值 | {{cpu_min}} |
| 最大值 | {{cpu_max}} |
| 平均值 | {{cpu_avg}} |
| 中位数 | {{cpu_median}} |
| 结论 | {{cpu_conclusion}} |

**分析说明**：
{{cpu_analysis}}

**节点拆分**：
{{cpu_node_breakdown}}

### 2️⃣ 内存使用率

**统计值**（{{memory_window}}）：

| 指标 | 数值 |
|------|------|
| 最小值 | {{memory_min}} |
| 最大值 | {{memory_max}} |
| 平均值 | {{memory_avg}} |
| 中位数 | {{memory_median}} |
| 结论 | {{memory_conclusion}} |

**分析说明**：
{{memory_analysis}}

**节点拆分**：
{{memory_node_breakdown}}

### 3️⃣ 磁盘使用率

**统计值**：

| 指标 | 数值 |
|------|------|
| 最小值 | {{disk_min}} |
| 最大值 | {{disk_max}} |
| 平均值 | {{disk_avg}} |
| 中位数 | {{disk_median}} |
| 结论 | {{disk_conclusion}} |

**分析说明**：
{{disk_analysis}}

**节点拆分**：
{{disk_node_breakdown}}

### 4️⃣ QPS / TPS

**统计值**：

| 指标 | 最小值 | 最大值 | 平均值 | 中位数 | 结论 |
|------|--------|--------|--------|--------|------|
| QPS | {{qps_min}} | {{qps_max}} | {{qps_avg}} | {{qps_median}} | {{qps_conclusion}} |
| TPS | {{tps_min}} | {{tps_max}} | {{tps_avg}} | {{tps_median}} | {{tps_conclusion}} |

**范围说明**：
{{qps_tps_scope_note}}

**分析说明**：
{{qps_tps_analysis}}

### 5️⃣ 主从延迟

**统计值**：

| 指标 | 数值 |
|------|------|
| 最小值 | {{replication_min}} |
| 最大值 | {{replication_max}} |
| 平均值 | {{replication_avg}} |
| 中位数 | {{replication_median}} |
| 结论 | {{replication_conclusion}} |

**分析说明**：
{{replication_analysis}}

**节点拆分**：
{{replication_node_breakdown}}

### 6️⃣ IOPS / 网络

**统计值**：

| 指标 | 最小值 | 最大值 | 平均值 | 中位数 | 结论 |
|------|--------|--------|--------|--------|------|
| IOPS | {{iops_min}} | {{iops_max}} | {{iops_avg}} | {{iops_median}} | {{iops_conclusion}} |
| 网络入流量 | {{network_in_min}} | {{network_in_max}} | {{network_in_avg}} | {{network_in_median}} | {{network_in_conclusion}} |
| 网络出流量 | {{network_out_min}} | {{network_out_max}} | {{network_out_avg}} | {{network_out_median}} | {{network_out_conclusion}} |

**分析说明**：
{{iops_network_analysis}}

**节点拆分**：
{{iops_network_node_breakdown}}

---

## 异常发现

> [!warning] 仅列出有明确证据支持的异常、风险或需要关注的模式；若无异常，明确写“本次未发现需要升级处理的异常”。

### 高优先级

{{high_priority_findings}}

### 中优先级

{{medium_priority_findings}}

### 低优先级 / 观察项

{{low_priority_findings}}

---

## 行动建议

### 🔥 立即处理

{{immediate_actions}}

### ⚠️ 需要关注

{{follow_up_actions}}

### 📈 长期建议

{{long_term_actions}}

---

**巡检报告生成时间**: {{report_time}}
**报告版本**: v1.0
**技术支持**: 火山引擎RDS MySQL巡检专家

%%
内部备注：
- 下次巡检建议时间：{{next_inspection_date}}
- 重点关注：{{focus_items}}
- 备注：{{internal_note}}
%%
