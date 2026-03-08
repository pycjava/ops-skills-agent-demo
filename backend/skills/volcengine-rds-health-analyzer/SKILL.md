---
name: volcengine-rds-health-analyzer
description: 使用火山引擎云监控 API 和本技能自带脚本，对 Volcengine RDS MySQL 实例做健康巡检、容量评估和巡检报告生成。当用户要求分析 CPU/内存/磁盘/QPS/TPS/主从延迟、排查资源瓶颈，或生成火山引擎 RDS MySQL 巡检报告时使用。
---

# 火山引擎 RDS MySQL 巡检技能

使用此技能对火山引擎 RDS MySQL 实例做只读巡检：先采集实例详情和监控指标，再由大模型基于采集结果完成分析、评分和报告输出。

## 本项目可用工具

本项目中应只使用以下能力，不要引用不存在的工具名：

- `execute`：运行采集脚本、创建输出目录、按需做轻量过滤
- `glob`：查找生成的 `metric_data/*.json` 文件
- `read_file`：按需读取单个结果文件
- `write_file` / `edit_file`：在用户要求保存报告时写入 Markdown 文件；巡检报告优先写入 `/memories/reports/`

项目内文件工具统一以 `backend/` 为虚拟根目录：
- `glob` 的 pattern 使用相对路径，例如 `metric_data/instance_data_*.json`
- `read_file` 优先使用相对路径，例如 `metric_data/instance_data_cpu.json`
- 如果文件路径来自 `glob` 结果，也可以直接复用 `/metric_data/...` 形式的虚拟路径
- 不要使用 `B:\...`、`C:\...`、`/backend/...`、`/memories/../backend/...`

## 运行约束

- 只做只读巡检，不直接连接数据库执行 SQL。
- 只使用本技能自带脚本：`./skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`
- 不要为了分析数据再创建新的 Python / Shell 分析脚本。
- 不要在回复中泄露 `AK/SK`、完整凭证或敏感配置。
- `analysis_depth` 与 `time_range` 是独立参数，不要绑定。
- 数据值已经是最终单位，禁止自行乘以 `100` 或做额外单位换算。
- 始终显式传入 `--output`，避免脚本把文件写到默认硬编码目录。
- 不要通过 `set VOLC_ACCESSKEY=...`、`export VOLC_ACCESSKEY=...` 等环境变量方式传递凭证；执行命令时始终直接使用 `--ak` 和 `--sk` 参数。

## 输入参数

- `instance_id`：实例 ID，必填，例如 `mysql-xxxxx`
- `region`：区域，默认 `cn-shanghai`
- `time_range`：巡检时间范围，默认最近 `24h`
- `analysis_depth`：`basic` / `standard` / `deep`
- `ak` / `sk`：火山引擎访问密钥（Access Key ID / Secret Key），必填，由用户提供

## 时间粒度策略

根据时间范围自动选择 `--period`：

| time_range | period |
|------------|--------|
| `< 24h` | `5m` |
| `1-7d` | `1h` |
| `> 7d` | `1d` |

## 标准工作流

1. 先收集参数：
   - `instance_id`
   - `region`
   - `time_range`
   - `analysis_depth`
   - `ak` / `sk`（必填，向用户索取）

2. 用 `execute` 运行采集脚本，输出到项目内相对路径，例如：

```bash
python ./skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py \
  --instance-id <instance_id> \
  --region <region> \
  --ak <ak> \
  --sk <sk> \
  --hours <hours> \
  --period <period> \
  --action all \
  --output ./metric_data/instance_data.json
```

如果用户提供的是明确的起止时间，则改用：

```bash
python ./skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py \
  --instance-id <instance_id> \
  --region <region> \
  --ak <ak> \
  --sk <sk> \
  --start "YYYY-MM-DD HH:MM" \
  --end "YYYY-MM-DD HH:MM" \
  --period <period> \
  --action all \
  --output ./metric_data/instance_data.json
```

3. 用 `glob` 查找生成的结果文件：
   - `./metric_data/instance_data_*.json`

4. 用 `read_file` 按需逐个读取结果文件，优先看每个指标里的 `summary`：
   - 推荐直接读取 `metric_data/instance_data_*.json`
   - 如果 `glob` 返回的是 `/metric_data/...`，可直接原样传给 `read_file`
   - 不要把路径改写成 `/backend/...`
   - 不要使用 `B:\...` 或 `/memories/../backend/...`
   - `summary.min`
   - `summary.max`
   - `summary.avg`
   - `summary.data_point_count`
   - `nodes`

5. 分析时遵循以下原则：
   - 先看 `summary`，不要一开始就把所有原始点位全读进上下文
   - 只有某个指标异常时，才继续读取对应文件里的 `nodes` / `data_points`
   - 顺序分析异常指标，不要并行读取一批大文件
   - 正常指标直接基于 `summary` 给出结论
   - JSON 结果分析优先使用 `read_file`，不要用 `execute python -c` 读取文件后却不输出任何结果
   - `execute` 仅用于采集脚本或必要的轻量过滤；如果使用它做过滤，命令必须明确产生 stdout
   - 如果 `execute` 返回“Command succeeded with no stdout/stderr”，说明命令已成功完成，应转去读取生成文件，不要继续猜测 `print flush`

6. 输出巡检结果：
   - 巡检概要
   - 健康评分
   - 核心指标分析
   - 异常发现
   - 行动建议

7. 如用户要求“保存报告”或“生成文件”，使用 `obsidian-markdown` 风格写成 Markdown，并用 `write_file` 写入 `/memories/reports/` 下的 `.md` 文件。
   - 生成报告前，先使用 `read_file` 读取模板文件 `./skills/volcengine-rds-health-analyzer/assets/inspection_report_template.md`
   - 报告内容必须按照模板结构填充，不要改变一级、二级标题顺序
   - 没有数据的字段写“未获取”或“无异常”，不要删除模板章节

## 采集结果说明

`--action all` 会生成多个 JSON 文件，每个文件对应一个指标。核心指标包括：

- `cpu`
- `memory`
- `disk_util`
- `qps`
- `tps`
- `replication_delay`
- `IOPSRate`
- `network_in`
- `network_out`

每个文件中最关键的字段是：

- `instance_detail`：实例规格、版本、节点等基础信息
- `resource_metrics.metrics.<metric_key>.summary`：该指标的汇总统计
- `resource_metrics.metrics.<metric_key>.nodes`：按节点拆分的数据

## 健康阈值

| 指标 | 正常 | 警告 | 危险 |
|------|------|------|------|
| CPU 使用率 | `< 60%` | `60%-80%` | `> 80%` |
| 内存使用率 | `< 70%` | `70%-85%` | `> 85%` |
| 磁盘使用率 | `< 70%` | `70%-85%` | `> 85%` |
| QPS / TPS | 基线内 | 峰值明显突增 | 峰值严重突增 |
| 主从延迟 | `< 1s` | `1-5s` | `> 5s` |
| IOPS | `< 70%上限` | `70%-90%上限` | `> 90%上限` |

## 评分规则（总分 100）

严格按以下规则计算：

1. CPU（20 分）
   - `avg < 60` → `20`
   - `60 <= avg < 70` → `15`
   - `70 <= avg < 80` → `10`
   - `avg >= 80` → `5`

2. 内存（20 分）
   - `avg < 70` → `20`
   - `70 <= avg < 80` → `15`
   - `80 <= avg < 90` → `10`
   - `avg >= 90` → `5`

3. 磁盘（20 分）
   - `avg < 70` → `20`
   - `70 <= avg < 80` → `15`
   - `80 <= avg < 90` → `10`
   - `avg >= 90` → `5`

4. 稳定性（15 分）
   - 初始 `15`
   - `qps`、`tps`、`IOPSRate` 中每出现一个 `max > 3 * avg` 的严重尖峰，扣 `5`
   - 最低 `0`

5. 主从延迟（15 分）
   - `max < 1` → `15`
   - `1 <= max < 5` → `10`
   - `5 <= max < 10` → `5`
   - `max >= 10` → `0`

6. 综合健康（10 分）
   - 没有红色指标 → `10`
   - `1-2` 个红色指标 → `5`
   - 超过 `2` 个红色指标 → `0`

## 报告输出要求

报告至少包含以下部分：

- **巡检概要**：实例信息、巡检范围、分析深度
- **健康评分**：总分与扣分说明
- **核心指标分析**：CPU、内存、磁盘、QPS、TPS、主从延迟、IOPS、网络
- **异常发现**：按严重程度排序
- **行动建议**：给出具体可执行建议

如需生成 Markdown 报告，必须使用模板文件：

- 模板路径：`./skills/volcengine-rds-health-analyzer/assets/inspection_report_template.md`
- 先用 `read_file` 读取该模板，再按模板结构填充实际分析结果
- 不要随意调整章节顺序；没有数据的字段写“未获取”或“无异常”
- 最终输出必须保持模板中的一级、二级标题和主要表格结构

如果保存为 Markdown，建议文件名与路径：

```text
/memories/reports/inspection_report_<instance_id>_<YYYYMMDD>.md
```

写入 `/memories/` 时必须使用 `write_file` / `edit_file`，不要使用 `execute` 里的 shell 重定向或 `echo >`。

## 错误处理

- `InstanceNotFound`：实例 ID 不存在或已删除，提示用户核对
- `ApiException 403`：AK/SK 无效或权限不足，提示用户检查凭证和权限
- 指标缺失：提示对应 metric / sub_namespace 可能不匹配
- API 限流：增大 `--period`，缩小时间范围，或稍后重试

## 参考路径

- 脚本：`./skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`
- 输出目录：`./metric_data/`
- 报告模板：`./skills/volcengine-rds-health-analyzer/assets/inspection_report_template.md`

## 强制要求

- 不要把 skill 当作独立 tool 名去调用。
- 不要输出“调用 `volcengine-rds-health-analyzer` 工具”这类表述。
- 采集数据时应遵循 skill 中的流程，并通过 `execute` 运行 skill 自带脚本。
- 任何项目文件的路径匹配都必须使用相对路径；读取项目文件时优先使用相对路径或直接复用 `glob` 返回的 `/...` 虚拟路径。
- `execute` 成功但无输出时，应把它视为“命令执行成功但没有终端文本”，不要围绕 `flush` 或同一条 `python -c` 命令反复重试。
- 生成巡检 Markdown 报告时，必须遵循 `./skills/volcengine-rds-health-analyzer/assets/inspection_report_template.md` 的格式与章节结构。
