# AgentWeave 总体设计

## 1. 产品定位

AgentWeave 是一个面向运维、数据库分析与通用知识工作的多 Agent 工作台。系统以 Web 对话为统一入口，把会话、流式执行、定时任务、任务提醒、MCP Server、长期记忆和权限控制组合成一个可运行的示例平台。

它不是单纯的聊天界面，也不是把不同 Agent 简单并排摆放，而是强调三件事：

- **统一入口**：用户始终从一个工作台进入系统。
- **显式编排**：由 `router` 和 `supervisor` 明确承担路由与复杂任务协调职责。
- **能力可治理**：Skills、MCP、长期记忆和权限都在后端做边界控制，而不是仅依赖前端隐藏按钮。

## 2. 设计目标

### 2.1 核心目标

- 为多 Agent 系统提供统一的会话式交互入口。
- 让不同领域能力通过白名单方式装配，避免能力漂移。
- 支持从即时对话过渡到后台异步任务，覆盖“现在分析”和“定时巡检”两类场景。
- 保持前后端职责清晰：前端负责工作台体验，后端负责运行时、数据一致性和能力治理。

### 2.2 非目标

- 不把当前实现设计成通用分布式调度平台。
- 不在前端复制 Agent 运行时逻辑。
- 不允许任何 Agent 默认获得全部 Skills、全部 MCP 或全部记忆访问权限。

## 3. 系统边界

系统由四类边界清晰的部分构成：

### 3.1 用户侧

- 浏览器中的 Vue 工作台负责聊天、任务、提醒、MCP、记忆和登录交互。
- 用户通过自然语言、附件、右侧面板和任务抽屉与系统交互。

### 3.2 应用侧

- FastAPI 提供 REST API 和 WebSocket。
- 后端服务层负责会话、任务、提醒、MCP、记忆、RAG 检索增强、认证和 Agent 运行时编排。

### 3.3 运行时侧

- `AgentManager` 负责构建和缓存 DeepAgents runtime。
- Skills 由 `backend/skills/` 提供。
- MCP 工具由 `mcp_servers` 配置动态绑定到指定 Agent。

### 3.4 持久化与外部依赖

- SQLite 负责业务实体和 LangGraph 持久化。
- `/memories/` 作为长期记忆与报告产物空间。
- Chroma 负责本地向量索引，embedding 默认通过远程接口生成。
- 外部依赖包括 Anthropic 模型、OIDC 提供方、远程主机、Docker/Kubernetes 集群、云 API 和外部 MCP Server。

## 4. 总体架构

```text
浏览器
  -> Vue 3 工作台
      -> REST API（列表、配置、任务、提醒、认证、MCP、记忆）
      -> WebSocket（流式对话）

FastAPI 应用
  -> 路由层
  -> 业务服务层
  -> RAG Service / Chroma Index
  -> AgentManager / Skill Catalog / MCP Registry
  -> SQLite / LangGraph Store / /memories/

Agent Runtime
  -> router / supervisor / general / dba / ops
  -> Skills 白名单
  -> MCP 工具绑定
  -> <rag_context> / /memories/ 上下文注入
  -> /memories/ 长期记忆读写
```

这一架构体现了两个关键原则：

- **同步配置走 REST，流式执行走 WebSocket**。
- **能力注入在后端完成，前端只消费结果与元数据**。

## 5. 核心子系统

### 5.1 会话子系统

会话子系统承载用户与 Agent 的主要互动，覆盖：

- 会话列表与当前会话切换。
- 消息持久化与流式渲染。
- 当前 Agent 选择与对话上下文绑定。
- 会话级附件快照。

实现映射：

- 前端入口：`frontend/src/App.vue`
- 前端状态：`frontend/src/stores/chat.ts`、`frontend/src/stores/chat/conversations.ts`、`frontend/src/stores/chat/socket.ts`
- 后端服务：`backend/services/conversation_state.py`、`backend/services/conversation_messages.py`
- 后端路由：`backend/api/routers/conversations.py`、`backend/api/ws/chat.py`

### 5.2 Agent Runtime 子系统

运行时子系统负责把“某个 Agent 的描述”转换为“可执行的真实 runtime”，并保证：

- 使用正确的 prompt 组合。
- 只装配允许的 Skills。
- 只绑定分配给该 Agent 的 MCP 工具。
- 对 `router`、`supervisor` 这类编排型 Agent 构建子 Agent 图。

实现映射：

- `backend/agent_profiles.py`
- `backend/agents/*/agent.toml`
- `backend/agent_manager.py`
- `backend/skill_catalog.py`

### 5.3 定时任务子系统

该子系统把原本一次性的会话请求提升为可以反复执行的后台任务，核心能力包括：

- 从会话识别“定时执行”意图。
- 生成任务草稿并允许用户确认。
- 周期性触发任务执行。
- 为每次执行创建运行会话、执行记录与提醒。

实现映射：

- 前端：`frontend/src/stores/chat/tasks.ts`、`frontend/src/components/TaskDrawer.vue`
- 后端：`backend/api/routers/inspection_tasks.py`、`backend/services/inspection_tasks.py`、`backend/services/inspection_scheduler.py`

### 5.4 能力扩展子系统

能力扩展由两部分组成：

- **Skills**：静态目录式能力包，负责流程规范、脚本、模板和参考资料。
- **MCP**：动态可配置工具连接，支持按 Agent 绑定。

这样区分的原因是：

- Skills 适合沉淀流程与方法论。
- MCP 适合接入外部可调用工具。

实现映射：

- Skills：`backend/skills/`
- MCP：`backend/models/mcp_server.py`、`backend/services/mcp_registry.py`、`backend/api/routers/mcp.py`

### 5.5 长期记忆与报告子系统

长期记忆负责在对话和任务之外保留可复用的上下文，包括：

- 共享说明与操作约束。
- Agent 专属记忆。
- 巡检报告、汇总文档等可下载产物。

实现映射：

- 后端服务：`backend/services/memory.py`
- 前端面板：`frontend/src/components/MemoryPanel.vue`
- 前端状态：`frontend/src/stores/chat/memory.ts`

### 5.6 RAG 检索增强子系统

RAG 子系统负责把“会话附件 + `/memories/` 文档”转成可检索的统一知识源，并在聊天链路中自动召回相关片段。它承担：

- 文档标准化与切块。
- 远程 embedding 生成。
- Chroma 本地向量索引持久化。
- 基于会话和 Agent 边界的召回过滤。
- 将检索结果格式化为 `<rag_context>` 注入运行时 prompt。

实现映射：

- 后端服务：`backend/services/rag.py`
- 后端入口：`backend/api/routers/rag.py`
- 聊天接入：`backend/agent.py`

### 5.7 认证与权限子系统

认证与权限子系统负责：

- 登录状态判定。
- OIDC / 密码登录接入。
- 基于角色的权限控制。
- 对 REST 与 WebSocket 统一施加权限检查。

实现映射：

- 后端：`backend/api/routers/auth.py`、`backend/auth/`
- 数据模型：`backend/models/auth.py`
- 前端状态：`frontend/src/stores/chat/auth.ts`

## 6. 关键业务链路

### 6.1 实时对话链路

```text
用户输入消息
  -> 前端通过 WebSocket 发送消息和上下文
  -> 后端确定当前会话与 agent_id
  -> RAG 从当前会话附件与可见 memories 中召回相关片段
  -> Agent runtime 执行
  -> 后端把 text_delta / thinking_delta / tool_call / tool_result / routing 等事件推送给前端
  -> 前端渐进更新消息气泡
  -> 完成后落库为会话消息
```

设计重点：

- 将“最终消息”拆成事件流，而不是等全部完成后一次性返回。
- 前端展示的是一条消息的生命周期，而不是一串互不关联的字符串。
- 检索增强默认自动发生，但任何索引或 embedding 问题都不应阻断对话主流程。

### 6.2 从会话到定时任务链路

```text
用户在聊天中提出“定时执行 / 定时巡检”
  -> 后端分析是否命中任务意图
  -> 生成任务草稿或直接创建任务
  -> 前端在任务抽屉中展示草稿
  -> 用户确认后保存为 InspectionTask
```

设计重点：

- 复用会话上下文减少重复配置。
- 把“任务生成”设计成显式确认流程，避免模型直接创建高风险后台任务。

### 6.3 后台任务执行链路

```text
调度器扫描到期任务
  -> 创建 InspectionTaskRun
  -> 创建运行会话
  -> 调用指定 Agent 执行
  -> 结果写入消息流和持久化记录
  -> 生成 TaskNotification
  -> 前端提醒中心显示未读提醒
```

设计重点：

- 任务执行结果通过“运行会话”进入与普通聊天一致的展示模型。
- 通知只承担异步唤醒作用，不替代完整结果查看。

## 7. 关键数据对象

### 7.1 会话域

- `Conversation`：会话本体，包含标题、来源、绑定 Agent、来源任务信息。
- `Message`：消息本体，支持文本、工具调用、工具结果、错误和思考信息。
- `ConversationAttachment`：会话级附件，支持上传后在后续消息中形成快照引用。

### 7.2 任务域

- `InspectionTask`：任务定义，记录调度表达式、目标 Agent、提示模板和最近执行状态。
- `InspectionTaskRun`：单次执行记录，记录运行会话、触发方式、完成状态和报告路径。
- `TaskNotification`：异步提醒，负责未读状态、摘要和报告下载入口。

### 7.3 扩展能力域

- `McpServer`：MCP 连接配置，包括传输方式、命令/URL、Agent 绑定和测试结果。
- `User` / `Role` / `Permission`：认证与权限模型。

## 8. 安全与治理

### 8.1 权限治理

- 登录不是前端状态判断，而是后端会话和权限校验。
- REST 路由通过权限依赖保护。
- WebSocket 在握手后执行写权限检查，未授权直接拒绝连接。

### 8.2 能力治理

- Agent 只能获得 `agent.toml` 中声明的 Skills。
- Agent 只能绑定被分配的 MCP Server。
- `router` 和 `supervisor` 不直接拥有业务型 Skills，避免编排层越权操作。

### 8.3 操作风险治理

- 高风险操作通过 Skill 文档内的确认规则约束。
- 报告和记忆统一落到 `/memories/`，避免散落在业务目录。

## 9. 设计取舍

- 使用单一工作台整合多种能力，提升一体化体验，但页面状态复杂度明显上升。
- 使用后端 runtime 白名单注入能力，治理性更强，但新增 Agent 或 Skill 时需要同步维护配置。
- 使用 SQLite 统一承载业务数据与 LangGraph 持久化，便于演示和本地部署，但不适合高并发多节点场景。
- 为本地开发引入 Chroma + 远程 embedding 的轻量 RAG 组合，降低了接入门槛，但仍然依赖外部 embedding 接口。
- 使用轮询调度器实现后台任务，简单可控，但不适合复杂调度与大规模任务场景。

## 10. 演进方向

- 引入更完整的运行时观测能力，例如会话耗时、任务成功率、工具使用统计。
- 将任务系统从“巡检任务”演进为更通用的后台自动化任务框架。
- 增强 `/memories/` 的元数据治理，使报告、记忆和通用文件具备更统一的索引能力，并与 RAG 检索边界保持一致。
- 在保留当前轻量结构的前提下，为多租户、分布式调度和更严格审计预留扩展空间。
