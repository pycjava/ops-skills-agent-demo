# Codebase Structure

**Analysis Date:** 2026-03-18

## Directory Layout

```text
[project-root]/
├── backend/                 # FastAPI app, agent runtime, services, data, tests, and bundled skills
│   ├── api/                 # REST routers and websocket transport
│   ├── agents/              # Runtime agent manifests loaded by `backend/agent_profiles.py`
│   ├── auth/                # Auth config, RBAC, and session helpers
│   ├── cli/                 # Skill store CLI and OpenClaw plugin assets
│   ├── db/                  # SQLAlchemy base and session setup
│   ├── models/              # ORM entities for conversations, tasks, auth, MCP, and notifications
│   ├── prompts/             # Prompt fragments referenced by agent manifests
│   ├── services/            # Business logic and orchestration
│   ├── skills/              # Runtime skill packages with `SKILL.md`, scripts, references, and assets
│   ├── tests/               # Backend test suite
│   ├── data/                # SQLite DB, attachments, and RAG data
│   ├── logs/                # Runtime log files
│   └── main.py              # FastAPI startup entry point
├── frontend/                # Vue 3 workspace
│   ├── src/
│   │   ├── components/      # Workspace panels and reusable UI blocks
│   │   ├── composables/     # UI orchestration hooks
│   │   ├── constants/       # Shared frontend constants
│   │   ├── stores/          # Pinia store facade plus chat domains
│   │   ├── utils/           # Frontend pure helpers
│   │   ├── views/           # Routed pages such as `/login`
│   │   ├── App.vue          # Main workspace shell
│   │   ├── RootApp.vue      # Router outlet
│   │   ├── main.ts          # Vue bootstrap
│   │   └── router.ts        # Auth-aware router factory
│   ├── dist/                # Built frontend output
│   └── node_modules/        # Installed frontend dependencies
├── docs/                    # System and skill design documents plus screenshots
├── agents/                  # Repository guidance/spec assets for other agent workflows
├── .agents/                 # Local Codex/Cursor skill definitions used outside the product runtime
├── .planning/               # Generated planning artifacts, including codebase maps
├── docker-compose.yml       # Demo/deployment composition
├── mcp.json                 # File-backed MCP server registry
└── README.md                # Product overview and setup
```

## Directory Purposes

**backend/:**
- Purpose: Main server code and backend-owned runtime assets.
- Contains: `backend/main.py`, `backend/api/`, `backend/services/`, `backend/models/`, `backend/agents/`, `backend/prompts/`, `backend/skills/`, `backend/tests/`, and runtime data folders.
- Key files: `backend/main.py`, `backend/config.py`, `backend/agent.py`, `backend/agent_manager.py`

**backend/api/:**
- Purpose: Transport boundary for HTTP, websocket, and SSE interfaces.
- Contains: REST routers in `backend/api/routers/` and live chat transport in `backend/api/ws/`.
- Key files: `backend/api/ws/chat.py`, `backend/api/routers/conversations.py`, `backend/api/routers/inspection_tasks.py`, `backend/api/routers/agent.py`

**backend/services/:**
- Purpose: Reusable business logic and orchestration code.
- Contains: Conversation, attachment, task, memory, RAG, MCP, browser-runtime, cloud-credential, and notification services.
- Key files: `backend/services/inspection_tasks.py`, `backend/services/rag.py`, `backend/services/mcp_registry.py`, `backend/services/conversation_attachments.py`, `backend/services/cloud_credentials.py`

**backend/agents/:**
- Purpose: Runtime agent manifests and registry metadata.
- Contains: `backend/agents/registry.toml`, `backend/agents/schema.py`, `backend/agents/loader.py`, and one `agent.toml` per agent directory.
- Key files: `backend/agents/registry.toml`, `backend/agents/router/agent.toml`, `backend/agents/supervisor/agent.toml`, `backend/agents/browser-runtime/agent.toml`

**backend/prompts/:**
- Purpose: Prompt fragments referenced by agent manifests.
- Contains: Shared base prompt plus role-specific prompt markdown files.
- Key files: `backend/prompts/base.md`, `backend/prompts/router.md`, `backend/prompts/supervisor.md`, `backend/prompts/ocr.md`

**backend/skills/:**
- Purpose: Bundled runtime skills resolved by `backend/skill_catalog.py`.
- Contains: One directory per skill with `SKILL.md` and optional `scripts/`, `references/`, or `assets/`.
- Key files: `backend/skills/using-superpowers/SKILL.md`, `backend/skills/mysql-sql-analyzer/SKILL.md`, `backend/skills/volcengine-rds-health-analyzer/scripts/get_instance_info.py`, `backend/skills/agent-browser/SKILL.md`

**backend/models/ and backend/db/:**
- Purpose: Persisted schema and database wiring.
- Contains: ORM models, declarative base, async engine, compatibility bootstrap, and session factory.
- Key files: `backend/db/session.py`, `backend/models/conversation.py`, `backend/models/message.py`, `backend/models/inspection_task.py`, `backend/models/auth.py`

**backend/tests/:**
- Purpose: Backend verification for routers, services, runtime assembly, and skill packaging.
- Contains: Flat pytest modules plus `backend/tests/conftest.py`.
- Key files: `backend/tests/conftest.py`, `backend/tests/test_conversations_router.py`, `backend/tests/test_inspection_tasks_service.py`, `backend/tests/test_agent_manager_prompts.py`

**frontend/src/components/:**
- Purpose: Reusable UI blocks for the workspace shell.
- Contains: Conversation list, message bubble, task drawer, notification center, MCP panel, memory panel, and attachment bar components.
- Key files: `frontend/src/components/ConversationList.vue`, `frontend/src/components/MessageBubble.vue`, `frontend/src/components/TaskDrawer.vue`, `frontend/src/components/TaskNotificationCenter.vue`

**frontend/src/composables/:**
- Purpose: UI orchestration helpers kept out of the big page component.
- Contains: Workspace initialization/theme/inspector logic and composer behavior.
- Key files: `frontend/src/composables/useAppChrome.ts`, `frontend/src/composables/useChatComposer.ts`

**frontend/src/stores/ and frontend/src/stores/chat/:**
- Purpose: Browser-side state and backend integration layer.
- Contains: `frontend/src/stores/chat.ts` as the public Pinia facade plus domain modules for `socket`, `conversations`, `tasks`, `auth`, `memory`, `mcp`, `attachments`, and `notifications`.
- Key files: `frontend/src/stores/chat.ts`, `frontend/src/stores/chat/socket.ts`, `frontend/src/stores/chat/tasks.ts`, `frontend/src/stores/chat/auth.ts`

**frontend/src/views/ and frontend/src/utils/:**
- Purpose: Page-level routes and pure helper logic.
- Contains: The login page plus utility functions for greetings, task intent detection, MySQL inspection hints, and title normalization.
- Key files: `frontend/src/views/LoginPage.vue`, `frontend/src/utils/mysqlInspection.ts`, `frontend/src/utils/taskIntent.ts`, `frontend/src/utils/conversationTitle.ts`

**docs/:**
- Purpose: Human-facing design documentation and screenshots.
- Contains: `docs/system-desigin/` for system design docs, `docs/skill/` for skill design docs, and `docs/assets/` for referenced images.
- Key files: `docs/README.md`, `docs/system-desigin/project-overall-design.md`, `docs/system-desigin/backend-design.md`, `docs/skill/skills-overview.md`

**agents/ and .agents/:**
- Purpose: Repository-side workflow guidance, not product runtime code.
- Contains: `agents/spec/` markdown guidance for external agent workflows and `.agents/skills/design-md/` skill assets for DESIGN.md generation.
- Key files: `agents/spec/backend/index.md`, `agents/spec/frontend/index.md`, `.agents/skills/design-md/SKILL.md`

## Key File Locations

**Entry Points:**
- `backend/main.py`: FastAPI startup, middleware, router registration, DB/runtime initialization, scheduler startup
- `backend/api/ws/chat.py`: Live chat websocket loop
- `backend/api/routers/agent.py`: Synchronous agent API for non-browser callers
- `frontend/src/main.ts`: Vue bootstrap
- `frontend/src/router.ts`: Auth-aware route factory
- `docker-compose.yml`: Two-container demo/deployment startup path

**Configuration:**
- `backend/config.py`: Backend env loading, SQLite path, RAG config, logging config, CORS config
- `backend/auth/config.py`: Auth feature flags and session cookie settings
- `backend/agents/registry.toml`: Public/default agent registry and alias map
- `mcp.json`: File-backed MCP server registry edited through the UI
- `frontend/vite.config.ts`: Frontend dev/build config
- `frontend/tsconfig.json`: Frontend TypeScript project config

**Core Logic:**
- `backend/agent.py`: Context building, OCR preprocessing, event streaming, and top-level agent execution
- `backend/agent_manager.py`: DeepAgents runtime assembly, subagent graph creation, MCP tool loading, and LangGraph store/checkpointer wiring
- `backend/services/inspection_tasks.py`: Task drafting, creation, scheduling, execution, and notification handoff
- `backend/services/rag.py`: Retrieval indexing, querying, and context formatting
- `backend/services/mcp_registry.py`: Parse/save/test MCP server config and filter by agent
- `frontend/src/stores/chat.ts`: Main browser store facade
- `frontend/src/stores/chat/socket.ts`: Websocket event mapping and outbound chat messages
- `frontend/src/App.vue`: Workspace composition and operator workflow glue

**Testing:**
- `backend/tests/conftest.py`: Shared backend fixtures
- `backend/tests/test_auth_rbac.py`: Auth and permission coverage
- `backend/tests/test_conversation_attachments_router.py`: Attachment API coverage
- `backend/tests/test_inspection_tasks_router.py`: Task API coverage
- `frontend/src/App.test.ts`: Workspace-level frontend coverage
- `frontend/src/router.test.ts`: Route guard coverage
- `frontend/src/stores/chat/socket.test.ts`: Websocket domain coverage
- `frontend/src/components/TaskDrawer.test.ts`: Task UI coverage

## Naming Conventions

**Files:**
- Backend Python modules use snake_case and are grouped by layer, for example `backend/services/conversation_state.py` and `backend/api/routers/task_notifications.py`.
- Vue components use PascalCase `.vue` filenames, usually with colocated tests such as `frontend/src/components/ConversationList.vue` and `frontend/src/components/ConversationList.test.ts`.
- Frontend composables use the `use*.ts` pattern, for example `frontend/src/composables/useAppChrome.ts`.
- Frontend chat domain modules use lower-case nouns under `frontend/src/stores/chat/`, for example `frontend/src/stores/chat/socket.ts` and `frontend/src/stores/chat/memory.ts`.
- Agent and skill IDs are kebab-case directory names, for example `backend/agents/db-runtime/agent.toml` and `backend/skills/volcengine-rds-health-analyzer/SKILL.md`.

**Directories:**
- Top-level product code directories stay lower-case: `backend/`, `frontend/`, and `docs/`.
- Agent, skill, and prompt folders mirror runtime IDs or role names, so new folders should follow the existing kebab-case or lower-case naming used in `backend/agents/` and `backend/skills/`.
- Documentation categories preserve existing path names exactly, including the typo in `docs/system-desigin/`.

## Where to Add New Code

**New Backend REST Feature:**
- Primary code: `backend/api/routers/<feature>.py`
- Service logic: `backend/services/<feature>.py`
- Persistence: `backend/models/<model>.py` if the feature introduces stored state
- Tests: `backend/tests/test_<feature>_router.py` and `backend/tests/test_<feature>_service.py`

**New WebSocket Chat Behavior:**
- Transport changes: `backend/api/ws/chat.py`
- Reusable logic: `backend/services/<feature>.py`
- Message persistence helpers: extend `backend/services/conversation_messages.py` or `backend/services/conversation_attachments.py` instead of burying new logic in the websocket loop
- Frontend consumer: `frontend/src/stores/chat/socket.ts`

**New Agent:**
- Manifest: `backend/agents/<agent-id>/agent.toml`
- Registry exposure: `backend/agents/registry.toml`
- Prompt text: `backend/prompts/<agent-id>.md`
- Frontend label/alias sync if needed: `frontend/src/stores/chat/helpers.ts`

**New Skill:**
- Implementation: `backend/skills/<skill-id>/SKILL.md`
- Scripts: `backend/skills/<skill-id>/scripts/`
- References or assets: `backend/skills/<skill-id>/references/` or `backend/skills/<skill-id>/assets/`
- Agent binding: update the relevant `backend/agents/<agent-id>/agent.toml`

**New Frontend Workspace Module:**
- Shared state and network logic: `frontend/src/stores/chat/<domain>.ts`
- UI component: `frontend/src/components/<Component>.vue`
- New routed page: `frontend/src/views/<Page>.vue` plus a route entry in `frontend/src/router.ts`
- Tests: colocate `*.test.ts` beside the component, composable, or store file

**Utilities:**
- Shared backend helpers: `backend/utils/<name>.py`
- Shared frontend helpers: `frontend/src/utils/<name>.ts`

**Design And Planning Docs:**
- System design docs: `docs/system-desigin/<topic>.md`
- Skill design docs: `docs/skill/<skill>-design.md`
- Codebase map outputs: `.planning/codebase/<DOC>.md`

## Special Directories

**backend/data/:**
- Purpose: SQLite database, conversation attachments, and RAG files
- Generated: Yes, except for `backend/data/.gitkeep`
- Committed: Partially; `backend/data/.gitkeep` is tracked, runtime files such as `backend/data/app.db` are local artifacts

**backend/logs/:**
- Purpose: Backend log output such as `backend/logs/app.log`
- Generated: Yes
- Committed: No

**backend/metric_data/:**
- Purpose: JSON metric snapshots consumed by the `backend/skills/volcengine-rds-health-analyzer/` skill
- Generated: Yes
- Committed: No

**frontend/dist/:**
- Purpose: Built frontend output
- Generated: Yes
- Committed: No

**frontend/node_modules/:**
- Purpose: Installed frontend dependencies
- Generated: Yes
- Committed: No

**.planning/codebase/:**
- Purpose: Generated repository maps for planning/execution workflows
- Generated: Yes
- Committed: Not currently tracked in git

---

*Structure analysis: 2026-03-18*
