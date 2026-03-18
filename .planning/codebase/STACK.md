# Technology Stack

**Analysis Date:** 2026-03-18

## Languages

**Primary:**
- Python 3.12 in containers, with Python 3.10+ documented for local development in `README.md`. The backend service, agent runtime, API routers, services, and ORM models all live under `backend/` (`backend/main.py`, `backend/api/`, `backend/services/`, `backend/models/`).
- TypeScript 5.9 (`frontend/package.json`) for the SPA, frontend store/router layer, Vitest tests, and the bundled OpenClaw plugin source in `backend/cli/plugin/index.ts`.

**Secondary:**
- Vue Single File Components in `frontend/src/App.vue`, `frontend/src/RootApp.vue`, and `frontend/src/components/*.vue`.
- Bash for install and diagnostic scripts in `backend/cli/install.sh`, `backend/skills/docker/scripts/docker_readonly_diagnose.sh`, and `backend/skills/kubernetes/scripts/k8s_readonly_diagnose.sh`.
- TOML for agent registry/manifests in `backend/agents/registry.toml` and `backend/agents/*/agent.toml`.
- Markdown as executable prompt/skill content in `backend/prompts/*.md` and `backend/skills/*/SKILL.md`.

## Runtime

**Environment:**
- Backend runtime: CPython. The container image is `python:3.12-slim` in `backend/Dockerfile`; local setup in `README.md` uses a standard virtualenv plus `pip install -r backend/requirements.txt`.
- Frontend runtime: Node.js for development/build. The builder image is `node:22.22-slim` in `frontend/Dockerfile`; local setup in `README.md` uses `npm install`.
- Frontend serving layer: `nginx:alpine` in `frontend/Dockerfile`, configured by `frontend/nginx.conf`.

**Package Manager:**
- Backend: `pip` against `backend/requirements.txt`. No `pyproject.toml`, Poetry, Pipenv, or Python lockfile is detected.
- Backend image also installs Astral `uv` in `backend/Dockerfile`, but the app still installs dependencies with `pip` and starts with `uvicorn`.
- Frontend: npm with `frontend/package-lock.json`.
- Lockfile: `frontend/package-lock.json` is present; no Python dependency lockfile is present.

## Frameworks

**Core:**
- FastAPI `>=0.115.0` and Uvicorn `>=0.34.0` power the HTTP and WebSocket service in `backend/main.py`, `backend/api/routers/`, and `backend/api/ws/chat.py`.
- DeepAgents `>=0.4.7,<0.5` plus LangGraph SQLite checkpoint/store drive the multi-agent runtime in `backend/agent_manager.py`.
- Vue `^3.5.25`, Pinia `^3.0.4`, and Vue Router `^4.5.1` implement the frontend workspace in `frontend/src/main.ts`, `frontend/src/stores/chat.ts`, and `frontend/src/router.ts`.
- SQLAlchemy `>=2.0` with `aiosqlite>=0.20.0` handles persistence in `backend/db/session.py` and `backend/models/*.py`.

**Testing:**
- pytest `>=8.3.0` with `pytest-asyncio>=0.24.0` for backend tests in `backend/tests/` and `backend/pytest.ini`.
- Vitest `^2.1.8` with `@vue/test-utils` and `jsdom` for frontend tests in `frontend/src/**/*.test.ts` and `frontend/vite.config.ts`.

**Build/Dev:**
- Vite `^7.3.1`, `@vitejs/plugin-vue`, `vue-tsc`, and strict TS configs in `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, and `frontend/tsconfig.node.json`.
- Docker Compose for the demo/deployment stack in `docker-compose.yml`.
- Nginx reverse proxy configuration in `frontend/nginx.conf`.
- Shell-based CLI/plugin installer for Skillhub/OpenClaw in `backend/cli/install.sh`.

## Key Dependencies

**Critical:**
- `deepagents>=0.4.7,<0.5` - creates the multi-agent runtime and tool/skill injection path in `backend/agent_manager.py`.
- `langchain-anthropic>=0.3.0` - `ChatAnthropic` is the main LLM client in `backend/agent_manager.py` and `backend/services/inspection_task_llm.py`.
- `langchain-mcp-adapters>=0.1.8` - bridges configured MCP servers into runtime tools in `backend/services/mcp_registry.py` and `backend/agent_manager.py`.
- `sqlalchemy[asyncio]>=2.0` and `aiosqlite>=0.20.0` - back both the REST data model and async SQLite access in `backend/db/session.py`.
- `chromadb>=0.5.20` - persistent vector index for RAG in `backend/services/rag.py`.
- `httpx>=0.28.0` - outbound HTTP client for OIDC and embeddings in `backend/auth/service.py` and `backend/services/rag.py`.
- `dompurify` and `marked` - sanitize/render assistant markdown in `frontend/src/components/MessageBubble.vue`.

**Infrastructure:**
- `langgraph-checkpoint-sqlite>=2.0.11` - persists agent checkpoints/store state in `backend/agent_manager.py`.
- `python-dotenv>=1.0.0` - loads backend env and skill env overlays in `backend/config.py`, `backend/services/cloud_credentials.py`, and skill scripts.
- `loguru` - centralized logging in `backend/utils/logger.py`.
- `volcengine-python-sdk==5.0.16` - powers Volcengine RDS and CloudMonitor skill scripts in `backend/skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`.

## Configuration

**Environment:**
- Backend process configuration is loaded from `backend/.env` at startup by `backend/config.py`; the auth layer extends that surface in `backend/auth/config.py`.
- Frontend runtime configuration comes from `VITE_API_BASE_URL` and `VITE_WS_URL` in `frontend/src/stores/chat.ts`. Mode-specific files exist at `frontend/.env.development` and `frontend/.env.production` (existence noted only).
- The live MCP source of truth is repo-root `mcp.json`, resolved through `backend/config.py` and parsed by `backend/services/mcp_registry.py`.
- Agent/runtime wiring is configured through `backend/agents/registry.toml`, `backend/agents/*/agent.toml`, and prompt files under `backend/prompts/`.

**Build:**
- Frontend build config lives in `frontend/vite.config.ts` and `frontend/tsconfig*.json`.
- Container/deployment config lives in `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, and `docker-compose.yml`.
- CLI/plugin packaging config lives in `backend/cli/metadata.json`, `backend/cli/version.json`, and `backend/cli/plugin/openclaw.plugin.json`.

## Platform Requirements

**Development:**
- Local Python virtualenv plus npm are assumed by `README.md`, `backend/requirements.txt`, and `frontend/package.json`.
- Writable local filesystem storage is required for `backend/data/` because SQLite, Chroma, attachments, assistant screenshots, and RAG status files all persist there (`backend/config.py`, `backend/services/conversation_attachments.py`, `backend/services/assistant_images.py`, `backend/services/rag.py`).
- `agent-browser` must be available on `PATH` because `backend/main.py` calls `verify_agent_browser_cli()` from `backend/services/browser_runtime.py` during startup.
- Optional skill-specific system tools are assumed by the shipped skills: `ssh` in `backend/skills/remote-ops/SKILL.md`, `/usr/local/bin/docker` in `backend/skills/docker/SKILL.md`, `/usr/local/bin/kubectl` plus kubeconfig in `backend/skills/kubernetes/SKILL.md`.
- The MySQL analysis skill in `backend/skills/mysql-sql-analyzer/scripts/analyze_mysql_sql.py` expects a working `mysql+pymysql` SQLAlchemy driver plus env-provided credentials.

**Production:**
- The committed deployment target is a two-container Docker Compose setup in `docker-compose.yml`: `backend` binds port 8000 and `frontend`/Nginx binds port 80 on `agent-network`.
- Persistent backend state is mounted from `./backend/data` to `/app/data` in `docker-compose.yml`.
- The stack assumes outbound access to Anthropic, any configured OIDC issuer, the configured embedding endpoint, any configured MCP servers, and optional Volcengine/Skillhub/OpenClaw endpoints referenced from `backend/auth/service.py`, `backend/services/rag.py`, `backend/services/mcp_registry.py`, and `backend/cli/metadata.json`.

---

*Stack analysis: 2026-03-18*
