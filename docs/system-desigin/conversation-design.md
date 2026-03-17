# AgentWeave 会话子系统设计

## 1. 背景与设计目标

会话子系统是 AgentWeave 的主交互骨架。它负责把“用户输入一条消息”扩展成一条完整链路：

- 管理会话列表与当前会话上下文
- 保存消息历史、标题和附件快照
- 通过 WebSocket 接收流式执行事件
- 把 Agent 运行中的文本、思考、工具调用和错误整理为统一消息流
- 为任务运行会话提供与普通聊天一致的回放体验

该子系统的设计目标是：

- 让 Web 工作台始终围绕“当前会话”组织状态
- 让流式执行和历史回放使用兼容的数据模型
- 让附件参与当前轮对话时具备可追溯的快照
- 让会话创建既支持显式新建，也支持首条消息和首个附件驱动的隐式创建

## 2. 子系统边界

会话子系统覆盖以下内容：

- `Conversation`、`Message`、`ConversationAttachment` 三类核心实体
- 会话列表、切换、删除、标题更新
- 聊天 WebSocket 会话初始化、流式收发、清空和中断
- 用户消息保存、助手消息保存、工具事件持久化
- 会话附件上传、列出、删除和附件快照构建
- 任务运行会话的历史流式回放

不属于本子系统的内容包括：

- Agent Runtime 的推理和工具执行逻辑
- RAG 检索细节
- 定时任务调度本身
- 认证与权限策略本身

## 3. 模块职责划分

### 3.1 持久化模型

- `Conversation`：记录会话标题、来源、绑定的 `agent_id`、以及是否来自任务运行。
- `Message`：记录会话内的每一条消息，支持 `text`、`tool_call`、`tool_result`、`error` 等类型，并保存 `thinking`、`tool_input` 和 `attachments_snapshot`。
- `ConversationAttachment`：记录某个会话下的附件文件元数据和存储路径。

### 3.2 后端服务层

- `services/conversation_state.py`：负责创建会话、获取会话、规范 `agent_id`。
- `services/conversation_messages.py`：负责保存消息、自动生成标题、更新标题。
- `services/conversation_attachments.py`：负责校验附件、写入文件、查询附件、构建附件快照和附件上下文。

### 3.3 实时入口层

- `api/ws/chat.py`：负责 WebSocket 生命周期、`init/message/clear/abort` 协议、流式事件转换、消息持久化和部分 OCR 协调。

### 3.4 REST 路由层

- `api/routers/conversations.py`：负责会话列表、显式创建、历史消息读取、删除和标题修改。
- `api/routers/conversation_attachments.py`：负责附件上传、列表和删除。

### 3.5 前端状态与组件

- `stores/chat/conversations.ts`：负责会话列表拉取、切换、任务运行会话流式回放、标题更新。
- `stores/chat/socket.ts`：负责 WebSocket 连接、事件映射、消息流拼装、重连和中断。
- `stores/chat/attachments.ts`：负责当前会话附件列表、上传和删除。
- `components/ConversationList.vue`：负责历史会话搜索、切换和删除入口。
- `components/ConversationAttachmentBar.vue`：负责当前会话附件展示和上传入口。

## 4. 关键流程

### 4.1 会话初始化

前端在连接 WebSocket 后发送 `init` 事件，携带当前 `conversation_id` 和候选 `agent_id`。

- 如果会话已存在，后端绑定到该会话，并以会话上已持久化的 `agent_id` 为准。
- 如果客户端未传 `conversation_id`，后端只初始化当前会话状态，等待首条消息或首个附件触发真正创建。
- 如果客户端传入的会话不存在，后端会尝试自动新建一个会话并返回新的 `conversation_id`。

这保证了会话可以被“显式创建”和“隐式创建”两种入口共用。

### 4.2 发送一条用户消息

用户发送消息时，前端会：

- 先将用户消息乐观写入本地消息列表
- 附带本轮引用的 `attachment_ids`
- 在无当前会话时默认从聊天入口 Agent 发起

后端收到 `message` 后会：

- 在必要时创建新会话
- 构建本轮 `attachments_snapshot`
- 保存用户消息
- 对默认标题的会话执行自动命名
- 启动 `run_agent(...)`

Agent 运行产生的事件会通过 `AgentEventState` 归一化后，再被发送给前端并保存到消息历史。

### 4.3 流式事件到消息历史的映射

会话子系统把运行时事件分成两类：

- 增量事件：`text_delta`、`thinking_delta`
- 离散事件：`tool_call`、`tool_result`、`routing`、`error`、`done`

前端通过 `socket.ts` 把这些事件拼成连续的消息体验；后端则在关键节点把它们固化为 `Message`：

- `tool_call` 持久化为 `system/tool_call`
- `tool_result` 持久化为 `system/tool_result`
- 最终助手文本在 `done` 时持久化为 `assistant/text`
- 错误持久化为 `system/error`

这种设计让历史回放和实时对话使用同一类消息结构。

### 4.4 附件上传与快照

会话附件既可以附着在已有会话上，也可以在无会话时触发创建：

- 上传时会校验扩展名、大小和编码
- 文本附件写入 UTF-8 文件，图片附件保留原始二进制
- 每个会话最多 50 个附件
- 成功写入后会更新会话 `updated_at`

发送消息时，前端仅发送附件 ID；后端通过 `build_attachment_snapshot(...)` 把本轮参与分析的附件固化到用户消息的 `attachments_snapshot` 中。

### 4.5 会话清空与中断

- `clear` 只删除当前会话下的消息记录，不删除会话和附件。
- `abort` 会取消正在运行的 Agent 任务，并将当前已累积的部分回答保存为带“用户中断”提示的助手消息。

这两个动作分别解决“清理历史”和“停止当前生成”两个不同问题。

### 4.6 任务运行会话回放

任务系统执行某个巡检任务后，会创建一个来源为 `task` 的运行会话。前端通过 `inspection-tasks/.../conversation/stream` 拉取回放事件，并复用普通会话的消息渲染逻辑显示历史。

这让“手动聊天”和“后台任务执行结果”在界面上尽量保持一致。

## 5. 数据 / 接口映射

### 5.1 核心字段

- `Conversation.agent_id`：会话绑定的运行时角色
- `Conversation.source`：会话来源，当前至少包括 `web` 和 `task`
- `Conversation.source_task_*`：标记任务来源会话
- `Message.type`：消息语义类型
- `Message.tool_input`：工具调用或工具结果的输入参数
- `Message.attachments_snapshot`：用户发送该条消息时绑定的附件快照
- `Message.thinking`：助手思考文本

### 5.2 REST 接口

- `GET /api/conversations`
- `POST /api/conversations`
- `PATCH /api/conversations/{conv_id}`
- `DELETE /api/conversations/{conv_id}`
- `GET /api/conversations/{conv_id}/messages`
- `POST /api/conversations/attachments`
- `GET /api/conversations/{conv_id}/attachments`
- `DELETE /api/conversations/{conv_id}/attachments/{attachment_id}`

### 5.3 WebSocket 事件

主通道为 `WS /ws/chat`。当前前后端会处理的核心事件包括：

- 输入事件：`init`、`message`、`clear`、`abort`
- 输出事件：`session`、`text_delta`、`thinking_delta`、`tool_call`、`tool_result`、`routing`、`ocr_status`、`ocr_result`、`title_update`、`task_notification`、`cleared`、`done`、`error`

## 6. 异常与默认策略

- 传入未知 `agent_id` 时，后端会回退到默认 Agent。
- 会话标题为空时，默认使用“新对话”；首条用户消息成功保存后可自动生成标题。
- 未配置 `ANTHROPIC_API_KEY` 时，聊天链路直接返回错误事件，不启动 Agent。
- DBA 运行态下检测到明文云凭证时，会拒绝继续处理该消息。
- WebSocket 中断时，前端会标记本次流式对话失败，并尝试延迟重连。
- 删除附件或同步 RAG 失败不会阻断会话主流程，但会记录 warning。

## 7. 设计取舍

- 使用“显式创建 + 隐式创建并存”模式，降低首次使用阻力，但也让会话生命周期略微复杂。
- 把工具调用和工具结果都写入 `Message`，牺牲了消息模型的纯粹性，换取统一的历史回放。
- 通过 `attachments_snapshot` 保存每次用户输入的附件视图，会有一定数据重复，但换来了历史消息的可追溯性。
- 流式文本通过短时间缓冲合并成 `text_delta`，改善前端展示频率，但事件与最终消息并非一一对应。
- `clear` 只清消息不删会话，保留了会话身份和附件关系，但用户需要理解“清空”和“删除”是两个动作。

## 8. 演进方向

- 进一步收敛 WebSocket 事件协议，减少前后端各自维护的特殊分支。
- 细化消息类型和附件类型，使历史回放更具可解释性。
- 为任务运行会话和普通聊天会话补更一致的检索、筛选和回放能力。
- 增强会话级观测，例如生成耗时、失败原因、流式中断来源。
- 为附件增加更清晰的上下文引用、OCR 状态和多模态能力说明。
