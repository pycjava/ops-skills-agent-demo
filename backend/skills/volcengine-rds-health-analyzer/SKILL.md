---
name: "volcengine-rds-health-analyzer"
description: "Automates comprehensive health and performance analysis for Volcengine RDS MySQL instances using cloud monitoring APIs. Use when the user needs to: (1) Generate database health reports for Volcengine RDS MySQL instances, (2) Monitor CPU, memory, disk usage and resource bottlenecks, (3) Perform routine database health checks or capacity planning for Volcengine RDS. This skill collects instance configuration and resource metrics to produce structured operational reports."
enabled_tools: "AnalyzeMetricData, Read, RunCommand, Glob"
script: "scripts/get_instance_info.py"
allowed_scripts: ["scripts/get_instance_info.py"]
type: "获取监控指标"
tools: ""
icon: "🤖"
is_online: "true"
---

# Volcengine RDS MySQL Health Analyzer

Automates comprehensive health and performance analysis for Volcengine RDS MySQL instances.

## Prerequisites

Ensure dependencies are installed:
```bash
pip install -r requirements.txt
```

## Workflow

When user requests database health analysis:

1. **Gather parameters** from user or calling agent:
   - `instance_id`: MySQL instance identifier (required)
   - `ak`, `sk`: Volcengine access key and secret key (required, passed from agent)
   - `region`: Region (default: `cn-shanghai`)
   - `time_range`: Analysis period (default: last 24 hours)
   - `analysis_depth`: basic | standard | deep (independent of time_range)

   **analysis_depth** — 决定分析深度和报告详细程度：

   | analysis_depth | 分析侧重 | 报告内容 |
   |----------------|----------|----------|
   | basic | 快速健康检查 | 关键指标概览、明显异常告警 |
   | standard | 性能分析与优化 | 趋势分析、模式识别、优化建议（推荐） |
   | deep | 根因定位与诊断 | 全指标深度分析、异常关联、瓶颈根因、详细优化方案 |

   **time_range** — 决定数据粒度（`--period`），与 analysis_depth 独立：

   | time_range | recommended --period | data points |
   |------------|---------------------|-------------|
   | < 24 hours | 5m (default) | ~288 points |
   | 1-7 days | 1h | 24-168 points |
   | > 7 days | 1d | 30+ points |

   ```bash
   python scripts/get_instance_info.py \
     --instance-id <instance_id> \
     --ak <ak> \
     --sk <sk> \
     --region <region> \
     --hours <time_range> \
     --period <period> \
     --action all \
     --output metric_data/instance_data.json
   ```

   Credentials: Use environment variables `VOLC_ACCESSKEY` and `VOLC_SECRETKEY`, or pass `--ak` and `--sk` arguments.

3. **Analyze collected data (Use AnalyzeMetricData first)**:

   > **CRITICAL RULE**: First call `AnalyzeMetricData` to extract summaries from `metric_data/instance_data_*.json`. Then perform anomaly detection and scoring by the **LLM (You)** based on the summarized data.
  > **TRUST THE DATA**: The `metric_data/instance_data_*.json` files already contain `summary` fields (min, max, avg). Use these values directly. Do NOT recalculate averages from raw data points unless you are identifying specific anomaly timestamps.
   > **DO NOT** create or run any separate Python/Shell scripts to perform the analysis or generate the report.
   > Only when summary data is insufficient, use `Read` or Python one-liners to inspect targeted raw data.

   > **Data Handling Alert**: The generated data files can be large. **DO NOT** read the full content of all files into context immediately. Follow this **Smart Read** process:

   > **Unit Warning**: 数据值已经是对应单位的最终值，**无需任何换算**。例如 CPU 值 `55.7` 即表示 `55.7%`，内存值 `70.2` 即表示 `70.2%`，IOPS 值 `1.4` 即表示 `1.4 Count/s`。**严禁**对数据进行乘以 100 或其他单位转换操作。

  **Step A: Scan Summaries**
  - Call `AnalyzeMetricData` with `glob=metric_data/instance_data_*.json` to get all summary blocks.
  - Check `min`, `max`, `avg` against the [Health Thresholds](#health-thresholds).

   **Step B: Identification & Filtering (Alert: Sequential Processing Only)**
   - Identify metrics that exceed thresholds or show anomalies (e.g., CPU max > 80%).
   - For **Normal** metrics: Use the summary statistics for the report. **Do not read the file.**
   - For **Abnormal** metrics:
     - **Process sequentially**: Analyze one metric at a time. **DO NOT** use parallel tool calls to read multiple files.
     - If the file is small (< 50KB), you may read it fully.
     - If the file is large, use the **Filter Command** (see below) to extract *only* the anomalous data points.

   **Step C: Segmented Analysis**
   - If analyzing a long period (e.g., 7 days), do not load all data points.
   - Ask Python to aggregate data by day or hour first, or extract data for the specific "peak" timestamp found in the summary.

4. **Present findings** to the user:
   - Executive summary with health score
   - Priority issues with severity levels and root causes
   - Actionable recommendations for capacity planning
   - Resource usage trends and predictions

5. **生成巡检报告（Markdown）**:

   > 分析完成后，使用 `obsidian-markdown` 技能语法将报告写入 Markdown 文件。

   **Markdown 报告编写要求**：
   - 使用 frontmatter 记录报告元数据（title、date、instance_id、analysis_depth）
   - 使用 callouts 标注异常级别：`> [!danger]` 严重、`> [!warning]` 警告、`> [!success]` 正常
   - 使用表格展示各指标统计值（均值/最大值/最小值/P95）+ 状态判定
   - 文件名格式：`inspection_report_<instance_id>_<date>.md`

   报告应包含以下内容：
   - **巡检概要**：实例基本信息表格（规格、版本、区域等）、巡检参数
   - **健康评分**：综合评分及各维度评分
   - **核心指标分析**：各指标统计表格 + 状态判定
   - **异常发现**：按严重程度排序的异常列表（使用 callouts）
   - **行动建议**：具体可操作的优化建议

6. **清理临时数据文件**:

  报告生成完成后，删除所有 `metric_data/instance_data_*.json` 临时数据文件：
   ```bash
  rm metric_data/instance_data_*.json
   ```

## Analysis Guidelines

大模型分析时参考以下标准：

### 健康阈值

| 指标 | 正常 (绿) | 警告 (黄) | 危险 (红) |
|------|-----------|-----------|-----------|
| CPU使用率 | < 60% | 60%-80% | > 80% |
| 内存使用率 | < 70% | 70%-85% | > 85% |
| 磁盘使用率 | < 70% | 70%-85% | > 85% |
| QPS | 基线内 | 突增>200% | 突增>500% |
| TPS | 基线内 | 突增>200% | 突增>500% |
| 主从延迟 | < 1s | 1-5s | > 5s |
| IOPS | < 70%上限 | 70%-90% | > 90% |

### 健康评分规则（0-100分）

**CRITICAL**: You MUST calculate the score strictly according to these tables. Do not guess.

**1. CPU Usage (Max 20 pts)**
| Average Usage | Score |
|---------------|-------|
| < 60%         | 20    |
| 60% - 70%     | 15    |
| 70% - 80%     | 10    |
| > 80%         | 5     |

**2. Memory Usage (Max 20 pts)**
| Average Usage | Score |
|---------------|-------|
| < 70%         | 20    |
| 70% - 80%     | 15    |
| 80% - 90%     | 10    |
| > 90%         | 5     |

**3. Disk Usage (Max 20 pts)**
| Average Usage | Score |
|---------------|-------|
| < 70%         | 20    |
| 70% - 80%     | 15    |
| 80% - 90%     | 10    |
| > 90%         | 5     |

**4. Stability (QPS/TPS/IOPS) (Max 15 pts)**
- **Baseline**: 15 points.
- **Penalty**: Deduct 5 points for *each* metric (QPS, TPS, IOPS) that has `Max > 3 * Avg` (indicating severe spikes).
- **Min Score**: 0.

**5. Replication Delay (Max 15 pts)**
| Max Delay | Score |
|-----------|-------|
| < 1s      | 15    |
| 1s - 5s   | 10    |
| 5s - 10s  | 5     |
| > 10s     | 0     |

**6. General Health (Max 10 pts)**
- **10 pts**: If no metric is in "Red" zone (Dangerous).
- **5 pts**: If 1-2 metrics are in "Red" zone.
- **0 pts**: If > 2 metrics are in "Red" zone.

**Total Score = Sum of above 6 sections.**

## Example Report (Reference)

```markdown
---
title: 火山引擎RDS MySQL巡检报告
instance_id: mysql-03ad84b450b2
instance_name: 灵工MySQL集群
date: 2026-02-13T17:08:20
time_range: 7天 (2026-02-06 ~ 2026-02-13)
analysis_depth: deep
health_score: 95
status: 优秀
tags:
  - 数据库巡检
  - RDS
  - MySQL
  - 火山引擎
---

# 📊 火山引擎RDS MySQL巡检报告

## 巡检概要

### 实例基本信息

| 项目 | 详情 |
|------|------|
| 实例ID | `mysql-03ad84b450b2` |
| 实例名称 | ==灵工MySQL集群== |
| 运行状态 | ✅ Running |
| 数据库版本 | MySQL 5.7 |
| 实例类型 | DoubleNode（双节点高可用） |
| 节点规格 | **8核 16GB** (rds.mysql.8c16g) |
| 节点数量 | 2个节点 |
| 存储容量 | 1000 GB (LocalSSD) |
| 实际使用 | 53.1 GB (5.31%) |
| 可用区 | cn-shanghai-a |
| 数据同步模式 | 异步复制 (Async) |
| 创建时间 | 2024-03-11 |
| 计费方式 | 预付费 |

### 巡检参数

| 参数 | 值 |
|------|-----|
| 巡检时间 | 2026-02-13 17:08:20 |
| 分析时间范围 | **最近7天** (2026-02-06 ~ 2026-02-13) |
| 数据采集粒度 | 1小时 |
| 数据点数量 | 336个时间点 |
| 分析深度 | **Deep** (深度分析) |

---

## 健康评分

> [!success] 综合评分: 95/100 ⭐⭐⭐⭐⭐
> **评级**: 优秀 - 实例运行健康，资源利用率合理，仅存在可预测的定时峰值

### 评分明细

| 维度 | 得分 | 满分 | 评价 |
|------|------|------|------|
| CPU使用率 | 20 | 20 | ✅ 均值14.25%，峰值69.66%，整体优秀 |
| 内存使用率 | 20 | 20 | ✅ 稳定在56%，无波动 |
| 磁盘使用率 | 20 | 20 | ✅ 仅5.31%，空间充足 |
| QPS/TPS稳定性 | 12 | 15 | ⚠️ 存在每日定时峰值（-3分） |
| 主从延迟 | 15 | 15 | ✅ 平均0.02秒，表现优异 |
| 综合波动 | 8 | 10 | ✅ 波动可控，可预测 |

---

## 核心指标分析

### 1️⃣ CPU 使用率

**统计值**（7天，336个数据点）：

| 指标 | 数值 |
|------|------|
| **平均值** | 14.25% |
| **最大值** | 69.66% (2026-02-07 17:00) |
| **最小值** | 0.036% |
| **P95** | ~0.50% |

**节点对比**：

- **节点1**（主节点）: 峰值 69.66%，Top 10 值在 50-70% 之间
  - 2026-02-07 17:00: 69.66%
  - 2026-02-13 14:00: 65.53%
  - 2026-02-09 14:00: 52.77%
- **节点2**（只读节点）: 峰值 21.68%，负载极低

> [!success] 趋势判断
> ✅ **健康** - CPU 均值处于理想区间（<20%），峰值虽然达到69.66%，但仅为个别时刻，未持续出现。主节点承载主要计算负载，只读节点压力极小。

---

### 2️⃣ 内存使用率

**统计值**：

| 指标 | 数值 |
|------|------|
| **平均值** | 56.31% |
| **最大值** | 57.39% |
| **最小值** | 55.71% |
| **波动范围** | 仅 1.68% |

> [!success] 趋势判断
> ✅ **优秀** - 内存使用率稳定在56%左右，波动极小（< 2%），说明缓存池配置合理，无内存泄漏风险。

---

### 3️⃣ 磁盘使用率

**统计值**：

| 指标 | 数值 |
|------|------|
| **平均值** | 5.31% |
| **最大值** | 5.31% |
| **实际使用** | 53.1 GB / 1000 GB |

> [!success] 趋势判断
> ✅ **优秀** - 磁盘空间充足，使用率恒定在5.31%，无增长趋势。当前配置的1TB存储空间可支撑长期使用。

---

### 4️⃣ QPS（每秒查询数）

**统计值**（168个数据点）：

| 指标 | 数值 |
|------|------|
| **平均值** | 71.57 QPS |
| **最大值** | 284.03 QPS |
| **最小值** | 8.81 QPS |
| **峰谷比** | 约 **4倍** |

> [!warning] 关键发现 - 定时峰值模式
> **每天凌晨 02:00 固定出现 QPS 峰值（~283 QPS）**：
>
> | 日期 | 时间 | QPS 值 |
> |------|------|--------|
> | 2026-02-07 | 02:00 | 283.30 |
> | 2026-02-08 | 02:00 | 283.69 |
> | 2026-02-09 | 02:00 | 283.05 |
> | 2026-02-10 | 02:00 | 282.98 |
> | 2026-02-11 | 02:00 | ==284.03== ← 峰值 |
> | 2026-02-12 | 02:00 | 283.13 |
> | 2026-02-13 | 02:00 | 282.94 |
>
> **次高峰出现在凌晨 03:00**（~83 QPS）

> [!warning] 趋势判断
> ⚠️ **需关注** - QPS 存在明显的**定时任务特征**，每天凌晨2点固定出现4倍流量突增。这很可能是：
> - 自动化备份任务
> - 数据统计或报表生成
> - 批量数据处理任务

---

### 5️⃣ TPS（每秒事务数）

**统计值**：

| 指标 | 数值 |
|------|------|
| **平均值** | 1.26 TPS |
| **最大值** | 3.03 TPS |
| **峰谷比** | 约 2.4倍 |

> [!success] 趋势判断
> ✅ **正常** - TPS 整体平稳，峰值波动在可接受范围内（< 3倍），说明写操作压力不大。

---

### 6️⃣ 主从复制延迟

**统计值**：

| 指标 | 数值 |
|------|------|
| **平均值** | 0.02 秒 |
| **最大值** | 0.055 秒 |
| **最小值** | 0 秒 |

> [!success] 趋势判断
> ✅ **优秀** - 主从延迟极低（< 0.1秒），远低于1秒健康阈值，说明异步复制工作正常，网络链路稳定。

---

### 7️⃣ IOPS

**统计值**：

| 指标 | 数值 |
|------|------|
| **平均值** | 1.4 IOPS |
| **最大值** | 4.83 IOPS |

> [!success] 趋势判断
> ✅ **优秀** - IOPS 极低，磁盘I/O无压力。LocalSSD 的性能远未达到瓶颈。

---

### 8️⃣ 网络流量

**入站流量**：

| 指标 | 数值 |
|------|------|
| 平均值 | 5.16 KB/s |
| 峰值 | 66.76 KB/s |
| 突增倍数 | **13倍** |

**出站流量**：

| 指标 | 数值 |
|------|------|
| 平均值 | 23.58 KB/s |
| 峰值 | 75.87 KB/s |
| 突增倍数 | 3.2倍 |

> [!warning] 趋势判断
> ⚠️ **需关注** - 网络入站流量存在13倍突增，与 QPS 定时峰值时间吻合，进一步证实了定时任务的存在。

---

## 异常发现

### 🟡 警告级别

> [!warning] 定时任务导致资源突增
> **发现时间**: 每天凌晨 02:00-03:00
> **影响指标**: QPS、网络入流量、CPU
> **严重程度**: 中等
>
> **详情**:
> - QPS 从均值 71 突增至 284（**+297%**）
> - 网络入流量从 5KB/s 突增至 67KB/s（**+1200%**）
> - CPU 在部分时刻达到 69.66%（接近警戒线）
>
> **根因分析**:
> 高度疑似为自动化定时任务（备份、统计或批处理），任务执行时间固定在凌晨2点，持续约1小时。

---

### ✅ 正常运行

> [!success] 以下指标运行健康
> - ✅ **内存使用率**: 稳定在56%，无波动
> - ✅ **磁盘使用率**: 仅5.31%，空间充足（剩余947GB）
> - ✅ **主从延迟**: 平均0.02秒，复制链路健康
> - ✅ **IOPS**: 极低压力，磁盘I/O无瓶颈
> - ✅ **TPS**: 平稳运行，写操作压力小

---

## 行动建议

### 🔴 优先级 P1（高优先级）

> [!danger] 1. 排查凌晨2点定时任务
> **问题**: 每天02:00出现4倍QPS突增，可能影响业务高峰期性能
>
> **建议**:
> - 检查 MySQL 的 Event Scheduler 是否有定时任务
> - 检查应用层是否有cron任务连接该实例
> - 如果是备份任务，建议调整至业务低谷期（如凌晨4-5点）
>
> **执行SQL**:
> ```sql
> SHOW EVENTS;  -- 查看数据库定时任务
> SELECT * FROM mysql.event WHERE status = 'ENABLED';
> ```

> [!danger] 2. 监控 CPU 峰值
> **问题**: CPU 峰值达到 69.66%，接近70%警戒线
>
> **建议**:
> - 设置 CPU 使用率告警（阈值: 70%）
> - 在下次峰值时段（参考历史峰值时间），使用慢查询日志分析高负载SQL
>
> **执行SQL**:
> ```sql
> SET GLOBAL slow_query_log = 'ON';
> SET GLOBAL long_query_time = 1;  -- 记录执行超过1秒的查询
> ```

---

### 🟡 优先级 P2（中优先级）

> [!warning] 3. 优化只读节点利用率
> **问题**: 只读节点 CPU 峰值仅21.68%，而主节点达到69.66%，负载不均衡
>
> **建议**:
> - 将部分读查询（如报表、统计类查询）分流到只读节点
> - 配置应用层读写分离中间件（如 ProxySQL、MySQL Router）
>
> **预期收益**: 降低主节点压力，提升整体吞吐能力

> [!warning] 4. 建立性能基线和告警
> **建议**:
> - 设置 QPS 突增告警（阈值: 200 QPS，即均值的3倍）
> - 设置网络流量异常告警（入站 > 50KB/s）
> - 启用火山引擎云监控的异常检测功能

---

### 🟢 优先级 P3（低优先级，长期优化）

> [!tip] 5. 磁盘空间容量规划
> **当前状态**: 使用 53GB / 1000GB (5.31%)
>
> **建议**: 当前配置的1TB存储空间充足，建议每季度检查一次增长趋势，预计未来2-3年内无需扩容。

> [!tip] 6. 考虑升级 MySQL 版本
> **当前版本**: MySQL 5.7
>
> **建议**: MySQL 5.7 将于2023年10月停止官方支持，建议规划升级至 MySQL 8.0，以获得更好的性能和安全性。

---

## 总结

> [!success] 整体评价
> 实例运行**健康稳定**，综合评分 **95/100**

### 🎯 核心优势

- ✅ CPU、内存、磁盘资源充足，利用率合理
- ✅ 主从复制健康，延迟极低（< 0.1秒）
- ✅ IOPS 和网络带宽远未达到瓶颈
- ✅ 双节点高可用架构，保障业务连续性

### ⚠️ 需要关注

- **定时任务优化**: 凌晨2点的定时任务导致QPS突增4倍，需排查并优化执行时间
- **读写负载均衡**: 只读节点利用率不足，可进一步分流读查询

### 📈 长期建议

- 建立完善的监控告警体系
- 规划 MySQL 8.0 升级路线
- 定期（每季度）进行性能巡检

---

**巡检报告生成时间**: 2026-02-13 17:08:20
**报告版本**: v1.0
**技术支持**: 火山引擎RDS MySQL巡检专家

%%
内部备注：
- 下次巡检建议时间：2026-03-13
- 重点关注凌晨2点定时任务优化进展
- 跟踪只读节点利用率变化
%%
```
```

## Error Handling

- **InstanceNotFound**: Instance ID invalid or deleted. Ask user to verify.
- **ApiException 403**: AK/SK credentials invalid or lack permission. Ask user to check.
- **metric not found**: Metric name or sub_namespace mismatch. Check Key Metrics table below.
- **API rate limit**: Script includes 0.1s delay between metric calls. For large time ranges, use coarser `--period`.

## Smart Data Analysis Strategy (Helper Commands)

Use these Python one-liners to analyze data without loading full files into context.

**1. Fast Summary Scan (Run this first)**
```python
import json, glob, os
print("Processing summaries...")
for f in glob.glob('metric_data/instance_data_*.json'):
    try:
        with open(f, 'r', encoding='utf-8') as fd:
            d = json.load(fd)
            # Support both new split format and old format
            summary = d.get('summary') or d.get('resource_metrics', {}).get('metrics', {}).values().__iter__().__next__().get('summary')
            print(f"File: {f}\nMetric: {d.get('resource_metrics', {}).get('metrics', {}).keys()}\nSummary: {summary}\n---")
    except Exception as e: print(f"{f}: {e}")
```

**2. Filter Anomalies (Drill-down)**
*Example: Get data points where value > 60 for CPU*
```python
import json
threshold = 60
with open('metric_data/instance_data_cpu.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    for node in data.get('nodes', []):
        anomalies = [p for p in node['data_points'] if p['value'] > threshold]
        print(f"Node: {node.get('legend')} - Found {len(anomalies)} anomalies (Top 5):")
        # Print top 5 highest to save context
        print(sorted(anomalies, key=lambda x: x['value'], reverse=True)[:5])
```

## Data Parsing Notes

The `metric_data/instance_data_*.json` files now contain pre-parsed, clean data structures:
- `summary`: Contains `min`, `max`, `avg`, `data_point_count`. **Reliable for overview.**
- `nodes`: List of nodes (Primary/Read-only).
- `data_points`: List of `{ts, time, value}`.
- `value`: Float with 4 decimal places.

## Available Scripts

- `get_instance_info.py` - Instance configuration and resource metrics (CPU, Memory, Disk, QPS, TPS, ReplicationDelay, IOPS, Network)

Supports `--action` modes: `detail` (instance info only), `metrics` (monitoring data only), `all` (both).

All scripts support `--ak`/`--sk` or environment variables for authentication.

## Key Metrics Collected

From Volcengine Cloud Monitor API (Namespace: `VCM_RDS_MySQL`):

| Metric Name | sub_namespace | Description | Unit |
|-------------|---------------|-------------|------|
| CpuUtil | resource_monitor_new | CPU usage | % |
| MemUtil | resource_monitor_new | Memory usage | % |
| DiskUtil | resource_monitor_new | Disk usage | % |
| QPS | engine_monitor | Queries per second | Count/s |
| TPS | engine_monitor | Transactions per second | Count/s |
| ReplicationDelay | deploy_monitor_new | Replication lag | Seconds |
| IOPSRate | resource_monitor_new | IOPS | Count/s |
| NetworkReceiveThroughput | resource_monitor_new | Network in | Bytes/s |
| NetworkTransmitThroughput | resource_monitor_new | Network out | Bytes/s |

## API Documentation

- [Cloud Monitor GetMetricData API](https://www.volcengine.com/docs/6408/105542)
- [RDS MySQL API](https://www.volcengine.com/docs/6313/170652)
- [Python SDK Guide](https://www.volcengine.com/docs/6408/170945)