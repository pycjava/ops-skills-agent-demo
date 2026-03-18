# 代码库结构

**分析日期：** 2026-03-18

## 目录布局

```text
[project-root]/
|- backend/                 # FastAPI 应用、Agent 运行时、服务层、数据目录、测试和内置 skills
|  |- api/                  # REST 路由与 WebSocket 传输层
|  |- agents/               # Agent manifest 与注册信息
|  |- auth/                 # 认证配置、RBAC、会话依赖
|  |- cli/                  # Skill 商店 CLI 与 OpenClaw 插件资产
|  |- db/                   # SQLAlchemy base 与 session 配置
|  |- models/               # 会话、任务、认证、MCP、通知等 ORM 模型
|  |- prompts/              # Agent 使用的 Prompt 片段
|  |- services/             # 业务逻辑与编排代码
|  |- skills/               # 运行时可加载的 skill 包
|  |- tests/                # 后端测试集
|  |- data/                 # SQLite、附件、RAG 数据等运行时文件
|  |- logs/                 # 运行日志
|  `- main.py               # FastAPI 启动入口
|- frontend/                # Vue 3 工作台
|  |- src/
|  |  |- components/        # 工作台面板与复用 UI 组件
|  |  |- composables/       # UI 编排 hooks
|  |  |- constants/         # 前端共享常量
|  |  |- stores/            # Pinia store 门面与 chat domains
|  |  |- utils/             # 纯工具函数
|  |  |- views/             # 路由页，例如 `/login`
|  |  |- App.vue            # 主工作台壳层
|  |  |- RootApp.vue        # Router outlet 容器
|  |  |- main.ts            # Vue 启动入口
|  |  `- router.ts          # 带认证的路由工厂
|  |- dist/                 # 前端构建输出
|  `- node_modules/         # 已安装依赖
|- docs/                    # 系统设计文档、skill 设计文档、界面截图
|- agents/                  # 仓库级规范文档，供外部 agent 工作流使用
|- .agents/                 # 本地 Codex/Cursor skill 定义
|- .planning/               # 规划产物，包括 codebase map
|- docker-compose.yml       # 演示/部署编排
|- mcp.json                 # 基于文件的 MCP Server 注册表
`- README.md                # 产品概览与启动说明
```

## 目录职责

**`backend/`：**
- 用途：主服务端代码与后端持有的运行时资源。
- 主要内容：`backend/main.py`、`backend/api/`、`backend/services/`、`backend/models/`、`backend/agents/`、`backend/prompts/`、`backend/skills/`、`backend/tests/`。
- 核心文件：`backend/main.py`、`backend/config.py`、`backend/agent.py`、`backend/agent_manager.py`

**`backend/api/`：**
- 用途：HTTP、WebSocket、SSE 的传输边界。
- 主要内容：`backend/api/routers/` 下的 REST 路由与 `backend/api/ws/` 下的聊天 WebSocket。
- 核心文件：`backend/api/ws/chat.py`、`backend/api/routers/conversations.py`、`backend/api/routers/inspection_tasks.py`、`backend/api/routers/agent.py`

**`backend/services/`：**
- 用途：可复用的业务逻辑和编排代码。
- 主要内容：会话、附件、任务、记忆、RAG、MCP、浏览器运行时、云凭据与通知服务。
- 核心文件：`backend/services/inspection_tasks.py`、`backend/services/rag.py`、`backend/services/mcp_registry.py`、`backend/services/conversation_attachments.py`、`backend/services/cloud_credentials.py`

**`backend/agents/`：**
- 用途：运行时 Agent 清单与注册元数据。
- 主要内容：`backend/agents/registry.toml`、`backend/agents/schema.py`、`backend/agents/loader.py` 和各个 Agent 目录内的 `agent.toml`。
- 核心文件：`backend/agents/registry.toml`、`backend/agents/router/agent.toml`、`backend/agents/supervisor/agent.toml`、`backend/agents/browser-runtime/agent.toml`

**`backend/prompts/`：**
- 用途：Agent manifest 引用的 Prompt 片段。
- 主要内容：基础 Prompt 与不同角色对应的 Markdown Prompt。
- 核心文件：`backend/prompts/base.md`、`backend/prompts/router.md`、`backend/prompts/supervisor.md`、`backend/prompts/ocr.md`

**`backend/skills/`：**
- 用途：由 `backend/skill_catalog.py` 解析和装配的内置 skills。
- 主要内容：每个 skill 目录下的 `SKILL.md` 以及可选的 `scripts/`、`references/`、`assets/`。
- 核心文件：`backend/skills/using-superpowers/SKILL.md`、`backend/skills/mysql-sql-analyzer/SKILL.md`、`backend/skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`、`backend/skills/agent-browser/SKILL.md`

**`backend/models/` 与 `backend/db/`：**
- 用途：数据库模式与连接配置。
- 主要内容：ORM 模型、declarative base、异步 engine、兼容性补丁与 session factory。
- 核心文件：`backend/db/session.py`、`backend/models/conversation.py`、`backend/models/message.py`、`backend/models/inspection_task.py`、`backend/models/auth.py`

**`backend/tests/`：**
- 用途：后端路由、服务、运行时装配与打包配置验证。
- 主要内容：扁平的 pytest 测试模块和 `backend/tests/conftest.py`。
- 核心文件：`backend/tests/conftest.py`、`backend/tests/test_conversations_router.py`、`backend/tests/test_inspection_tasks_service.py`、`backend/tests/test_agent_manager_prompts.py`

**`frontend/src/components/`：**
- 用途：工作台主界面的可复用 UI 组件。
- 主要内容：会话列表、消息气泡、任务抽屉、通知中心、MCP 面板、记忆面板、附件条等。
- 核心文件：`frontend/src/components/ConversationList.vue`、`frontend/src/components/MessageBubble.vue`、`frontend/src/components/TaskDrawer.vue`、`frontend/src/components/TaskNotificationCenter.vue`

**`frontend/src/composables/`：**
- 用途：从大页面中抽出的 UI 编排逻辑。
- 主要内容：应用初始化、主题控制、面板控制和输入框行为。
- 核心文件：`frontend/src/composables/useAppChrome.ts`、`frontend/src/composables/useChatComposer.ts`

**`frontend/src/stores/` 与 `frontend/src/stores/chat/`：**
- 用途：浏览器端状态与后端接口整合层。
- 主要内容：`frontend/src/stores/chat.ts` 作为公开门面，底下拆分出 `socket`、`conversations`、`tasks`、`auth`、`memory`、`mcp`、`attachments`、`notifications` 等模块。
- 核心文件：`frontend/src/stores/chat.ts`、`frontend/src/stores/chat/socket.ts`、`frontend/src/stores/chat/tasks.ts`、`frontend/src/stores/chat/auth.ts`

**`frontend/src/views/` 与 `frontend/src/utils/`：**
- 用途：页面级路由和纯工具逻辑。
- 主要内容：登录页、问候语、任务意图识别、MySQL 提示词拼接、会话标题规范化等。
- 核心文件：`frontend/src/views/LoginPage.vue`、`frontend/src/utils/mysqlInspection.ts`、`frontend/src/utils/taskIntent.ts`、`frontend/src/utils/conversationTitle.ts`

**`docs/`：**
- 用途：面向开发者的人类可读设计文档和截图。
- 主要内容：`docs/system-desigin/` 系统设计文档、`docs/skill/` skill 设计文档、`docs/assets/` 截图资源。
- 核心文件：`docs/README.md`、`docs/system-desigin/project-overall-design.md`、`docs/system-desigin/backend-design.md`、`docs/skill/skills-overview.md`

**`agents/` 与 `.agents/`：**
- 用途：仓库级工作流规范，而不是产品运行时代码。
- 主要内容：`agents/spec/` 下的规范文档，以及 `.agents/skills/design-md/` 下的本地 skill 资源。
- 核心文件：`agents/spec/backend/index.md`、`agents/spec/frontend/index.md`、`.agents/skills/design-md/SKILL.md`

## 关键文件位置

**入口点：**
- `backend/main.py`：FastAPI 启动、数据库初始化、Agent 运行时初始化、调度器启动
- `backend/api/ws/chat.py`：实时聊天 WebSocket 主循环
- `backend/api/routers/agent.py`：供非浏览器调用方使用的同步 Agent API
- `frontend/src/main.ts`：Vue 启动入口
- `frontend/src/router.ts`：带认证的路由工厂
- `docker-compose.yml`：双容器部署入口

**配置文件：**
- `backend/config.py`：后端环境变量、SQLite、RAG、日志、CORS 配置
- `backend/auth/config.py`：认证开关与 Session Cookie 配置
- `backend/agents/registry.toml`：默认 Agent 与别名映射
- `mcp.json`：通过 UI 编辑的 MCP Server 注册表
- `frontend/vite.config.ts`：前端开发/构建配置
- `frontend/tsconfig.json`：前端 TypeScript 工程配置

**核心逻辑：**
- `backend/agent.py`：上下文拼装、OCR 预处理、事件流转、顶层 Agent 执行
- `backend/agent_manager.py`：DeepAgents runtime 装配、子 Agent 图创建、MCP 工具加载、LangGraph store/checkpointer 接线
- `backend/services/inspection_tasks.py`：任务草稿、创建、调度、执行与通知交接
- `backend/services/rag.py`：检索索引、查询与上下文格式化
- `backend/services/mcp_registry.py`：解析/保存/测试 MCP 配置并按 Agent 过滤
- `frontend/src/stores/chat.ts`：浏览器侧统一 store 门面
- `frontend/src/stores/chat/socket.ts`：WebSocket 事件映射与消息发送
- `frontend/src/App.vue`：工作台编排与交互胶水层

**测试位置：**
- `backend/tests/conftest.py`：共享 fixture
- `backend/tests/test_auth_rbac.py`：认证与权限覆盖
- `backend/tests/test_conversation_attachments_router.py`：附件 API 覆盖
- `backend/tests/test_inspection_tasks_router.py`：任务 API 覆盖
- `frontend/src/App.test.ts`：工作台级前端测试
- `frontend/src/router.test.ts`：路由守卫测试
- `frontend/src/stores/chat/socket.test.ts`：WebSocket domain 测试
- `frontend/src/components/TaskDrawer.test.ts`：任务 UI 测试

## 命名约定

**文件命名：**
- 后端 Python 模块使用 `snake_case.py`，例如 `backend/services/conversation_state.py`、`backend/api/routers/task_notifications.py`。
- Vue 组件使用 `PascalCase.vue`，通常会配套同名测试文件，例如 `frontend/src/components/ConversationList.vue` 与 `frontend/src/components/ConversationList.test.ts`。
- 前端 composable 使用 `useX.ts` 模式，例如 `frontend/src/composables/useAppChrome.ts`。
- 前端 chat domain 模块多为小写名词，例如 `frontend/src/stores/chat/socket.ts`、`frontend/src/stores/chat/memory.ts`。
- Agent 与 skill ID 目录多为 kebab-case，例如 `backend/agents/db-runtime/agent.toml`、`backend/skills/volcengine-rds-health-analyzer/SKILL.md`。

**目录命名：**
- 产品主目录保持小写：`backend/`、`frontend/`、`docs/`。
- Agent、skill、prompt 文件夹名通常直接镜像运行时 ID。
- 文档目录保留现有路径名，即使其中存在 `docs/system-desigin/` 这样的拼写错误，也没有被统一修正。

## 新代码应该放哪里

**新增后端 REST 功能：**
- 路由：`backend/api/routers/<feature>.py`
- 服务逻辑：`backend/services/<feature>.py`
- 持久化：必要时新增 `backend/models/<model>.py`
- 测试：`backend/tests/test_<feature>_router.py` 与 `backend/tests/test_<feature>_service.py`

**新增 WebSocket 聊天行为：**
- 传输层修改：`backend/api/ws/chat.py`
- 可复用逻辑：`backend/services/<feature>.py`
- 消息持久化：优先扩展 `backend/services/conversation_messages.py` 或 `backend/services/conversation_attachments.py`
- 前端消费者：`frontend/src/stores/chat/socket.ts`

**新增 Agent：**
- Manifest：`backend/agents/<agent-id>/agent.toml`
- 注册表：`backend/agents/registry.toml`
- Prompt：`backend/prompts/<agent-id>.md`
- 如需前端标签同步：修改 `frontend/src/stores/chat/helpers.ts`

**新增 Skill：**
- 主体：`backend/skills/<skill-id>/SKILL.md`
- 脚本：`backend/skills/<skill-id>/scripts/`
- 参考或资源：`backend/skills/<skill-id>/references/` 或 `backend/skills/<skill-id>/assets/`
- 绑定到 Agent：更新相关 `backend/agents/<agent-id>/agent.toml`

**新增前端工作台模块：**
- 状态与网络逻辑：`frontend/src/stores/chat/<domain>.ts`
- UI 组件：`frontend/src/components/<Component>.vue`
- 新页面：`frontend/src/views/<Page>.vue`，并在 `frontend/src/router.ts` 注册路由
- 测试：就近添加 `*.test.ts`

**工具类代码：**
- 后端共用工具：`backend/utils/<name>.py`
- 前端共用工具：`frontend/src/utils/<name>.ts`

**设计与规划文档：**
- 系统设计文档：`docs/system-desigin/<topic>.md`
- skill 设计文档：`docs/skill/<skill>-design.md`
- codebase map 输出：`.planning/codebase/<DOC>.md`

## 特殊目录

**`backend/data/`：**
- 用途：保存 SQLite、会话附件与 RAG 文件
- 是否生成：是
- 是否提交：只有 `backend/data/.gitkeep` 被跟踪，真实运行数据通常不提交

**`backend/logs/`：**
- 用途：保存后端日志，例如 `backend/logs/app.log`
- 是否生成：是
- 是否提交：否

**`backend/metric_data/`：**
- 用途：火山云巡检 skill 使用的 JSON 指标快照目录
- 是否生成：是
- 是否提交：否

**`frontend/dist/`：**
- 用途：前端构建产物
- 是否生成：是
- 是否提交：否

**`frontend/node_modules/`：**
- 用途：前端安装依赖
- 是否生成：是
- 是否提交：否

**`.planning/codebase/`：**
- 用途：为 GSD 规划/执行流程生成的代码库地图
- 是否生成：是
- 是否提交：当前仓库已经将其纳入 git 跟踪

---

*结构分析：2026-03-18*
