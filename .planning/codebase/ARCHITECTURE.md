# 架构

**分析日期：** 2026-03-18

## 模式概览

**整体形态：**
- 这是一个前后端分离的单仓项目，后端以 Agent 运行时为核心，前端提供统一工作台界面。
- `backend/main.py` 在一个 `FastAPI` 进程中同时承载 REST 路由和 `/ws/chat` WebSocket。
- Agent 执行逻辑没有直接塞进路由层，而是拆分到 `backend/agent.py`、`backend/agent_manager.py`、`backend/agent_profiles.py`、`backend/agents/`、`backend/prompts/` 和 `backend/skills/` 这一整套运行时装配层。
- 前端通过 `frontend/src/stores/chat.ts` 暴露一个统一的 Pinia 门面，再把认证、会话、任务、MCP、记忆和 WebSocket 逻辑拆到 `frontend/src/stores/chat/` 的多个 domain 模块中。
- SQLite 在这里承担双重角色：`backend/models/` 下的 SQLAlchemy 模型用于业务数据持久化，`backend/agent_manager.py` 中的 LangGraph saver/store 用于运行时状态与 `/memories/`。
- 长流程主要走事件驱动：交互式聊天通过 `backend/api/ws/chat.py` 流式传输；定时任务通过 `backend/services/inspection_tasks.py` 复用相同的 Agent 执行器；任务通知通过 `backend/services/realtime_events.py` 广播到在线客户端。

## 主要子系统

**会话与流式聊天：**
- 关键文件：`backend/api/ws/chat.py`、`backend/services/conversation_state.py`、`backend/services/conversation_messages.py`、`backend/services/conversation_attachments.py`、`frontend/src/stores/chat/socket.ts`、`frontend/src/stores/chat/conversations.ts`、`frontend/src/components/MessageBubble.vue`
- 职责：维护实时会话绑定、消息持久化、附件快照、工具事件、OCR 结果以及历史回放。

**Agent 运行时与能力装配：**
- 关键文件：`backend/agent.py`、`backend/agent_manager.py`、`backend/agent_profiles.py`、`backend/agents/registry.toml`、`backend/agents/*/agent.toml`、`backend/prompts/*.md`、`backend/skill_catalog.py`、`backend/services/mcp_registry.py`
- 职责：把 Agent 清单、Prompt 片段、Skill 目录、MCP 配置和 LangGraph 持久化组合成可执行 DeepAgents runtime。

**任务调度与通知：**
- 关键文件：`backend/services/inspection_tasks.py`、`backend/services/inspection_scheduler.py`、`backend/services/inspection_task_llm.py`、`backend/services/task_notifications.py`、`backend/api/routers/inspection_tasks.py`、`backend/api/routers/task_notifications.py`、`frontend/src/stores/chat/tasks.ts`、`frontend/src/components/TaskDrawer.vue`、`frontend/src/components/TaskNotificationCenter.vue`
- 职责：从对话中提炼巡检任务、调度执行、生成运行会话，并把结果通知回工作台。

**记忆、RAG 与云上下文：**
- 关键文件：`backend/services/memory.py`、`backend/services/rag.py`、`backend/services/cloud_credentials.py`、`backend/services/cloud_instance_candidates.py`、`backend/api/routers/memories.py`、`backend/api/routers/rag.py`、`backend/api/routers/cloud_credentials.py`、`frontend/src/stores/chat/memory.ts`、`frontend/src/components/MemoryPanel.vue`
- 职责：维护 `/memories/` 文档树、索引附件与记忆到 RAG、解析云凭据引用并为 DBA/OPS 类 Agent 提供上下文。

**认证与授权：**
- 关键文件：`backend/auth/config.py`、`backend/auth/service.py`、`backend/auth/dependencies.py`、`backend/auth/permissions.py`、`backend/api/routers/auth.py`、`frontend/src/router.ts`、`frontend/src/stores/chat/auth.ts`、`frontend/src/views/LoginPage.vue`
- 职责：提供 Session、OIDC、本地管理员登录、RBAC、路由守卫和 WebSocket 权限控制。

## 分层结构

**前端展示层：**
- 位置：`frontend/src/App.vue`、`frontend/src/views/`、`frontend/src/components/`
- 负责：渲染主工作台、登录页、抽屉、面板、消息 UI。
- 依赖：`frontend/src/stores/chat.ts`、`frontend/src/composables/useAppChrome.ts`、`frontend/src/composables/useChatComposer.ts`

**前端状态与传输层：**
- 位置：`frontend/src/stores/chat.ts`、`frontend/src/stores/chat/*.ts`
- 负责：集中管理浏览器端状态、HTTP 调用和 WebSocket 通信。
- 对外暴露：供 `App.vue`、`LoginPage.vue` 以及各个面板组件统一消费。

**API 与传输边界层：**
- 位置：`backend/api/routers/*.py`、`backend/api/ws/chat.py`
- 负责：暴露 HTTP/WebSocket 接口，做请求校验、权限检查和传输格式转换。
- 依赖：`backend/services/*`、`backend/auth/dependencies.py`、`backend/db/session.py`

**领域服务层：**
- 位置：`backend/services/`
- 负责：封装会话、附件、任务、记忆、RAG、MCP、OCR、浏览器运行时、通知和云上下文等业务逻辑。
- 调用方：REST 路由、WebSocket 处理器、任务调度器、Agent 运行时。

**Agent 运行时层：**
- 位置：`backend/agent.py`、`backend/agent_manager.py`、`backend/agent_profiles.py`、`backend/agents/`、`backend/prompts/`、`backend/skills/`
- 负责：加载 Agent 配置、构建子 Agent 图、注入 Skill/MCP、拼装记忆/RAG/附件上下文，并统一输出事件流。

**持久化层：**
- 位置：`backend/db/`、`backend/models/`、`backend/data/`
- 负责：保存结构化业务数据、附件文件、RAG 数据、日志和运行时资产。

## 数据流

**交互式聊天流：**
1. `frontend/src/main.ts` 启动应用，`frontend/src/composables/useAppChrome.ts` 初始化认证、Agent 列表、会话列表、通知、MCP 数据和 WebSocket。
2. `frontend/src/stores/chat/socket.ts` 连接 `/ws/chat`，发送 `init`，后续再发送携带 `attachment_ids` 的 `message` 事件。
3. `backend/api/ws/chat.py` 解析或创建 `Conversation`，通过 `backend/services/conversation_messages.py` 保存用户消息，并触发 `agent.run_agent_turn(...)`。
4. `backend/agent.py` 先决定是否做 OCR 预处理，然后从 `backend/services/rag.py` 构造 RAG 上下文，必要时回退到长时记忆与附件摘要，再调用 `backend/agent_manager.py` 构建的 runtime。
5. `backend/api/ws/chat.py` 把 runtime 事件转成 WebSocket 消息，同时持久化工具消息、助手消息、OCR 结果或截图文件，最后发送 `done` 或 `error`。
6. `frontend/src/stores/chat/socket.ts` 把事件映射为 `ChatMessage`，由 `frontend/src/App.vue` 和 `frontend/src/components/MessageBubble.vue` 渲染。

**定时巡检流：**
1. 前端通过 `frontend/src/App.vue` 和 `frontend/src/stores/chat/tasks.ts` 调用 `/api/inspection-tasks/draft`、`/api/inspection-tasks/from-conversation-message/stream` 或 `/api/inspection-tasks/{task_id}/trigger`。
2. `backend/api/routers/inspection_tasks.py` 将请求委派给 `backend/services/inspection_tasks.py`；需要 LLM 帮助时，再交给 `backend/services/inspection_task_llm.py`。
3. `backend/services/inspection_tasks.py` 创建 `InspectionTaskRun`、生成专用任务会话，把任务提示词作为用户消息写入，再复用 `backend/agent.py` 执行目标 Agent。
4. 执行过程中产生的工具输出和助手输出会继续落到运行会话中，并同步更新 `InspectionTask` / `InspectionTaskRun` 状态。
5. 任务结束后，`backend/services/task_notifications.py` 创建 `TaskNotification`，再由 `backend/services/realtime_events.py` 广播给在线客户端。
6. 前端通过 `frontend/src/stores/chat/tasks.ts`、`frontend/src/stores/chat/notifications.ts` 和 `frontend/src/stores/chat/socket.ts` 刷新运行记录、徽标与任务抽屉。

**记忆与检索流：**
1. `/memories/` 文档由 `backend/services/memory.py` 管理，底层依赖 `backend/agent_manager.py` 暴露的 LangGraph store。
2. 附件上传后会被 `backend/services/conversation_attachments.py` 落到 `backend/data/conversation_attachments/<conversation_id>/`，并同步索引到 `backend/services/rag.py`。
3. 记忆写入也会触发 RAG 同步，因此手工记忆和附件内容都能参与检索。
4. 聊天执行时，`backend/agent.py` 会优先尝试 `build_rag_context(...)`；如果没检索到结果，再回退到 `/memories/` 树扫描与附件摘要。
5. 这套记忆能力同时通过 `backend/api/routers/memories.py` 暴露给前端，在 `frontend/src/components/MemoryPanel.vue` 中浏览。

**认证流：**
1. `frontend/src/router.ts` 在路由跳转前调用 `chatStore.fetchAuthStatus()`；若 `auth_enabled=true` 且用户未登录，则跳转 `/login`。
2. `backend/api/routers/auth.py` 负责返回认证状态、发起 OIDC 跳转、处理密码登录和注销。
3. `backend/auth/dependencies.py` 负责将同一套权限模型应用到 REST 和 `/ws/chat`。
4. `backend/main.py` 安装 `SessionMiddleware`，所以 `Request` 和 `WebSocket` 都能共享会话状态。

## 状态管理

- 浏览器端状态集中在 `frontend/src/stores/chat.ts`，该文件组合多个 domain factory，而不是把网络调用分散到组件中。
- 业务数据通过 `backend/models/` 中的 ORM 模型落到 `backend/data/app.db`。
- Agent 运行时状态和 `/memories/` 则通过 `backend/agent_manager.py` 初始化的 LangGraph SQLite saver/store 保存。
- 单轮流式执行中的临时状态主要存在于 `backend/api/ws/chat.py`，例如 `AgentEventState`、delta 缓冲、abort 状态与附件上下文。

## 关键抽象

**Agent Profile 注册表：**
- 作用：声明某个 Agent 应该加载哪些 Prompt、Skill、可转交目标和执行模式。
- 相关文件：`backend/agent_profiles.py`、`backend/agents/registry.toml`、`backend/agents/router/agent.toml`、`backend/agents/supervisor/agent.toml`
- 模式：基于文件的 manifest 先被标准化成 `AgentProfile`，再用于创建 runtime。

**会话事件日志：**
- 作用：作为聊天、工具事件、附件、OCR 结果、截图和任务回放的统一事实来源。
- 相关文件：`backend/models/conversation.py`、`backend/models/message.py`、`backend/services/conversation_messages.py`、`backend/api/ws/chat.py`
- 模式：所有重要事件最终都要保存为 `Message` 行，再通过 REST、SSE 或 WebSocket 回放给客户端。

**任务自动化三元组：**
- 作用：分别表示周期任务配置、单次任务运行和面对操作者的通知。
- 相关文件：`backend/models/inspection_task.py`、`backend/models/inspection_task_run.py`、`backend/models/task_notification.py`、`backend/services/inspection_tasks.py`
- 模式：`InspectionTask` 保存配置，`InspectionTaskRun` 保存执行状态，`TaskNotification` 保存广播摘要。

**记忆与检索边界：**
- 作用：把人工/Agent 生成的长期记忆从业务 SQL 表中分离出来，但仍可被检索。
- 相关文件：`backend/services/memory.py`、`backend/services/rag.py`、`backend/api/routers/memories.py`
- 模式：`/memories/` 走 LangGraph store，RAG 则把这些路径与会话附件作为二级读模型。

**MCP 注册层：**
- 作用：把外部 MCP Server 绑定到可用 Agent，并把 `mcp.json` 转为真正的工具连接。
- 相关文件：`backend/services/mcp_registry.py`、`backend/api/routers/mcp.py`、`mcp.json`
- 模式：当前实际运行路径是基于文件的 JSON 配置，而不是数据库优先。

**前端聊天门面：**
- 作用：给 UI 一个稳定 API，屏蔽后端多个子系统的复杂度。
- 相关文件：`frontend/src/stores/chat.ts`、`frontend/src/stores/chat/socket.ts`、`frontend/src/stores/chat/tasks.ts`、`frontend/src/stores/chat/memory.ts`
- 模式：单个 Pinia store 组合多个 domain factory，再向 `frontend/src/App.vue` 暴露扁平接口。

## 入口点

**后端 HTTP / WebSocket 应用：**
- 位置：`backend/main.py`
- 触发方式：`python main.py`、`docker-compose.yml` 启动容器、或任意导入 `main:app` 的 ASGI 运行器
- 职责：创建 FastAPI 应用、安装中间件、初始化数据库与 Agent 运行时、启动调度器并注册全部路由

**交互式聊天 Socket：**
- 位置：`backend/api/ws/chat.py`
- 触发方式：浏览器通过 `frontend/src/stores/chat/socket.ts` 建立 WebSocket
- 职责：绑定会话、持久化消息、流式发送 Agent 事件、处理中断与通知

**程序化聊天 API：**
- 位置：`backend/api/routers/agent.py`
- 触发方式：HTTP `POST /api/agent/chat`
- 职责：为非浏览器调用方提供同步整轮调用接口，并复用同一套 Agent runtime 与消息存储逻辑

**巡检调度器：**
- 位置：`backend/services/inspection_scheduler.py`
- 触发方式：`backend/main.py` 的 startup hook
- 职责：轮询到期任务并调用 `backend/services/inspection_tasks.py`

**前端引导入口：**
- 位置：`frontend/src/main.ts`
- 触发方式：Vite dev server 或打包后的前端页面加载
- 职责：创建 Pinia、创建 Vue Router，并挂载 `frontend/src/RootApp.vue`

## 错误处理

**总体策略：**
- 传输层尽早校验输入，服务层抛出明确的 Python 异常，WebSocket 路径把运行时失败转换为可持久化的错误消息和终止事件。

**具体模式：**
- REST 路由通常把 `ValueError` 映射为 `400`，把 `LookupError` 映射为 `404`，可见于 `backend/api/routers/conversations.py`、`backend/api/routers/mcp.py`、`backend/api/routers/inspection_tasks.py`。
- `backend/api/ws/chat.py` 维护 `AgentEventState`，在 abort 时也会把部分助手输出写回数据库，再发送最终 `done`。
- `backend/services/agent_errors.py` 与 `backend/services/agent_event_state.py` 负责把运行时错误和快照统一成标准结构。
- 某些二级能力的失败不会中断主流程，例如 RAG 同步失败时，`backend/services/conversation_attachments.py` 与 `backend/services/memory.py` 会记录 warning，但不会让主请求失败。
- 涉及敏感凭据的聊天内容会在进入 runtime 前由 `backend/utils/credential_safety.py` 先拦截。

## 横切关注点

**日志：**
- `backend/utils/logger.py` 提供全局 `logger`，后端模块基本都复用它而不是自建 logger。

**校验：**
- 请求结构校验主要在 `backend/api/routers/*.py` 完成。
- 领域规则校验位于服务层，例如 `backend/services/inspection_tasks.py` 中的 cron 规范化、`backend/services/memory.py` 中的路径规范化、`backend/services/conversation_attachments.py` 中的附件校验。

**认证：**
- `backend/main.py` 安装 `SessionMiddleware`。
- `backend/auth/dependencies.py` 把同一套 RBAC 应用于 REST 和 WebSocket。
- `frontend/src/stores/chat/auth.ts` 与 `frontend/src/router.ts` 则把权限状态反映到路由守卫和 UI 开关上。

---

*架构分析：2026-03-18*
