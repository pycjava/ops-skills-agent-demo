# 代码库关注点

**分析日期：** 2026-03-18

## 技术债

**启动时内联执行 SQLite 模式迁移：**
- 问题：`backend/db/session.py` 在 `init_db()` 里直接通过 `ALTER TABLE` 和数据回填修改线上 schema，还顺便处理兼容字段和历史标题修正。
- 影响：应用启动本身成了迁移机制，变更难审查、难回滚，多个实例首次启动时还可能对同一个 SQLite 文件竞争。
- 涉及文件：`backend/db/session.py`
- 建议：把 schema 演进迁移到显式 migration 流程，应用启动阶段只做 readiness 和 seed 校验。

**大文件集中承载核心逻辑，但缺少风格门禁：**
- 问题：关键行为集中在几个高频变更的大文件中，例如 `frontend/src/App.vue`、`frontend/src/components/MessageBubble.vue`、`backend/agent.py`、`backend/services/inspection_tasks.py`、`backend/services/conversation_attachments.py`、`backend/services/cloud_credentials.py`。
- 影响：重构成本高、代码评审噪声大、冲突概率上升，而且前端又没有 ESLint / Prettier / Biome 这类自动门禁。
- 涉及文件：`frontend/src/App.vue`、`frontend/src/components/MessageBubble.vue`、`frontend/src/stores/chat.ts`、`frontend/src/stores/chat/socket.ts`、`backend/agent.py`、`backend/services/inspection_tasks.py`、`backend/services/conversation_attachments.py`、`backend/services/cloud_credentials.py`、`frontend/package.json`
- 建议：继续拆分 UI 和 runtime domain，并在 CI 中补上 lint/format 检查。

**文档与实际运行拓扑存在漂移：**
- 问题：`frontend/README.md` 还是默认 Vite 模板，`README.md` 对“内置 Agent 数量”的描述也和 `backend/agents/` 中真实 runtime profile 不完全一致。
- 影响：新成员 onboarding、部署准备和运行前置条件判断都会被误导。
- 涉及文件：`frontend/README.md`、`README.md`、`backend/agents/`
- 建议：替换掉默认前端 README，把“用户可见 Agent”和“内部运行时 Agent”明确区分，并把文档校验纳入发布前检查表。

## 已知问题

**后端容器启动依赖 `agent-browser`，但镜像本身没有安装它：**
- 现象：即使没有启用浏览器自动化，后端启动时也可能因为 `agent-browser` 不存在而抛出 `RuntimeError`。
- 触发条件：在全新环境或 `docker compose up` 中直接启动后端且没有手动安装 `agent-browser`。
- 涉及文件：`backend/main.py`、`backend/services/browser_runtime.py`、`backend/Dockerfile`、`docker-compose.yml`、`backend/tests/test_browser_runtime_service.py`
- 临时绕过：人工安装 `agent-browser` 或屏蔽启动校验。

**云凭据状态检测对容器注入环境变量不友好：**
- 现象：如果凭据只通过进程环境变量或 `env_file` 注入，而不写进 `backend/.env`，云凭据注册表可能仍显示 `missing`。
- 触发条件：部署环境通过运行时注入 `VOLC_CREDENTIAL_<REF>_AK` 和 `VOLC_CREDENTIAL_<REF>_SK`。
- 涉及文件：`backend/services/cloud_credentials.py`、`docker-compose.yml`
- 临时绕过：把敏感信息重复写进 `backend/.env`，但这会增加密钥扩散风险。

**删除会话后 OCR 产物文件可能残留：**
- 现象：`data/conversation_attachments/<conversation_id>/_ocr/` 下的 OCR Markdown 文件在删除会话后仍可能留在磁盘上。
- 触发条件：先上传图片、生成 OCR，再删除该会话。
- 涉及文件：`backend/services/conversation_attachments.py`、`backend/api/routers/conversations.py`
- 临时绕过：手工清理 `backend/data/conversation_attachments/` 中对应 `_ocr` 目录。

## 安全关注点

**MCP 配置中的密钥被提交并可能通过 API 返回：**
- 风险：`mcp.json` 已纳入版本库，而且允许内联 `env` 密钥；`backend/api/routers/mcp.py` 会返回原始 `config_text`，`backend/services/mcp_registry.py` 与 `backend/models/mcp_server.py` 也会把 `env` 放进“公开”响应结构。
- 涉及文件：`mcp.json`、`.gitignore`、`backend/api/routers/mcp.py`、`backend/services/mcp_registry.py`、`backend/models/mcp_server.py`、`backend/tests/test_mcp_router.py`
- 当前缓解：只做了 `mcp_servers:*` 级别的权限控制。
- 建议：立即轮换已暴露密钥，不再把真实密钥写进受版本控制的 `mcp.json`，API 只返回 key 名而不是 value，并为脱敏建立回归测试。

**认证默认行为偏向 fail-open：**
- 风险：当 `AUTH_ENABLED=false` 时，`require_permission(...)` 会直接放行，整个 API 面几乎处于无认证状态；`backend/auth/config.py` 还提供了默认 `SESSION_SECRET="agentweave-session-secret"`，本地管理员密码也以明文环境变量形式存在。
- 涉及文件：`backend/auth/config.py`、`backend/auth/dependencies.py`、`backend/api/routers/auth.py`、`backend/api/routers/conversations.py`、`backend/api/routers/mcp.py`、`backend/api/routers/task_notifications.py`、`backend/tests/test_auth_rbac.py`、`README.md`
- 当前缓解：主要靠 README 的配置说明。
- 建议：增加显式“仅开发环境允许绕过认证”的开关；认证开启时若仍是默认 session secret，应拒绝启动；本地管理员凭据建议改为哈希存储或彻底交给外部身份系统。

**缺少 owner / tenant 级数据边界：**
- 风险：虽然有 RBAC，但会话、任务、附件和通知没有用户或租户归属字段；很多查询返回的是全局数据，实时通知也会广播给当前进程里的所有连接。
- 涉及文件：`backend/models/conversation.py`、`backend/models/conversation_attachment.py`、`backend/models/inspection_task.py`、`backend/models/task_notification.py`、`backend/api/routers/conversations.py`、`backend/api/routers/task_notifications.py`、`backend/services/realtime_events.py`
- 当前缓解：仅靠角色权限做粗粒度控制。
- 建议：为核心表增加 owner / tenant 字段，把列表/读取/更新都收敛到当前 principal 范围内，并把实时通知改为用户级频道。

## 性能瓶颈

**云凭据解析会扫描整个 memory 树：**
- 问题：`resolve_cloud_request_context()` 会遍历 `/memories`、扁平化路径、逐个读取匹配文档，再重新解析实例信息和凭据状态。
- 原因：缺少缓存或预计算索引。
- 涉及文件：`backend/services/cloud_credentials.py`、`backend/services/memory.py`
- 建议：缓存解析后的 memory 元数据，并在写入时增量刷新；凭据状态也应基于进程环境一次性构建，而不是每次重新读文件。

**图片附件会快速放大 prompt 体积：**
- 问题：图片会被读入内存并直接编码成 base64 块塞进模型输入；系统允许每会话最多 50 个附件、单文件 1 MB，但在 prompt 组装前没有压缩、缩放或每轮预算控制。
- 原因：`build_image_attachment_blocks()` 直接序列化原始文件字节。
- 涉及文件：`backend/services/conversation_attachments.py`、`backend/agent.py`、`backend/services/multimodal_ocr.py`
- 建议：限制单轮图片数量，服务端压缩或缩放图片，优先使用 OCR / 摘要而不是原图 base64。

**前端热点路径中过多逻辑堆在组件层：**
- 问题：`frontend/src/App.vue` 管着大量工作台状态与布局切换，`frontend/src/components/MessageBubble.vue` 则承载 Markdown 渲染、清洗、资产识别和附件交互。
- 原因：展现逻辑和行为逻辑仍然高度耦合。
- 涉及文件：`frontend/src/App.vue`、`frontend/src/components/MessageBubble.vue`
- 建议：把 Markdown 渲染抽到共用 utility/composable 中，把工作台壳层拆成更小的路由级与面板级组件。

## 脆弱区域

**任务调度器不具备并发安全：**
- 原因：`get_due_inspection_task_ids()` 先查到期任务，`execute_inspection_task()` 再去 claim 任务；多个后端实例可能在 `next_run_at` 更新前同时捞到同一任务。
- 涉及文件：`backend/services/inspection_scheduler.py`、`backend/services/inspection_tasks.py`
- 安全修改方向：在同一个事务中加入数据库级 claim / lease 步骤。
- 当前测试：覆盖了单实例流程，但没有跨进程竞争测试。

**实时通知只在单进程内有效：**
- 原因：WebSocket 连接保存在单进程内存集合中；如果任务在一个副本上完成，而用户连在另一个副本上，就收不到通知。
- 涉及文件：`backend/services/realtime_events.py`、`backend/services/inspection_tasks.py`、`backend/api/ws/chat.py`
- 安全修改方向：改为共享 pub/sub，并视需求持久化投递状态。
- 当前测试：只验证 payload 结构，不验证多进程行为。

**浏览器运行时和启动流程耦合过紧：**
- 原因：应用启动、截图补采和图片资产持久化都默认依赖外部 `agent-browser` CLI 与本地工作目录行为稳定。
- 涉及文件：`backend/main.py`、`backend/services/browser_runtime.py`、`backend/services/assistant_images.py`、`backend/api/ws/chat.py`
- 安全修改方向：把浏览器自动化改成显式特性开关或可选子系统，并暴露独立健康状态。
- 当前测试：只有 helper 级测试，没有容器启动路径集成测试。

## 扩展限制

**同一个 SQLite 文件同时承载业务数据和 Agent 运行时状态：**
- 现状：`SQLITE_PATH` 同时被 SQLAlchemy、`AsyncSqliteSaver` 和 `AsyncSqliteStore` 使用。
- 限制：随着会话、checkpoint、记忆、任务运行变多，文件锁和写竞争会变明显，尤其是在多进程或共享卷场景下。
- 方向：把业务库与 LangGraph checkpoint / memory 存储拆开，必要时迁移到更适合服务化部署的后端。

**调度器默认假设只有一个后端进程：**
- 现状：`InspectionSchedulerRuntime` 在应用进程内每 30 秒轮询一次。
- 限制：一旦多实例部署，重复执行任务的概率会上升。
- 方向：把调度能力迁移到独立 worker，或引入分布式锁/租约机制。

**通知投递假设单进程内 WebSocket 广播即可：**
- 现状：`RealtimeEventManager` 只维护本地进程内连接。
- 限制：没有跨实例传播，也没有断线期间的可靠回放。
- 方向：引入共享 pub/sub，并按用户持久化未读状态。

## 风险依赖

**后端 Python 依赖没有锁文件：**
- 风险：`backend/requirements.txt` 里很多包是区间版本，例如 `deepagents`、`langchain-anthropic`、`langchain-mcp-adapters`；新环境安装结果可能漂移。
- 影响：事件流结构、MCP 行为、Agent runtime 语义都可能与测试时不同。
- 建议：生成并提交后端锁文件或 constraints 文件。

**`elasticsearch==7.10.0`：**
- 风险：虽然写在 `backend/requirements.txt` 里，但当前运行时代码中几乎没有实际使用痕迹。
- 影响：镜像体积更大、维护面更广、额外攻击面增加。
- 建议：确认是否真有规划中的特性依赖它；如果没有，直接删除。

## 缺失的关键能力

**按用户 / 团队隔离数据：**
- 问题：当前权限模型只做角色控制，没有把会话、任务、通知、MCP 配置、附件收敛到某个用户或团队边界。
- 阻碍：无法安全支撑多用户部署、审计和最小权限访问，也很难演进成托管型或团队共享部署模式。

## 测试缺口

**MCP 脱敏与配置净化：**
- 未覆盖：`/api/mcp/config` 与 `/api/mcp/servers` 是否会对 `config_text`、`env` 和 header 中的敏感信息做脱敏。
- 涉及文件：`backend/api/routers/mcp.py`、`backend/services/mcp_registry.py`、`backend/tests/test_mcp_router.py`
- 风险等级：高

**调度并发与跨进程通知：**
- 未覆盖：并发调度器下是否会重复执行同一任务，多进程部署下通知是否会漏投。
- 涉及文件：`backend/services/inspection_scheduler.py`、`backend/services/inspection_tasks.py`、`backend/services/realtime_events.py`
- 风险等级：高

**OCR 产物清理：**
- 未覆盖：删除会话后 `_ocr` 文件和目录是否会一并清除。
- 涉及文件：`backend/services/conversation_attachments.py`、`backend/api/routers/conversations.py`
- 风险等级：中

**运行时环境变量来源的凭据状态检测：**
- 未覆盖：当云凭据来自进程环境而不是 `backend/.env` 时，状态检测是否准确。
- 涉及文件：`backend/services/cloud_credentials.py`、`docker-compose.yml`
- 风险等级：中

**运行时打包与文档一致性：**
- 未覆盖：默认镜像是否具备所有外部运行时依赖，仓库文档是否与真实运行拓扑保持一致。
- 涉及文件：`backend/Dockerfile`、`docker-compose.yml`、`backend/main.py`、`README.md`、`frontend/README.md`
- 风险等级：中

---

*关注点分析：2026-03-18*
