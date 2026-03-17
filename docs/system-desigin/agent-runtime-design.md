# Agent Runtime 与 Skills 装配设计

## 1. 设计目标

运行时层负责回答三个关键问题：

- 当前会话应该由哪个 Agent 执行？
- 该 Agent 在这一轮执行中到底拥有哪些能力？
- 多 Agent 协调时如何避免能力越权和职责混乱？

因此，运行时设计的重点不是“尽可能强”，而是“能力边界清晰、装配过程稳定、默认策略可解释”。

## 2. Agent 配置模型

### 2.1 配置来源

运行时配置来自两层：

- `backend/agents/registry.toml`：定义默认 Agent 和对外公开顺序。
- `backend/agents/*/agent.toml`：定义单个 Agent 的角色、prompt、Skills 和编排关系。

### 2.2 AgentProfile 字段

`AgentProfile` 统一描述每个 Agent 的运行时元信息，核心字段包括：

- `id`：稳定标识。
- `label` / `description`：面向 UI 和日志的说明。
- `prompt_paths`：要组合的 prompt 文件。
- `skills`：允许装配的 Skills 白名单。
- `capabilities`：对能力边界的自然语言描述。
- `risk_level`：风险等级。
- `execution_mode`：执行模式。
- `allowed_handoffs`：允许转交的目标 Agent。
- `subagent_configs`：在 runtime 中需要预构建的子 Agent 列表。

### 2.3 当前 Agent 拓扑

- `router`：默认入口，负责一次性轻量路由和升级判断。
- `supervisor`：复杂任务协调器，负责多域整合。
- `general`：通用问答、文档阅读、代码解释、Markdown 整理。
- `dba`：数据库分析、RDS 巡检和 SQL 分析。
- `ops`：远程运维、Docker 与 Kubernetes 诊断。

## 3. Runtime 初始化流程

`AgentManager` 负责按需初始化 runtime 资源。

### 3.1 基础资源初始化

首次请求 runtime 时会初始化：

- `AsyncSqliteSaver`：用作 LangGraph checkpoint。
- `AsyncSqliteStore`：用作共享存储。
- `ChatAnthropic`：模型实例。
- `McpRegistryService`：MCP 连接解析器。

这样做的原因是：

- 避免应用启动时为所有可能能力做重初始化。
- 同时保证资源在整个进程生命周期内可复用。

### 3.2 Runtime 构建流程

```text
收到 agent_id
  -> 解析 AgentProfile
  -> 检查 runtime 缓存
  -> 组合 system prompt
  -> 解析 Skills 路径
  -> 加载绑定的 MCP tools
  -> 如有需要构建 subagents
  -> 调用 create_deep_agent
  -> 缓存 runtime
```

## 4. 执行模式设计

### 4.1 `direct`

`general`、`dba`、`ops` 属于直接执行模式。

特点：

- 直接响应用户任务。
- 不调度其他 Agent。
- 只关注自己领域的 Skills 和工具。

### 4.2 `router`

`router` 是默认入口 Agent。

它的职责被刻意收窄为：

- 识别任务属于哪一类。
- 判断是否可以直达叶子 Agent。
- 判断是否需要升级到 `supervisor`。

它不应承担：

- 深入领域分析。
- 多域并行诊断。
- 最终复杂结果整合。

### 4.3 `supervisor`

`supervisor` 只处理从 `router` 升级而来的复杂任务。

职责包括：

- 串行或并行调用叶子 Agent。
- 整理跨域证据。
- 输出统一结论、优先级和建议。

它不会把任务再交回 `router`，以避免路由环路。

## 5. Prompt 装配策略

### 5.1 静态 Prompt

每个 Agent 声明若干 `prompt_paths`，通常包含：

- `prompts/base.md`
- 角色专属 prompt，如 `prompts/router.md`、`prompts/dba.md`

### 5.2 运行时 Hint

`AgentManager` 在静态 prompt 之后追加运行时 Hint，明确说明：

- 当前 `agent_id` 与显示名称。
- 执行模式和风险等级。
- 能力边界和可调度子 Agent。
- 长期记忆优先写入路径。
- “只能使用当前 runtime 已注入的 Skills 和工具”。

这一步很关键，因为它把“配置层的约束”转成了模型执行时可见的指令。

### 5.3 对话上下文装配

除了 system prompt 之外，聊天链路还会在 `backend/agent.py` 中为当前用户消息组装可复用上下文。当前顺序为：

```text
用户消息
  -> 尝试构建 <rag_context>
  -> 若 RAG 不可用或无命中，回退到 <memory_context> + <attachment_context>
  -> 叠加 <multimodal_context>
  -> 生成最终 HumanMessage
```

这里刻意把上下文装配放在 runtime 外部，而不是把 RAG 逻辑塞进 prompt 文件，原因是：

- 检索、作用域过滤和回退策略属于运行时行为，不应依赖静态 prompt 文案表达。
- 这样可以在不改 Agent 配置的情况下替换检索实现或关闭 RAG。

## 6. Skills 装配原则

### 6.1 白名单装配

Skills 不由前端决定，也不依赖 prompt 中自由描述，而是由 `agent.toml` 中的 `skills` 字段显式声明。

装配过程：

```text
读取 agent.skills
  -> 在 backend/skills 中解析元数据
  -> 转成 runtime 可用路径
  -> 注入 create_deep_agent(...)
```

### 6.2 当前装配策略

- `general`：`file_reader`、`code_explainer`、`obsidian-markdown`、`using-superpowers`
- `dba`：`mysql-sql-analyzer`、`volcengine-rds-health-analyzer`、`volcengine-rds-report-summarizer`、`using-superpowers`
- `ops`：`remote-ops`、`docker`、`kubernetes`、`using-superpowers`
- `router` / `supervisor`：仅 `using-superpowers`

### 6.3 设计原因

- 让编排层只拥有编排能力，不直接拥有业务型操作能力。
- 让领域 Agent 的能力边界可预测、可测试。
- 让新增 Skill 时只需更新白名单，而不是在系统中隐式“生效”。

## 7. 子 Agent 装配策略

### 7.1 SubAgent 构建

如果某个 Agent 声明了 `subagent_configs`，运行时会递归构建子 Agent 配置，并将其传给 DeepAgents。

子 Agent 继承自己的：

- `id`
- `description`
- `system_prompt`
- `skills`

而不是沿用父 Agent 的技能集。

### 7.2 循环防护

运行时通过 `lineage` 检查递归路径，避免配置错误导致的循环子 Agent 依赖。

## 8. MCP 工具装配

### 8.1 装配流程

```text
读取当前 Agent 的 MCP 绑定
  -> 查询连接配置
  -> 为每个 server 获取 tools
  -> 汇总后注入 runtime
```

### 8.2 失败策略

- 某个 MCP server 加载失败时，仅跳过该 server。
- MCP 依赖缺失时 runtime 仍可继续构建。
- 没有连接时直接返回空工具集。

这保证了外部工具故障不会完全阻断基础对话能力。

## 9. 长期记忆装配

### 9.1 暴露方式

`AgentManager` 使用 `CompositeBackend` 将 `/memories/` 路由到 `StoreBackend`，使 runtime 能通过统一路径读写长期记忆。

### 9.2 记忆边界

运行时 Hint 会明确建议：

- 新写入记忆优先进入 `/memories/agents/<agent_id>/`
- 共享说明和报告通过 `/memories/` 暴露

这样做的好处是：

- 共享信息与 Agent 私有经验可分层治理。
- 前端可以把报告和记忆都作为 artifact 打开。

### 9.3 与 RAG 的关系

RAG 并不替代 `/memories/` 的原始读写能力，而是把 `/memories/` 和文本附件进一步转换为“可检索上下文”。因此运行时层同时依赖两条能力：

- `/memories/` 作为长期真值存储与工具可访问路径。
- `RagService` 作为聊天场景下的自动召回增强层。

这样可保证：

- Agent 仍可按工具链显式读写 `/memories/`。
- 聊天主链路在进入 runtime 前就能得到更紧凑的相关上下文。

## 10. 缓存与生命周期

### 10.1 缓存

- runtime 构建后按 `agent_id` 缓存。
- 配置变更时可通过失效机制清空缓存。

### 10.2 生命周期

- 应用启动时只做数据库和调度器初始化，不强制构建所有 runtime。
- 首次使用某个 Agent 时再初始化对应 runtime。
- 应用关闭时统一释放 SQLite 资源和 runtime 资源。

## 11. 默认策略与兼容性

- 默认 Agent 由 `registry.toml` 指定为 `router`。
- 旧数据中的历史别名或无效 `agent_id` 在读取时可做规范化或回退。
- public Agent 顺序决定前端默认可见的主 Agent 顺序。

## 12. 风险控制

- 通过 `risk_level` 为不同 Agent 提供风险标识。
- 通过 `allowed_handoffs` 限制可调度目标。
- 通过 Skills 和 MCP 白名单防止能力越界。
- 通过运行时 Hint 明确禁止使用未注入能力。

## 13. 设计取舍

- 用配置文件定义 Agent，扩展性强，但要求配置和代码同时保持一致。
- 用缓存复用 runtime，性能更好，但配置更新后需要显式失效。
- 把权限、Skill 和 MCP 限制都放在后端，更安全，但系统设计上更偏“后端治理中心”。

## 14. 演进方向

- 把 runtime 观测信息暴露为更可视化的调试数据。
- 对 `risk_level` 和 `capabilities` 引入更结构化的策略用途。
- 支持更细粒度的 memory namespace 和基于任务的上下文隔离。
