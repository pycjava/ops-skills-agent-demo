# 后端设计

## 1. 分层

- `api/routers`：REST 与 WebSocket 入口
- `services`：会话、巡检任务、MCP、记忆等业务逻辑
- `models`：SQLAlchemy 数据模型
- `agent_manager` / `agent_profiles` / `agents/`：Agent 注册、运行时构建与提示词装配

## 2. Agent Runtime

后端通过 `AgentManager` 按需构建并缓存 Deep Agent runtime：

1. 读取 Agent manifest 与 profile
2. 组合基础 Prompt 与角色 Prompt
3. 装配 Skills 白名单
4. 解析绑定的 MCP Server
5. 构建可复用 runtime

其中 `router` / `supervisor` 这类编排型 Agent 会构建其可调度的子 Agent 配置，叶子 Agent 则直接执行。

## 3. 业务能力

- 会话与消息管理
- 定时巡检任务创建、执行、回放
- MCP Server 配置与连接测试
- 云凭证与上下文解析
- `/memories/` 长期记忆读写

## 4. 默认策略

- 新会话默认进入 `router`
- 复杂、多域任务交给 `supervisor`
- 历史无效 `agent_id` 在读取时回退到默认 Agent，创建新资源时要求显式使用真实 Agent id
