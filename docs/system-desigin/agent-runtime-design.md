# Agent 运行时与 Skills 装配设计说明

## 1. 子系统定位

Agent 运行时是 AgentWeave 最核心的差异化子系统。它解决的问题不是“如何调用一个模型”，而是：

- 如何把不同角色的 Agent 明确化
- 如何为每个 Agent 注入不同的 Prompt、Skills 和工具
- 如何让 `orchestrator` 能安全地路由到专业子 Agent
- 如何把长期记忆、MCP 与 Skills 统一纳入运行上下文

## 2. 运行时组成

```text
AgentProfile
  → Prompt 片段
  → Skill 白名单
  → MCP 连接
  → 执行模式
  → 风险等级
  → 可交接子 Agent
```

关键实现文件：

- `backend/agent_profiles.py`
- `backend/agent_manager.py`
- `backend/agent.py`
- `backend/skill_catalog.py`
- `backend/prompts/*.md`

## 3. Agent 配置模型

每个 Agent 通过 `AgentProfile` 声明自身能力边界，包括：

- 身份信息：`id`、`label`、`description`
- Prompt 组合：`prompt_paths`
- Skill 白名单：`skills`
- 业务能力：`capabilities`
- 风险等级：`risk_level`
- 执行方式：`execution_mode`
- 路由范围：`allowed_handoffs`

当前内置的核心 Agent 包括：

- `orchestrator`：默认入口与任务路由
- `general`：通用阅读、解释、Markdown 整理
- `dba`：数据库分析与巡检
- `ops`：运维排障

## 4. Runtime 构建流程

```text
收到 agent_id
  → AgentManager 读取对应 AgentProfile
  → 组合 prompts/base + 领域 Prompt
  → 解析 profile.skills 对应的 Skill 路径
  → 查询该 Agent 绑定的 MCP Servers
  → 组装 Deep Agent runtime
  → 放入本地缓存
```

其中 `AgentManager` 的职责是“按需构建 + 复用缓存”，避免每个请求都重新装配完整运行时。

## 5. Skill 装配机制

### 5.1 技能发现

`skill_catalog.py` 会扫描 `backend/skills/*/SKILL.md`，从 Frontmatter 中提取：

- `name`
- `description`
- `path`

并生成统一的 Skill Catalog。

### 5.2 白名单注入

Skill 不由前端决定，而由后端根据 AgentProfile 注入运行时：

- `general` 只拿到通用阅读与 Markdown 相关 Skills
- `dba` 只拿到数据库和巡检相关 Skills
- `ops` 只拿到远程运维、Docker、Kubernetes 等 Skills
- `orchestrator` 则以编排型 Skill 为主

这样可以防止：

- 能力越权
- UI 与运行时不一致
- 因前端隐藏而导致的“假隔离”

## 6. Prompt 组合机制

Prompt 不写成一个超长固定文件，而是通过 `prompt_paths` 组合：

- 通用基础 Prompt
- 领域 Prompt
- 运行时提示

其中运行时提示会补充：

- 当前 Agent 可交接的子 Agent
- 长期记忆写入位置
- 当前可用的 Skills 与工具边界

## 7. 长期记忆注入

`agent.py` 会根据用户消息内容和当前 Agent 身份，从 `/memories/` 中挑选相关文档片段注入上下文。重点来源包括：

- `/memories/instructions.txt`
- `/memories/agents/<agent_id>/`
- `dba` 相关的云凭证注册表

注入过程采用关键词匹配和有限摘录，而不是把整棵记忆树一次性加载进上下文。

## 8. 事件输出模型

运行时最终输出给前端的不是单一文本，而是结构化事件流：

| 事件 | 含义 |
|------|------|
| `text_delta` | 普通文本增量 |
| `thinking_delta` | 思考过程增量 |
| `tool_call` | 工具调用开始 |
| `tool_result` | 工具执行结果 |
| `routing` | 正在切换到专业子 Agent |
| `done` | 本轮执行结束 |
| `error` | 执行失败 |

这种事件模型使前端能区分“模型在说什么”和“系统在做什么”。

## 9. MCP 集成机制

`AgentManager` 在构建 runtime 时会查询该 Agent 可用的 MCP 连接，并将其加载为工具列表。这样 MCP 被统一纳入 Agent 的能力集合，而不是独立成另一套调用体系。

优点包括：

- 工具发现入口统一
- Agent 能力边界更清晰
- 后续可以按 Agent 做 MCP 权限隔离

## 10. 设计价值

这个子系统的价值在于把“LLM 调用”提升为“可治理的 Agent Runtime”：

- 角色明确
- 能力可控
- 扩展一致
- 路由可解释
- 技能可维护

这也是项目后续继续扩展领域 Agent、团队权限和企业级审计能力的基础。
