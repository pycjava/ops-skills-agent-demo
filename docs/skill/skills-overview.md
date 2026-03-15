# Skills 设计总览

## 1. 设计目标

本项目中的 Skill 不是“额外提示词碎片”，而是 Agent 能力治理的基础单元。Skill 体系要解决三个问题：

- 如何让不同 Agent 只拥有与其职责匹配的能力。
- 如何把脚本、模板、参考文档和执行约束一起打包沉淀。
- 如何让 AI 在执行领域任务时遵循稳定工作流，而不是每次临场发挥。

## 2. Skill 在系统中的位置

Skill 运行在后端 runtime 体系中，基本关系如下：

```text
AgentProfile
  -> 声明 skills 白名单
  -> AgentManager 解析 skill 路径
  -> Deep Agent runtime 加载 skill 指令
  -> Agent 在对话或任务中调用 skill 约束的流程、脚本和模板
```

换句话说，Skill 不是前端概念，也不是 UI 配置项，而是后端运行时能力包。

## 3. Skill 目录契约

一个标准 Skill 目录通常包含：

```text
backend/skills/<skill-name>/
├── SKILL.md            # 核心指令、约束和流程
├── scripts/            # 可选，封装只读诊断或分析脚本
├── references/         # 可选，故障排查手册、规则说明
├── assets/             # 可选，报告模板、示例文件
└── agents/             # 可选，附加配置
```

设计原因：

- `SKILL.md` 负责定义“该怎么做”。
- `scripts/` 负责把容易出错的命令流程固定下来。
- `references/` 负责沉淀可被按需读取的领域知识。
- `assets/` 负责模板化输出，保证报告结构稳定。

## 4. 加载与装配机制

### 4.1 元数据加载

`backend/skill_catalog.py` 会扫描 `backend/skills/` 目录：

- 识别含 `SKILL.md` 的目录。
- 解析 frontmatter 中的 `name` 与 `description`。
- 生成前端面板和 runtime 装配所需的元数据。

### 4.2 Agent 绑定

Skill 是否可用由 Agent 白名单决定，而不是由前端手工选择决定。

当前绑定关系如下：

| Agent | 绑定 Skills | 设计意图 |
| --- | --- | --- |
| `router` | `using-superpowers` | 只做流程决策与路由，不直接执行领域操作 |
| `supervisor` | `using-superpowers` | 只做复杂任务编排与结果整合 |
| `general` | `file_reader`、`code_explainer`、`obsidian-markdown`、`using-superpowers` | 通用阅读、解释与文档整理 |
| `dba` | `mysql-sql-analyzer`、`volcengine-rds-health-analyzer`、`volcengine-rds-report-summarizer`、`using-superpowers` | 数据库分析与巡检 |
| `ops` | `remote-ops`、`docker`、`kubernetes`、`using-superpowers` | 远程运维与平台排障 |

## 5. Skill 类型划分

### 5.1 流程型 Skill

代表：`using-superpowers`

特点：

- 约束“什么时候该调用 Skill、如何决策”。
- 不直接完成业务动作。
- 常作为所有 Agent 的前置流程规范。

### 5.2 基础能力 Skill

代表：`file_reader`、`code_explainer`、`shell_command`

特点：

- 覆盖读文件、解释代码、执行只读命令等底层能力。
- 常用于通用 Agent 或作为其他复杂 Skill 的辅助能力。
- 其中 `shell_command` 当前保留为可选基础 Skill，不在公开 Agent 默认白名单中。

### 5.3 领域执行 Skill

代表：`remote-ops`、`docker`、`kubernetes`、`mysql-sql-analyzer`

特点：

- 面向明确领域任务。
- 通常具有标准化命令流程和只读优先策略。
- 经常依赖脚本或参考手册。

### 5.4 报告与文档 Skill

代表：`obsidian-markdown`、`volcengine-rds-health-analyzer`、`volcengine-rds-report-summarizer`

特点：

- 强调格式稳定性和模板化输出。
- 与 `/memories/` 中的报告产物关系紧密。

## 6. 安全模型

Skill 体系承担的是“能力治理”，因此安全边界是设计重点。

### 6.1 白名单控制

- Agent 只能看到自己白名单内的 Skill。
- 编排型 Agent 不直接拥有高风险执行类 Skill。

### 6.2 只读优先

多数诊断类 Skill 优先采用只读命令或只读分析：

- `remote-ops`：优先日志、状态、资源查看。
- `docker`：优先 `ps`、`inspect`、`logs`、`stats`。
- `kubernetes`：优先 `get`、`describe`、`logs`。
- `mysql-sql-analyzer`：只运行 `EXPLAIN` 和元数据查询。

### 6.3 写操作确认

涉及状态变更的 Skill 都要求：

1. 说明计划执行的命令。
2. 说明影响范围。
3. 获得用户确认。
4. 再执行写操作。

### 6.4 产物规范化

报告类 Skill 会把输出写入 `/memories/reports/`，原因是：

- 前端可以直接识别为可下载产物。
- 结果可在记忆面板中统一浏览。
- 避免把报告散落到业务目录。

## 7. Skill 与前端的关系

前端不直接执行 Skill，但通过两个入口感知 Skill：

- `SkillPanel.vue`：显示当前 Agent 可见的 Skills。
- 输入框中的 `@skill` 补全：帮助用户显式提示技能使用。

需要注意的是，前端只负责“可见性”和“引导”，真正能不能使用某个 Skill 仍由后端 runtime 决定。

## 8. 文档索引

| 文档 | 主题 |
| --- | --- |
| `using-superpowers-design.md` | Skill 调用流程与流程图约束 |
| `builtin-skills-design.md` | 基础只读技能层 |
| `obsidian-markdown-design.md` | Obsidian Markdown 编辑与模板输出 |
| `remote-ops-design.md` | SSH 远程运维 |
| `docker-design.md` | 远程 Docker 排障 |
| `kubernetes-design.md` | Kubernetes 排障 |
| `mysql-sql-analyzer-design.md` | MySQL SQL 执行计划分析 |
| `volcengine-rds-health-analyzer-design.md` | 单实例巡检 |
| `volcengine-rds-report-summarizer-design.md` | 多实例巡检汇总 |

## 9. 设计取舍

- 采用目录式 Skill，扩展简单，但要求维护者同步更新文档、脚本和模板。
- 用白名单绑定 Agent，治理性强，但新增 Skill 时需要显式配置。
- 让 Skill 同时承载流程、脚本和输出格式，复用性高，但单个 Skill 的文档复杂度会提升。
