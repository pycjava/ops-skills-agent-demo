# 技术栈

**分析日期：** 2026-03-18

## 语言

**主语言：**
- Python 是后端主语言，服务入口、API 路由、Agent 运行时、服务层和 ORM 模型都位于 `backend/`，典型文件包括 `backend/main.py`、`backend/api/`、`backend/services/`、`backend/models/`。
- TypeScript 是前端主语言，负责单页应用、Pinia 状态层、路由层以及前端测试；另外 `backend/cli/plugin/index.ts` 中也包含一份打包到插件侧的 TypeScript 源码。

**次要语言与内容格式：**
- Vue 单文件组件位于 `frontend/src/App.vue`、`frontend/src/RootApp.vue` 和 `frontend/src/components/*.vue`。
- Bash 脚本用于安装和诊断，例如 `backend/cli/install.sh`、`backend/skills/docker/scripts/docker_readonly_diagnose.sh`、`backend/skills/kubernetes/scripts/k8s_readonly_diagnose.sh`。
- TOML 用于 Agent 清单和注册表，例如 `backend/agents/registry.toml` 与 `backend/agents/*/agent.toml`。
- Markdown 既是文档格式，也是 Prompt 与 Skill 的可执行内容载体，例如 `backend/prompts/*.md` 与 `backend/skills/*/SKILL.md`。

## 运行时

**后端运行时：**
- 容器镜像基于 `python:3.12-slim`，定义在 `backend/Dockerfile`。
- 本地开发说明写在 `README.md` 中，默认使用虚拟环境加 `pip install -r backend/requirements.txt`。
- Web 服务通过 `uvicorn` 运行，入口是 `backend/main.py`。

**前端运行时：**
- 开发与构建依赖 Node.js，构建镜像使用 `node:22.22-slim`，定义在 `frontend/Dockerfile`。
- 本地开发通过 `npm install` 与 `npm run dev` 启动，依赖清单位于 `frontend/package.json`。

**前端交付层：**
- 生产态静态文件由 `nginx:alpine` 承载，配置文件为 `frontend/nginx.conf`。
- `frontend/Dockerfile` 采用构建镜像 + Nginx 运行镜像的多阶段构建方式。

**包管理：**
- 后端依赖通过 `pip` + `backend/requirements.txt` 管理；当前仓库未发现 `pyproject.toml`、Poetry、Pipenv 或 Python 锁文件。
- `backend/Dockerfile` 额外安装了 Astral `uv`，但依赖安装与应用启动仍然走 `pip` 和 `uvicorn`。
- 前端依赖通过 `npm` 管理，并提交了 `frontend/package-lock.json`。

## 框架与核心库

**后端框架：**
- `FastAPI` 与 `Uvicorn` 负责 HTTP 和 WebSocket 服务，主要代码位于 `backend/main.py`、`backend/api/routers/`、`backend/api/ws/chat.py`。
- `DeepAgents` + `LangGraph` 负责多 Agent 运行时、子 Agent 组合与记忆存储，核心装配点在 `backend/agent_manager.py`。
- `SQLAlchemy` + `aiosqlite` 负责业务数据持久化，数据库接线在 `backend/db/session.py`，模型位于 `backend/models/*.py`。

**前端框架：**
- `Vue 3` 承担工作台 UI。
- `Pinia` 负责浏览器端状态汇聚，核心入口是 `frontend/src/stores/chat.ts`。
- `Vue Router` 负责登录页与主工作台的路由切换，入口位于 `frontend/src/router.ts`。

**测试框架：**
- 后端使用 `pytest` 与 `pytest-asyncio`，测试位于 `backend/tests/`。
- 前端使用 `Vitest`、`@vue/test-utils` 与 `jsdom`，测试位于 `frontend/src/**/*.test.ts`。

**构建与开发工具：**
- 前端开发工具链为 `Vite`、`vue-tsc`、`@vitejs/plugin-vue`，配置在 `frontend/vite.config.ts` 和 `frontend/tsconfig*.json`。
- 演示/部署编排通过根目录 `docker-compose.yml` 完成。
- Nginx 作为前端反向代理层，配置在 `frontend/nginx.conf`。

## 关键依赖

**核心依赖：**
- `deepagents>=0.4.7,<0.5`：多 Agent 运行时的核心，负责 skill/tool 注入与执行图构建，代码入口在 `backend/agent_manager.py`。
- `langchain-anthropic>=0.3.0`：通过 `ChatAnthropic` 提供主要 LLM 接口，使用点在 `backend/agent_manager.py` 和 `backend/services/inspection_task_llm.py`。
- `langchain-mcp-adapters>=0.1.8`：将 MCP Server 暴露为 Agent 可调用工具，使用点在 `backend/services/mcp_registry.py` 和 `backend/agent_manager.py`。
- `sqlalchemy[asyncio]>=2.0` 与 `aiosqlite>=0.20.0`：承担业务表与异步 SQLite 访问。
- `chromadb>=0.5.20`：RAG 向量索引后端，位于 `backend/services/rag.py`。
- `httpx>=0.28.0`：用于 OIDC、Embedding 请求等外部 HTTP 调用。
- `dompurify` 与 `marked`：用于前端消息 Markdown 渲染与清洗，使用点在 `frontend/src/components/MessageBubble.vue`。

**基础设施依赖：**
- `langgraph-checkpoint-sqlite>=2.0.11`：持久化 Agent checkpoint 与 `/memories/`。
- `python-dotenv>=1.0.0`：加载后端 `.env`，定义在 `backend/config.py`。
- `loguru`：统一日志设施，位于 `backend/utils/logger.py`。
- `volcengine-python-sdk==5.0.16`：支撑火山云 RDS 巡检相关 skill 脚本。

## 配置面

**环境配置：**
- 后端配置集中在 `backend/config.py`；认证相关扩展配置位于 `backend/auth/config.py`。
- 前端运行时配置由 `frontend/src/stores/chat.ts` 读取 `VITE_API_BASE_URL` 与 `VITE_WS_URL`。
- MCP 的实际配置源是仓库根目录 `mcp.json`，由 `backend/services/mcp_registry.py` 解析。
- Agent/Prompt/Skill 装配由 `backend/agents/registry.toml`、`backend/agents/*/agent.toml` 和 `backend/prompts/*.md` 控制。

**构建配置：**
- 前端构建配置位于 `frontend/vite.config.ts` 和 `frontend/tsconfig*.json`。
- 容器与部署配置位于 `backend/Dockerfile`、`frontend/Dockerfile`、`frontend/nginx.conf`、`docker-compose.yml`。
- CLI/插件打包配置位于 `backend/cli/metadata.json`、`backend/cli/version.json`、`backend/cli/plugin/openclaw.plugin.json`。

## 平台要求

**本地开发要求：**
- 需要 Python 虚拟环境与 npm，参见 `README.md`、`backend/requirements.txt`、`frontend/package.json`。
- 需要可写本地文件系统，因为 SQLite、Chroma、附件、截图和 RAG 状态文件都持久化到 `backend/data/`。
- `agent-browser` 需要在 `PATH` 中可用，因为 `backend/main.py` 会在启动时调用 `verify_agent_browser_cli()`。
- 若启用某些运维类 skill，还需要额外系统工具，例如 `ssh`、`docker`、`kubectl`。
- MySQL 分析 skill 依赖可用的 `mysql+pymysql` 驱动和环境变量注入的数据库凭据。

**部署要求：**
- 当前仓库默认的部署方式是 `docker-compose.yml` 定义的双容器结构：`backend` 监听 `8000`，`frontend`/Nginx 暴露 `80`。
- `./backend/data` 会挂载到容器内 `/app/data` 以保存持久化状态。
- 对外网络依赖包括 Anthropic、OIDC 提供方、Embedding 接口、MCP Server，以及可选的火山云/Skillhub/OpenClaw 端点。

---

*技术栈分析：2026-03-18*
