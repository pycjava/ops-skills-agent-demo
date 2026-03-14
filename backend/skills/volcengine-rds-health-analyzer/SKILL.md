---
name: volcengine-rds-health-analyzer
description: Use when users need Volcengine RDS MySQL 单实例健康巡检、CPU/内存/磁盘/QPS/TPS/主从延迟分析、资源瓶颈排查，或生成单实例巡检报告。
---

# 火山引擎 RDS MySQL 巡检技能

使用此技能对火山引擎 RDS MySQL 实例做只读巡检：先采集实例详情和监控指标，再由大模型基于采集结果完成分析、评分和报告输出。

## 平衡版分析补充

- 保留主窗口和最近 `3d` 辅助窗口，并新增最近 `24h` 辅助窗口 `recent24h`。
- 最近 `24h` 辅助窗口的采集结果使用 `instance_data_recent24h.json`，批量快照可使用 `instance_data_recent24h_*.json`。
- 当主窗口正常、最近 `3d` 正常、但最近 `24h` 异常时，应判定为 `最新出现的短时异常`，不要让短窗口结论覆盖主窗口。
- `qps`、`tps`、`IOPSRate`、`network_in`、`network_out` 这类吞吐指标，不再依赖固定 `capacity model`，而是用 `启发式` 信号做风险升级。
- 吞吐启发式要联合引用 `p95`、`p99`、`cv`、`spike_ratio` 与滑动 MAD 尖峰结果；只有组合信号足够强时才升级到 ``risk_tier = high``。
- 资源评分采用 `avg + median + p95` 的平衡视角，避免低均值掩盖持续偏高或高分位压力。
- 对 `cpu`、`memory`、`disk_util` 额外识别 `pressure.level`，用于捕捉“没有明显尖峰、但持续高位运行”的资源压力。
- 对 `qps`、`tps`、`IOPSRate`、`network_in`、`network_out` 额外识别 `saturation.level`，用于标记“稳定高吞吐平台期”，避免只因波动不大就低估风险。
- 采集后要结合 `correlation_summary` 做跨指标关联判断，优先区分“业务负载上升”“计算压力”“存储路径压力”“复制链路压力”。

## 本项目可用工具

本项目中应只使用以下能力，不要引用不存在的工具名：

- `execute`：仅用于运行 `./skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py` 和必要的非分析型目录操作
- `glob`：查找生成的 `metric_data/*.json` 文件
- `grep`：仅用于从已有结果文件中做简单定位，不得替代分析脚本做批量汇总
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
- 禁止为分析数据生成或运行任何临时脚本，包括落盘的 `.py` / `.sh` / `.ps1` 文件，以及 `execute python -c`、`python <<EOF`、PowerShell inline script 等内联脚本。
- 不要在回复中泄露 `AK/SK`、完整凭证或敏感配置。
- `analysis_depth` 与 `time_range` 是独立参数，不要绑定。
- 对用户提供的参数值必须原样使用，不得擅自改写、猜测修正、补全、截断、拼接、解码、重新编码、改变大小写或脱敏后再传给脚本。
- 对用户输入、长期记忆命中的实例信息、脚本采集结果、以及最终写入报告的字段值，都必须按原值使用，不对任何数据做修改。
- 不得改写、猜测修正、补全、截断、拼接、重新编码、改变大小写、四舍五入、格式化美化、单位换算、乘除换算、百分比折算或用估算值覆盖原值。
- 凭证优先使用 `credential_ref`，再由脚本从 `backend/.env` 解析真实 `AK/SK`；不要要求用户在聊天中直接提交真实密钥。
- 数据值已经是最终单位，禁止自行乘以 `100` 或做额外单位换算。
- 始终显式传入 `--output`，避免脚本把文件写到默认硬编码目录。
- 不要通过 `set VOLC_ACCESSKEY=...`、`export VOLC_ACCESSKEY=...` 等环境变量方式临时拼装命令；使用 `--credential-ref` 让脚本自行从 `backend/.env` 读取对应凭证。

## 输入参数

- `instance_id`：实例 ID，优先来自用户输入或长期记忆中的高置信匹配，例如 `mysql-xxxxx`
- `region`：区域，默认 `cn-shanghai`
- `time_range`：巡检时间范围，默认最近 `30d`
- `analysis_depth`：`basic` / `standard` / `deep`，默认 `deep`
- `credential_ref`：凭证引用，优先来自长期记忆或 `/memories/agents/dba/cloud_credentials_registry.json`

## 时间粒度策略

主窗口统一使用 `5m` 粒度采集，优先保留完整原始点位，再通过脚本预计算出的证据摘要进行分析。

双窗口辅助规则：

- 当主窗口 `time_range >= 7d` 时，除主窗口采集外，必须额外执行一次最近 `3d` 的辅助采集
- 主窗口统一使用 `5m` 粒度采集
- 最近 `3d` 辅助窗口也使用 `5m` 粒度
- `analysis_depth` 不影响这条双窗口规则；只要主窗口达到 `7d` 及以上，就执行最近 `3d` 辅助采集
- 如果用户显式要求只分析 `3d` 或更短时间范围，则不再追加第二个 `3d` 辅助窗口
- 最近 `3d` 辅助窗口用于快速判断近期问题是否仍在持续发生，不替代主窗口的长期趋势、容量与周期性分析

## 标准工作流

1. 先查长期记忆中的实例候选：
   - 优先查看 `/memories/instructions.txt`
   - 再查看 `/memories/agents/<当前_agent_id>/`
   - 如果存在 `/memories/agents/dba/cloud_credentials_registry.json`，优先结合其中的项目默认绑定和实例覆盖绑定解析 `credential_ref`
   - 必要时再扩展到其他 `/memories/agents/*/`
   - 如果命中 1 个高置信实例候选，优先使用记忆中的 `instance_id` / `region`，并向用户做最小确认
   - 如果命中多个候选，先让用户选择，不要直接开始巡检
   - 如果没有命中，再向用户追问实例信息

2. 再收集参数：
   - `instance_id`（可来自用户输入或长期记忆）
   - `region`（可来自用户输入或长期记忆）
   - `time_range`
   - `analysis_depth`
   - `credential_ref`（可来自用户输入、长期记忆或凭证注册表；缺失时再追问）
   - 如果长期记忆或注册表已经给出 `instance_id` / `region` / `credential_ref`，不要重复追问，只继续收集缺失项
   - 缺少参数时，用自然语言逐项追问；一次只追问当前继续巡检所需的一个关键缺项
   - 未经用户明确确认，不要擅自使用推荐默认值直接开始巡检
   - 收集后按原值使用，不要对任何参数做自动修正或转换；尤其不要改动 `credential_ref`

3. 用 `execute` 运行采集脚本，输出到项目内相对路径，例如：

   - 主窗口继续写到 `./metric_data/instance_data.json`
   - 当主窗口 `time_range >= 7d` 时，最近 `3d` 辅助窗口写到 `./metric_data/instance_data_recent3d.json`
   - 两个窗口必须分别采集、分别落盘，避免覆盖主窗口文件

```bash
python ./skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py \
  --instance-id <instance_id> \
  --region <region> \
  --credential-ref <credential_ref> \
  --hours <hours> \
  --period 5m \
  --action all \
  --output ./metric_data/instance_data.json
```

当主窗口 `time_range >= 7d` 时，再额外执行一次最近 `3d` 辅助采集：

```bash
python ./skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py \
  --instance-id <instance_id> \
  --region <region> \
  --credential-ref <credential_ref> \
  --hours 72 \
  --period 5m \
  --action all \
  --output ./metric_data/instance_data_recent3d.json
```

如果用户提供的是明确的起止时间，则改用：

```bash
python ./skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py \
  --instance-id <instance_id> \
  --region <region> \
  --credential-ref <credential_ref> \
  --start "YYYY-MM-DD HH:MM" \
  --end "YYYY-MM-DD HH:MM" \
  --period 5m \
  --action all \
  --output ./metric_data/instance_data.json
```

如果主窗口起止时间覆盖范围达到 `7d` 及以上，仍需额外执行上面的最近 `3d` 辅助采集；该辅助窗口始终表示“执行巡检时刻往回最近 3 天”。

4. 用 `glob` 查找生成的结果文件：
   - 主窗口：`./metric_data/instance_data_*.json`
   - 当主窗口 `time_range >= 7d` 时，辅助窗口：`./metric_data/instance_data_recent3d_*.json`

5. 用 `read_file` 按需逐个读取结果文件，优先看每个指标里的 `summary`、`evidence` 和 `node_summaries`：
   - 推荐直接读取 `metric_data/instance_data_*.json`
   - 当主窗口 `time_range >= 7d` 时，分析阶段按同一指标成对读取：先读主窗口结果，再读最近 `3d` 辅助窗口结果
   - 如果 `glob` 返回的是 `/metric_data/...`，可直接原样传给 `read_file`
   - 不要把路径改写成 `/backend/...`
   - 不要使用 `B:\...` 或 `/memories/../backend/...`
   - `summary.min`
   - `summary.max`
   - `summary.range`
   - `summary.avg`
   - `summary.median`
   - `summary.weighted`
   - `summary.data_point_count`
   - `evidence.coverage`
   - `evidence.distribution`
   - `evidence.variability`
   - `evidence.pressure`
   - `evidence.saturation`
   - `evidence.spikes.sliding_mad`
   - `evidence.spikes.risk_tier`
   - `evidence.spikes.risk_reason`
   - `evidence.trend`
   - `node_summaries[*].node`
   - `node_summaries[*].avg`
   - `node_summaries[*].median`
   - `node_summaries[*].weighted`
   - `node_summaries[*].range`
   - `node_summaries[*].evidence`
   - `node_summaries[*].max`
   - `node_summaries[*].all_zero`
   - `nodes`

6. 分析时遵循以下原则：
   - 先读 `summary`
   - 再读 `evidence`
   - 最后才在异常指标上回看 `nodes[].data_points`，不要一开始就把所有原始点位全读进上下文
   - `node_count == 1` 或指标为 `qps` / `tps` 时，沿用实例级分析
   - `node_count > 1` 且指标为 `cpu` / `memory` / `disk_util` / `IOPSRate` / `network_in` / `network_out` / `replication_delay` 时，必须先比较 `summary` 与 `node_summaries`
   - 只有某个指标异常、或 `node_summaries` 已显示明显热点节点 / 偏斜时，才继续读取对应文件里的 `nodes` / `data_points`
   - 顺序分析异常指标，不要并行读取一批大文件
   - 正常指标直接基于 `summary` 给出结论
   - `summary` 负责轻量统计概览；`evidence` 负责分析证据，不要把 `nodes[].data_points` 当作默认入口
   - 用 `summary.range` / `node_summaries[*].range` 解释波动幅度，用 `evidence.distribution` / `evidence.variability` 解释分布与波动，用 `evidence.spikes.sliding_mad` 判断是否存在统计学瞬时尖峰，再用 `evidence.spikes.risk_tier` 判断是否属于高风险尖峰
   - `evidence.spikes.sliding_mad.method` 固定为 `sliding_mad`，阈值固定为 `6 x MAD`
   - `evidence.spikes.risk_tier` 取值固定为 `none` / `low` / `high`
   - `evidence.spikes.risk_reason` 用于解释为什么该尖峰被判为 `low` 或 `high`
   - `cpu` / `memory` / `disk_util` 中，`evidence.spikes.sliding_mad.spike_count > 0` 且绝对值达到 `70%` 时，才升级为 `risk_tier = high`
   - `qps` / `tps` / `IOPSRate` / `network_in` / `network_out` / `replication_delay` 第一版只有统计学尖峰分层，没有 capacity model；即使出现 `spike_count > 0`，默认也只写为 `risk_tier = low`
   - `evidence.spikes.sliding_mad.spike_count > 0` 且 `risk_tier = low` 时，要明确写出“存在相对尖峰，但绝对值较低或暂未建立 capacity model，暂不按高风险尖峰处理”
   - `evidence.spikes.sliding_mad.spike_count > 0` 且 `risk_tier = high` 时，仍需明确写出“存在高风险瞬时尖峰，不能仅因均值正常而判定为低风险”
   - `evidence.coverage.coverage_ratio` 偏低时，要明确说明证据不完整，不要脑补高置信结论
   - 多节点结论必须同时写“实例整体结论”和“节点拆分结论”
   - 不猜测主节点 / 从节点 / 只读节点角色，只使用 `Node ID` 叙述
   - JSON 结果分析必须优先通过 `read_file` / `glob` / `grep` 完成，不要用 `execute python -c`、heredoc 或 PowerShell inline script 读取、汇总或分析 JSON
   - `execute` 仅用于运行采集脚本或必要的非分析型目录操作，不得用于编写、拼接、落盘或运行任何分析脚本
   - 如果 `execute` 返回"Command succeeded with no stdout/stderr"，说明命令已成功完成，应转去使用 `glob` / `read_file` 检查生成文件，不要继续猜测 `print flush`，也不要改用 inline 脚本补救
   - 不创建新脚本来进行分析；不得在 `backend/`、`backend/tmp/`、`/tmp` 或当前工作目录生成任何分析脚本，所有分析工作应通过读取已有文件完成
   - Skill 触发后，不要重新退回“先问 `instance_id`”的旧路径；如果长期记忆已经提供了高置信实例候选，应沿用该候选继续流程
   - 不要要求用户在聊天中提交真实 `AK/SK`；如果用户直接粘贴明文凭证，应提示改用 `credential_ref + backend/.env`
   - 当主窗口 `time_range >= 7d` 时，主窗口负责长期趋势、容量与周期性风险判断；最近 `3d` 辅助窗口负责确认问题是否当前仍在异常
   - 主窗口异常 + 最近 `3d` 异常：判定为“持续性 / 当前仍存在的问题”
   - 主窗口异常 + 最近 `3d` 正常：判定为“历史波动或阶段性问题”
   - 主窗口正常 + 最近 `3d` 异常：判定为“最近新出现或近期加剧的问题”
   - 主窗口正常 + 最近 `3d` 正常：维持健康 / 低风险结论
   - 如果最近 `3d` 辅助采集失败但主窗口成功，仍可输出主窗口分析，但必须明确写“最近 3 天辅助判断未获取”，不能脑补近期结论
   - 即使 `spikes.risk_tier != high`，只要 `pressure.level = high`，也要把它视为真实资源压力，而不是简单写“未见明显异常”
   - `saturation.level` 仅表示稳定高吞吐信号，不单独等价于容量瓶颈；要结合 `cpu` / `disk_util` / `IOPSRate` / `replication_delay` 以及 `correlation_summary` 再下结论

7. 输出巡检结果：
   - 如果用户只是要“结论”“概览”“摘要”，可以用简版结构回复：
     - 巡检概要
     - 健康评分
     - 核心指标分析
     - 异常发现
     - 行动建议
   - 如果用户明确要“报告”“巡检报告”“完整报告”“按模板输出”或“严格按照模板样式进行输出”，不要自由组织章节，直接遵循下方“报告输出要求”

8. 如用户要求“保存报告”或“生成文件”，使用 `obsidian-markdown` 风格写成 Markdown，并用 `write_file` 写入 `/memories/reports/` 下的 `.md` 文件。
   - 生成报告前，先使用 `read_file` 读取模板文件 `./skills/volcengine-rds-health-analyzer/assets/inspection_report_template.md`
   - 报告内容必须按照模板结构填充，只允许在模板已有占位符所在位置写入实际内容
   - 不要改变一级、二级标题顺序，也不要新增、删除、改名、重排模板固定章节
   - 没有数据的字段写“未获取”或“无异常”，不要删除模板章节
   - 报告文件名必须使用 `/memories/reports/<sanitized_instance_name>-inspection-<YYYYMMDD>.md` 格式，不要再使用 `inspection_report_<instance_id>_<YYYYMMDD>.md`
   - 文件名前缀优先使用采集结果里的 `instance_name`；缺失时回退到 `instance_id`
   - `sanitized_instance_name` 规则固定为：转小写；将非字母数字字符替换为 `-`；连续 `-` 折叠为单个；去掉首尾 `-`
   - 例如：`peets-prod-boh-mysql-paas-n-inspection-20260309.md`
   - 报告文件必须通过 `write_file` / `edit_file` 直接落到 `/memories/reports/`，这样前端页面才能把它识别为可下载的“Skill 报告”
   - 保存成功后，回复中要明确说明“这是由 `volcengine-rds-health-analyzer` Skill 生成的巡检报告，可在页面中直接下载”
   - 只有用户明确要求“保存报告”或“生成文件”时才写报告 Markdown；如果只是让你“记住”某个 instance id 或实例信息，应写入 `/memories/agents/<当前_agent_id>/` 下的长期记忆文件，而不是生成报告

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
- `resource_metrics.metrics.<metric_key>.evidence.pressure`：持续高压识别结果；资源型指标重点看 `level` / `reason` / `drivers`
- `resource_metrics.metrics.<metric_key>.evidence.saturation`：稳定高吞吐识别结果；吞吐型指标重点看 `level` / `reason`
- `resource_metrics.metrics.<metric_key>.node_summaries`：每个节点的轻量统计摘要
- `resource_metrics.metrics.<metric_key>.nodes`：按节点拆分的数据
- `resource_metrics.correlation_summary`：跨指标关联摘要；用于辅助判断是业务增长、CPU 压力、存储压力还是复制问题

按指标拆分方式处理：

- 节点级指标：`cpu`、`memory`、`disk_util`、`replication_delay`、`IOPSRate`、`network_in`、`network_out`
- 实例级指标：`qps`、`tps`（当前无节点拆分，不做节点排名）

## 多节点分析规则

- `node_count == 1`：沿用实例级分析，直接基于 `summary` 给结论
- `node_count > 1` 且属于节点级指标：先读 `summary` 与 `node_summaries`，只有节点异常或需要解释偏斜时才继续读 `nodes[].data_points`
- 节点级结论必须分两层：先给实例整体结论，再给最差节点 / 热点节点结论，避免跨节点均值掩盖单节点热点
- `2` 节点集群：重点写“节点 A vs 节点 B”的并排对比；如果整体正常但单节点进入告警档，异常发现里必须点名该 `Node ID`
- `3` 节点及以上：按加权值从高到低排序，明确写出热点节点、次热点节点和低负载节点，并解释负载分布；`weighted = 0.5 * avg + 0.5 * median`
- 不猜测主从角色，只使用 `Node ID`；没有可靠角色字段时，不要自行标注“主节点 / 从节点 / 只读节点”
- `replication_delay` 中 `all_zero = true` 的节点视为“非适用 / 疑似源节点候选”，不参与最差节点比较；若所有节点都为 `all_zero = true`，写“未观测到复制延迟”
- `qps` / `tps` 明确标注为“实例级指标，无节点拆分，不能用于定位单节点热点”

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

- 多节点补充规则：
  - `cpu` / `memory` / `disk_util` 等节点级指标统一先计算 `weighted = 0.5 * avg + 0.5 * median`
  - `cpu` / `memory` / `disk_util` 等节点级指标，先按 `summary.weighted` 计算实例级得分，再按每个适用节点的 `node.weighted` 计算节点得分，最终取更差者：`final_score = min(score(summary.weighted), min(score(node.weighted) for node in node_summaries if node.weighted is not None))`
  - `replication_delay` 仍按延迟上界判断，但仅比较 `all_zero != true` 的节点；最终取实例级与最差适用节点中更差者
  - `qps` / `tps` 继续按实例级 `summary` 评分 / 分析，不做节点排名
  - `range = max - min`，用于描述波动幅度；统计学瞬时尖峰统一以 `evidence.spikes.sliding_mad` / `node_summaries[*].evidence.spikes.sliding_mad` 为准，风险等级再看 `evidence.spikes.risk_tier`
  - `sliding_mad` 的阈值固定为 `6 x MAD`
  - `evidence.spikes.risk_tier = high` 表示“统计学尖峰 + 绝对值/容量占比达到高风险门槛”；`risk_tier = low` 表示“识别到统计学尖峰，但暂不按高风险负载尖峰处理”
  - `evidence.distribution.p95` / `evidence.distribution.p99` 用于识别高位压力
  - `evidence.variability.stddev` / `evidence.variability.cv` 用于识别波动强度

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
   - `qps`、`tps`、`IOPSRate`、`network_in`、`network_out` 中每出现一个 `evidence.spikes.risk_tier = high` 的指标，扣 `5`
   - 最低 `0`

5. 主从延迟（15 分）
   - `max < 1` → `15`
   - `1 <= max < 5` → `10`
   - `5 <= max < 10` → `5`
   - `max >= 10` → `0`

6. 综合健康（10 分）
   - 没有核心指标出现 `evidence.spikes.risk_tier = high` → `10`
   - `1-2` 个核心指标出现 `evidence.spikes.risk_tier = high` → `5`
   - 超过 `2` 个核心指标出现 `evidence.spikes.risk_tier = high` → `0`

## 报告输出要求

以下部分由模板固定提供，仅用于帮助理解模板覆盖范围；不要据此自行改写模板目录：

- **巡检概要**：实例信息、巡检范围、分析深度
- **健康评分**：总分与扣分说明
- **核心指标分析**：CPU、内存、磁盘、QPS、TPS、主从延迟、IOPS、网络
- **异常发现**：按严重程度排序
- **行动建议**：给出具体可执行建议
- **多节点拆分**：对节点级指标补充拓扑摘要和热点节点说明

凡是输出“巡检报告”类内容（无论是在聊天中直接展示，还是保存为 Markdown 文件），都必须先读取模板文件：

- 模板路径：`./skills/volcengine-rds-health-analyzer/assets/inspection_report_template.md`
- 先用 `read_file` 读取该模板，再按模板结构填充实际分析结果
- `inspection_report_template.md` 是巡检 Markdown 报告的唯一骨架来源，必须固定章节/标题顺序
- 只要输出目标是“巡检报告”或用户要求“按模板样式”，无论是在聊天中直接展示还是保存为文件，都必须从模板标题开始输出，不要在模板前后追加导语、总结、额外小节、下载说明或自由发挥的补充段落
- 固定章节/标题顺序，只允许在模板已有占位符所在位置填充内容
- 不得新增、删除、改名、重排模板中已存在的固定章节或标题
- 保留模板中现有一级、二级标题顺序，以及 Markdown 表格、callout、分隔线和内部备注块
- 模板已有表格必须继续使用，不要改成纯段落、列表或新增自定义小节
- 不要把模板内容包在 Markdown 代码块、引用块或额外容器里，也不要把模板表格改写成列表、段落或 JSON
- 所有填入占位符的实例 ID、实例名称、节点 ID、时间、配置值、监控值都必须来自原始输入或采集结果原文
- 分析结论、健康评分、风险等级可以新增，但它们属于派生内容，不得反向覆盖、替换或伪装成原始采集数据
- 没有数据的字段写“未获取”或“无异常”
- 无法确认时写“未获取”，不要估算、脑补或生成近似值
- 所有双窗口判断只能填入模板现有占位符位置
- 当主窗口 `time_range >= 7d` 时，必须显式区分“主窗口（用户请求范围）”与“最近 3 天辅助窗口”
- 不允许用最近 `3d` 的数据覆盖主窗口数据，也不允许把主窗口数据改写成最近 `3d` 结论；两者都必须按原值引用并带窗口标签
- 若本次分析还包含最近 `24h` 辅助窗口，则也必须在模板现有占位符内明确标注为“最近 24 小时辅助窗口”或 `recent24h`，并在“主窗口正常、最近 `3d` 正常、但最近 `24h` 异常”时表述为“最新出现的短时异常”；后续若调整该窗口语义，必须同步更新 `inspection_report_template.md` 顶部使用说明，避免模板与正文规则漂移
- `{{node_topology_summary}}`：写实例的节点拓扑摘要；`2` 节点突出对比，`3` 节点及以上突出排序
- `{{cpu_node_breakdown}}`、`{{memory_node_breakdown}}`、`{{disk_node_breakdown}}`、`{{replication_node_breakdown}}`、`{{iops_network_node_breakdown}}` 只允许填充模板已有位置；必须输出 Markdown 表格，列固定为 `Node | Avg | Median | Max | 风险级别 | 说明`，并按加权值从高到低排序
- `{{qps_tps_scope_note}}`：明确写“该指标当前无节点拆分，不能用于定位单节点热点”
- `{{cpu_range}}`、`{{memory_range}}`、`{{disk_range}}`、`{{qps_range}}`、`{{tps_range}}`、`{{replication_range}}`、`{{iops_range}}`、`{{network_in_range}}`、`{{network_out_range}}` 必须填写原始统计值对应的极差（`max - min`）

## median / weighted 补充约定

- 多节点指标优先读取 `summary.avg`、`summary.median`、`summary.weighted`，再对比 `node_summaries[*].avg`、`node_summaries[*].median`、`node_summaries[*].weighted`
- `summary.median` 用于补足只看均值时对持续高负载的识别盲区
- `node_summaries[*].median` 用于识别持续偏高节点，而不是只看瞬时峰值
- `summary.weighted` 用于实例级排序、热点判断和 CPU / 内存 / 磁盘评分
- `node_summaries[*].weighted` 用于节点排序、热点节点判断和节点级评分
- `summary.range` / `node_summaries[*].range` 用于衡量波动区间，避免瞬时尖峰被平均值和中位数掩盖
- `evidence.distribution` 用于汇总 `min` / `max` / `range` / `avg` / `median` / `p95` / `p99`
- `evidence.variability` 用于输出 `stddev` 与 `cv`
- `evidence.spikes.sliding_mad` 用于输出滑动窗口 MAD 尖峰判断结果，其中 `method` 固定为 `sliding_mad`
- `evidence.spikes.risk_tier` 用于输出尖峰风险分层结果：`none` / `low` / `high`
- `evidence.spikes.risk_reason` 用于输出尖峰分层原因，便于在结论中直接引用
- `node_summaries[*].evidence` 用于节点级证据摘要；优先用它定位热点节点，而不是默认读原始点位
- `evidence.spikes.sliding_mad.spike_count > 0` 时，应在结论、异常发现和行动建议里显式说明“瞬时尖峰已被识别”
- `evidence.spikes.risk_tier = low` 时，应写“存在相对尖峰，但绝对值较低”或“暂未建立 capacity model”
- `evidence.spikes.risk_tier = high` 时，才按高风险尖峰参与扣分、排序和行动建议升级
- `weighted = 0.5 * avg + 0.5 * median`
- 节点拆分表格固定表头：`Node | Avg | Median | Max | 风险级别 | 说明`
- `3` 节点及以上时，热点节点、次热点节点和低负载节点均按加权值排序与描述

如果保存为 Markdown，建议文件名与路径：

```text
/memories/reports/<sanitized_instance_name>-inspection-<YYYYMMDD>.md
```

其中：

- `<sanitized_instance_name>`：优先取采集结果中的 `instance_name`，缺失时回退到 `instance_id`
- 规范化规则：转小写；将非字母数字字符替换为 `-`；连续 `-` 折叠为单个；去掉首尾 `-`
- 示例：`/memories/reports/peets-prod-boh-mysql-paas-n-inspection-20260309.md`

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
- 当产出巡检报告文件时，要强调这是 `volcengine-rds-health-analyzer` Skill 的输出结果，而不是“某个工具文件”。
- 采集数据时应遵循 skill 中的流程，并通过 `execute` 运行 skill 自带脚本。
- 任何项目文件的路径匹配都必须使用相对路径；读取项目文件时优先使用相对路径或直接复用 `glob` 返回的 `/...` 虚拟路径。
- `execute` 成功但无输出时，应把它视为“命令执行成功但没有终端文本”，不要围绕 `flush`、同一条 `python -c` 命令或其他 inline script 反复重试。
- 不得通过 `write_file` / `edit_file` 生成分析脚本，也不得通过 `execute python -c`、`python <<EOF`、PowerShell inline script 对 `metric_data/*.json` 做脚本化分析。
- 生成巡检 Markdown 报告时，必须遵循 `./skills/volcengine-rds-health-analyzer/assets/inspection_report_template.md` 的格式与章节结构。
## metric_data retention

- 每次执行采集脚本前，会自动清理 `./metric_data/` 中修改时间超过 `30` 天的 `.json` 文件
- 可通过 `--retention-days <days>` 调整保留期
- 可通过 `--skip-cleanup` 跳过本次清理
