# Claude Agent Web Service — DeepAgents 进阶版

基于 **FastAPI + Vue 3 + DeepAgents** 构建的 Web 对话 Agent。当前已落地 **多 Agent 基础版**：内置 `general` / `dba` / `ops` 三类 Agent，支持会话级 Agent 绑定、长时记忆上下文、多组件 UI，以及基于 Markdown 的 Skills 公共仓库 + 白名单装配能力。

## ✨ 核心特性

- **DeepAgents & LangGraph**：底层抛弃基础调用，转用 LangGraph 架构，原生支持复杂 Agent 循环并提供安全的 LocalShellBackend。
- **多 Agent 基础版**：内置 `general`、`dba`、`ops` 三类 Agent；会话创建后固定绑定 `agent_id`，并为后续 Router / Supervisor 升级保留接口与数据位。
- **Skills 公共仓库 + 白名单装配**：所有 Skills 统一存放在 `backend/skills/`，每个 Agent 只加载自己被授权的 Skill 子集。
- **打字机流式输出 (Streaming)**：真正的逐 Token 细粒度推流（通过 WebSocket），前端实时回显思考及回答过程。
- **原生上下文记忆**：集成 LangGraph Checkpointer / Store，既保留同一会话上下文，也为 Agent 级长期记忆留出命名空间。
- **持久化存储 (SQLite)**：彻底从内存切到数据库，持久化你的全部对话列表、消息与 Agent 状态，前端随时加载漫游。
- **高颜值纯享 UI**：分离左右双侧边栏（会话列表与动态技能表），黑暗/明亮模式无缝切换，参数结果代码块高亮。

## 📸 界面预览

### 浅色模式 & 技能热插拔展示

![浅色模式主界面](docs/assets/main_light_mode.png)

### 深色模式 & 沉浸式终端交互

![深色模式主界面](docs/assets/main_dark_mode.png)

### 动态技能面板加载

![动态技能面板](docs/assets/skills_panel.png)

### 流式对话与 Markdown 富文本渲染

![流式对话演示](docs/assets/active_conversation.png)

## 🚀 快速开始

### 环境依赖

- Python >= 3.10
- Node.js >= 18
- SQLite（随 Python 内置，无需额外数据库服务）

### 1. 配置数据库与环境变量

```bash
cd backend
cp .env.example .env
# 编辑 .env：填入你的 ANTHROPIC_API_KEY，按需调整 SQLITE_PATH
```

> `backend/.env` 仅用于本地运行或容器运行时注入，不会被打进 `backend` Docker 镜像层。

### 2. 初始化与启动后端

#### 方法 A：使用 Docker Compose（推荐）

项目根目录提供了 `docker-compose.yml` 文件，可通过容器方式一键启动后端服务，并将 SQLite 数据文件持久化到宿主机。
默认同时挂载：

- `./backend/skills -> /app/skills`
- `./backend/prompts -> /app/prompts`
- `./backend/data -> /app/data`

```bash
# 在项目根目录执行
docker-compose up -d --build
```

> **提示**：如果使用 Docker 启动，您不需要配置单独的数据库服务。第一次启动时会自动创建 SQLite 数据文件及表结构。
> 后端服务运行在 `http://127.0.0.1:8000`。
> 如需热修改 Agent 提示词，请直接编辑宿主机上的 `backend/prompts/*.md`；容器内对应路径为 `/app/prompts/*.md`。
> 注意：`docker-compose.yml` 会通过 `env_file` 在**运行时**读取 `backend/.env`，特别是 `ANTHROPIC_API_KEY`；该文件不会被复制进镜像层。

#### 方法 B：本地环境运行

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 初次运行时，代码中的 init_db 会自动在 SQLite 中创建表格
python main.py
```

> 后端默认运行在 `http://127.0.0.1:8000`

### 3. 配置前端环境变量并构建/启动

在启动前端或者构建 Docker 镜像前往，**必须要设置生产环境变量配置**。

```bash
cd frontend
cp .env.production.example .env.production
# 编辑 .env.production 文件，配置好后端/WebSocket 接口的对应访问地址和端口

# 本地调试启动：
npm install
npm run dev

# 如需构建生产版本：
# npm run build
```

> 前端本地运行默认在 `http://127.0.0.1:5173`

打开浏览器访问，开启你的 Agent 会话。

## 🧩 多 Agent 快速上手

当前版本内置 3 个 Agent，推荐按下面方式开始使用：

| Agent | 适合什么问题 | 默认可用 Skills |
| --- | --- | --- |
| `general` | 通用问答、文件阅读、代码解释、Markdown 整理 | `file_reader`、`code_explainer`、`obsidian-markdown` |
| `dba` | MySQL SQL 分析、执行计划解读、Volcengine RDS 健康巡检 | `mysql-sql-analyzer`、`volcengine-rds-health-analyzer` |
| `ops` | 远程运维、Docker 排障、Kubernetes 诊断 | `remote-ops`、`docker`、`kubernetes` |

- 进入首页后，先选择本次新对话要使用的 Agent。
- 点击“新对话”后，前端会进入一个**草稿会话**；真正的 `conversation_id` 会在你发送第一条消息时创建。
- 一旦会话创建成功，该会话就固定绑定当前 `agent_id`；如果要切换 Agent，请新建对话。
- 右侧技能面板和输入框里的 `@skill` 补全，只会显示当前 Agent 可用的 Skills。
- 历史旧会话、旧客户端或未显式传入 `agent_id` 的请求，默认都会落到 `general`。

## 🤖 多 Agent 使用说明

### 1) 先分清 Agent 和 Skill

- **Agent** 是职责、权限和上下文边界，例如 `general`、`dba`、`ops`。
- **Skill** 是公共能力资产，统一存放在 `backend/skills/`。
- 关系不是“每个 Skill 都属于一个 Agent”，而是“Skill 放在公共仓库里，再按 Agent Profile 白名单授权使用”。

### 2) 当前内置 Agent 一览

| agent_id | 显示名称 | 主要职责 | 可用 Skills | 风险等级 |
| --- | --- | --- | --- | --- |
| `general` | 通用助手 | 通用问答、文件阅读、代码解释、Markdown 整理 | `file_reader`、`code_explainer`、`obsidian-markdown` | `low` |
| `dba` | 数据库助手 | MySQL SQL 分析、RDS 巡检、数据库诊断 | `mysql-sql-analyzer`、`volcengine-rds-health-analyzer` | `medium` |
| `ops` | 运维助手 | 远程运维、Docker 排障、Kubernetes 诊断 | `remote-ops`、`docker`、`kubernetes` | `high` |

### 3) Web UI 怎么用

- 首页顶部会显示 Agent 选择器；你可以先选 `general` / `dba` / `ops`，再发送第一条消息。
- 左侧会话列表会显示每个历史会话所属的 Agent badge。
- 聊天页头部也会显示当前会话的 Agent badge，方便确认自己正在和哪个 Agent 交互。
- “新对话”不会立即落库，而是进入草稿态；首条消息发出后，后端才会创建 `Conversation(agent_id=...)`。

### 4) 会话、上下文与兼容规则

- `conversation_id` 绑定的是一个会话实例，`agent_id` 绑定的是这个会话的 owner/default agent。
- 会话一旦创建，后续请求即使再传别的 `agent_id`，后端也会以会话绑定的 `agent_id` 为准。
- LangGraph 侧仍然使用 `thread_id = conv_id` 维持同一会话的图状态连续性。
- `Message.agent_id` 会记录每条消息的实际执行 Agent；当前版本通常与会话 `agent_id` 一致，但它也为未来 handoff / supervisor 预留了扩展位。
- 对旧数据库里的历史数据，系统会自动回填 `agent_id = general`，保证兼容。

### 5) 记忆与权限边界

- `/memories/` 仍是公共持久化存储入口，但新的长期记忆建议写入 `/memories/agents/<agent_id>/...`。
- 当前前端记忆面板还没有做按 Agent 的强过滤，但命名约定已经为后续隔离做好准备。
- Skills 和工具权限不是靠前端隐藏实现的，而是在 Agent Runtime 创建时按白名单注入。
- 这意味着 `general` 运行时根本不会拿到 `remote-ops` / `docker` / `kubernetes` 这些高风险技能。

## 📂 项目结构

```text
demo-agent/
├── backend/                  # FastAPI 核心处理层
│   ├── main.py               # FastAPI 入口与多 Agent 路由注册
│   ├── agent.py              # 多 Agent 统一运行入口（按 agent_id 分发）
│   ├── agent_profiles.py     # Agent 声明式配置（提示词、Skills、能力边界）
│   ├── agent_manager.py      # Agent Runtime 注册表 / 懒加载缓存
│   ├── skill_catalog.py      # Skills 元数据扫描与白名单路径解析
│   ├── prompts/              # base/general/dba/ops prompt 组合（Compose 热挂载到 /app/prompts）
│   ├── config.py             # 配置模块（含 SQLite, 目录等）
│   ├── api/
│   │   ├── routers/
│   │   │   ├── agents.py         # Agent Catalog 接口
│   │   │   ├── conversations.py  # 会话管理（含 agent_id）
│   │   │   ├── skills.py         # Skills 查询与按 Agent 过滤
│   │   │   ├── agent.py          # 同步 Agent 调用接口
│   │   │   └── memories.py       # 长期记忆读取接口
│   │   └── ws/chat.py        # WebSocket 连接、Agent 绑定、增量推流分发、数据库写库
│   ├── db/
│   │   ├── session.py        # SQLAlchemy 异步引擎
│   │   └── base_class.py     # Base
│   ├── models/               # ORM 表模型 (Conversation, Message, agent_id)
│   ├── services/
│   │   └── conversation_state.py # 会话与 agent_id 绑定逻辑
│   └── skills/               # ⭐️ Markdown 格式的指令集
│       ├── remote-ops/
│       ├── mysql-sql-analyzer/
│       ├── volcengine-rds-health-analyzer/
│       └── ...
└── frontend/                 # Vue 3 前端界面
    ├── index.html
    ├── src/
    │   ├── App.vue           # 布局框架（含 Agent 选择器 / 会话 badge）
    │   ├── stores/chat.ts    # Pinia 状态中心（Agent / 会话 / Skills / WS）
    │   └── components/
    │       ├── MessageBubble.vue     # Markdown 富文本渲染与指令折叠
    │       ├── ConversationList.vue  # 历史会话 + Agent badge
    │       └── SkillPanel.vue        # 当前 Agent 的技能卡片
```

## 🧭 架构与实现

这一节不重复“如何启动”，而是站在**架构评审 / 技术接手**的角度，说明本项目到底用了哪些技术、它们分别负责什么，以及一次请求是如何穿过前端、后端、Agent、Skills 和存储层的。

当前版本已经从“单 Agent + 全量 Skills”演进为“**多 Agent 基础版**”：

- Skill 继续作为公共能力仓库存在于 `backend/skills/`
- Agent 通过 `AgentProfile -> AgentManager -> Runtime` 链路构建
- Conversation 固定绑定 `agent_id`
- Message 记录实际执行 Agent，为未来 Router / Supervisor / Handoff 留出升级空间

### 技术选型总览

#### 1) 前端层

| 技术 | 在项目中的角色 | 在链路中的位置 |
| --- | --- | --- |
| `Vue 3` | 负责界面组件化、响应式渲染和页面状态驱动 | 承载首页、会话列表、消息区、技能面板、记忆面板 |
| `Pinia` | 承担前端状态中心 | 统一管理 WebSocket 连接、消息列表、会话列表、技能列表、记忆树 |
| `Vite` | 前端开发服务器与构建工具 | 提供本地开发、生产构建、环境变量注入 |
| `marked` | Markdown 渲染器 | 将 Agent 的回答、工具结果渲染成富文本消息 |

前端不是“只负责展示”，而是承担了一个轻量编排层：`frontend/src/stores/chat.ts` 统一管理 WebSocket 生命周期、REST 拉取、会话切换、消息增量拼装和右侧辅助面板数据加载。

#### 2) 后端服务层

| 技术 | 在项目中的角色 | 在链路中的位置 |
| --- | --- | --- |
| `FastAPI` | HTTP / WebSocket 服务框架 | 对外暴露会话、技能、记忆、同步 Agent 调用等接口 |
| `WebSocket` | 实时双向通信 | 承接打字机流式输出、工具调用事件、会话绑定与中断 |
| `SQLAlchemy asyncio` | 异步 ORM 与数据库访问层 | 持久化 `Conversation`、`Message` 两张业务表 |
| `SQLite` | 轻量持久化数据库 | 既保存业务数据，也被 LangGraph 持久化组件复用 |
| `python-dotenv` | 环境变量加载 | 从 `backend/.env` 注入模型、SQLite 路径、日志等配置 |
| `loguru` | 日志输出 | 记录启动、会话、技能、错误等运行信息 |

后端承担两类职责：一类是**传统 Web 服务职责**（API、数据库、连接管理）；另一类是**Agent 运行时承载职责**（模型调用、工具事件转发、记忆路由）。

#### 3) Agent 编排层

| 技术 | 在项目中的角色 | 在链路中的位置 |
| --- | --- | --- |
| `deepagents` | Agent 编排框架 | 创建可使用 Skills、文件系统、Shell 的 Agent Runtime |
| `langchain-anthropic` | Claude 模型接入层 | 把 Anthropic / 兼容 Anthropic 协议的模型接到 Agent 上 |
| `ChatAnthropic` | 具体模型实例 | 负责生成回答、思考过程和工具调用决策 |
| `AsyncSqliteSaver` | LangGraph Checkpointer | 保存同一会话的图状态，支持上下文延续 |
| `AsyncSqliteStore` | LangGraph Store | 为 `/memories/` 提供跨会话持久化存储 |
| `LocalShellBackend / CompositeBackend / StoreBackend` | 工具路由层 | 把本地文件、Shell 和记忆文件分别路由到不同后端 |

这里最关键的一点是：本项目不是“直接调 Claude API 返回文本”，而是先构建一个 **多 Agent Runtime 层**，再把模型、profile prompt、Skills 白名单、记忆、Shell 能力绑定进去，最后通过 WebSocket / HTTP 暴露给前端和程序调用方。

### 核心组件职责

#### `backend/main.py`

- 作为 FastAPI 入口，负责创建应用、挂载路由和注册启动/关闭钩子。
- 启动时先调用 `init_db()` 创建业务表，再调用 `init_agent_runtime()` 初始化多 Agent 共享的 LangGraph Checkpointer、Store 与模型实例。
- 对外挂出 6 类能力：Agent Catalog、会话管理、技能列表、同步 Agent 调用、记忆读取、WebSocket 聊天。

#### `backend/agent_profiles.py` + `backend/agent_manager.py`

- `AgentProfile` 定义 `id`、`label`、`prompt_paths`、`skills`、`capabilities`、`risk_level`、`execution_mode`、`allowed_handoffs`。
- `AgentManager` 负责按 `agent_id` 懒加载并缓存 Runtime，而不是启动时一次性创建全部 Agent。
- 每个 Runtime 都会组合：
  - 基础 prompt
  - profile prompt
  - runtime hint（当前 Agent 的边界、风险等级、handoff 预留位）
  - profile 对应的 Skills 白名单

#### `backend/agent.py`

- 这是多 Agent 统一运行入口。
- `run_agent(...)` 会根据会话绑定的 `agent_id` 向 `AgentManager` 取回对应 Runtime。
- Runtime 执行时仍然使用 `thread_id = conv_id`，因此“继续这个会话”依旧能续接 LangGraph 图状态。
- 所有流式事件都会带上 `agent_id`，前端与 API 调用方可以感知当前是哪一个 Agent 在执行。

#### `backend/api/ws/chat.py`

- 这是浏览器实时聊天的桥梁。
- 负责处理 4 类客户端消息：
  - `init`：绑定或预备创建会话，可在草稿阶段携带 `agent_id`
  - `message`：提交用户问题并启动 Agent；若当前没有会话，则按传入 `agent_id` 创建新会话
  - `clear`：清空当前会话消息
  - `abort`：中断正在执行的 Agent
- 负责把 Agent Runtime 的事件转换成前端可消费的 WebSocket 事件，如 `text_delta`、`thinking_delta`、`tool_call`、`tool_result`、`done`、`error`。
- `session`、`title_update`、`tool_call`、`tool_result`、`done` 等事件都会透出当前 `agent_id`。
- 负责把用户消息、工具调用结果、最终回答、错误等同步落到 SQLite，并把 `Message.agent_id` 一起写入。
- 负责为“新对话”的第一条消息自动生成标题，并通过 `title_update` 推回前端。

#### `backend/api/routers/*.py`

- `agents.py`：提供 `GET /api/agents`，返回当前可用 Agent Catalog。
- `conversations.py`：提供会话列表、创建会话、加载历史消息、删除会话；会话实体带 `agent_id`。
- `skills.py`：扫描 `backend/skills/` 并解析每个 `SKILL.md` 的元数据；支持通过 `agent_id` 过滤当前 Agent 可见的 Skills。
- `agent.py`：提供同步 `POST /api/agent/chat`，方便 CI/CD、告警系统、脚本程序直接调用指定 Agent。
- `memories.py`：提供 `/api/memories/tree` 和 `/api/memories/content`，把 LangGraph Store 里的长期记忆转换成前端可浏览结构。

#### `frontend/src/stores/chat.ts`

- 这是前端最重要的“状态编排器”。
- 负责：
  - 创建并维护 WebSocket 连接
  - 根据 `VITE_WS_URL` / `VITE_API_BASE_URL` 决定实时和 REST 请求目标
  - 拉取 Agent Catalog，并维护 `draftAgentId` / `activeAgentId`
  - 发送用户消息时先本地入栈，再把新会话的 `agent_id` 一起发到后端
  - 按事件类型把流式响应拼装成最终消息，并保留 `agentId`
  - 通过 REST 拉取会话、技能、记忆树和记忆文档
- 这意味着 Vue 组件本身偏展示层，真正的业务流转几乎都收敛在 store 内。

#### `frontend/src/components/MessageBubble.vue`

- 负责消息渲染分流：
  - 用户消息
  - 助手回答
  - 工具调用
  - 工具结果
  - 系统错误
- 对非流式完成态消息使用 `marked` 做 Markdown 渲染，对流式消息使用轻量 HTML 转义，避免未完成 Markdown 造成闪烁。

### 端到端链路

下面按“系统真正怎么跑起来”的顺序串起来看。

#### 1) 应用启动链路

1. 启动 `backend/main.py`。
2. FastAPI 进入 `startup`：
   - 初始化 SQLAlchemy 业务表；
   - 初始化 `AsyncSqliteSaver` 和 `AsyncSqliteStore`；
   - 创建共享的 `ChatAnthropic` 模型实例；
   - 初始化 `AgentManager`，但不立即把所有 Runtime 全部实例化。
3. 前端启动后，`frontend/src/stores/chat.ts` 创建 WebSocket 连接。
4. WebSocket 建立成功后，前端立即发送 `init`，尝试把当前页面绑定到某个会话；如果还是草稿态，则同时带上默认/已选择的 `agent_id`。
5. 首页同时通过 REST 预取 Agent 列表、会话列表和当前 Agent 的技能列表；当打开记忆面板时，再请求记忆树和记忆内容。
6. 第一次真正使用某个 Agent 时，`AgentManager` 才会按该 Agent 的 Profile 懒加载对应 Runtime。

#### 2) 实时聊天链路（浏览器主流程）

1. 用户在前端输入问题并点击发送。
2. `chat.ts` 先把用户消息直接写入本地 `messages` 数组，保证界面即时回显。
3. 如果这是一个草稿会话，store 会通过 WebSocket 发送 `{"type":"message","content":"...","agent_id":"..."}` 给后端；已存在会话则只传消息内容。
4. `backend/api/ws/chat.py` 收到消息后：
   - 若当前还没有会话，则先创建 `Conversation(agent_id=...)`；
   - 保存用户消息到 `messages` 表；
   - 若会话标题还是“新对话”，则自动生成标题并推送 `title_update`。
5. 后端异步启动 `run_agent(...)`，把 `user_message`、`conv_id`、`agent_id` 和 `on_event` 回调交给 Agent Runtime。
6. `backend/agent.py` 中的 Agent 开始执行：
   - 模型读取“基础 prompt + profile prompt + runtime hint”；
   - 在当前 Agent 白名单技能中选择技能或工具；
   - 输出思考片段、文本增量、工具调用、工具结果等事件，并附带 `agent_id`。
7. `ws/chat.py` 的 `on_event` 把这些事件转成 WebSocket 消息推回浏览器，并把关键结果持久化到数据库。
8. 前端收到事件后按类型更新 UI：
   - `thinking_delta` → 追加到助手思考面板
   - `text_delta` → 追加到正在流式生成的回答
   - `tool_call` / `tool_result` → 追加系统消息块
   - `done` → 结束流式状态并刷新会话列表

#### 3) 同步 HTTP 调用链路（程序集成）

1. 外部程序调用 `POST /api/agent/chat`。
2. 后端检查 `ANTHROPIC_API_KEY` 是否配置。
3. 若未传 `conversation_id`，则新建一条 `source="api"` 的会话。
4. 若请求里指定了 `skill`，后端会把消息转换为 `@skill 原始问题`，让 Agent 显式优先使用对应技能。
5. 后端保存用户消息，然后直接调用同一个 `run_agent(...)`。
6. 与 WebSocket 不同的是，HTTP 路由不会把事件一条条推给客户端，而是把：
   - 最终文本
   - thinking 内容
   - tool_calls 记录
   汇总后一次性返回。
7. 最终回答和工具结果同样会写入数据库，因此 HTTP 和 Web UI 共享同一套会话与消息存储。

#### 4) 长期记忆链路

1. Agent Runtime 中，`CompositeBackend` 把 `/memories/` 路径路由到 `StoreBackend`，而不是本地文件系统。
2. 这意味着 Agent 对 `/memories/` 的读写，本质上是写入 LangGraph Store，而不是写磁盘文件。
3. `backend/services/memory.py` 再把 Store 适配成“目录树 + 文档内容”的形式：
   - `list_memory_tree()` 返回树形节点
   - `read_memory_document(path)` 返回具体文档
4. `backend/api/routers/memories.py` 通过 REST 暴露给前端。
5. `frontend/src/stores/chat.ts` 调用 `/api/memories/tree` 和 `/api/memories/content`，`MemoryPanel.vue` 负责展示。
6. 因此，长期记忆既能被 Agent 当“文件”读取，也能被人类用户在右侧面板中直观看到。

### Skills 如何接入

本项目的一个关键设计是：**Skill 不是写死在 Python 代码里的，而是放在 `backend/skills/` 目录中的一组可插拔能力包。**

#### 技能目录组织

一个典型 Skill 目录通常至少包含：

```text
backend/skills/<skill-name>/
├── SKILL.md
├── scripts/         # 可选，技能脚本
├── references/      # 可选，参考资料
└── assets/          # 可选，模板或资源
```

其中 `SKILL.md` 是核心，它定义了：

- 这个技能什么时候应该被触发
- 需要读取哪些文件
- 可以调用哪些脚本
- 输出时应该遵循什么格式

#### 技能是如何被加载的

`backend/agent.py` 中的：

```python
create_deep_agent(
    ...,
    skills=["./skills/"],
)
```

表示 Agent Runtime 会把 `backend/skills/` 当作技能根目录，自动发现其中的技能。也就是说，**新增 Skill 的主路径不是改 Python 代码，而是新增一个符合约定的技能目录**。

#### 技能如何出现在前端

`/api/skills` 会扫描 `backend/skills/` 下的每个目录，读取 `SKILL.md` 的元数据（如名称、描述），再返回给前端。前端 `fetchSkills()` 获取后，右侧技能面板和输入框 `@技能名` 补全都会使用这份数据。

#### Skill 与 Agent / Shell / Memory 的边界

- Skill 决定“**应该怎么做**”
- Deep Agent 决定“**当前该用哪个 Skill / 工具**”
- `LocalShellBackend` 提供 Shell 和本地文件访问能力
- `StoreBackend` 提供 `/memories/` 的长期记忆能力

换句话说，Skill 更像声明式工作手册；真正执行命令、读写文件、推送事件的，仍然是 Deep Agent Runtime 和它绑定的后端能力。

### 数据与状态流

#### 1) SQLite 在本项目中承担两类职责

| 存储对象 | 技术入口 | 作用 |
| --- | --- | --- |
| 业务数据（会话 / 消息） | `SQLAlchemy asyncio` | 保存 `Conversation`、`Message`，支撑会话列表、历史消息回放 |
| Agent 持久化状态 | `AsyncSqliteSaver` / `AsyncSqliteStore` | 保存 LangGraph 图状态和 `/memories/` 内容 |

也就是说，这个项目虽然只用一个 SQLite 文件，但里面同时承载了**业务层数据**和**Agent 运行时持久化数据**。

#### 2) 业务表设计

| 表 | 主要字段 | 作用 |
| --- | --- | --- |
| `Conversation` | `id`、`title`、`source`、`created_at`、`updated_at` | 表示一个完整对话线程 |
| `Message` | `conversation_id`、`role`、`content`、`type`、`tool_name`、`tool_input`、`thinking` | 表示会话中的消息、工具调用结果、错误和思考片段 |

这样设计后，UI 回放历史对话时，不需要再次调用模型，而是直接从数据库恢复消息序列。

#### 3) 会话上下文如何和 Agent 绑定

- 业务层以 `Conversation.id` 表示一个会话。
- `Conversation.agent_id` 表示这个会话的 owner/default agent。
- `Message.agent_id` 表示这条消息的实际执行 Agent；当前版本通常与会话 `agent_id` 一致，但它也为未来 handoff / supervisor 留出了数据位。
- Agent 层继续把 `conv_id` 作为 `thread_id` 传给 LangGraph。
- 因此，“继续这个会话”在技术上同时意味着：
  - 读取同一条会话的历史消息；
  - 复用同一条 Agent 图上下文线程；
  - 始终沿用该会话绑定的 `agent_id`。

这也是为什么当前项目已经是“多 Agent 会话绑定”架构，但仍然不是“多个 Agent 在单个请求里自动协作”的 Supervisor 系统。

#### 4) 前端消息状态是如何拼装出来的

前端 store 会把 WebSocket 事件转换成 UI 可消费的消息流：

| WebSocket 事件 | 前端处理方式 |
| --- | --- |
| `session` | 记录当前 `conversation_id` 与 `agent_id`，完成会话绑定 |
| `text_delta` | 追加到最后一条助手消息，形成打字机效果，并保留 `agentId` |
| `thinking_delta` | 追加到助手消息的 `thinking` 字段 |
| `tool_call` | 生成一条系统消息，展示工具名、描述、参数和执行 Agent |
| `tool_result` | 生成一条系统消息，展示工具输出和执行 Agent |
| `done` | 结束流式状态，并刷新会话列表 |
| `error` | 生成错误消息，并结束 loading |
| `title_update` | 更新左侧会话标题与当前 Agent 信息 |
| `cleared` | 清空当前前端消息数组 |

这套设计让“消息渲染”和“事件流处理”解耦：组件只关心展示，状态拼装全部放在 store。

#### 5) 现有 API / 事件契约

**REST 接口**

| 接口 | 用途 |
| --- | --- |
| `GET /api/health` | 健康检查与 API Key 配置状态 |
| `GET /api/agents` | 获取当前可用 Agent Catalog |
| `GET /api/conversations` | 获取会话列表 |
| `POST /api/conversations` | 创建新会话（可显式传入 `agent_id`） |
| `GET /api/conversations/{conv_id}/messages` | 获取历史消息 |
| `DELETE /api/conversations/{conv_id}` | 删除会话 |
| `GET /api/skills` | 获取 Skills 公共目录元数据 |
| `GET /api/skills?agent_id=...` | 获取某个 Agent 可见的 Skills 列表 |
| `GET /api/memories/tree` | 获取长期记忆目录树 |
| `GET /api/memories/content?path=...` | 读取记忆文档 |
| `POST /api/agent/chat` | 同步调用 Agent（支持 `agent_id`） |

**WebSocket 事件**

`/ws/chat` 当前主要使用这些事件类型：`session`、`text`、`text_delta`、`thinking_delta`、`tool_call`、`tool_result`、`done`、`error`、`cleared`、`title_update`。

- `session` 事件会返回 `conversation_id` 和 `agent_id`
- 首次 `init` / `message` 可以携带 `agent_id`
- 一旦会话已存在，后续请求中的 `agent_id` 会被忽略，以会话绑定值为准
- 客户端应忽略未知字段，为未来 `run_id`、`handoff_from`、`route_reason` 等扩展位保留兼容性

**前端环境变量**

| 变量 | 作用 |
| --- | --- |
| `VITE_WS_URL` | 显式指定 WebSocket 地址；未配置时默认使用当前域名的 `/ws/chat` |
| `VITE_API_BASE_URL` | 显式指定 REST API 基地址；未配置时使用相对路径 |

### 扩展点与演进方向

从当前实现来看，这个项目已经具备“可运行的多 Agent 基础版平台”雏形，但也有非常明确的扩展方向。

#### 1) 从多 Agent 基础版升级到 Router / Supervisor

当前系统已经具备以下基础设施：

- `Agent Registry`：通过 `AgentProfile` 声明多个 Agent 配置
- `Agent Manager`：按 `agent_id` 懒加载并缓存 Runtime
- `Conversation.agent_id`：让会话天然绑定某个 Agent
- `Message.agent_id`：为未来单会话内多 Agent 输出保留扩展位

因此，后续若要演进到更高阶架构，优先增加的应该是：

- `Router`：在用户无感知的情况下自动为问题选择 Agent
- `Supervisor`：把一个复杂任务拆给多个子 Agent 并汇总结果
- `Handoff`：允许同一条任务链在多个 Agent 间顺序转办

#### 2) 权限与 Skill 白名单配置化

当前白名单已经收敛在 `backend/agent_profiles.py`。后续可以继续把这些约束外提为更完整的配置中心：

- 哪个 Agent 可以用哪些 Skill
- 哪个 Agent 可以执行哪些 Shell / 文件操作
- 哪些路径允许访问，哪些路径必须拒绝

这会让“通用助手”“K8s 助手”“数据库巡检助手”真正具备隔离边界。

#### 3) 记忆隔离与作用域提升

当前版本已经采用 `Conversation.agent_id` 和 `/memories/agents/<agent_id>/...` 约定来为后续隔离预留空间。若继续引入多 Agent / 多租户，建议把命名方式扩展为更显式的形式，例如：

- `user_id:agent_id:conv_id`
- 或者将长期记忆进一步区分为用户级、Agent 级、全局级

这样可以避免不同 Agent 或不同用户共享同一块记忆命名空间。

#### 4) 当前实现的边界

当前架构最适合：

- 单团队内部使用
- 以 WebSocket 实时对话为主
- 借助 Markdown Skill + Agent 白名单快速扩能力
- 使用 SQLite 做一体化存储
- 由用户显式选择 Agent，而不是完全自动路由

如果后续要继续演进，通常会优先从以下位置下手：

- Agent 配置中心
- 认证与权限系统
- 多模型 / 多 Agent 路由
- 任务队列与长任务执行
- 更细粒度的可观测性（链路耗时、token、工具调用统计）

## 🛠️ 关于自定义技能开发

当前版本中，Skill 和 Agent 是两层概念：

1. **先创建 Skill 本体**  
   在 `backend/skills/<skill-id>/SKILL.md` 下编写技能说明；如有需要，可在同目录下放置 `scripts/`、`references/`、`assets/`。

2. **再把 Skill 授权给目标 Agent**  
   Skill 被扫描进公共 catalog 后，还需要把它加入 `backend/agent_profiles.py` 中某个 Agent 的 `skills` 白名单，前端技能面板和 `@skill` 补全才会对该 Agent 可见。

3. **如果要新增一个专门的 Agent**  
   需要同时补充：
   - `backend/agent_profiles.py`
   - `backend/prompts/<agent>.md`
   - 如有需要，再在前端增加对应展示文案

也就是说：**Skill 可以零代码接入公共仓库，但想让某个 Agent 实际使用它，还需要做一次 Agent 侧授权**。

> 💡 **快速生成 Skill**：`backend/skills/` 下的所有技能均可通过官方的 **skill-creator** 工具自动生成，只需描述你想要的能力，它就能帮你产出完整的 Skill Markdown 文件。
>
> 👉 [skill-creator — Anthropic 官方技能生成器](https://github.com/anthropics/skills/tree/main/skills/skill-creator)

## 🔌 HTTP API（程序调用）

除了 WebSocket 前端交互之外，项目也提供了一组 **HTTP / WebSocket 接口**，供外部程序（告警系统、CI/CD、运维脚本等）直接获取 Agent Catalog、创建会话并调用指定 Agent。

### 先获取 Agent Catalog

```http
GET http://localhost:8000/api/agents
```

返回结果中会包含：

- `id`
- `label`
- `description`
- `capabilities`
- `is_default`

推荐先读取这份列表，再决定调用 `general`、`dba` 还是 `ops`。

### 创建一个指定 Agent 的会话（可选）

```http
POST http://localhost:8000/api/conversations
Content-Type: application/json
```

```json
{
  "agent_id": "dba"
}
```

如果你是通过 Web UI 使用，一般不需要主动调用这一步；前端会在首条消息发送时自动建会话。

### 接口地址

```http
POST http://localhost:8000/api/agent/chat
Content-Type: application/json
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message` | string | ✅ | 用户问题 |
| `conversation_id` | string | ❌ | 会话 ID，传入可继续上下文对话 |
| `skill` | string | ❌ | 指定使用的 Skill 名称（必须是当前 Agent 可见的 Skill） |
| `agent_id` | string | ❌ | 新会话要绑定的 Agent；若已传 `conversation_id`，则以后者绑定值为准 |

### 响应格式

```json
{
  "conversation_id": "uuid",
  "agent_id": "dba",
  "content": "Agent 最终回复（Markdown 文本）",
  "thinking": "Agent 思考过程",
  "tool_calls": [
    {
      "tool_name": "execute",
      "tool_input": {"command": "df -h"},
      "result": "Filesystem  Size  Used  ..."
    }
  ]
}
```

### 调用示例

**按 Agent 发起新会话**：

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我分析一下这条慢 SQL", "agent_id": "dba", "skill": "mysql-sql-analyzer"}'
```

**多轮对话**（传入上一轮返回的 `conversation_id`）：

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "继续看一下实例 CPU 和延迟趋势", "conversation_id": "上一轮返回的 uuid"}'
```

**Python 调用**：

```python
import requests

resp = requests.post("http://localhost:8000/api/agent/chat", json={
    "message": "SELECT * FROM orders WHERE status='pending' 这条 SQL 为什么慢",
    "agent_id": "dba",
    "skill": "mysql-sql-analyzer"
}, timeout=300)

result = resp.json()
print(result["agent_id"])     # 实际执行的 Agent
print(result["content"])      # 最终分析结果
print(result["tool_calls"])   # 工具调用过程
```

### WebSocket 多 Agent 约定

浏览器主流程使用 `/ws/chat`，当前与多 Agent 相关的最小契约如下：

**首次绑定 / 草稿态初始化**

```json
{"type":"init","conversation_id":null,"agent_id":"ops"}
```

**首条消息创建会话**

```json
{"type":"message","content":"帮我查看 Docker 容器状态","agent_id":"ops"}
```

**服务端返回 session**

```json
{"type":"session","conversation_id":"uuid","session_id":"uuid","agent_id":"ops"}
```

注意事项：

- `agent_id` 只在“尚未创建会话”的阶段决定新会话归属
- 一旦 `conversation_id` 已存在，后续消息即使再传别的 `agent_id` 也不会切换 Agent
- 客户端应忽略未知字段，为未来 `run_id`、`handoff_from`、`route_reason` 等扩展字段保留兼容性

> ⚠️ **超时提示**：Agent 执行可能较耗时（SSH 排查、多轮工具调用），建议客户端设置 **5 分钟超时**。

## 🇨🇳 国产替代：MiniMax-M2.5

如果你没有 Claude API Key 或者希望使用国产大模型，本项目兼容 **MiniMax-M2.5**（海螺 AI）。MiniMax 提供了与 Anthropic 完全兼容的 API 接口，只需修改 `backend/.env` 中的 API 配置即可无缝切换：

```bash
# backend/.env
ANTHROPIC_API_KEY=你的MiniMax_API_Key
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
MODEL_NAME=MiniMax-M2.5
```

> 🎁 **新用户福利**：注册并完成实名认证后即可获得 **15 元体验券**，足够深度测试。
>
> 👉 [MiniMax Anthropic 兼容 API 文档](https://platform.minimaxi.com/docs/api-reference/text-anthropic-api)
