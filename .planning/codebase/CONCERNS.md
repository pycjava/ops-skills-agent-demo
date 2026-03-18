# Codebase Concerns

**Analysis Date:** 2026-03-18

## Tech Debt

**Ad-hoc SQLite schema migration during startup:**
- Issue: `backend/db/session.py` mutates the live schema with inline `ALTER TABLE` statements and data backfills inside `init_db()`, including compatibility columns and legacy title rewrites.
- Files: `backend/db/session.py`
- Impact: startup becomes the migration mechanism, schema changes are hard to review or roll back, and concurrent first boots can race on the same file-backed database.
- Fix approach: move schema evolution into explicit migrations and keep application startup limited to readiness and seed validation.

**Large, high-churn files without an enforced style gate:**
- Issue: core behavior is concentrated in a few large files, including `frontend/src/App.vue` (1930 lines), `frontend/src/components/MessageBubble.vue` (832 lines), `backend/agent.py` (646 lines), `backend/services/inspection_tasks.py` (672 lines), `backend/services/conversation_attachments.py` (406 lines), and `backend/services/cloud_credentials.py` (341 lines). The frontend has no detected ESLint, Prettier, or Biome config, and `frontend/package.json` exposes `dev`, `build`, `build:prod`, `preview`, and `test` only.
- Files: `frontend/src/App.vue`, `frontend/src/components/MessageBubble.vue`, `frontend/src/stores/chat.ts`, `frontend/src/stores/chat/socket.ts`, `backend/agent.py`, `backend/services/inspection_tasks.py`, `backend/services/conversation_attachments.py`, `backend/services/cloud_credentials.py`, `frontend/package.json`
- Impact: refactors are expensive, reviews are noisy, merge conflicts become more likely, and style drift is not caught automatically.
- Fix approach: split UI/runtime domains into smaller modules and add a lint/format gate in CI before the next round of feature work.

**Documentation and runtime topology drift:**
- Issue: `frontend/README.md` contains the stock Vite template instead of project-specific instructions. `README.md` describes five built-in agents, while runtime agent profiles currently exist under `backend/agents/` for `backend`, `browser-runtime`, `db-runtime`, `db-schema`, `frontend`, `general`, `ocr`, `ops-runtime`, `platform`, `router`, `security`, and `supervisor`.
- Files: `frontend/README.md`, `README.md`, `backend/agents/`
- Impact: onboarding and deployment instructions are not trustworthy, and real prerequisites such as browser runtime setup are easy to miss.
- Fix approach: replace the generated frontend README, distinguish user-facing agents from internal runtime agents, and add a docs validation checklist to releases.

## Known Bugs

**Backend container startup depends on `agent-browser`, but the image does not install it:**
- Symptoms: backend startup raises a `RuntimeError` instructing the operator to install `agent-browser`, even when browser automation is not being used.
- Files: `backend/main.py`, `backend/services/browser_runtime.py`, `backend/Dockerfile`, `docker-compose.yml`, `backend/tests/test_browser_runtime_service.py`
- Trigger: start the backend in a clean environment or via `docker compose up` without manually adding the `agent-browser` CLI.
- Workaround: manually install `agent-browser` and run its installer, or patch out the startup verification.

**Cloud credential status reports false negatives in environment-injected deployments:**
- Symptoms: cloud credential registry entries report `status: "missing"` unless credentials are present in `backend/.env`, even when `VOLC_CREDENTIAL_<REF>_AK` and `VOLC_CREDENTIAL_<REF>_SK` are supplied through process environment variables or container `env_file` injection.
- Files: `backend/services/cloud_credentials.py`, `docker-compose.yml`
- Trigger: run the backend with cloud credentials provided by runtime environment only.
- Workaround: duplicate secrets into `backend/.env`, which increases secret sprawl and does not solve the underlying detection bug.

**Conversation deletion leaves OCR artifact files behind:**
- Symptoms: OCR markdown files under `data/conversation_attachments/<conversation_id>/_ocr/` remain on disk after the conversation is deleted.
- Files: `backend/services/conversation_attachments.py`, `backend/api/routers/conversations.py`
- Trigger: upload an image, generate an OCR result, then delete the conversation.
- Workaround: remove the `_ocr` directory manually from `backend/data/conversation_attachments/`.

## Security Considerations

**MCP configuration secrets are committed and exposed through the API surface:**
- Risk: `mcp.json` is tracked in the repository and contains inline `env` secrets. `backend/api/routers/mcp.py` returns raw `config_text`, and `backend/services/mcp_registry.py` plus `backend/models/mcp_server.py` include `env` in the “public” payload returned to clients. `backend/tests/test_mcp_router.py` encodes this response shape as expected behavior.
- Files: `mcp.json`, `.gitignore`, `backend/api/routers/mcp.py`, `backend/services/mcp_registry.py`, `backend/models/mcp_server.py`, `backend/tests/test_mcp_router.py`
- Current mitigation: route-level permission checks on `mcp_servers:*`.
- Recommendations: rotate the exposed secret, stop storing secrets in tracked `mcp.json`, remove `env` and raw `config_text` from client responses, return only key names, and add regression tests for redaction.

**Authentication defaults fail open for the full API surface:**
- Risk: when `AUTH_ENABLED=false`, `require_permission(...)` returns `None` and all protected routes become accessible without authentication. `backend/tests/test_auth_rbac.py` explicitly verifies this behavior. `backend/auth/config.py` also falls back to `SESSION_SECRET="agentweave-session-secret"`, and local admin login reads a plaintext password from environment variables.
- Files: `backend/auth/config.py`, `backend/auth/dependencies.py`, `backend/api/routers/auth.py`, `backend/api/routers/conversations.py`, `backend/api/routers/mcp.py`, `backend/api/routers/task_notifications.py`, `backend/tests/test_auth_rbac.py`, `README.md`
- Current mitigation: configuration guidance in `README.md`.
- Recommendations: require an explicit development-only flag for auth bypass, refuse startup with the default session secret when auth is enabled, and replace plaintext local admin credentials with hashed credentials or an external identity provider only.

**No owner or tenant boundary exists for conversations, tasks, attachments, or notifications:**
- Risk: RBAC gates actions by permission, but there is no user or team ownership field on conversations, tasks, attachments, or task notifications. Query handlers return global datasets, and realtime notifications are broadcast to every connected websocket in the process.
- Files: `backend/models/conversation.py`, `backend/models/conversation_attachment.py`, `backend/models/inspection_task.py`, `backend/models/task_notification.py`, `backend/api/routers/conversations.py`, `backend/api/routers/task_notifications.py`, `backend/services/realtime_events.py`
- Current mitigation: role-based permission checks only.
- Recommendations: add owner or tenant columns to core tables, scope list/read/update operations to the current principal, and broadcast realtime events to user-specific channels instead of the global socket set.

## Performance Bottlenecks

**Cloud credential resolution scans and parses the whole memory tree per request:**
- Problem: `resolve_cloud_request_context()` loads the entire `/memories` tree, flattens it, reads each matching markdown document, parses candidate instance records, and re-reads credential status from `.env`.
- Files: `backend/services/cloud_credentials.py`, `backend/services/memory.py`
- Cause: no cache or precomputed index exists for project bindings, instance records, or credential status.
- Improvement path: cache parsed memory metadata, refresh it on write, and derive credential status from process environment once instead of re-reading a file on each request.

**Image attachments can inflate prompt size sharply:**
- Problem: image attachments are read from disk and embedded as base64 blocks in model input. The service allows up to 50 attachments per conversation and 1 MB per upload, with no resize, compression, or per-turn image budget before prompt assembly.
- Files: `backend/services/conversation_attachments.py`, `backend/agent.py`, `backend/services/multimodal_ocr.py`
- Cause: `build_image_attachment_blocks()` serializes raw file bytes directly into the message payload.
- Improvement path: cap images per turn, resize or compress server-side, and favor OCR or extracted summaries over raw base64 blocks.

**Frontend rendering and markdown processing stay in the hottest path:**
- Problem: `frontend/src/App.vue` drives most of the workspace state and layout transitions, while `frontend/src/components/MessageBubble.vue` owns markdown rendering, sanitization, artifact inference, and attachment actions for every message.
- Files: `frontend/src/App.vue`, `frontend/src/components/MessageBubble.vue`
- Cause: UI behavior is centralized in component-level logic instead of isolated presentation and utility layers.
- Improvement path: move markdown rendering into a shared utility/composable, split the workspace shell into route-level and panel-level components, and reduce the amount of state owned by `App.vue`.

## Fragile Areas

**Inspection scheduler is not concurrency-safe:**
- Files: `backend/services/inspection_scheduler.py`, `backend/services/inspection_tasks.py`
- Why fragile: `get_due_inspection_task_ids()` selects due rows first, and `execute_inspection_task()` claims work later. Two backend instances can select the same task before `next_run_at` is advanced.
- Safe modification: add a database claim step or lease token inside the same transaction that decides task ownership.
- Test coverage: current tests cover task creation and single-run flows, not scheduler races across two workers.

**Realtime notifications are process-local only:**
- Files: `backend/services/realtime_events.py`, `backend/services/inspection_tasks.py`, `backend/api/ws/chat.py`
- Why fragile: websocket connections live in an in-memory set inside one process. Task notifications created on one replica do not propagate to clients connected to a different replica.
- Safe modification: move websocket fan-out to shared pub/sub infrastructure and persist delivery state if missed notifications matter.
- Test coverage: route and service tests verify payload shape, not multi-process behavior.

**Browser runtime behavior is tightly coupled to startup and filesystem side effects:**
- Files: `backend/main.py`, `backend/services/browser_runtime.py`, `backend/services/assistant_images.py`, `backend/api/ws/chat.py`
- Why fragile: application startup, screenshot follow-up execution, and image asset persistence all assume the external `agent-browser` CLI and local workspace files behave as expected.
- Safe modification: isolate browser automation behind a feature flag and treat it as an optional subsystem with explicit health reporting.
- Test coverage: helper-level tests exist in `backend/tests/test_browser_runtime_service.py`, but there is no integration test for the containerized startup path.

## Scaling Limits

**One SQLite file stores both business data and agent runtime state:**
- Current capacity: a single `SQLITE_PATH` file is reused by SQLAlchemy, `AsyncSqliteSaver`, and `AsyncSqliteStore`.
- Limit: write contention and file locking increase as conversations, agent checkpoints, memory documents, and scheduled task runs grow, especially if multiple processes mount the same volume.
- Scaling path: split operational tables from LangGraph checkpoint or memory state and move them to server-grade backing services.

**The scheduler assumes one backend process owns timed execution:**
- Current capacity: one in-process `InspectionSchedulerRuntime` loop polling every 30 seconds.
- Limit: duplicate task execution appears when more than one backend instance is alive.
- Scaling path: move scheduling to a dedicated worker or use distributed locking and leased jobs.

**Notification delivery assumes single-process websocket fan-out:**
- Current capacity: one process-local `RealtimeEventManager`.
- Limit: no cross-instance propagation and no durable replay for clients that disconnect during delivery.
- Scaling path: introduce shared pub/sub plus persisted unread state keyed by user.

## Dependencies at Risk

**Backend Python dependency set without a lockfile (`deepagents`, `langchain-anthropic`, `langchain-mcp-adapters`, and most of `backend/requirements.txt`):**
- Risk: the backend installs from range-based requirements rather than a pinned lockfile, so fresh environments can drift away from the versions the tests were written against.
- Impact: streaming event shapes, MCP client behavior, and agent runtime semantics can change across installs.
- Migration plan: generate and commit a pinned lock or constraints file for the backend install path.

**`elasticsearch==7.10.0`:**
- Risk: the package is declared in `backend/requirements.txt` but is not imported by runtime code under `backend/`.
- Impact: larger images, unnecessary dependency maintenance, and extra attack surface for a package that does not appear to power a live feature.
- Migration plan: verify whether any upcoming feature needs Elasticsearch; remove it from `backend/requirements.txt` if not.

## Missing Critical Features

**Per-user or per-team data isolation:**
- Problem: authenticated users are role-gated but not scoped to their own conversations, tasks, notifications, MCP configuration, or attachments.
- Blocks: safe multi-user deployment, auditability, least-privilege data access, and any future hosted or shared-team deployment model.

## Test Coverage Gaps

**MCP secret redaction and config sanitization:**
- What's not tested: that `/api/mcp/config` and `/api/mcp/servers` redact raw `config_text`, `env` values, and any secret-bearing headers before returning data to the frontend.
- Files: `backend/api/routers/mcp.py`, `backend/services/mcp_registry.py`, `backend/tests/test_mcp_router.py`
- Risk: secret exposure is treated as normal API behavior and can regress silently.
- Priority: High

**Scheduler concurrency and cross-process delivery:**
- What's not tested: duplicate task execution under concurrent schedulers or notification delivery across multiple backend processes.
- Files: `backend/services/inspection_scheduler.py`, `backend/services/inspection_tasks.py`, `backend/services/realtime_events.py`
- Risk: duplicate task runs and missing notifications appear only after scale-out.
- Priority: High

**Filesystem cleanup for OCR artifacts:**
- What's not tested: deleting a conversation after OCR removes `_ocr` files and directories along with attachment files.
- Files: `backend/services/conversation_attachments.py`, `backend/api/routers/conversations.py`
- Risk: orphaned extracted text accumulates on disk and can outlive the conversation that produced it.
- Priority: Medium

**Credential status detection from runtime environment:**
- What's not tested: cloud credential status when secrets come from process environment variables instead of `backend/.env`.
- Files: `backend/services/cloud_credentials.py`, `docker-compose.yml`
- Risk: operators get misleading “missing credential” signals in containerized deployments.
- Priority: Medium

**Runtime packaging and documentation parity:**
- What's not tested: backend image startup with all required external runtime dependencies and alignment between repo documentation and the actual runtime topology.
- Files: `backend/Dockerfile`, `docker-compose.yml`, `backend/main.py`, `README.md`, `frontend/README.md`
- Risk: the default deployment path fails or confuses operators even when unit tests are green.
- Priority: Medium

---

*Concerns audit: 2026-03-18*
