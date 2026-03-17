# AgentWeave 长期记忆与报告子系统设计

## 1. 背景与设计目标

长期记忆与报告子系统负责沉淀跨会话可复用的信息。当前它既承担“长期记忆”的角色，也承担“报告产物目录”的角色，主要覆盖：

- 共享说明和操作约束
- Agent 私有记忆
- 任务或 Skill 生成的报告文件
- 前端的记忆树浏览与报告下载入口

该子系统的设计目标是：

- 用统一的 `/memories/` 路径空间承载长期内容
- 让运行时和前端都能以一致方式访问这些内容
- 让报告产物能够被任务系统、提醒系统和 RAG 检索复用
- 保持低运维和本地持久化特性

## 2. 子系统边界

该子系统覆盖：

- `/memories/` 路径空间的树结构读取、内容读取和删除
- LangGraph Store 到 `/memories/` 路由空间的适配
- 记忆文件与报告文件的前端展示和下载
- 报告路径在任务运行和任务提醒中的引用
- memory 文档与 RAG 索引之间的同步钩子

不属于本子系统的内容包括：

- 聊天消息历史本身
- RAG 检索逻辑本身
- 巡检任务调度逻辑本身
- 具体报告模板内容本身

## 3. 模块职责划分

### 3.1 Memory Store 适配层

`services/memory.py` 通过 `StoreBackend` 把 LangGraph Store 暴露为 `/memories/` 路径空间，主要负责：

- 路径规范化与合法性校验
- 内部路径和公共路径互转
- 目录树组装
- 文档内容读取
- 文档删除

当前对外公开的 REST 能力以“读”和“删”为主；写入逻辑已存在于服务层，但当前主要通过运行时 `/memories/` backend 或内部服务调用触发，而不是前端直接写。

### 3.2 报告产物沉淀

报告的当前主落点是 `/memories/reports/`。它们通常由 Skill 在运行时通过 `write_file` / `edit_file` 写入，然后由下游服务复用：

- `agent.py` 会把写入 `/memories/reports/` 的文件识别为 `report` 类型产物
- `inspection_tasks.py` 会在任务完成后从消息中提取最新报告路径
- `task_notifications.py` 会把报告路径附加到提醒上

### 3.3 前端记忆与报告体验

- `stores/chat/memory.ts` 负责记忆树加载、内容加载、删除和打开某个 memory 文件
- `components/MemoryPanel.vue` 负责树形浏览、内容预览和删除确认
- `stores/chat/notifications.ts` 会通过 `/api/memories/content` 下载报告内容，并根据扩展名推断 MIME 类型
- `components/TaskNotificationCenter.vue` 提供“打开会话”和“下载报告”入口

### 3.4 与 RAG 的关系

memory 文档写入或删除后，会尝试触发 `services.rag` 的同步逻辑：

- `write_memory_document(...)` 成功后调用 `sync_memory_document(...)`
- `delete_memory_document(...)` 成功后调用 `delete_memory_source(...)`

同步失败只会记录 warning，不会阻断 memory 主流程。

## 4. 关键流程

### 4.1 记忆树读取

前端通过 `GET /api/memories/tree` 获取 `/memories/` 的当前目录树。

后端流程是：

1. 获取底层 Store
2. 递归组装目录和文件节点
3. 将内部路径统一转换为 `/memories/...` 公共路径

前端拿到树后，会自动选择第一个可读文件作为默认展示项。

### 4.2 记忆内容读取

前端通过 `GET /api/memories/content?path=...` 读取单个文件：

- 后端校验路径必须位于 `/memories/`
- 目录路径不可直接读取
- 内容以文本形式返回，并带上 `updated_at`

### 4.3 删除记忆文件

前端可以删除当前选中的 memory 文件：

- 后端先确认文件存在
- 从底层 Store 删除
- 尝试同步删除对应 RAG source
- 返回删除成功结果

当前删除入口既适用于普通 memory 文件，也适用于报告文件。

### 4.4 报告生成与通知引用

任务运行过程中，如果 Agent 通过 `write_file` / `edit_file` 写出了报告文件：

1. 消息历史中会出现对应工具结果
2. `inspection_tasks.py` 在任务完成后提取最新报告引用
3. `InspectionTaskRun.report_name / report_path` 被更新
4. `task_notifications.py` 基于运行记录生成提醒，并附上 `report_name / report_path`
5. 前端提醒中心允许用户直接下载报告

### 4.5 Memory 产物驱动前端刷新

当前前端 `socket.ts` 会在接收到带 `artifact_kind=memory/report` 的工具结果后，通知 memory domain 刷新记忆树。这样 Agent 新生成的 memory 或报告文件可以尽快出现在右侧面板中。

## 5. 数据 / 接口映射

### 5.1 路径约定

- Memory 根路径：`/memories/`
- 共享说明：例如 `/memories/instructions.txt`
- Agent 私有记忆：例如 `/memories/agents/<agent_id>/...`
- 报告产物：例如 `/memories/reports/report-a.md`

### 5.2 关键数据对象

- `MemoryNode`：前端目录树节点
- `MemoryDocument`：前端内容预览对象
- `InspectionTaskRun.report_name / report_path`
- `TaskNotification.report_name / report_path`

### 5.3 主要接口

- `GET /api/memories/tree`
- `GET /api/memories/content`
- `DELETE /api/memories/content`
- `GET /api/task-notifications`
- `POST /api/task-notifications/{notification_id}/read`
- `POST /api/task-notifications/read-all`

## 6. 异常与默认策略

- 底层 memory store 未初始化时，相关请求返回 503。
- 非 `/memories/` 路径会被拒绝。
- 目录路径不能按文件读取。
- 删除不存在的 memory 文件返回 404。
- RAG 同步失败不影响 memory 写删主流程。
- 报告引用提取依赖工具事件和文件路径约定，若路径未落到约定目录，前端下载链路可能无法识别。

## 7. 设计取舍

- 采用统一文件树而不是单独的报告系统，降低了系统复杂度，但也让 memory 与 report 的元数据都比较轻。
- 前端当前主要提供读取和删除，不提供完整的在线编辑能力，保持了边界简单，但操作入口有限。
- 报告引用基于消息中工具输入的路径推断，接入成本低，但鲁棒性依赖命名和路径规范。
- 报告下载通过重新读取 memory 文档实现，省去了单独文件下载服务，但下载体验与 memory API 紧耦合。

## 8. 演进方向

- 为 memory 和 report 增加更明确的元数据，如类型、来源、归属 Agent、生成时间和标签。
- 引入更清晰的报告生命周期管理，例如归档、保留和清理策略。
- 让高价值 memory / report 更容易被结构化利用，而不仅仅是作为文本文件存在。
- 增强前端记忆面板，使其更好地区分共享记忆、私有记忆和报告产物。
