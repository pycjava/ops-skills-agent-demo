# AgentWeave 文档索引与设计文档写作约定

## 1. 文档结构

`docs/` 当前分为三类内容：

- `docs/system-desigin/`：系统级设计文档，说明整体架构、前后端、运行时与任务系统。
- `docs/skill/`：Skill 设计文档，说明单个 Skill 的目标、触发条件、执行流程和安全边界。
- `docs/assets/`：README 和设计文档引用的界面截图等静态资源。

> 目录名 `system-desigin` 保持现状以兼容当前仓库结构；后续新增文档时继续沿用该目录，不在本轮重构路径。

## 2. 推荐阅读顺序

### 2.1 先理解整体

1. `docs/system-desigin/project-overall-design.md`
2. `docs/system-desigin/backend-design.md`
3. `docs/system-desigin/conversation-design.md`
4. `docs/system-desigin/capability-extension-design.md`
5. `docs/system-desigin/memory-and-reports-design.md`
6. `docs/system-desigin/auth-and-permissions-design.md`
7. `docs/system-desigin/rag-design.md`
8. `docs/system-desigin/frontend-design.md`
9. `docs/system-desigin/agent-runtime-design.md`
10. `docs/system-desigin/task-scheduling-design.md`

### 2.2 再看各子系统路线图

1. `docs/system-desigin/conversation-roadmap.md`
2. `docs/system-desigin/capability-extension-roadmap.md`
3. `docs/system-desigin/memory-and-reports-roadmap.md`
4. `docs/system-desigin/auth-and-permissions-roadmap.md`
5. `docs/system-desigin/rag-roadmap.md`

### 2.3 再理解能力层

1. `docs/skill/skills-overview.md`
2. 按 Agent 绑定关系阅读相应 Skill 文档：
   - `general`：`builtin-skills-design.md`、`obsidian-markdown-design.md`
   - `dba`：`mysql-sql-analyzer-design.md`、`volcengine-rds-health-analyzer-design.md`、`volcengine-rds-report-summarizer-design.md`
   - `ops`：`remote-ops-design.md`、`docker-design.md`、`kubernetes-design.md`
   - 编排层：`using-superpowers-design.md`

## 3. 系统设计文档索引

| 文档 | 主题 | 关注点 |
| --- | --- | --- |
| `project-overall-design.md` | 总体架构 | 子系统关系、关键链路、数据边界 |
| `backend-design.md` | 后端架构 | 分层、路由、服务、模型、权限 |
| `conversation-design.md` | 会话子系统 | 会话模型、消息流、附件快照、WebSocket 协议 |
| `conversation-roadmap.md` | 会话子系统路线图 | 会话模型治理、流式协议、附件体验、观测能力 |
| `capability-extension-design.md` | 能力扩展子系统 | Skills 目录、MCP 配置、运行时装配、前端面板 |
| `capability-extension-roadmap.md` | 能力扩展子系统路线图 | 能力治理、测试审计、绑定边界、扩展标准化 |
| `memory-and-reports-design.md` | 长期记忆与报告 | `/memories/`、报告引用、通知下载、RAG 同步 |
| `memory-and-reports-roadmap.md` | 长期记忆与报告路线图 | 元数据治理、报告生命周期、结构化沉淀 |
| `auth-and-permissions-design.md` | 认证与权限子系统 | Session、OIDC、本地登录、RBAC、REST/WS 权限保护 |
| `auth-and-permissions-roadmap.md` | 认证与权限子系统路线图 | 权限边界统一、审计、最小权限、隔离预留 |
| `rag-design.md` | 检索增强 | 文档源、索引、查询注入、回退策略 |
| `rag-roadmap.md` | 检索增强路线图 | 普通 RAG、混合检索、结构化知识层、GraphRAG |
| `frontend-design.md` | 前端工作台 | 状态管理、组件职责、交互流程 |
| `agent-runtime-design.md` | Agent Runtime | Agent 配置、Skills/MCP 装配、handoff |
| `task-scheduling-design.md` | 定时任务 | 任务草稿、调度、运行会话、提醒 |

## 4. Skill 设计文档索引

| 文档 | Skill | 关注点 |
| --- | --- | --- |
| `using-superpowers-design.md` | `using-superpowers` | Skill 决策流程与流程图约束 |
| `builtin-skills-design.md` | `file_reader` / `code_explainer` / `shell_command` | 基础只读能力 |
| `obsidian-markdown-design.md` | `obsidian-markdown` | Obsidian Markdown 写作规范 |
| `remote-ops-design.md` | `remote-ops` | SSH 运维、安全分层与 sudo 白名单 |
| `docker-design.md` | `docker` | 远程 Docker 排障与写操作护栏 |
| `kubernetes-design.md` | `kubernetes` | K8s 只读排障与逐层诊断 |
| `mysql-sql-analyzer-design.md` | `mysql-sql-analyzer` | SQL 执行计划分析与证据输出 |
| `volcengine-rds-health-analyzer-design.md` | `volcengine-rds-health-analyzer` | 单实例巡检流程与报告生成 |
| `volcengine-rds-report-summarizer-design.md` | `volcengine-rds-report-summarizer` | 多报告汇总与模板化输出 |

## 5. 设计文档写作约定

后续继续补充设计文档时，建议统一遵循以下模板。

### 5.1 系统设计文档模板

建议至少包含：

1. 背景 / 设计目标
2. 子系统边界
3. 模块职责划分
4. 关键流程
5. 数据或接口映射
6. 异常与默认策略
7. 设计取舍
8. 演进方向

写作要求：

- 优先按“行为和职责”组织，不要只按文件清单罗列。
- 每个关键设计点都解释“为什么这样做”。
- 尽量映射到实际实现模块，但不要把文档写成源码逐行翻译。

### 5.2 Skill 设计文档模板

建议至少包含：

1. Skill 目标与适用场景
2. 触发条件与输入约束
3. 标准执行流程
4. 工具、脚本或模板依赖
5. 安全边界与确认点
6. 失败场景与回退策略
7. 与 Agent Runtime 的关系

写作要求：

- 明确写清“什么时候应该触发该 Skill”。
- 区分只读操作和写操作。
- 如果 Skill 依赖模板、脚本或参考资料，应在文档中点明作用。

## 6. 术语约定

- **Agent**：后端定义的运行时角色，如 `router`、`dba`、`ops`。
- **Skill**：位于 `backend/skills/` 的 Markdown 能力包，可带脚本、模板和参考资料。
- **Runtime**：由 `AgentManager` 组合出的可执行 Agent 实例。
- **MCP Server**：按 Agent 绑定的外部工具连接。
- **Memory**：挂载到 `/memories/` 的长期记忆与报告产物。
- **Task Run**：某个定时任务的一次实际执行。

## 7. 维护原则

- 文档变更应优先与现有实现保持一致，不臆造仓库中不存在的机制。
- 当设计已经明显领先于实现时，应显式标注为“后续演进方向”，不要伪装成现状。
- 新增 Agent、新增 Skill 或新增重要子系统时，应同步补全对应设计文档，而不是只改 README。
