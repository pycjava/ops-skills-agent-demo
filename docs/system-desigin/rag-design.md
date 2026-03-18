# 本地 RAG 检索增强设计

## 1. 背景与设计目标

当前系统已经具备两类可复用知识来源：

- 会话附件：用户在对话过程中上传的文本附件。
- `/memories/`：长期记忆、共享说明、Agent 专属记忆和报告产物。

在引入 RAG 之前，这两类来源主要通过“附件清单提示 + `/memories/` 关键词扫描”的方式进入对话上下文。该方案实现简单，但存在三个问题：

- 随着附件和记忆文档变多，手工拼接上下文的命中质量会下降。
- `/memories/` 只能按路径和关键词粗粒度筛选，难以稳定召回相关片段。
- 会话附件与长期记忆的检索链路分离，难以形成统一的引用与调试能力。

因此，本轮设计的目标是：

- 在不改变主聊天入口的前提下，为对话链路增加一个轻量、本地持久化的检索增强层。
- 统一接入“会话附件 + `/memories/`”两类文档源。
- 保持单机、个人使用场景下的低运维成本，并保留后续替换 embedding 模型或扩展检索策略的空间。

非目标：

- 不构建企业级知识库管理平台。
- 不引入分布式向量库或复杂的混合检索链路。
- 不在首期加入 reranker、多租户隔离或专门的前端知识库管理界面。

## 2. 子系统边界

RAG 子系统位于现有会话系统、memory 系统和 Agent runtime 之间，承担“文档标准化 -> 切块 -> 向量索引 -> 查询召回 -> 上下文注入”的职责。

```text
附件 / /memories/
  -> RAG Sources
  -> RAG Service
      -> Embedding Client
      -> Chroma Index
      -> Status Metadata
  -> agent.py 上下文组装
  -> Agent Runtime
```

边界约束如下：

- RAG 不替代 `/memories/` 的展示和管理能力；`/memories/` 仍然是长期知识的主存储入口。
- RAG 不保存业务主数据；附件和 memory 的真实内容仍由现有服务层负责读写。
- RAG 只维护索引、检索结果和索引状态，不负责会话消息持久化。

## 3. 模块职责划分

### 3.1 文档源装配

`backend/services/rag.py` 中的 source loader 负责把两类已有数据源转换为统一文档模型：

- `load_attachment_source_documents(...)`
- `load_memory_source_documents(...)`
- `build_attachment_source_document(...)`
- `build_memory_source_document(...)`

统一后的 `RagSourceDocument` 具备：

- `source_type`
- `source_id`
- `title`
- `path_or_filename`
- `content`
- `conversation_id`
- `agent_id`
- `updated_at`

这样做的原因是：RAG 服务只关心“可索引文档”，而不需要了解附件表、memory store 或 OCR 文件的存储细节。

### 3.2 检索服务

`RagService` 是 RAG 子系统的核心编排器，负责：

- 将原始文档切块。
- 调用 embedding client 生成向量。
- 将 chunk 写入或删除自 Chroma。
- 按会话和 Agent 作用域执行查询。
- 生成可直接注入 prompt 的文本上下文。
- 维护索引状态文件。

对外统一暴露四类动作：

- `build_context(...)`
- `search(...)`
- `reindex(...)`
- `status()`

### 3.3 向量索引层

`ChromaIndexBackend` 负责本地向量存储与查询。首期选择 Chroma 的原因是：

- 零额外服务部署，适合本地开发与个人使用。
- 可直接落盘到 `backend/data/rag/chroma`。
- 已满足小规模附件和 memory 文档的持久化检索需求。

索引层只承担：

- chunk upsert
- source delete
- metadata list
- vector query

它不承担文档解析、权限治理和 prompt 组装。

### 3.4 Embedding 层

`RemoteEmbeddingClient` 负责调用远程 embedding API。当前设计默认：

- 向量库和状态文件在本地。
- embedding 模型先走云端接口。
- 聊天模型配置与 embedding 模型配置解耦。

这样做的好处是：

- 不增加本地模型部署负担。
- 可先让 RAG 跑通，再逐步替换为本地 embedding 模型。

## 4. 数据模型与索引策略

### 4.1 统一文档主键

每个 chunk 的主键格式为：

```text
<source_type>:<source_id>#<chunk_index>
```

例如：

- `attachment:123456#0`
- `memory:/memories/agents/dba/instances.md#2`

这样可保证：

- memory 与 attachment 不会冲突。
- 同一 source 可增量重建。
- 删除某个 source 时可按 metadata 批量清理其所有 chunks。

### 4.2 Chunk metadata

每个 chunk 至少携带以下 metadata：

- `source_type`
- `source_id`
- `title`
- `path_or_filename`
- `conversation_id`
- `agent_id`
- `updated_at`

这些字段的作用不是“做完整权限系统”，而是支持：

- 当前会话附件过滤
- 当前 Agent 的 memory 作用域过滤
- 调试接口返回来源
- 索引状态统计

### 4.3 默认切块策略

当前默认值来自配置：

- `RAG_CHUNK_SIZE=1200`
- `RAG_CHUNK_OVERLAP=200`
- `RAG_TOP_K=4`

首期采用字符级切块而非更复杂的 token-aware splitter，原因是：

- 降低实现复杂度。
- 足以覆盖当前以 Markdown、log、SQL、文本附件为主的场景。
- 后续若接入本地 tokenizer，可在服务内部替换，而不改变外部接口。

## 5. 查询与上下文注入流程

### 5.1 聊天链路中的检索流程

当前 `backend/agent.py` 在进入 runtime 前增加了 RAG 查询步骤：

```text
用户消息
  -> build_rag_context(query, conversation_id, agent_id)
  -> 若命中结果，生成 <rag_context>
  -> 若未命中或 RAG 不可用，回退到旧的 memory/attachment context
  -> 组装最终 HumanMessage
  -> Agent Runtime 执行
```

该设计有两个关键点：

- RAG 是增强层，不是强依赖。任何索引、配置或网络问题都不应阻断聊天。
- RAG 命中时优先使用统一的 `<rag_context>`，减少旧的双链路上下文重复注入。

### 5.2 作用域过滤策略

检索时采用轻量作用域过滤：

- 附件检索只看当前 `conversation_id` 下的文本附件。
- memory 检索只允许：
  - `/memories/instructions.txt`
  - 非 Agent 私有的共享 memory
  - 当前 Agent 对应的 `/memories/agents/<agent_id>/`

这保证：

- 当前会话不会跨会话误召回附件。
- Agent 私有 memory 不会被无关 Agent 命中。
- `/memories/instructions.txt` 这类共享约束可继续被检索链路优先利用。

### 5.3 RAG 上下文格式

`RagService.format_context(...)` 将召回结果格式化为紧凑文本块，保留：

- 查询语句
- 来源类型
- 标题
- 可引用路径
- chunk 内容

注入格式为：

```text
<rag_context>
...
</rag_context>
```

这样做的目的不是让模型直接“看到向量检索实现”，而是让它得到一份清晰、可引用、可回退的检索摘要。

## 6. 索引更新策略

### 6.1 附件增量同步

附件服务中已经接入两条钩子：

- `create_attachment_record(...)` 成功后调用 `sync_attachment_record(...)`
- `delete_conversation_attachment(...)` 成功后调用 `delete_attachment_source(...)`

设计原因：

- 会话附件天然是 RAG 的增量来源，最适合在上传与删除时同步索引。
- 失败只记录 warning，不影响附件主流程。

### 6.2 Memory 增量同步

memory 服务中也接入了增量同步：

- `write_memory_document(...)` 成功后调用 `sync_memory_document(...)`
- `delete_memory_document(...)` 成功后调用 `delete_memory_source(...)`

这让 `/memories/` 既保留原有文件树能力，又能持续更新检索索引。

### 6.3 全量重建

对于以下场景，提供显式重建接口：

- embedding 模型切换
- 切块参数调整
- 索引损坏恢复
- 批量导入初始 memory 文档

全量重建通过 `/api/rag/reindex` 触发，支持：

- `all`
- `memories`
- `conversation_attachments`

## 7. API 设计

RAG 子系统对外提供三个调试/管理接口：

### 7.1 `GET /api/rag/status`

返回：

- 是否启用
- 禁用原因
- collection 名称
- Chroma 落盘目录
- source 数量
- chunk 数量
- 最近重建时间

作用：

- 帮助本地开发排查 embedding 配置和索引状态。

### 7.2 `POST /api/rag/search`

输入：

- `query`
- `conversation_id`
- `agent_id`
- `limit`

输出：

- 召回的 source 和 chunk 内容
- 来源路径
- 距离值

作用：

- 用于调试检索质量，而不是直接给前端用户作为主要入口。

### 7.3 `POST /api/rag/reindex`

输入：

- `scope`
- 可选 `conversation_id`
- 可选 `agent_id`

输出：

- 本次重建范围
- 索引 source 数
- chunk 数
- 最近重建时间

作用：

- 为开发调参和恢复索引提供最小运维接口。

## 8. 配置与默认策略

当前后端新增配置项：

- `RAG_ENABLED`
- `RAG_TOP_K`
- `RAG_CHUNK_SIZE`
- `RAG_CHUNK_OVERLAP`
- `RAG_COLLECTION_NAME`
- `RAG_CHROMA_PATH`
- `RAG_STATUS_PATH`
- `RAG_EMBEDDING_API_URL`
- `RAG_EMBEDDING_API_KEY`
- `RAG_EMBEDDING_MODEL`

默认策略：

- `RAG_ENABLED=true`
- 只要 embedding client 或 Chroma 不可用，就自动降级为“无 RAG”模式
- 状态文件和索引目录都保存在 `backend/data/rag/` 下

这样设计可以保证：

- 本地单机部署路径清晰。
- 对现有聊天系统是可插拔增强，而不是硬依赖。

## 9. 异常与回退策略

RAG 子系统采用“失败不阻塞主流程”的原则：

- Chroma 未安装：RAG 状态显示 disabled，聊天回退到旧上下文链路。
- embedding 配置缺失：不执行检索，但不影响会话。
- source 文件读取失败：记录 warning，跳过该 source。
- 增量同步失败：附件和 memory 主流程继续成功。
- 检索无结果：直接回退到原始聊天行为。

这对个人本地开发尤其重要，因为本地环境更容易出现临时缺依赖、索引目录损坏或配置未完成的情况。

## 10. 设计取舍

- 采用 Chroma 而非 Milvus/Qdrant，牺牲大规模扩展能力，换取零运维和快速落地。
- 采用远程 embedding 而非全本地模型，牺牲离线能力，换取更低的机器门槛。
- 采用统一 service 文件承载首期 RAG 逻辑，降低模块数量，但后续若增加 PDF 解析、reranker 或多集合治理，可能需要继续拆分。
- 采用字符级切块与 metadata 过滤，简单直接，但检索质量上限低于 token-aware splitter + reranker 的组合。

## 11. 演进方向

- 引入更稳定的文本解析链路，支持 PDF、HTML、OCR 结果和更复杂附件格式。
- 将 embedding client 抽象为可插拔适配器，支持本地模型和不同云端供应商。
- 为 `/memories/`、附件和报告引入更明确的文档分类与标签元数据。
- 在需要时升级到 hybrid search、reranker 或更强的向量库。
- 在前端增加索引状态与重建入口，但仍保持聊天自动检索为默认行为。
