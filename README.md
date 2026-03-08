# Claude Agent Web Service — DeepAgents 进阶版

基于 **FastAPI + Vue 3 + DeepAgents** 构建的 Web 对话 Agent。已支持完整的长时记忆对话上下文、多组件 UI 及基于 Markdown 零代码的 Skill 加载能力。

## ✨ 核心特性

- **DeepAgents & LangGraph**：底层抛弃基础调用，转用 LangGraph 架构，原生支持复杂 Agent 循环并提供安全的 LocalShellBackend。
- **打字机流式输出 (Streaming)**：真正的逐 Token 细粒度推流（通过 WebSocket），前端实时回显思考及回答过程。
- **全自动零代码技能 (Skills)**：后端取消硬编码，仅需丢入 Markdown 技能描述（`backend/skills/`），Agent 热插拔即可拥有系统级能力。
- **原生上下文记忆**：集成 `MemorySaver`，数据库与图状态协同，真正记住你在历史会话里聊了什么。
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

### 2. 初始化与启动后端

#### 方法 A：使用 Docker Compose（推荐）

项目根目录提供了 `docker-compose.yml` 文件，可通过容器方式一键启动后端服务，并将 SQLite 数据文件持久化到宿主机。

```bash
# 在项目根目录执行
docker-compose up -d --build
```

> **提示**：如果使用 Docker 启动，您不需要配置单独的数据库服务。第一次启动时会自动创建 SQLite 数据文件及表结构。
> 后端服务运行在 `http://127.0.0.1:8000`。
> 注意：环境变量文件 `.env` 依然需要配置，特别提供 `ANTHROPIC_API_KEY`。

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

## 📂 项目结构

```text
demo-agent/
├── backend/                  # FastAPI 核心处理层
│   ├── main.py               # 路由入口与静态挂载
│   ├── agent.py              # Deepagent Graph 定义与流式解析
│   ├── config.py             # 配置模块（含 SQLite, 目录等）
│   ├── AGENTS.md             # ⭐️ 核心 Agent 系统提示词/人设注入
│   ├── api/
│   │   ├── routers/skills.py # Restful 技能查询接口
│   │   └── ws/chat.py        # WebSocket 连接、增量推流分发、数据库写库
│   ├── db/
│   │   ├── session.py        # SQLAlchemy 异步引擎
│   │   └── base_class.py     # Base
│   ├── models/               # ORM 表模型 (Conversation, Message)
│   └── skills/               # ⭐️ Markdown 格式的指令集
│       ├── shell_command.md
│       ├── file_reader.md
│       └── code_explainer.md
└── frontend/                 # Vue 3 前端界面
    ├── index.html
    ├── src/
    │   ├── App.vue           # 布局框架 (左会话、中聊天、右技能)
    │   ├── stores/chat.ts    # 基于 Pinia 的状态流转器 & WebSocket 控制中心
    │   └── components/
    │       ├── MessageBubble.vue     # Markdown 富文本渲染与指令折腾
    │       ├── ConversationList.vue  # 历史会话漫游
    │       └── SkillPanel.vue        # 技能卡片
```

## 🧭 架构与实现

这一节不重复“如何启动”，而是站在**架构评审 / 技术接手**的角度，说明本项目到底用了哪些技术、它们分别负责什么，以及一次请求是如何穿过前端、后端、Agent、Skills 和存储层的。

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

这里最关键的一点是：本项目不是“直接调 Claude API 返回文本”，而是先构建一个 **Deep Agent Runtime**，再把模型、Skills、记忆、Shell 能力绑定进去，最后通过 WebSocket / HTTP 暴露给前端和程序调用方。

### 核心组件职责

#### `backend/main.py`

- 作为 FastAPI 入口，负责创建应用、挂载路由和注册启动/关闭钩子。
- 启动时先调用 `init_db()` 创建业务表，再调用 `init_agent_runtime()` 初始化 Deep Agent、LangGraph Checkpointer 和 Store。
- 对外挂出 5 类能力：会话管理、技能列表、同步 Agent 调用、记忆读取、WebSocket 聊天。

#### `backend/agent.py`

- 这是 Agent Runtime 的核心装配文件。
- 通过 `ChatAnthropic(...)` 绑定底层大模型，通过 `create_deep_agent(...)` 组装出真正可运行的 Agent。
- `memory=["./AGENTS.md"]` 会把 `backend/AGENTS.md` 作为运行时系统提示注入给 Agent；这也是 Agent“人设 / 工作原则 / 禁止事项”的主入口。
- `skills=["./skills/"]` 会自动扫描 `backend/skills/` 下的技能目录并加载 `SKILL.md`。
- `_make_backend()` 使用 `CompositeBackend` 做路径路由：
  - 普通项目路径 → `LocalShellBackend`
  - `/memories/` → `StoreBackend`
- `thread_id = conv_id` 把 LangGraph 的上下文线程和业务会话绑定在一起，使得“同一个会话继续对话”既能读到历史消息，也能续接 Agent 图状态。

#### `backend/api/ws/chat.py`

- 这是浏览器实时聊天的桥梁。
- 负责处理 4 类客户端消息：
  - `init`：绑定或创建会话
  - `message`：提交用户问题并启动 Agent
  - `clear`：清空当前会话消息
  - `abort`：中断正在执行的 Agent
- 负责把 Agent Runtime 的事件转换成前端可消费的 WebSocket 事件，如 `text_delta`、`thinking_delta`、`tool_call`、`tool_result`、`done`、`error`。
- 负责把用户消息、工具调用结果、最终回答、错误等同步落到 SQLite。
- 负责为“新对话”的第一条消息自动生成标题，并通过 `title_update` 推回前端。

#### `backend/api/routers/*.py`

- `conversations.py`：提供会话列表、创建会话、加载历史消息、删除会话。
- `skills.py`：扫描 `backend/skills/` 并解析每个 `SKILL.md` 的元数据，把技能名和描述返回给前端。
- `agent.py`：提供同步 `POST /api/agent/chat`，方便 CI/CD、告警系统、脚本程序直接调用 Agent。
- `memories.py`：提供 `/api/memories/tree` 和 `/api/memories/content`，把 LangGraph Store 里的长期记忆转换成前端可浏览结构。

#### `frontend/src/stores/chat.ts`

- 这是前端最重要的“状态编排器”。
- 负责：
  - 创建并维护 WebSocket 连接
  - 根据 `VITE_WS_URL` / `VITE_API_BASE_URL` 决定实时和 REST 请求目标
  - 发送用户消息时先本地入栈，再发到后端
  - 按事件类型把流式响应拼装成最终消息
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
   - 创建 `ChatAnthropic` 模型实例；
   - 调用 `create_deep_agent(...)`，把 `AGENTS.md`、`skills/`、backend 路由能力、checkpoint/store 全部装进 Agent。
3. 前端启动后，`frontend/src/stores/chat.ts` 创建 WebSocket 连接。
4. WebSocket 建立成功后，前端立即发送 `init`，尝试把当前页面绑定到某个会话。
5. 首页同时通过 REST 预取技能列表、会话列表；当打开记忆面板时，再请求记忆树和记忆内容。

#### 2) 实时聊天链路（浏览器主流程）

1. 用户在前端输入问题并点击发送。
2. `chat.ts` 先把用户消息直接写入本地 `messages` 数组，保证界面即时回显。
3. store 通过 WebSocket 发送 `{"type":"message","content":"..."}` 给后端。
4. `backend/api/ws/chat.py` 收到消息后：
   - 若当前还没有会话，则先创建 `Conversation`；
   - 保存用户消息到 `messages` 表；
   - 若会话标题还是“新对话”，则自动生成标题并推送 `title_update`。
5. 后端异步启动 `run_agent(...)`，把 `user_message`、`conv_id` 和 `on_event` 回调交给 Agent Runtime。
6. `backend/agent.py` 中的 Agent 开始执行：
   - 模型读取 `AGENTS.md` 的规则；
   - 根据需要选择技能或工具；
   - 输出思考片段、文本增量、工具调用、工具结果等事件。
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
- Agent 层把 `conv_id` 作为 `thread_id` 传给 LangGraph。
- 因此，“继续这个会话”在技术上同时意味着：
  - 读取同一条会话的历史消息；
  - 复用同一条 Agent 图上下文线程。

这也是为什么当前项目天然更接近“单 Agent + 多轮会话”架构，而不是“每次请求都完全无状态”。

#### 4) 前端消息状态是如何拼装出来的

前端 store 会把 WebSocket 事件转换成 UI 可消费的消息流：

| WebSocket 事件 | 前端处理方式 |
| --- | --- |
| `session` | 记录当前 `conversation_id`，完成会话绑定 |
| `text_delta` | 追加到最后一条助手消息，形成打字机效果 |
| `thinking_delta` | 追加到助手消息的 `thinking` 字段 |
| `tool_call` | 生成一条系统消息，展示工具名、描述和参数 |
| `tool_result` | 生成一条系统消息，展示工具输出 |
| `done` | 结束流式状态，并刷新会话列表 |
| `error` | 生成错误消息，并结束 loading |
| `title_update` | 更新左侧会话标题 |
| `cleared` | 清空当前前端消息数组 |

这套设计让“消息渲染”和“事件流处理”解耦：组件只关心展示，状态拼装全部放在 store。

#### 5) 现有 API / 事件契约

**REST 接口**

| 接口 | 用途 |
| --- | --- |
| `GET /api/health` | 健康检查与 API Key 配置状态 |
| `GET /api/conversations` | 获取会话列表 |
| `POST /api/conversations` | 创建新会话 |
| `GET /api/conversations/{conv_id}/messages` | 获取历史消息 |
| `DELETE /api/conversations/{conv_id}` | 删除会话 |
| `GET /api/skills` | 获取技能元数据列表 |
| `GET /api/memories/tree` | 获取长期记忆目录树 |
| `GET /api/memories/content?path=...` | 读取记忆文档 |
| `POST /api/agent/chat` | 同步调用 Agent |

**WebSocket 事件**

`/ws/chat` 当前主要使用这些事件类型：`session`、`text`、`text_delta`、`thinking_delta`、`tool_call`、`tool_result`、`done`、`error`、`cleared`、`title_update`。

**前端环境变量**

| 变量 | 作用 |
| --- | --- |
| `VITE_WS_URL` | 显式指定 WebSocket 地址；未配置时默认使用当前域名的 `/ws/chat` |
| `VITE_API_BASE_URL` | 显式指定 REST API 基地址；未配置时使用相对路径 |

### 扩展点与演进方向

从当前实现来看，这个项目已经具备“可运行的单 Agent 平台”雏形，但也有非常明确的扩展方向。

#### 1) 从单 Agent + 多 Skills 演进到多 Agent Registry

当前 `backend/agent.py` 在启动时只创建了一个全局 Agent Runtime，并统一加载 `AGENTS.md` 与整个 `skills/` 目录。  
如果要做多 Agent，推荐演进为：

- `Agent Registry`：定义多个 agent 配置（提示词、模型、技能白名单、权限策略）
- `Agent Manager`：按 `agent_id` 构建和缓存 Runtime
- `Conversation` 增加 `agent_id`，让会话天然绑定某个 agent

#### 2) 权限与 Skill 白名单配置化

当前所有技能由一个统一的 Agent 共享。后续可以把这些约束外提为配置：

- 哪个 Agent 可以用哪些 Skill
- 哪个 Agent 可以执行哪些 Shell / 文件操作
- 哪些路径允许访问，哪些路径必须拒绝

这会让“通用助手”“K8s 助手”“数据库巡检助手”真正具备隔离边界。

#### 3) 记忆隔离与作用域提升

当前 `thread_id = conv_id` 适合单 Agent 场景。若引入多 Agent / 多租户，建议扩展为更显式的命名方式，例如：

- `user_id:agent_id:conv_id`
- 或者将长期记忆进一步区分为用户级、Agent 级、全局级

这样可以避免不同 Agent 或不同用户共享同一块记忆命名空间。

#### 4) 当前实现的边界

当前架构最适合：

- 单团队内部使用
- 以 WebSocket 实时对话为主
- 借助 Markdown Skill 快速扩能力
- 使用 SQLite 做一体化存储

如果后续要继续演进，通常会优先从以下位置下手：

- Agent 配置中心
- 认证与权限系统
- 多模型 / 多 Agent 路由
- 任务队列与长任务执行
- 更细粒度的可观测性（链路耗时、token、工具调用统计）

## 🛠️ 关于自定义技能开发

无需修改任意一行 Python 代码，只需在 `backend/skills/` 目录下创建一个新的 `.md` 文件（参照已有的格式，包含 yaml metadata 描述和正文指导即可）。后端会自动装载该 Skill，同时前端右上角 `⚡` 面板会实时展示出你的扩建能力。

> 💡 **快速生成 Skill**：`backend/skills/` 下的所有技能均可通过官方的 **skill-creator** 工具自动生成，只需描述你想要的能力，它就能帮你产出完整的 Skill Markdown 文件。
>
> 👉 [skill-creator — Anthropic 官方技能生成器](https://github.com/anthropics/skills/tree/main/skills/skill-creator)

## 🔌 HTTP API（程序调用）

除了 WebSocket 前端交互之外，项目提供了 **HTTP POST 接口**，供外部程序（告警系统、CI/CD、运维脚本等）直接调用 Agent 并获取最终结果。

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
| `skill` | string | ❌ | 指定使用的 Skill 名称 |

### 响应格式

```json
{
  "conversation_id": "uuid",
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

**单轮调用**：

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我分析下 10.0.0.1 的磁盘使用情况", "skill": "remote-ops"}'
```

**多轮对话**（传入上一轮返回的 `conversation_id`）：

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "继续看一下内存", "conversation_id": "上一轮返回的 uuid"}'
```

**Python 调用**：

```python
import requests

resp = requests.post("http://localhost:8000/api/agent/chat", json={
    "message": "SELECT * FROM orders WHERE status='pending' 这条 SQL 为什么慢",
    "skill": "sql-analyzer"
}, timeout=300)

result = resp.json()
print(result["content"])      # 最终分析结果
print(result["tool_calls"])   # 工具调用过程
```

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
