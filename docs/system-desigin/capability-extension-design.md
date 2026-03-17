# AgentWeave 能力扩展子系统设计

## 1. 背景与设计目标

能力扩展子系统负责把 AgentWeave 中“可治理的能力”组织起来，当前主要由两部分构成：

- Skills：以目录和 `SKILL.md` 为核心的能力包
- MCP：按 `mcp.json` 配置的外部工具连接

该子系统的设计目标是：

- 让 Agent 能力通过白名单显式装配，而不是隐式拥有
- 让外部工具接入有统一配置、测试和绑定机制
- 让前端能看到某个 Agent 当前可见的 Skills 和 MCP 状态
- 让 Runtime 构建时可以按 Agent 精确注入 Skills 与工具

## 2. 子系统边界

该子系统覆盖：

- Skills 元数据扫描与路径解析
- Agent 与 Skills 的绑定关系
- MCP 配置读取、校验、归一化、测试和按 Agent 过滤
- Runtime 构建时的 Skills / MCP 注入
- 前端 Skills 面板和 MCP 面板

不属于本子系统的内容：

- 单个 Skill 的内部执行规则
- Agent prompt 设计本身
- 外部 MCP 服务实现本身
- 认证授权策略本身

## 3. 模块职责划分

### 3.1 Skills 目录与元数据

- `skill_catalog.py` 扫描 `SKILLS_DIR` 下的目录
- 通过读取每个 `SKILL.md` 的 front matter 生成 `SkillMetadata`
- 提供 `list_skills(...)` 和 `resolve_skill_paths(...)`

它只负责“有哪些 Skill”以及“这些 Skill 的路径是什么”，不负责 Skill 内容执行。

### 3.2 Runtime 装配

- `agent_manager.py` 在构建 runtime 时读取 Agent profile
- 将 profile 中声明的 Skill ID 解析为路径列表
- 通过 `McpRegistryService` 解析当前 Agent 可见的 MCP 连接
- 最终把 Skills 和 MCP tools 一起注入 `create_deep_agent(...)`

这使得“能力授予”发生在后端 runtime 组装阶段，而不是前端展示阶段。

### 3.3 MCP 注册表服务

`services/mcp_registry.py` 负责：

- 读取项目根目录 `mcp.json`
- 校验 `mcpServers` 的 JSON 形状
- 标准化 `transport`、`url`、`command`、`agentIds` 等字段
- 对单个服务执行测试并缓存最近测试结果
- 输出适合 Runtime 使用的 connection dict

当前它的核心特点是：

- 配置源是文件，而不是数据库
- 测试结果缓存在服务内存中
- 启用状态和 Agent 绑定通过配置显式表达

### 3.4 API 与前端面板

- `api/routers/skills.py`：返回全量 Skill 列表或某个 Agent 可见的 Skill 列表
- `api/routers/mcp.py`：返回 `mcp.json` 文本、解析后的服务器列表，支持保存配置和测试单个服务
- `frontend/src/components/SkillPanel.vue`：展示当前 Agent 可见 Skill 的 ID 和描述
- `frontend/src/components/McpPanel.vue`：展示原始配置、解析结果、测试状态和工具预览

### 3.5 数据模型

仓库中存在 `models/mcp_server.py`，定义了 MCP Server 的 ORM 结构。但当前注册表服务的运行时真实来源仍然是 `mcp.json` 文件和内存中的测试状态，而不是数据库表。

## 4. 关键流程

### 4.1 Skills 列表获取

当前 Agent 变化后，前端会请求 `/api/skills?agent_id=...`：

- 后端根据 Agent profile 返回可见 Skill 元数据
- 前端 `SkillPanel` 只做只读展示

因此 Skills 面板反映的是“运行时白名单视图”，不是“所有磁盘目录的原始清单”。

### 4.2 Runtime 构建

当某个 Agent runtime 被初始化时：

1. `AgentManager` 获取 Agent profile
2. 解析 profile 的 Skill 列表为路径
3. 查询该 Agent 当前可用的 MCP connections
4. 使用这些输入构建 Deep Agent runtime

这样做的关键点是：

- Skills 在 runtime 创建时就已固定
- MCP connections 会受到启用状态和 `agentIds` 过滤影响
- 配置变更后需要失效 runtime 缓存

### 4.3 保存 MCP 配置

前端在 `McpPanel` 中编辑 `mcp.json` 文本后，通过 `/api/mcp/config` 提交：

- 后端解析 JSON
- 验证 `mcpServers` 的结构和字段
- 归一化后写回配置文件
- 清空当前测试状态缓存
- 触发 runtime cache 失效

### 4.4 测试 MCP 服务

对某个 MCP server 执行测试时：

- 后端基于解析后的连接配置构建 `MultiServerMCPClient`
- 尝试拉取工具列表
- 将结果记录为 `ok/error`、错误信息和工具预览
- 成功时触发 runtime cache 失效

这使得前端既能看到当前配置，也能看到“最近一次实际连通性测试”的结果。

## 5. 数据 / 接口映射

### 5.1 Skills 元数据

`SkillMetadata` 当前包含：

- `id`
- `name`
- `description`
- `path`

对外 API 默认只暴露 `id / name / description`。

### 5.2 MCP 记录

`McpServerRecord` 当前包含：

- 基础连接信息：`transport`、`url`、`command`、`args`
- 控制信息：`enabled`、`agent_ids`
- 安全相关配置：`headers`、`env`
- 测试信息：`last_test_status`、`last_tested_at`、`last_error`、`last_tools`

### 5.3 主要接口

- `GET /api/skills`
- `GET /api/mcp/config`
- `PUT /api/mcp/config`
- `GET /api/mcp/servers`
- `POST /api/mcp/servers/{server_name}/test`

## 6. 异常与默认策略

- Skill 目录不存在时，Skills 列表返回空集合。
- 某个 Skill 的 `SKILL.md` 读取失败时，会记录日志并回退为最小元数据。
- `mcp.json` 不存在时，注册表服务返回一个默认的空配置文档。
- `mcp.json` 结构错误时，保存接口返回 400。
- MCP 适配器导入失败或 MCP 服务连通失败时，不阻断整个 Agent Runtime，只是跳过对应工具或返回测试失败。
- `agentIds` 中的 Agent 名称会在保存时规范化为已知 Agent ID。

## 7. 设计取舍

- Skills 采用目录扫描和 front matter 解析，接入简单，但元数据表达能力有限。
- MCP 配置采用文件作为运行时真源，降低了复杂度，但缺少更强的版本化和审计能力。
- 测试状态保存在内存中，读写轻量，但服务重启后不会保留历史。
- Runtime 在配置变化后统一失效缓存，简单直接，但失效范围偏粗。
- 前端对 Skills 只做只读展示，有助于保持治理边界清晰，但不提供更细粒度的发现和帮助信息。

## 8. 演进方向

- 为 Skills 增加更丰富的元数据，例如分类、风险级别、输入约束和依赖说明。
- 为 MCP 配置增加更明确的生命周期和变更审计。
- 细化运行时缓存失效策略，减少全量失效。
- 为能力扩展层提供更清晰的健康状态、工具发现和接入规范。
- 在保持白名单治理的前提下，为新能力接入提供更标准化的扩展框架。
