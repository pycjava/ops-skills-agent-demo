# MySQL SQL Analyzer 设计说明

## 1. Skill 定位

`mysql-sql-analyzer` 用于分析单条 MySQL SQL 的执行计划和潜在性能风险。它不是数据库变更工具，也不是 SQL 执行器，而是一个**只读执行计划分析 Skill**。

## 2. 设计目标

- 对单条 SQL 建立稳定、可重复的执行计划分析流程。
- 自动补充相关表结构和索引证据，避免只看 `EXPLAIN` 表面字段。
- 把优化建议建立在真实计划与元数据上，而不是经验猜测。

## 3. 输入约束

进入分析前必须拿到：

- 单条完整 SQL
- `host`
- `port`
- `database`

连接凭据不通过用户聊天直接传递，而是通过环境变量注入：

- `MYSQL_USER`
- `MYSQL_PASSWORD`

这体现了“连接目标与敏感凭据分离”的设计。

## 4. 运行边界

- 仅执行 `EXPLAIN`、`SHOW` 和 `information_schema` 查询。
- 禁止直接执行原 SQL，尤其是 `UPDATE`、`DELETE`、`INSERT`。
- 禁止在回复中泄露数据库密码或完整连接串。

该边界的意义在于：既能获得足够分析证据，又不引入数据写风险。

## 5. 标准执行流程

```text
收集 SQL 和连接目标
  -> 调用 analyze_mysql_sql.py
  -> 获取 EXPLAIN FORMAT=JSON
  -> 抽取涉及表
  -> 读取表结构和索引
  -> 按规则识别风险
  -> 输出摘要、证据与优化建议
```

### 5.1 默认分析

默认使用 `EXPLAIN FORMAT=JSON`，原因是：

- 成本较低
- 风险更小
- 已足以识别大多数计划层问题

### 5.2 深入分析

只有在用户明确要求、并能接受额外开销时，才启用 `EXPLAIN ANALYZE`。

## 6. 依赖资产

该 Skill 当前依赖：

- `backend/skills/mysql-sql-analyzer/scripts/analyze_mysql_sql.py`
- `backend/skills/mysql-sql-analyzer/references/rules.md`
- `backend/skills/mysql-sql-analyzer/references/env-vars.md`

这些资产的分工是：

- 脚本负责标准化采集与输出。
- `rules.md` 负责判读规则。
- `env-vars.md` 负责环境变量约束和连接安全建议。

## 7. 分析输出结构

Skill 推荐按以下结构给出结论：

- 执行计划摘要
- 风险发现
- 表结构与索引证据
- 优化建议

重点不是只说“慢”，而是回答：

- 为什么慢
- 慢在什么访问路径
- 哪些索引没有命中或设计不合理
- 优化优先级应该怎么排

## 8. 典型风险类型

该 Skill 重点关注：

- 全表扫描
- `filesort`
- 临时表
- 低效 join 顺序
- 错误或缺失索引
- 计划中行数估计异常

## 9. 与其他 Skill 的边界

- 如果用户要做数据库巡检，应切换到 `volcengine-rds-health-analyzer`。
- 如果用户要解释 SQL 语法本身，而不是执行计划，可由 `general` 能力处理。
- 如果用户要求真正执行 SQL 或修改索引，该 Skill 只能先提供诊断和建议，不能直接代替变更流程。

## 10. 失败场景与回退

- 缺少 SQL 或连接目标时，应先补齐输入。
- 无法连接数据库时应反馈连接问题，不应猜测性能结论。
- 无法安全执行 `EXPLAIN ANALYZE` 时，应退回默认只读分析模式。

## 11. 设计取舍

- 通过脚本统一分析流程，结果更稳定，但也要求脚本与规则持续同步。
- 只做只读计划分析，安全性更高，但不能直接验证全部真实运行时问题。
