# 后端设计

## 1. 设计目标

后端负责把多 Agent 能力、业务状态和权限控制组织为一套稳定的服务层。它需要同时满足四类需求：

- 为前端提供结构清晰的 REST 与 WebSocket 接口。
- 为 Agent 提供可治理的运行时与扩展能力装配。
- 为会话、任务、提醒、MCP、记忆等业务提供持久化支持。
- 在能力扩展的同时保持权限边界和默认策略清晰。

## 2. 分层结构

后端按“入口层 -> 服务层 -> 模型层 -> 运行时层”组织。

```text
FastAPI 入口
  -> api/routers + api/ws
业务编排
  -> services/*
数据模型
  -> models/*
Agent Runtime 与扩展装配
  -> agent_manager.py / agent_profiles.py / skill_catalog.py / services/mcp_registry.py
基础设施
  -> db/, auth/, utils/, config.py
```

### 2.1 入口层

- `backend/main.py` 负责创建 FastAPI 应用、注册中间件、挂载 REST 与 WebSocket 路由，并在启动时初始化数据库、Agent runtime 和调度器。
- `backend/api/routers/` 提供显式请求-响应接口，适合列表、配置、创建、更新、删除和测试类操作。
- `backend/api/ws/chat.py` 提供流式聊天入口，负责把 Agent 事件转换为 WebSocket 推送。

### 2.2 服务层

服务层把路由层和模型层隔离开，负责：

- 参数归一化与默认策略。
- 跨实体的业务编排。
- 事件与运行状态汇总。
- 与 Agent runtime、MCP、记忆系统的集成。

### 2.3 模型层

模型层使用 SQLAlchemy 声明业务实体，强调：

- 会话、消息、任务、通知等对象的关系一致性。
- 通过 `to_dict()` 输出前后端可直接消费的结构。
- 对历史 Agent id 做兼容回退，避免旧数据因新配置变化而无法读取。

### 2.4 运行时层

运行时层并不暴露为独立 HTTP 服务，而是作为后端内部能力存在，负责：

- Agent 配置读取。
- Prompt 组合。
- Skill 路径解析。
- MCP 工具绑定。
- LangGraph checkpoint/store 复用。

## 3. API 入口设计

### 3.1 REST 路由分组

当前 REST 路由按照业务域拆分：

- `conversations`：会话列表、消息历史、标题和删除。
- `conversation_attachments`：附件上传、绑定和删除。
- `inspection_tasks`：任务、草稿生成、执行记录与任务流式回放。
- `task_notifications`：通知列表、已读和批量已读。
- `agents` / `agent` / `skills`：Agent 元数据与可见 Skills。
- `mcp`：MCP 配置读取、保存和服务测试。
- `memories`：记忆树、内容读取和删除。
- `auth`：认证状态、登录、回调和登出。
- `cloud_credentials`：云凭证及候选实例上下文相关接口。

设计原因：

- 每个路由模块聚焦一个业务域，降低单文件复杂度。
- 复杂流程下沉到 `services/`，避免路由层堆积业务逻辑。

### 3.2 WebSocket 聊天入口

`/ws/chat` 是主会话链路，负责：

- 校验会话写权限。
- 接收用户输入、上下文和当前 Agent 信息。
- 订阅 Agent 执行过程。
- 把事件分解为前端可消费的消息增量和状态事件。

WebSocket 之所以独立于 REST，是因为聊天过程天然是长连接、增量输出和多阶段状态变化，不适合传统请求-响应模型。

## 4. 服务层职责划分

### 4.1 会话服务

- `conversation_state.py`：会话标题、会话绑定 Agent、会话选择等状态读取。
- `conversation_messages.py`：消息持久化、消息历史读取和工具消息组织。
- `conversation_attachments.py`：附件快照、会话附件列表和删除逻辑。

设计重点是把“聊天消息”“工具消息”“附件快照”统一放进会话模型，而不是为每种显示形态单独建通道。

### 4.2 任务服务

- `inspection_task_llm.py`：任务意图分析与任务模板总结。
- `inspection_tasks.py`：任务草稿生成、任务 CRUD、触发执行、运行记录管理。
- `inspection_scheduler.py`：后台轮询、到期任务发现、任务触发。
- `task_notifications.py`：通知摘要抽取、报告引用识别、未读计数维护。

任务服务不是简单的定时器包装，而是把“任务定义”“任务执行”“任务结果提醒”拆成独立对象。

### 4.3 扩展能力服务

- `mcp_registry.py`：读取 MCP 配置、过滤 Agent 可见连接、测试工具连通性。
- `memory.py`：记忆树构建、记忆内容读取、删除和路径规范化。
- `cloud_credentials.py` / `cloud_instance_candidates.py`：云侧上下文解析与实例候选推断。

### 4.4 Agent 事件服务

- `agent_event_state.py`：收集 text / thinking / tool 调用与结果状态。
- `agent_event_identity.py`：标识事件归属，保持前端渲染一致性。
- `realtime_events.py`：用于任务通知等广播场景的轻量实时事件分发。

## 5. Agent Runtime 集成

### 5.1 配置来源

Agent 定义来自两层配置：

- `backend/agents/registry.toml`：默认 Agent 和公开 Agent 顺序。
- `backend/agents/*/agent.toml`：单个 Agent 的角色说明、技能白名单和可调度关系。

### 5.2 构建流程

```text
读取 agent_id
  -> 解析 AgentProfile
  -> 初始化 SQLite checkpointer/store（按需）
  -> 装配 prompt
  -> 解析 Skills 目录路径
  -> 加载 Agent 绑定的 MCP 工具
  -> 构建 Deep Agent runtime
  -> 放入缓存
```

`AgentManager` 采用缓存策略，是因为运行时初始化涉及模型、checkpoint、store 和工具装配，重复构建成本较高。

### 5.3 Prompt 组合

运行时 prompt 由两部分组成：

- 角色 prompt 文件，例如 `prompts/base.md` 与 `prompts/dba.md`。
- 运行时提示片段，用于说明当前 Agent 的能力边界、执行模式、可调度子 Agent 和记忆写入位置。

这种组合方式让“静态人格”和“运行时约束”分离，避免在单一 prompt 文件里堆积所有上下文。

### 5.4 Skills 与工具注入

- Skills 通过 `skill_catalog.py` 从 `backend/skills/` 解析并转为 runtime 可用路径。
- MCP 工具通过 `McpRegistryService` 按 Agent 过滤后注入。
- `/memories/` 路径通过 `StoreBackend` 暴露给 runtime。

重点不是“给 Agent 更多工具”，而是“只给正确 Agent 必要工具”。

## 6. 数据模型设计

### 6.1 会话与消息

- `Conversation` 记录会话标题、来源、Agent、任务来源信息。
- `Message` 记录角色、消息类型、工具名称、工具输入、附件快照和思考内容。

这种设计支持一条会话同时承载：

- 普通用户消息
- 助手文本回复
- 工具调用记录
- 工具结果
- 任务运行产物引用

### 6.2 任务与通知

- `InspectionTask` 表示可重复执行的任务定义。
- `InspectionTaskRun` 表示某次执行实例，并关联运行会话与报告路径。
- `TaskNotification` 表示异步提醒及未读状态。

三者拆分的价值在于：

- 任务定义稳定存在。
- 运行记录可多次累积。
- 通知是对运行结果的轻量投递，而不是执行状态本体。

### 6.3 扩展能力与认证

- `McpServer` 负责保存 transport、连接参数、Agent 绑定和最近测试结果。
- `User` / `Role` / `Permission` 负责本地 RBAC。

## 7. 认证与权限

### 7.1 中间件与会话

- `SessionMiddleware` 负责保存登录态。
- `auth/config.py` 控制认证开关、OIDC 与密码登录方式。

### 7.2 路由与 WebSocket 权限

- REST 路由通过 `require_permission(...)` 保护。
- WebSocket 使用 `ensure_websocket_permission(...)` 在连接阶段校验权限。

这样设计的原因是：前端只能做体验层禁用，真正的安全边界必须在后端。

### 7.3 权限粒度

系统把权限拆到业务动作级，例如：

- `conversations:read` / `conversations:write`
- `inspection_tasks:*`
- `task_notifications:*`
- `mcp_servers:*`
- `memories:*`

这为未来细化角色或引入更复杂 RBAC 留出空间。

## 8. 关键流程

### 8.1 会话消息处理

```text
前端发起消息
  -> 后端查找当前会话和 Agent
  -> runtime 执行
  -> 事件缓冲与聚合
  -> 消息落库
  -> 前端收到 done / error
```

### 8.2 任务运行回放

```text
前端请求 run 流
  -> 后端先发送历史消息
  -> 再轮询新增消息和运行状态
  -> 直到 run 不再是 running
  -> 输出 done
```

这样既支持已完成任务查看，也支持正在执行任务的增量回放。

## 9. 默认策略与异常策略

### 9.1 默认策略

- 默认入口 Agent 为 `router`。
- 读取旧数据中无效 `agent_id` 时回退到默认 Agent。
- MCP 加载失败时不阻塞整体 runtime 构建，而是降级为无 MCP 工具。
- 未配置 `ANTHROPIC_API_KEY` 时，服务可启动，但 Agent 对话能力不可用。

### 9.2 异常处理

- 配置加载失败时记录日志并抛出显式异常。
- 单个 MCP server 失败时跳过该 server，而不是让全部 Agent runtime 构建失败。
- 调度和任务执行失败时写入 `InspectionTaskRun.error_message` 并生成失败通知。

## 10. 设计取舍

- 让后端承担大部分能力治理，提升一致性，但后端职责更重。
- 使用服务层显式编排业务流程，代码更清晰，但相对增加了模块数量。
- 使用统一 SQLite 持久化简化部署，但对高并发与大规模运行并不理想。

## 11. 演进方向

- 引入更细粒度的 runtime 观测与审计日志。
- 为 MCP 加入更强的连接健康状态和重试策略。
- 把任务执行链路中的报告、消息、通知关系进一步抽象成统一产物模型。
