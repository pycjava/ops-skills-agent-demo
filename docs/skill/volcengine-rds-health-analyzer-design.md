# Volcengine RDS 单实例巡检技能设计说明

## 概述

`volcengine-rds-health-analyzer` 用于对单个火山引擎 RDS MySQL 实例做 **只读健康巡检**。它的工作模式不是让 Agent 直接连接数据库做自由分析，而是先调用技能自带脚本采集实例详情和监控指标，再由 Agent 基于结构化 JSON 结果完成评分、异常判断和报告输出。

该设计把“数据采集”和“结果解读”分成两层：采集层由脚本保证稳定性，分析层由 Skill 约束输出结构和判断规则。

## 架构

```text
用户："帮我巡检这个 RDS 实例最近 30 天状态"
  → Agent 确定 instance_id / region / credential_ref / time_range
  → execute 运行 get_instance_info.py 采集主窗口数据
  → 当 time_range >= 7d 时，再采集最近 3d 辅助窗口
  → read_file 读取 metric_data/*.json 中的 summary / evidence / node_summaries
  → 按阈值、尖峰和多节点规则生成健康结论
  → 如用户要求保存，按 inspection_report_template.md 输出 Markdown 报告
```

## 设计要点

- **只读巡检**：禁止直接连库执行 SQL，只允许通过 `get_instance_info.py` 采集云侧指标和实例信息。
- **参数来源可追溯**：`instance_id`、`region`、`credential_ref` 优先来自长期记忆和凭证注册表，缺项时再逐项追问。
- **主窗口 + 辅助窗口**：主窗口负责长期趋势判断；当时间范围达到 `7d` 及以上时，增加最近 `3d` 辅助窗口确认问题是否仍在持续。
- **短时异常补充语义**：Skill 顶部额外定义了最近 `24h` 辅助窗口语义，用于识别“最新出现的短时异常”，但不允许短窗口覆盖主窗口结论。
- **证据优先分析**：读取 JSON 时先看 `summary`、`evidence`、`node_summaries`，只有异常时才回看原始点位，避免把大量时序数据直接灌入上下文。
- **多节点友好**：对 `cpu`、`memory`、`disk_util`、`IOPSRate`、`network_in/out`、`replication_delay` 做节点拆分，先给实例级结论，再给热点节点结论。
- **加权评分机制**：节点级指标使用 `weighted = 0.5 * avg + 0.5 * median`，避免平均值掩盖持续高负载。
- **尖峰风险识别**：结合 `p95`、`p99`、`cv`、`sliding_mad` 和 `risk_tier` 做瞬时尖峰判断，而不是只看均值。
- **模板驱动输出**：无论聊天中展示完整报告，还是保存为文件，都必须遵循 `inspection_report_template.md` 固定章节结构。
- **报告落盘规范**：保存路径固定在 `/memories/reports/`，文件名使用 `<sanitized_instance_name>-inspection-<YYYYMMDD>.md`。

## 指标与评分模型

- **核心指标**：`cpu`、`memory`、`disk_util`、`qps`、`tps`、`replication_delay`、`IOPSRate`、`network_in`、`network_out`
- **健康阈值**：对 CPU、内存、磁盘、主从延迟等指标定义“正常 / 警告 / 危险”区间
- **总分模型**：总分 `100`，由 CPU、内存、磁盘、稳定性、主从延迟和综合健康共同构成
- **节点级兜底**：实例级得分与最差节点得分取更差者，避免集群均值掩盖热点节点
- **风险说明**：当辅助窗口缺失或覆盖率不足时，必须显式写明“证据不完整”，不能脑补结论

## 目录结构

```text
backend/skills/volcengine-rds-health-analyzer/
├── SKILL.md                               # 巡检流程、评分规则、报告约束
├── scripts/
│   └── get_instance_info.py               # 指标采集脚本
└── assets/
    └── inspection_report_template.md      # 单实例巡检报告模板
```

## 运行时产物

```text
backend/metric_data/
├── instance_data_*.json                   # 主窗口指标结果
├── instance_data_recent3d_*.json          # 最近 3d 辅助窗口结果
└── instance_data_recent24h_*.json         # 最近 24h 补充窗口结果
```
