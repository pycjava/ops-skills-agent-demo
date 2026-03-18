# External Integrations

**Analysis Date:** 2026-03-18

## APIs & External Services

**LLM and AI providers:**
- Anthropic Claude - primary chat and structured task-analysis model used by the backend runtime.
  - SDK/Client: `langchain-anthropic` `ChatAnthropic`
  - Auth: `ANTHROPIC_API_KEY`
  - Files: `backend/agent_manager.py`, `backend/services/inspection_task_llm.py`, `backend/config.py`
- OpenAI-compatible embeddings endpoint - used only for RAG vector generation, not for chat completion.
  - SDK/Client: raw `httpx.AsyncClient`
  - Auth: `RAG_EMBEDDING_API_KEY`
  - Config: `RAG_EMBEDDING_API_URL`, `RAG_EMBEDDING_MODEL`
  - Files: `backend/config.py`, `backend/services/rag.py`

**Authentication and identity:**
- Generic OIDC provider / Keycloak-compatible issuer - login redirect, token exchange, userinfo fetch, and role mapping.
  - SDK/Client: raw `httpx.AsyncClient`
  - Auth: `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`
  - Files: `backend/auth/config.py`, `backend/auth/service.py`, `backend/api/routers/auth.py`
- Local password-based admin login - optional fallback path stored in backend env and mapped to the local `admin` role.
  - SDK/Client: internal only
  - Auth: `LOCAL_AUTH_ENABLED`, `LOCAL_ADMIN_USERNAME`, `LOCAL_ADMIN_PASSWORD`
  - Files: `backend/auth/config.py`, `backend/auth/service.py`, `backend/api/routers/auth.py`

**MCP and tool runtimes:**
- Model Context Protocol servers - dynamic tool providers attached per agent.
  - SDK/Client: `langchain_mcp_adapters.client.MultiServerMCPClient`
  - Auth: per-server `env` and `headers` blocks inside `mcp.json`
  - Files: `mcp.json`, `backend/services/mcp_registry.py`, `backend/api/routers/mcp.py`, `backend/agent_manager.py`
- MiniMax MCP server - the current committed `mcp.json` example defines one enabled stdio server named `MiniMax`.
  - Command: `uvx minimax-coding-plan-mcp`
  - Auth/config keys: `MINIMAX_API_KEY`, `MINIMAX_MCP_BASE_PATH`, `MINIMAX_API_HOST`, `MINIMAX_API_RESOURCE_MODE`
  - Files: `mcp.json`, `backend/services/mcp_registry.py`
- `agent-browser` CLI - browser automation is integrated as an external command-line runtime, not a Python package.
  - SDK/Client: subprocess execution of `agent-browser`
  - Auth: none in repo; browser session/cookies are local runtime state
  - Files: `backend/services/browser_runtime.py`, `backend/skills/agent-browser/SKILL.md`

**Cloud and database operations:**
- Volcengine RDS MySQL and CloudMonitor APIs - used by the DBA inspection skill set.
  - SDK/Client: `volcengine-python-sdk`
  - Auth: `VOLC_CREDENTIAL_<REF>_AK` and `VOLC_CREDENTIAL_<REF>_SK`
  - Files: `backend/services/cloud_credentials.py`, `backend/api/routers/cloud_credentials.py`, `backend/skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`
- MySQL servers - used by the SQL analysis skill through a SQLAlchemy MySQL engine.
  - SDK/Client: SQLAlchemy URL `mysql+pymysql`
  - Auth: `MYSQL_USER`, `MYSQL_PASSWORD`, optional `MYSQL_CONNECT_TIMEOUT`, `MYSQL_CHARSET`
  - Files: `backend/skills/mysql-sql-analyzer/scripts/analyze_mysql_sql.py`

**Remote infrastructure access:**
- SSH-managed remote hosts - exposed through the `remote-ops` skill.
  - SDK/Client: external `ssh`
  - Auth: skill expects `./skills/remote-ops/keys/agent_ops_key`
  - Files: `backend/skills/remote-ops/SKILL.md`
- Remote Docker Engine endpoints - exposed through the `docker` skill.
  - SDK/Client: external `/usr/local/bin/docker`
  - Auth: `DOCKER_HOST`, optional `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH`
  - Files: `backend/skills/docker/SKILL.md`
- Kubernetes clusters - exposed through the `kubernetes` skill.
  - SDK/Client: external `/usr/local/bin/kubectl`
  - Auth: kubeconfig file under `backend/skills/kubernetes/`
  - Files: `backend/skills/kubernetes/SKILL.md`

**Registry, plugin, and CLI distribution:**
- Skillhub and ClawHub registries - used by the bundled CLI for search, download, lock sync, and self-upgrade.
  - SDK/Client: Python `urllib.request`
  - Auth: no required token is documented; env overrides exist for endpoints
  - Files: `backend/cli/skills_store_cli.py`, `backend/cli/metadata.json`
- OpenClaw plugin and gateway integration - local installer copies a plugin and can restart the OpenClaw gateway on loopback port `18789`.
  - SDK/Client: shell commands plus `openclaw/plugin-sdk` type import in `backend/cli/plugin/index.ts`
  - Auth: OpenClaw local config, not stored in this repo
  - Files: `backend/cli/install.sh`, `backend/cli/plugin/index.ts`, `backend/cli/plugin/openclaw.plugin.json`

## Data Storage

**Databases:**
- SQLite - the main business database for conversations, messages, tasks, notifications, auth/RBAC, attachments metadata, and the `mcp_servers` ORM model.
  - Connection: `SQLITE_PATH` -> `DATABASE_URL` / `DATABASE_URL_SYNC`
  - Client: SQLAlchemy async engine in `backend/db/session.py`
  - Models: `backend/models/*.py`
- LangGraph SQLite persistence - the same SQLite path is also reused for agent checkpoint/store persistence.
  - Connection: `AsyncSqliteSaver.from_conn_string(SQLITE_PATH)` and `AsyncSqliteStore.from_conn_string(SQLITE_PATH)`
  - Client: LangGraph SQLite adapters in `backend/agent_manager.py`

**File Storage:**
- Local filesystem only for application assets and attachments.
  - Conversation attachments: `backend/data/conversation_attachments/` via `backend/services/conversation_attachments.py`
  - Assistant/browser screenshots: `backend/data/conversation_assets/` via `backend/services/assistant_images.py`
  - RAG metadata/status: `backend/data/rag/` via `backend/config.py` and `backend/services/rag.py`
  - MCP config source of truth: repo-root `mcp.json` via `backend/services/mcp_registry.py`
  - Skillhub install/cache home: `~/.skillhub` via `backend/cli/install.sh`
  - OpenClaw plugin install target: `~/.openclaw/extensions/skillhub` via `backend/cli/install.sh`
  - Volcengine skill output: default metric JSON output is `D:\Study\python\agent\maintenance-agent\metric_data` unless overridden by CLI args in `backend/skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`

**Caching:**
- No Redis or external cache is detected.
- In-process caches exist only for runtime convenience:
  - agent runtime cache in `backend/agent_manager.py`
  - MCP test-state cache in `backend/services/mcp_registry.py`

## Authentication & Identity

**Auth Provider:**
- Configurable OIDC provider with local password fallback.
  - Implementation: Starlette `SessionMiddleware` in `backend/main.py`, local RBAC stored in SQLite via `backend/models/auth.py`, and frontend `fetch(..., credentials: 'include')` in `frontend/src/stores/chat/helpers.ts`
  - Session gatekeeping: REST uses `require_permission(...)` and WebSocket uses `ensure_websocket_permission(...)` in `backend/auth/dependencies.py`
  - Frontend route guard: `frontend/src/router.ts`

## Monitoring & Observability

**Error Tracking:**
- None detected. No Sentry, Datadog, Rollbar, or similar SaaS integration is referenced.

**Logs:**
- App logging uses `loguru` with stderr output plus optional rotating file logs configured by `LOG_FILE`, `LOG_MAX_SIZE_MB`, and `LOG_BACKUP_COUNT` in `backend/utils/logger.py` and `backend/config.py`.
- Container health checks are built into `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml`.

## CI/CD & Deployment

**Hosting:**
- Self-hosted/local container deployment is the only committed deployment path.
  - Backend container: `backend/Dockerfile`, exposes `8000`, runs `uvicorn main:app`
  - Frontend container: `frontend/Dockerfile`, serves built assets through Nginx
  - Compose orchestration: `docker-compose.yml`
  - Reverse proxy wiring: `frontend/nginx.conf` proxies `/api/` and `/ws/` to `http://backend:8000`

**CI Pipeline:**
- Not detected. No GitHub Actions, GitLab CI, Jenkinsfile, Azure Pipelines, or similar pipeline config is present in the repository root.

## Environment Configuration

**Required env vars:**
- Backend core: `ANTHROPIC_API_KEY`, `MODEL_NAME`, `MULTIMODAL_ENABLED`, `VISION_MODEL_ALLOWLIST`, `MAX_TURNS`, `SQLITE_PATH`, `LOG_LEVEL`, `LOG_FILE`, `LOG_MAX_SIZE_MB`, `LOG_BACKUP_COUNT`, `CORS_ALLOW_ORIGINS`
- Auth/RBAC: `AUTH_ENABLED`, `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`, `OIDC_SCOPE`, `OIDC_ROLE_CLAIM`, `OIDC_ROLE_MAP`, `AUTH_DEFAULT_ROLE`, `LOCAL_AUTH_ENABLED`, `LOCAL_ADMIN_USERNAME`, `LOCAL_ADMIN_PASSWORD`, `LOCAL_ADMIN_DISPLAY_NAME`, `SESSION_SECRET`, `SESSION_COOKIE_NAME`, `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_SECURE`
- RAG: `RAG_ENABLED`, `RAG_TOP_K`, `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`, `RAG_COLLECTION_NAME`, `RAG_CHROMA_PATH`, `RAG_STATUS_PATH`, `RAG_EMBEDDING_API_URL`, `RAG_EMBEDDING_API_KEY`, `RAG_EMBEDDING_MODEL`
- Frontend: `VITE_API_BASE_URL`, `VITE_WS_URL`
- Volcengine skill/auth mapping: `VOLC_CREDENTIAL_<REF>_AK`, `VOLC_CREDENTIAL_<REF>_SK`
- MySQL skill: `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_CONNECT_TIMEOUT`, `MYSQL_CHARSET`
- Docker skill: `DOCKER_HOST`, `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH`
- Skillhub CLI overrides: `SKILLHUB_SEARCH_URL`, `SKILLHUB_PRIMARY_DOWNLOAD_URL_TEMPLATE`, `SKILLHUB_CLAWHUB_LOCK_PATH`, `LOG`

**Secrets location:**
- `backend/.env` is present and is the main backend secret/config file. Its contents are intentionally not quoted.
- `mcp.json` can carry secret-bearing MCP `env` values and should be treated as sensitive config even though it lives at repo root.
- Frontend env files exist at `frontend/.env.example`, `frontend/.env.development`, and `frontend/.env.production` (existence noted only).
- Skillhub/OpenClaw installer writes runtime config outside the repo under `~/.skillhub/` and `~/.openclaw/`.

## Webhooks & Callbacks

**Incoming:**
- OIDC login callback: `GET /api/auth/callback` in `backend/api/routers/auth.py`
- Browser/client WebSocket session: `WS /ws/chat` in `backend/api/ws/chat.py`
- No third-party webhook receiver endpoints are detected.

**Outgoing:**
- OIDC discovery, token exchange, userinfo fetch in `backend/auth/service.py`
- Embedding POST requests to `RAG_EMBEDDING_API_URL` in `backend/services/rag.py`
- MCP stdio/http/sse connections constructed from `mcp.json` in `backend/services/mcp_registry.py`
- Volcengine API calls in `backend/skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`
- Skillhub/ClawHub search/download/self-upgrade requests in `backend/cli/skills_store_cli.py`

---

*Integration audit: 2026-03-18*
