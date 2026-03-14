# Agent Runtime 与 Skills 装配设计

## 1. 设计目标

运行时层需要解决以下问题：

- 如何清晰定义不同 Agent 的职责边界
- 如何为不同 Agent 注入不同 Prompt、Skills 与 MCP 工具
- 如何让 `router` / `supervisor` 安全调度叶子 Agent
- 如何把长期记忆纳入上下文而不破坏边界

## 2. Agent 配置模型

每个 Agent 由 manifest + profile 描述，核心字段包括：

- `id` / `label` / `description`
- `prompt_paths`
- `skills`
- `capabilities`
- `risk_level`
- `execution_mode`
- `allowed_handoffs`
- `subagent_configs`

当前内置 Agent：

- `router`：默认入口、轻量路由与升级判断
- `supervisor`：复杂任务协调、并行调度、结果整合
- `general`：通用阅读、解释、Markdown 整理
- `dba`：数据库分析与巡检
- `ops`：运维排障

## 3. Runtime 构建流程

```text
收到 agent_id
  -> AgentManager 读取 AgentProfile
  -> 组合 prompts/base + 角色 Prompt
  -> 解析 Skills 路径
  -> 查询绑定的 MCP Servers
  -> 按需构建并缓存 runtime
```

如果 Agent 声明了 `subagent_configs`，运行时会继续构建可调度的子 Agent 结构。

## 4. Skills 装配原则

- `general` 只注入通用阅读与 Markdown 相关 Skills
- `dba` 只注入数据库与巡检相关 Skills
- `ops` 只注入远程运维、Docker、Kubernetes 等 Skills
- `router` / `supervisor` 只持有编排所需的最小能力

这样可以避免越权、前后端边界漂移和隐式能力暴露。

## 5. 长期记忆

运行时从 `/memories/` 中按需读取相关片段，优先注入：

- `/memories/instructions.txt`
- `/memories/agents/<agent_id>/`
- 领域专属注册信息（例如 DBA 云凭证注册表）

注入遵循“相关片段优先、有限摘录”的原则，而不是整棵记忆树一次性加载。
