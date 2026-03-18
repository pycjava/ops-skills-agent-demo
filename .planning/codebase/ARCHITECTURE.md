# Architecture

**Analysis Date:** 2026-03-18

## Pattern Overview

**Overall:** Split frontend/backend monorepo with an agent-runtime-centered backend and a single-workspace frontend.

**Key Characteristics:**
- `backend/main.py` creates one `FastAPI` application that serves REST routers and the `/ws/chat` websocket from the same process.
- Agent execution is not embedded in routers. `backend/agent.py`, `backend/agent_manager.py`, `backend/agent_profiles.py`, `backend/agents/`, `backend/prompts/`, and `backend/skills/` form a separate runtime assembly layer.
- The frontend keeps one Pinia facade in `frontend/src/stores/chat.ts` and pushes transport, auth, tasks, memory, MCP, and websocket behavior into small domain modules under `frontend/src/stores/chat/`.
- SQLite is used twice: SQLAlchemy models in `backend/models/` persist product data, while LangGraph saver/store in `backend/agent_manager.py` persist agent runtime state and `/memories/`.
- Long-running behavior is event-driven. Interactive chat streams over `backend/api/ws/chat.py`; scheduled task execution reuses the same agent runner from `backend/services/inspection_tasks.py`; cross-session task notifications fan out through `backend/services/realtime_events.py`.

## Major Subsystems

**Conversation And Streaming Chat:**
- `backend/api/ws/chat.py`
- `backend/services/conversation_state.py`
- `backend/services/conversation_messages.py`
- `backend/services/conversation_attachments.py`
- `frontend/src/stores/chat/socket.ts`
- `frontend/src/stores/chat/conversations.ts`
- `frontend/src/components/MessageBubble.vue`

This subsystem owns live chat session binding, user/assistant/system message persistence, attachment snapshots, streamed tool events, and replay of stored conversation history.

**Agent Runtime And Capability Assembly:**
- `backend/agent.py`
- `backend/agent_manager.py`
- `backend/agent_profiles.py`
- `backend/agents/registry.toml`
- `backend/agents/*/agent.toml`
- `backend/prompts/*.md`
- `backend/skill_catalog.py`
- `backend/services/mcp_registry.py`

This subsystem turns manifest files, prompt fragments, skill directories, MCP server configuration, and LangGraph persistence into executable DeepAgents runtimes.

**Task Scheduling And Notifications:**
- `backend/services/inspection_tasks.py`
- `backend/services/inspection_scheduler.py`
- `backend/services/inspection_task_llm.py`
- `backend/services/task_notifications.py`
- `backend/api/routers/inspection_tasks.py`
- `backend/api/routers/task_notifications.py`
- `frontend/src/stores/chat/tasks.ts`
- `frontend/src/components/TaskDrawer.vue`
- `frontend/src/components/TaskNotificationCenter.vue`

This subsystem derives inspection tasks from conversations, schedules and executes them, creates run-specific conversations, and pushes completion notifications back to connected workspaces.

**Memory, RAG, And Cloud Context:**
- `backend/services/memory.py`
- `backend/services/rag.py`
- `backend/services/cloud_credentials.py`
- `backend/services/cloud_instance_candidates.py`
- `backend/api/routers/memories.py`
- `backend/api/routers/rag.py`
- `backend/api/routers/cloud_credentials.py`
- `frontend/src/stores/chat/memory.ts`
- `frontend/src/components/MemoryPanel.vue`

This subsystem manages `/memories/` documents, indexes attachments and memory docs into RAG, and resolves cloud credential references from long-term memory rather than raw secrets in chat.

**Authentication And Authorization:**
- `backend/auth/config.py`
- `backend/auth/service.py`
- `backend/auth/dependencies.py`
- `backend/auth/permissions.py`
- `backend/api/routers/auth.py`
- `frontend/src/router.ts`
- `frontend/src/stores/chat/auth.ts`
- `frontend/src/views/LoginPage.vue`

This subsystem owns session cookies, optional OIDC and local admin login, RBAC seed data, REST guards, websocket guards, and frontend route gating.

## Layers

**Frontend Presentation Layer:**
- Purpose: Render the workspace, login page, drawers, panels, and message UI.
- Location: `frontend/src/App.vue`, `frontend/src/views/`, `frontend/src/components/`
- Contains: Routed pages, visual shell, message rendering, task drawer, notification center, MCP and memory panels.
- Depends on: `frontend/src/stores/chat.ts`, `frontend/src/composables/useAppChrome.ts`, `frontend/src/composables/useChatComposer.ts`
- Used by: Browser clients bootstrapped by `frontend/src/main.ts`

**Frontend State And Transport Layer:**
- Purpose: Centralize all browser-side state and backend I/O.
- Location: `frontend/src/stores/chat.ts`, `frontend/src/stores/chat/*.ts`
- Contains: Domain modules for websocket chat, conversations, auth, tasks, attachments, notifications, MCP, and memory.
- Depends on: Browser `fetch`, `WebSocket`, backend endpoints such as `/api/*` and `/ws/chat`
- Used by: `frontend/src/App.vue`, `frontend/src/views/LoginPage.vue`, and panel components

**API And Transport Layer:**
- Purpose: Expose HTTP and websocket interfaces and convert transport errors into API-level responses.
- Location: `backend/api/routers/*.py`, `backend/api/ws/chat.py`
- Contains: Pydantic request models, route handlers, SSE stream producers, websocket session loop, permission dependencies.
- Depends on: `backend/services/*`, `backend/auth/dependencies.py`, `backend/db/session.py`
- Used by: The Vue frontend, programmatic clients, and background browser sessions

**Domain Service Layer:**
- Purpose: Hold business logic outside transport code.
- Location: `backend/services/`
- Contains: Conversation, attachment, task, memory, RAG, MCP, OCR preprocessing, browser runtime, notification, and cloud-context services.
- Depends on: `backend/models/*`, `backend/db/session.py`, `backend/agent.py`, filesystem paths under `backend/data/`, and selected external clients configured elsewhere
- Used by: REST routers, websocket handlers, scheduler runtime, and the agent runtime

**Agent Runtime Layer:**
- Purpose: Construct and execute agent runtimes from manifests, prompts, skills, MCP tools, and shared stores.
- Location: `backend/agent.py`, `backend/agent_manager.py`, `backend/agent_profiles.py`, `backend/agents/`, `backend/prompts/`, `backend/skills/`
- Contains: Agent registry loading, runtime caching, subagent graph construction, context injection, OCR preprocessing policy, tool/result normalization.
- Depends on: `backend/services/mcp_registry.py`, `backend/services/memory.py`, `backend/services/rag.py`, `backend/services/message_preprocess.py`, `backend/skill_catalog.py`
- Used by: `backend/api/ws/chat.py`, `backend/api/routers/agent.py`, `backend/services/inspection_tasks.py`

**Persistence Layer:**
- Purpose: Persist structured product state and runtime artifacts.
- Location: `backend/db/`, `backend/models/`, `backend/data/`
- Contains: SQLAlchemy session setup, ORM models, SQLite database, conversation attachments, RAG index data, logs, and generated assistant image assets.
- Depends on: `backend/config.py`
- Used by: Every backend service that reads or writes conversations, tasks, auth state, MCP metadata, or reports

## Data Flow

**Interactive Chat Flow:**

1. `frontend/src/main.ts` mounts the app, and `frontend/src/composables/useAppChrome.ts` initializes auth, agents, conversations, notifications, MCP data, and the websocket connection.
2. `frontend/src/stores/chat/socket.ts` opens `/ws/chat`, sends an `init` payload, and later sends `message` payloads with optional `attachment_ids`.
3. `backend/api/ws/chat.py` resolves or creates a `Conversation`, persists the user message through `backend/services/conversation_messages.py`, applies default-title logic, and starts `agent.run_agent_turn`.
4. `backend/agent.py` optionally runs OCR preprocessing, builds RAG context from `backend/services/rag.py`, falls back to long-term memory and attachment context, and streams DeepAgents events from the runtime built by `backend/agent_manager.py`.
5. `backend/api/ws/chat.py` converts runtime events into websocket payloads, persists tool and assistant messages, saves OCR outputs or assistant screenshots when needed, and sends `done` or `error` events.
6. `frontend/src/stores/chat/socket.ts` turns those events into `ChatMessage` records consumed by `frontend/src/App.vue` and `frontend/src/components/MessageBubble.vue`.

**Scheduled Inspection Flow:**

1. `frontend/src/App.vue` and `frontend/src/stores/chat/tasks.ts` call `/api/inspection-tasks/draft`, `/api/inspection-tasks/from-conversation-message/stream`, or `/api/inspection-tasks/{task_id}/trigger`.
2. `backend/api/routers/inspection_tasks.py` delegates to `backend/services/inspection_tasks.py` and, when task creation needs LLM help, `backend/services/inspection_task_llm.py`.
3. `backend/services/inspection_tasks.py` creates an `InspectionTaskRun`, creates a dedicated task `Conversation`, stores the task prompt as a user message, and reuses `backend/agent.py` to execute the target agent.
4. As agent events arrive, `backend/services/inspection_tasks.py` persists tool and assistant output into the run conversation and updates `InspectionTask` / `InspectionTaskRun` status fields.
5. After completion or failure, `backend/services/task_notifications.py` creates a `TaskNotification`, and `backend/services/realtime_events.py` broadcasts it to connected websocket clients.
6. The frontend updates `inspectionTaskRuns`, notification badges, and task drawers through `frontend/src/stores/chat/tasks.ts`, `frontend/src/stores/chat/notifications.ts`, and `frontend/src/stores/chat/socket.ts`.

**Memory And Retrieval Flow:**

1. Memory documents are stored under the virtual `/memories/` namespace by `backend/services/memory.py`, which wraps the LangGraph store exposed through `backend/agent_manager.py`.
2. Attachment uploads are persisted by `backend/services/conversation_attachments.py` into `backend/data/conversation_attachments/<conversation_id>/` and mirrored into the RAG index via `backend/services/rag.py`.
3. Memory writes in `backend/services/memory.py` also trigger RAG synchronization, so both manual memory content and attachment content become searchable.
4. During a chat turn, `backend/agent.py` calls `build_rag_context(...)`; if retrieval does not return context, it falls back to `/memories/` tree scanning and attachment summaries.
5. The same memory surface is exposed to operators via `backend/api/routers/memories.py` and browsed in `frontend/src/components/MemoryPanel.vue`.

**Authentication Flow:**

1. `frontend/src/router.ts` calls `chatStore.fetchAuthStatus()` before each route and redirects unauthenticated users to `/login` when `auth_enabled` is true.
2. `backend/api/routers/auth.py` returns auth status, starts OIDC redirects, handles password login, and clears sessions on logout.
3. `backend/auth/dependencies.py` enforces the same permission strings on REST routes and on the `/ws/chat` websocket.
4. `backend/main.py` installs `SessionMiddleware`, so permission state is available to both `Request` and `WebSocket` handlers.

**State Management:**
- Browser state is centralized in `frontend/src/stores/chat.ts`, which composes domain-specific modules instead of distributing network calls across components.
- Product data lives in SQLAlchemy models under `backend/models/`, persisted through `backend/db/session.py` to `backend/data/app.db`.
- Agent runtime state and `/memories/` live in the LangGraph SQLite saver/store initialized in `backend/agent_manager.py`.
- Per-turn streaming state is ephemeral and lives inside `backend/api/ws/chat.py` via `AgentEventState`, delta buffering, abort tracking, and pending attachment context.

## Key Abstractions

**Agent Profile Registry:**
- Purpose: Declare which prompts, skills, handoffs, and execution mode belong to an agent.
- Examples: `backend/agent_profiles.py`, `backend/agents/registry.toml`, `backend/agents/router/agent.toml`, `backend/agents/supervisor/agent.toml`
- Pattern: File-backed manifests loaded once and normalized into `AgentProfile` objects before runtime creation

**Conversation Event Log:**
- Purpose: Provide the canonical history for chat, tool events, attachments, OCR outputs, assistant screenshots, and task-run replay.
- Examples: `backend/models/conversation.py`, `backend/models/message.py`, `backend/services/conversation_messages.py`, `backend/api/ws/chat.py`
- Pattern: Every meaningful runtime event is saved as a `Message` row and then replayed by REST or SSE consumers

**Task Automation Triplet:**
- Purpose: Represent recurring work, one execution of that work, and the operator-facing notification for that execution.
- Examples: `backend/models/inspection_task.py`, `backend/models/inspection_task_run.py`, `backend/models/task_notification.py`, `backend/services/inspection_tasks.py`
- Pattern: `InspectionTask` stores configuration, `InspectionTaskRun` stores execution state, and `TaskNotification` stores the broadcast summary

**Memory And Retrieval Boundary:**
- Purpose: Separate human-curated or agent-written memory from SQL domain tables while still making it searchable.
- Examples: `backend/services/memory.py`, `backend/services/rag.py`, `backend/api/routers/memories.py`
- Pattern: `/memories/` is backed by LangGraph store paths; RAG indexes those paths and conversation attachments as secondary read models

**MCP Registry:**
- Purpose: Map external MCP servers to eligible agents and turn `mcp.json` into runtime tool connections.
- Examples: `backend/services/mcp_registry.py`, `backend/api/routers/mcp.py`, `mcp.json`
- Pattern: File-backed JSON registry with in-memory test state; `backend/models/mcp_server.py` exists, but the active runtime path uses `mcp.json`

**Frontend Chat Store:**
- Purpose: Give the UI one stable facade even though behavior is split across several backend subsystems.
- Examples: `frontend/src/stores/chat.ts`, `frontend/src/stores/chat/socket.ts`, `frontend/src/stores/chat/tasks.ts`, `frontend/src/stores/chat/memory.ts`
- Pattern: One Pinia store composes multiple domain factories and exposes a flat API to `frontend/src/App.vue`

## Entry Points

**Backend HTTP/WebSocket App:**
- Location: `backend/main.py`
- Triggers: `python main.py`, container startup from `docker-compose.yml`, or any ASGI runner importing `main:app`
- Responsibilities: Build the FastAPI app, install session/CORS middleware, initialize DB and agent runtime, start the scheduler, and include all routers

**Interactive Chat Socket:**
- Location: `backend/api/ws/chat.py`
- Triggers: Browser websocket connection from `frontend/src/stores/chat/socket.ts`
- Responsibilities: Bind session to a conversation, persist inbound/outbound messages, stream agent events, support abort, and broadcast notifications

**Programmatic Chat API:**
- Location: `backend/api/routers/agent.py`
- Triggers: HTTP `POST /api/agent/chat`
- Responsibilities: Provide a synchronous, full-turn API for external callers while reusing the same agent runtime and message persistence

**Inspection Scheduler:**
- Location: `backend/services/inspection_scheduler.py`
- Triggers: Startup hook in `backend/main.py`
- Responsibilities: Poll for due task IDs and invoke `backend/services/inspection_tasks.py` on a background loop

**Frontend Bootstrap:**
- Location: `frontend/src/main.ts`
- Triggers: Vite dev server or built frontend loading in the browser
- Responsibilities: Create Pinia, create the Vue Router, and mount `frontend/src/RootApp.vue`

**Frontend Route Gate:**
- Location: `frontend/src/router.ts`
- Triggers: Every route navigation
- Responsibilities: Load auth status, redirect between `/login` and the workspace, and keep login flow on the frontend side thin

## Error Handling

**Strategy:** Transport layers validate early, domain services raise typed Python exceptions or `HTTPException`, and the websocket path converts runtime failures into persisted error messages plus terminal events.

**Patterns:**
- REST routers translate `ValueError` into `400` and `LookupError` into `404`, as seen in `backend/api/routers/conversations.py`, `backend/api/routers/mcp.py`, and `backend/api/routers/inspection_tasks.py`.
- `backend/api/ws/chat.py` keeps an `AgentEventState`, buffers partial deltas, and on abort writes a partial assistant message before sending a final `done` event.
- `backend/services/agent_errors.py` and `backend/services/agent_event_state.py` normalize runtime errors and event snapshots before they are persisted or sent to the client.
- Secondary indexing failures do not fail the primary request path. `backend/services/conversation_attachments.py` and `backend/services/memory.py` log warnings when RAG sync fails after the main write succeeds.
- Security-sensitive chat input is rejected before runtime execution in `backend/api/ws/chat.py` and `backend/api/routers/agent.py` when `backend/utils/credential_safety.py` detects raw cloud credentials.

## Cross-Cutting Concerns

**Logging:** `backend/utils/logger.py` configures the global Loguru logger, and backend modules log through `logger` rather than creating per-module logging stacks.

**Validation:** Transport models in `backend/api/routers/*.py` handle request-shape validation, while service-level normalizers such as `_normalize_cron_expr` in `backend/services/inspection_tasks.py`, `_normalize_memory_path` in `backend/services/memory.py`, and `validate_attachment_upload` in `backend/services/conversation_attachments.py` enforce domain rules.

**Authentication:** `backend/main.py` installs `SessionMiddleware`; `backend/auth/dependencies.py` applies RBAC to both REST and websocket flows; `frontend/src/stores/chat/auth.ts` and `frontend/src/router.ts` mirror that state into route guards and permission-based UI toggles.

---

*Architecture analysis: 2026-03-18*
