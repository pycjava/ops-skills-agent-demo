# Backend 模块设计说明

## 1. 模块职责

后端是整个 AgentWeave 平台的 **编排中枢**。它承担四类职责：

- 作为 FastAPI 服务暴露 REST API 与 WebSocket
- 作为 Agent 运行宿主负责 Prompt、Skills、MCP 工具装配
- 作为业务层处理会话、任务、附件、提醒、记忆和云上下文
- 作为持久化入口管理 SQLite 与长期记忆后端

## 2. 目录结构

```text
backend/
├── main.py                    # FastAPI 入口与生命周期
├── agent.py                   # Agent 执行入口与事件转换
├── agent_manager.py           # Runtime 初始化、缓存、Prompt/Skill/MCP 装配
├── agent_profiles.py          # Agent 配置与白名单
├── api/
│   ├── routers/               # REST API
│   └── ws/chat.py             # WebSocket 主链路
├── services/                  # 业务服务层
├── models/                    # ORM 模型
├── db/                        # SQLAlchemy 会话与基类
├── prompts/                   # Agent Prompt 片段
├── auth/                      # 认证、权限与会话配置
├── skills/                    # Markdown Skills 仓库
└── utils/                     # 日志、适配器与通用工具
```

## 3. 启动生命周期

`main.py` 在应用启动时完成以下初始化：

1. 初始化数据库
2. 初始化 Agent Runtime
3. 启动定时巡检调度器
4. 输出技能目录与 Agent 列表日志

关闭时则反向释放：

1. 停止调度器
2. 关闭 Agent Runtime
3. 关闭数据库连接

这种设计把“Web 服务生命周期”和“Agent 运行时生命周期”统一挂在 FastAPI 上，减少分散初始化带来的状态不一致。

## 4. 接口层设计

### 4.1 REST 路由

后端 REST 路由按领域拆分，主要包括：

- `conversations`：会话管理、消息查询、标题更新、删除
- `conversation_attachments`：会话附件上传、列表和删除
- `inspection_tasks`：任务草稿、任务 CRUD、执行、执行记录和流式回放
- `task_notifications`：提醒列表、已读状态和批量更新
- `agents` / `agent` / `skills`：Agent 与 Skill 元数据
- `mcp`：MCP 配置读取、保存和测试
- `cloud_credentials`：云凭证上下文解析与注册表相关能力
- `memories`：记忆树、记忆内容读取、删除
- `auth`：认证状态、登录登出等接口

### 4.2 WebSocket 路由

`/ws/chat` 是实时对话主通道，承载：

- 用户消息发送
- 模型文本流式返回
- thinking 增量
- 工具调用事件
- 工具执行结果
- 子 Agent 路由通知
- 错误与结束事件

相比纯 REST 轮询，WebSocket 更适合承载 Agent 的长链路、多阶段、事件化执行。

## 5. Agent 运行时设计

### 5.1 Profile 驱动

后端通过 `AgentProfile` 声明每个 Agent 的：

- `id` / `label` / `description`
- Prompt 文件列表
- Skill 白名单
- 能力标签
- 风险等级
- 执行模式
- 可交接的子 Agent

这种方式把“Agent 是什么”和“Agent 能做什么”从执行逻辑中抽离出来，方便后续扩展。

### 5.2 Runtime 构建

`AgentManager` 负责：

- 初始化 MCP Registry 与 Memory Store
- 组合 Prompt 片段
- 解析 Skill 路径
- 为运行时注入 MCP Tools
- 对 Runtime 做缓存与失效控制

对 `orchestrator` 这类编排型 Agent，还会构建其可用的专业子 Agent 配置。

### 5.3 执行事件模型

`agent.py` 把底层运行时事件标准化为前端可消费的事件类型，例如：

- `text_delta`
- `thinking_delta`
- `tool_call`
- `tool_result`
- `done`
- `error`

同时它还负责拼接长期记忆上下文、识别报告产物和抽取与消息相关的记忆片段。

## 6. 服务层设计

服务层是后端的业务核心，主要分为以下域：

### 6.1 会话域

- `conversation_state`
- `conversation_messages`
- `conversation_attachments`

负责会话列表、消息落库、会话标题、附件快照等逻辑。

### 6.2 任务域

- `inspection_tasks`
- `inspection_scheduler`
- `inspection_task_llm`
- `task_notifications`

负责从会话生成任务、解析调度配置、执行到期任务、写入运行记录和推送通知。

### 6.3 扩展域

- `mcp_registry`
- `cloud_credentials`
- `cloud_instance_candidates`
- `memory`

分别负责 MCP 配置、云实例上下文、凭证绑定和长期记忆访问。

### 6.4 辅助域

- `agent_event_state`
- `agent_event_identity`
- `realtime_events`

负责事件身份、运行态事件和前端展示所需的辅助转换。

## 7. 持久化设计

### 7.1 SQLite 业务表

后端业务数据使用 SQLAlchemy + SQLite 管理，核心模型包括：

- `Conversation`
- `Message`
- `ConversationAttachment`
- `InspectionTask`
- `InspectionTaskRun`
- `TaskNotification`
- `McpServer`
- `User`
- `Role`
- `Permission`

### 7.2 长期记忆

长期记忆通过独立存储后端暴露为 `/memories/` 目录树，再由 `services/memory.py` 统一提供：

- 列出树结构
- 读取文档
- 写入文档
- 删除文档

这种设计把“记忆”从普通业务表中分离出来，更贴近 Agent 对文件型上下文的使用方式。

## 8. 认证与权限

`auth/` 目录提供：

- OIDC 配置解析
- 当前用户身份与登录状态服务
- 权限依赖注入
- 角色与权限模型

路由层通过 `require_permission(...)` 做细粒度授权。当认证关闭时，系统可以退化为无登录模式，便于本地演示。

## 9. 可扩展性设计

- **新增 Agent**：补充 `agent_profiles.py` 与对应 Prompt 即可
- **新增 Skill**：在 `backend/skills/<skill>/SKILL.md` 放入文档即可被扫描
- **新增业务 API**：在 `api/routers` 与 `services` 中按领域扩展
- **新增 MCP Server**：更新 `mcp.json` 并通过现有面板管理
- **替换存储**：数据库与 Memory Store 具备清晰边界，具备后续抽象空间

## 10. 设计取舍

- 选择 SQLite 是为了降低示例项目启动门槛，但并发与审计能力有限
- 选择 Skill 白名单是为了安全和可解释性，但牺牲了一部分动态灵活度
- 选择 WebSocket 事件流是为了更贴近 Agent 执行过程，但前端状态管理复杂度更高
