# 外部集成

**分析日期：** 2026-03-18

## API 与外部服务

**LLM 与 AI 服务：**
- Anthropic Claude：当前后端聊天与任务分析的主模型提供方。
  - 客户端：`langchain-anthropic` 的 `ChatAnthropic`
  - 认证：`ANTHROPIC_API_KEY`
  - 相关文件：`backend/agent_manager.py`、`backend/services/inspection_task_llm.py`、`backend/config.py`
- OpenAI 兼容的 Embeddings 接口：仅用于 RAG 向量生成，不参与聊天补全。
  - 客户端：原生 `httpx.AsyncClient`
  - 认证：`RAG_EMBEDDING_API_KEY`
  - 配置：`RAG_EMBEDDING_API_URL`、`RAG_EMBEDDING_MODEL`
  - 相关文件：`backend/config.py`、`backend/services/rag.py`

**认证与身份服务：**
- 通用 OIDC / Keycloak 兼容服务：负责登录跳转、Token 交换、userinfo 拉取和角色映射。
  - 客户端：原生 `httpx.AsyncClient`
  - 认证：`OIDC_ISSUER_URL`、`OIDC_CLIENT_ID`、`OIDC_CLIENT_SECRET`、`OIDC_REDIRECT_URI`
  - 相关文件：`backend/auth/config.py`、`backend/auth/service.py`、`backend/api/routers/auth.py`
- 本地用户名密码管理员登录：作为可选兜底路径，凭据从后端环境变量读取并映射到本地 `admin` 角色。
  - 客户端：内部实现
  - 认证：`LOCAL_AUTH_ENABLED`、`LOCAL_ADMIN_USERNAME`、`LOCAL_ADMIN_PASSWORD`
  - 相关文件：`backend/auth/config.py`、`backend/auth/service.py`、`backend/api/routers/auth.py`

**MCP 与工具运行时：**
- Model Context Protocol Server：按 Agent 动态挂载的工具来源。
  - 客户端：`langchain_mcp_adapters.client.MultiServerMCPClient`
  - 认证：`mcp.json` 中各服务的 `env` 与 `headers`
  - 相关文件：`mcp.json`、`backend/services/mcp_registry.py`、`backend/api/routers/mcp.py`、`backend/agent_manager.py`
- MiniMax MCP Server：当前仓库提交的 `mcp.json` 示例中包含一个启用的 `MiniMax` stdio server。
  - 命令：`uvx minimax-coding-plan-mcp`
  - 配置键：`MINIMAX_API_KEY`、`MINIMAX_MCP_BASE_PATH`、`MINIMAX_API_HOST`、`MINIMAX_API_RESOURCE_MODE`
  - 相关文件：`mcp.json`、`backend/services/mcp_registry.py`
- `agent-browser` CLI：浏览器自动化通过外部命令行工具接入，而不是纯 Python 包。
  - 客户端：子进程执行 `agent-browser`
  - 认证：仓库内未见固定配置，浏览器会话依赖本地运行时状态
  - 相关文件：`backend/services/browser_runtime.py`、`backend/skills/agent-browser/SKILL.md`

**云与数据库运维：**
- 火山引擎 RDS MySQL 与 CloudMonitor API：供 DBA 巡检 skill 调用。
  - 客户端：`volcengine-python-sdk`
  - 认证：`VOLC_CREDENTIAL_<REF>_AK` 与 `VOLC_CREDENTIAL_<REF>_SK`
  - 相关文件：`backend/services/cloud_credentials.py`、`backend/api/routers/cloud_credentials.py`、`backend/skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`
- MySQL 服务：供 SQL 分析 skill 连接真实数据库。
  - 客户端：SQLAlchemy `mysql+pymysql`
  - 认证：`MYSQL_USER`、`MYSQL_PASSWORD`，可选 `MYSQL_CONNECT_TIMEOUT`、`MYSQL_CHARSET`
  - 相关文件：`backend/skills/mysql-sql-analyzer/scripts/analyze_mysql_sql.py`

**远程基础设施接入：**
- SSH 主机：由 `remote-ops` skill 使用。
  - 客户端：外部 `ssh`
  - 认证：skill 约定使用 `./skills/remote-ops/keys/agent_ops_key`
  - 相关文件：`backend/skills/remote-ops/SKILL.md`
- 远程 Docker Engine：由 `docker` skill 使用。
  - 客户端：外部 `/usr/local/bin/docker`
  - 认证：`DOCKER_HOST`，可选 `DOCKER_TLS_VERIFY` 与 `DOCKER_CERT_PATH`
  - 相关文件：`backend/skills/docker/SKILL.md`
- Kubernetes 集群：由 `kubernetes` skill 使用。
  - 客户端：外部 `/usr/local/bin/kubectl`
  - 认证：kubeconfig 文件
  - 相关文件：`backend/skills/kubernetes/SKILL.md`

**仓库、插件与 CLI 分发：**
- Skillhub / ClawHub：供内置 CLI 执行搜索、下载、锁文件同步和自升级。
  - 客户端：Python `urllib.request`
  - 认证：文档中未声明必须 token，但支持环境变量覆盖端点
  - 相关文件：`backend/cli/skills_store_cli.py`、`backend/cli/metadata.json`
- OpenClaw 插件与网关：本地安装脚本会复制插件并可重启本地 `18789` 端口上的 OpenClaw 网关。
  - 客户端：Shell 命令与 `openclaw/plugin-sdk` 类型导入
  - 认证：依赖本地 OpenClaw 配置，不保存在当前仓库中
  - 相关文件：`backend/cli/install.sh`、`backend/cli/plugin/index.ts`、`backend/cli/plugin/openclaw.plugin.json`

## 数据存储

**数据库：**
- SQLite：业务主数据库，保存会话、消息、任务、通知、认证/RBAC、附件元数据以及 `mcp_servers` ORM 模型。
  - 连接：`SQLITE_PATH` -> `DATABASE_URL` / `DATABASE_URL_SYNC`
  - 客户端：`backend/db/session.py` 中的 SQLAlchemy Async Engine
  - 模型：`backend/models/*.py`
- LangGraph SQLite 持久化：与业务数据库复用同一个 SQLite 路径，用于 Agent checkpoint 与 `/memories/`。
  - 连接：`AsyncSqliteSaver.from_conn_string(SQLITE_PATH)` 与 `AsyncSqliteStore.from_conn_string(SQLITE_PATH)`
  - 客户端：`backend/agent_manager.py`

**文件存储：**
- 当前项目没有接入对象存储，应用资产与附件都落本地文件系统。
- 会话附件：`backend/data/conversation_attachments/`，由 `backend/services/conversation_attachments.py` 管理。
- Assistant / 浏览器截图：`backend/data/conversation_assets/`，由 `backend/services/assistant_images.py` 管理。
- RAG 元数据与状态文件：`backend/data/rag/`，由 `backend/config.py` 与 `backend/services/rag.py` 使用。
- MCP 配置源：仓库根目录 `mcp.json`。
- Skillhub 安装/缓存目录：`~/.skillhub`。
- OpenClaw 插件安装目录：`~/.openclaw/extensions/skillhub`。

**缓存：**
- 未发现 Redis 或外部缓存。
- 仅存在进程内缓存：
  - `backend/agent_manager.py` 中的 Agent 运行时缓存
  - `backend/services/mcp_registry.py` 中的 MCP 测试状态缓存

## 认证与身份

**认证方式：**
- 支持 OIDC 和本地密码登录两条路径。
- 会话通过 `backend/main.py` 安装的 `SessionMiddleware` 维护。
- 本地 RBAC 数据持久化在 SQLite 中，对应模型是 `backend/models/auth.py`。
- 前端统一通过 `fetch(..., credentials: 'include')` 保持 Cookie 会话，相关逻辑位于 `frontend/src/stores/chat/helpers.ts`。
- REST 路由通过 `require_permission(...)` 控制权限，WebSocket 则通过 `ensure_websocket_permission(...)` 控制，定义在 `backend/auth/dependencies.py`。

## 监控与可观测性

**错误跟踪：**
- 未发现 Sentry、Datadog、Rollbar 等 SaaS 级错误采集服务。

**日志：**
- 日志由 `loguru` 输出到 stderr，并可按 `LOG_FILE`、`LOG_MAX_SIZE_MB`、`LOG_BACKUP_COUNT` 写入滚动文件。
- 容器级健康检查定义在 `backend/Dockerfile`、`frontend/Dockerfile` 和 `docker-compose.yml` 中。

## CI/CD 与部署

**部署方式：**
- 当前仓库唯一明确提交的部署路径是本地/自托管容器部署。
- 后端容器：`backend/Dockerfile`，暴露 `8000`，启动命令为 `uvicorn main:app`。
- 前端容器：`frontend/Dockerfile`，使用 Nginx 提供静态资源。
- 编排文件：`docker-compose.yml`。
- 反向代理：`frontend/nginx.conf` 将 `/api/` 与 `/ws/` 转发到 `http://backend:8000`。

**CI：**
- 仓库中未发现 GitHub Actions、GitLab CI、Jenkinsfile 或 Azure Pipelines 等持续集成配置。

## 环境变量

**核心后端：**
- `ANTHROPIC_API_KEY`、`MODEL_NAME`、`MULTIMODAL_ENABLED`、`VISION_MODEL_ALLOWLIST`、`MAX_TURNS`
- `SQLITE_PATH`、`LOG_LEVEL`、`LOG_FILE`、`LOG_MAX_SIZE_MB`、`LOG_BACKUP_COUNT`
- `CORS_ALLOW_ORIGINS`

**认证与权限：**
- `AUTH_ENABLED`、`OIDC_ISSUER_URL`、`OIDC_CLIENT_ID`、`OIDC_CLIENT_SECRET`、`OIDC_REDIRECT_URI`
- `OIDC_SCOPE`、`OIDC_ROLE_CLAIM`、`OIDC_ROLE_MAP`、`AUTH_DEFAULT_ROLE`
- `LOCAL_AUTH_ENABLED`、`LOCAL_ADMIN_USERNAME`、`LOCAL_ADMIN_PASSWORD`、`LOCAL_ADMIN_DISPLAY_NAME`
- `SESSION_SECRET`、`SESSION_COOKIE_NAME`、`SESSION_COOKIE_SAMESITE`、`SESSION_COOKIE_SECURE`

**RAG：**
- `RAG_ENABLED`、`RAG_TOP_K`、`RAG_CHUNK_SIZE`、`RAG_CHUNK_OVERLAP`
- `RAG_COLLECTION_NAME`、`RAG_CHROMA_PATH`、`RAG_STATUS_PATH`
- `RAG_EMBEDDING_API_URL`、`RAG_EMBEDDING_API_KEY`、`RAG_EMBEDDING_MODEL`

**前端：**
- `VITE_API_BASE_URL`、`VITE_WS_URL`

**运维类 skill：**
- `VOLC_CREDENTIAL_<REF>_AK`、`VOLC_CREDENTIAL_<REF>_SK`
- `MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_CONNECT_TIMEOUT`、`MYSQL_CHARSET`
- `DOCKER_HOST`、`DOCKER_TLS_VERIFY`、`DOCKER_CERT_PATH`
- `SKILLHUB_SEARCH_URL`、`SKILLHUB_PRIMARY_DOWNLOAD_URL_TEMPLATE`、`SKILLHUB_CLAWHUB_LOCK_PATH`

**敏感配置位置：**
- `backend/.env` 是主配置与密钥文件。
- `mcp.json` 也可能包含带密钥的 `env` 字段，应视为敏感配置。
- 前端存在 `frontend/.env.example`、`frontend/.env.development`、`frontend/.env.production`。

## 回调与双向连接

**入站：**
- OIDC 登录回调：`GET /api/auth/callback`，实现于 `backend/api/routers/auth.py`
- 浏览器到服务端的 WebSocket：`WS /ws/chat`，实现于 `backend/api/ws/chat.py`
- 未发现第三方 webhook 接收端点。

**出站：**
- `backend/auth/service.py` 负责 OIDC discovery、token 交换与 userinfo 请求。
- `backend/services/rag.py` 负责向 `RAG_EMBEDDING_API_URL` 发送 embedding 请求。
- `backend/services/mcp_registry.py` 负责根据 `mcp.json` 建立 stdio/http/sse MCP 连接。
- 火山云 skill 脚本会主动调用火山引擎 API。
- `backend/cli/skills_store_cli.py` 会向 Skillhub / ClawHub 发起搜索、下载与升级请求。

---

*外部集成分析：2026-03-18*
