# 核心子系统文档补齐设计

## 1. 目标

为 AgentWeave 当前缺少独立系统级文档的四个核心子系统补齐成套文档，每个子系统各包含：

- 1 份现状设计文档
- 1 份演进路线图文档

同时更新 `docs/README.md`，把这些新增文档纳入系统设计索引和推荐阅读顺序。

## 2. 范围

本轮覆盖以下四个子系统：

1. 会话子系统
2. 能力扩展子系统（Skills + MCP）
3. 长期记忆与报告子系统
4. 认证与权限子系统

不在本轮范围内的内容：

- 已经有独立文档的系统级模块，例如 backend、frontend、agent runtime、task scheduling、RAG
- 单个 Skill 的设计文档
- 代码逻辑调整或架构重构

## 3. 交付文件

### 3.1 新增系统设计文档

- `docs/system-desigin/conversation-design.md`
- `docs/system-desigin/capability-extension-design.md`
- `docs/system-desigin/memory-and-reports-design.md`
- `docs/system-desigin/auth-and-permissions-design.md`

### 3.2 新增路线图文档

- `docs/system-desigin/conversation-roadmap.md`
- `docs/system-desigin/capability-extension-roadmap.md`
- `docs/system-desigin/memory-and-reports-roadmap.md`
- `docs/system-desigin/auth-and-permissions-roadmap.md`

### 3.3 索引更新

- `docs/README.md`

## 4. 文档分工

### 4.1 设计文档

每份 `*-design.md` 只回答“当前是如何设计和工作的”，重点包括：

- 子系统边界
- 关键模块职责
- 关键流程
- 数据与接口映射
- 异常和默认策略
- 设计取舍

### 4.2 路线图文档

每份 `*-roadmap.md` 只回答“接下来应该如何演进”，重点包括：

- 当前状态和当前短板
- 演进原则
- 分阶段路线
- 进入下一阶段的条件
- 风险、优先级和执行建议

## 5. 统一模板

### 5.1 设计文档模板

1. 背景与设计目标
2. 子系统边界
3. 模块职责划分
4. 关键流程
5. 数据 / 接口映射
6. 异常与默认策略
7. 设计取舍
8. 演进方向

### 5.2 路线图模板

1. 文档目标与读者
2. 一句话结论
3. 当前状态
4. 当前短板
5. 演进原则
6. 阶段路线图
7. 每阶段进入条件与完成标准
8. 关键风险与非目标
9. 推荐优先级
10. 下一步执行建议

## 6. 路线图阶段主题

### 6.1 会话子系统

- Phase 1：稳定会话与消息模型
- Phase 2：完善流式事件协议与前后端同步
- Phase 3：增强附件上下文与运行会话体验
- Phase 4：引入更强的会话观测、回放和治理能力

### 6.2 能力扩展子系统

- Phase 1：固化 Skills/MCP 的注册与绑定边界
- Phase 2：补齐测试、调试与审计能力
- Phase 3：细化能力可见性、授权和生命周期管理
- Phase 4：为更多外部能力接入提供标准化扩展框架

### 6.3 长期记忆与报告子系统

- Phase 1：规范 memory 与报告的目录、读写和展示
- Phase 2：补齐元数据、分类和检索质量
- Phase 3：沉淀高价值结构化对象与报告摘要层
- Phase 4：和 RAG / GraphRAG / 任务系统形成更强联动

### 6.4 认证与权限子系统

- Phase 1：把登录、角色和权限保护做稳
- Phase 2：统一 REST / WS / 子系统权限边界
- Phase 3：增强敏感操作保护、审计和最小权限
- Phase 4：为更复杂隔离场景预留能力

## 7. 写作要求

- 以仓库真实实现为准，不臆造不存在的机制。
- 设计文档优先映射到实际服务、模型、路由和前端域状态。
- 路线图文档明确区分“现状”和“后续建议”，不混写。
- 文风保持系统设计文档的一致性，适合技术和非技术读者共同阅读。
