# Coding Conventions

**Analysis Date:** 2026-03-18

## Naming Patterns

**Files:**
- Frontend Vue components, views, and large UI modules use `PascalCase.vue` with matching `PascalCase.test.ts` files. Examples: `frontend/src/components/TaskDrawer.vue`, `frontend/src/components/TaskDrawer.test.ts`, `frontend/src/views/LoginPage.vue`, `frontend/src/views/LoginPage.test.ts`.
- Frontend composables use the `useX.ts` pattern. Examples: `frontend/src/composables/useChatComposer.ts`, `frontend/src/composables/useAppChrome.ts`.
- Frontend store domains and helpers use lower-case or lower camel case module names inside `frontend/src/stores/chat/`. Examples: `frontend/src/stores/chat/auth.ts`, `frontend/src/stores/chat/attachments.ts`, `frontend/src/stores/chat/helpers.ts`.
- Frontend utility modules also use lower camel case file names. Examples: `frontend/src/utils/conversationTitle.ts`, `frontend/src/utils/mysqlInspection.ts`, `frontend/src/utils/taskIntent.ts`.
- Backend Python modules use `snake_case.py`, and tests use `test_*.py`. Examples: `backend/services/conversation_messages.py`, `backend/services/mcp_registry.py`, `backend/tests/test_conversations_router.py`.
- Backend ORM model files are singular resource names in `backend/models/`. Examples: `backend/models/conversation.py`, `backend/models/task_notification.py`, `backend/models/conversation_attachment.py`.

**Functions:**
- TypeScript functions use `camelCase`. Examples: `createAppRouter` in `frontend/src/router.ts`, `resolveBackendPath` in `frontend/src/stores/chat/helpers.ts`, `streamInspectionTaskRunConversation` in `frontend/src/stores/chat/conversations.ts`.
- Vue emitted event names use kebab-case string literals. Examples in `frontend/src/components/TaskDrawer.vue`: `'save-draft'`, `'open-conversation'`, `'delete-task'`.
- Python functions use `snake_case`, including async services. Examples: `create_conversation` in `backend/services/conversation_state.py`, `update_conversation_title` in `backend/services/conversation_messages.py`, `save_config_text` in `backend/services/mcp_registry.py`.

**Variables:**
- Boolean refs and computed values usually start with `is`, `has`, or `can`. Examples: `isAuthLoading`, `hasMessages`, `canWriteTasks` in `frontend/src/stores/chat.ts` and `frontend/src/App.vue`.
- Shared constants use `UPPER_SNAKE_CASE`. Examples: `CHAT_ENTRY_AGENT_ID` in `frontend/src/stores/chat/helpers.ts`, `TITLE_MAX_LENGTH` in `backend/services/conversation_messages.py`, `DEFAULT_SQLITE_PATH` in `backend/config.py`.
- Short-lived factory helpers in tests use `createX` naming. Examples: `createUser` in `frontend/src/stores/chat/auth.test.ts`, `createNotification` in `backend/tests/test_task_notifications_router.py`.

**Types:**
- TypeScript interfaces, type aliases, and unions use `PascalCase`. Examples: `AuthStatusResponse`, `InspectionTaskRunConversationStreamEvent`, `TaskDrawerTab` in `frontend/src/stores/chat/types.ts` and `frontend/src/components/TaskDrawer.vue`.
- SQLAlchemy models, dataclasses, and service records use `PascalCase`. Examples: `Conversation` in `backend/models/conversation.py`, `AuthSettings` in `backend/auth/config.py`, `McpServerRecord` in `backend/services/mcp_registry.py`.
- Literal unions are preferred over raw strings where the shape is stable. Examples: `ArtifactKind` in `frontend/src/stores/chat/types.ts`, `McpTransport` and `McpTestStatus` in `backend/services/mcp_registry.py`.

## Code Style

**Formatting:**
- No dedicated frontend formatter or linter config is detected. There is no `eslint.config.*`, `.eslintrc*`, `.prettierrc*`, or `biome.json` in the repo root or `frontend/`.
- Frontend code in `frontend/src` follows a consistent Prettier-like style anyway: 2-space indentation, no semicolons, trailing commas in multiline arrays and objects, and blank lines between import groups. Examples: `frontend/src/router.ts`, `frontend/src/stores/chat.ts`, `frontend/src/views/LoginPage.vue`.
- Vue single-file components follow the section order `<script setup lang="ts">`, `<template>`, `<style scoped>`. Examples: `frontend/src/components/ConversationTitleEditor.vue`, `frontend/src/components/TaskDrawer.vue`, `frontend/src/views/LoginPage.vue`.
- No Python formatter or lint config is detected in `backend/`. There is no `pyproject.toml`, `ruff.toml`, `mypy.ini`, `setup.cfg`, or `.flake8`.
- Backend Python follows standard handwritten style: 4-space indentation, blank lines between stdlib, third-party, and local imports, and minimal inline comments. Examples: `backend/tests/conftest.py`, `backend/services/mcp_registry.py`, `backend/db/session.py`.

**Linting:**
- Frontend static quality gates come from `frontend/tsconfig.app.json`, not from ESLint.
- New frontend code should stay compatible with the existing TypeScript compiler rules in `frontend/tsconfig.app.json`: `strict`, `noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly`, `noFallthroughCasesInSwitch`, and `noUncheckedSideEffectImports`.
- No equivalent automated lint gate is configured for backend Python. Match the existing style instead of introducing a one-off formatter profile.

## Import Organization

**Order:**
1. Standard library or framework imports first.
2. Third-party packages next.
3. Local project imports last, separated by a blank line.

**Observed examples:**
- Frontend framework-first imports: `frontend/src/main.ts`, `frontend/src/router.ts`, `frontend/src/composables/useChatComposer.ts`.
- Frontend type-only imports are explicit with `import type`. Examples: `frontend/src/router.ts`, `frontend/src/stores/chat/auth.ts`, `frontend/src/stores/chat/types.ts`.
- Backend stdlib -> third-party -> local grouping: `backend/tests/conftest.py`, `backend/services/mcp_registry.py`, `backend/auth/config.py`.

**Path Aliases:**
- Not detected.
- Frontend uses relative paths only, such as `../stores/chat`, `./helpers`, and `../../utils/conversationTitle`.
- Backend code imports project modules as top-level packages from within `backend/`, such as `from services.mcp_registry import McpRegistryService` and `from models import Conversation`.
- Backend tests rely on `backend/tests/conftest.py` inserting `backend/` into `sys.path` so test imports resolve the same way as runtime imports.

## Typing

**Frontend TypeScript:**
- Prefer explicit interfaces and tagged unions from `frontend/src/stores/chat/types.ts` instead of anonymous object types.
- Type component props and emits inline with `defineProps<...>()` and `defineEmits<...>()`. Examples: `frontend/src/components/ConversationTitleEditor.vue`, `frontend/src/components/TaskDrawer.vue`, `frontend/src/components/MemoryPanel.vue`.
- Domain factories take typed dependency objects built from `Ref` and `ComputedRef`. Examples: `frontend/src/stores/chat/auth.ts`, `frontend/src/stores/chat/attachments.ts`, `frontend/src/stores/chat/conversations.ts`, `frontend/src/composables/useChatComposer.ts`.
- API payloads are usually cast once after `res.json()` and then handled with strict types. Example: `const payload = (await res.json()) as AuthStatusResponse` in `frontend/src/stores/chat/auth.ts`.

**Backend Python:**
- Prefer modern Python typing syntax such as `str | None`, `list[str]`, and `dict[str, Any]`. This appears across `backend/auth/config.py`, `backend/services/mcp_registry.py`, and `backend/services/conversation_messages.py`.
- Newer backend service modules use `from __future__ import annotations` when type references would otherwise be forward-declared. Examples: `backend/services/conversation_messages.py`, `backend/services/mcp_registry.py`, `backend/services/rag.py`.
- ORM models use SQLAlchemy 2 typed mappings with `Mapped[...]` and `mapped_column(...)`. Example: `backend/models/conversation.py`.
- Stable DTO-like objects use dataclasses instead of loose dicts. Examples: `AuthSettings` in `backend/auth/config.py`, `McpServerRecord` and `McpTestState` in `backend/services/mcp_registry.py`.
- Request bodies at the HTTP edge use small Pydantic models where the shape is stable. Example: `CreateConversationRequest` in `backend/api/routers/conversations.py`.

## Error Handling

**Patterns:**
- Frontend domain modules prefer user-facing error refs plus a boolean or nullable return value over throwing for every failure.
- `frontend/src/stores/chat/helpers.ts` centralizes response parsing in `readErrorMessage(...)`. Reuse it instead of duplicating JSON and text fallback logic.
- Frontend modules that can recover locally set an error ref and log a warning. Examples:
  - `frontend/src/stores/chat/attachments.ts` sets `attachmentError` and returns `false`.
  - `frontend/src/stores/chat/notifications.ts` sets `taskNotificationError` and returns `null` or `false`.
  - `frontend/src/stores/chat/conversations.ts` uses `console.warn(...)` for non-fatal history loading failures.
- Frontend functions throw only when the caller needs to branch on failure, such as `loginWithPassword(...)` in `frontend/src/stores/chat/auth.ts` and `updateConversationTitle(...)` in `frontend/src/stores/chat/conversations.ts`.
- Backend services separate validation and lookup failures with exception type:
  - `ValueError` for invalid user input or invalid config in `backend/services/conversation_messages.py`, `backend/services/mcp_registry.py`, and `backend/services/inspection_tasks.py`.
  - `LookupError` for missing persisted state in `backend/services/conversation_messages.py`, `backend/services/task_notifications.py`, and `backend/services/inspection_tasks.py`.
  - `HTTPException` only inside service modules that are already HTTP-bound, such as `backend/services/memory.py`, `backend/services/conversation_attachments.py`, and `backend/services/cloud_credentials.py`.
- API routers convert service exceptions to HTTP status codes near the boundary. Examples: `backend/api/routers/conversations.py`, `backend/api/routers/mcp.py`, `backend/api/routers/inspection_tasks.py`.
- Long-running backend flows log and degrade unexpected failures into structured error events instead of crashing the process. Examples: `backend/agent.py`, `backend/api/ws/chat.py`, `backend/services/inspection_scheduler.py`.

## Logging

**Framework:** `loguru` via the shared `logger` exported from `backend/utils/logger.py`.

**Patterns:**
- Import `logger` from `backend/utils/logger.py` instead of creating a per-module logger. Examples: `backend/main.py`, `backend/db/session.py`, `backend/api/routers/conversations.py`, `backend/services/mcp_registry.py`.
- Use `logger.info(...)` for lifecycle events, `logger.warning(...)` for recoverable issues, `logger.debug(...)` for lower-level persistence traces, and `logger.exception(...)` when stack context matters.
- Frontend does not define a logging abstraction. Non-fatal client failures use `console.warn(...)`. Examples: `frontend/src/stores/chat.ts`, `frontend/src/stores/chat/attachments.ts`, `frontend/src/stores/chat/conversations.ts`, `frontend/src/App.vue`.

## Comments

**When to Comment:**
- Backend infrastructure modules use short module docstrings or function docstrings for setup and compatibility code. Examples: `backend/config.py`, `backend/utils/logger.py`, `backend/db/session.py`.
- Inline comments are sparse and only appear where the code is doing compatibility or setup work that is not obvious from the statements alone. Examples: SQLite bootstrap comments in `backend/db/session.py`, logger setup notes in `backend/utils/logger.py`.
- Frontend source in `frontend/src` is almost entirely comment-free. Favor clear helper names and typed interfaces over inline commentary.

**JSDoc/TSDoc:**
- Not detected in `frontend/src`.
- Do not add large doc blocks unless a module is unusually opaque; that would be out of pattern for the current codebase.

## Configuration Access

- Frontend runtime env access is centralized in `frontend/src/stores/chat.ts` through `import.meta.env.VITE_WS_URL` and `import.meta.env.VITE_API_BASE_URL`.
- Downstream frontend domains receive `backendUrl` and `wsUrl` as constructor dependencies instead of reading env vars directly. Examples: `frontend/src/stores/chat/auth.ts`, `frontend/src/stores/chat/attachments.ts`, `frontend/src/stores/chat/conversations.ts`.
- Backend environment access is centralized in `backend/config.py` and `backend/auth/config.py`.
- Auth settings are cached with `@lru_cache` in `backend/auth/config.py`; tests that mutate auth env vars clear that cache explicitly in `backend/tests/test_auth_rbac.py`.

## Function Design

**Size:**
- Small normalization and validation helpers are defined above the exported factory or handler. Examples: `sanitizeNextPath` in `frontend/src/router.ts`, `normalizeAttachmentSnapshots` in `frontend/src/stores/chat/helpers.ts`, `normalize_conversation_title` in `backend/services/conversation_messages.py`.
- Larger orchestration modules are acceptable when they compose multiple domains or streaming states, but they still extract helpers first. Examples: `frontend/src/stores/chat.ts`, `frontend/src/App.vue`, `backend/services/inspection_tasks.py`.

**Parameters:**
- Frontend factories take a single dependency object instead of long positional parameter lists. Examples: `createAuthDomain`, `createAttachmentDomain`, `createConversationDomain`, `useChatComposer`.
- Backend service APIs use keyword-only arguments after `*` when optional collaborators or contextual inputs are passed in. Examples: `save_message(...)` in `backend/services/conversation_messages.py`, `McpRegistryService.__init__(...)` in `backend/services/mcp_registry.py`.

**Return Values:**
- Frontend handlers often return `boolean`, `null`, or a typed payload so the caller can decide whether to continue the UI flow. Examples: `uploadConversationAttachment(...)`, `markTaskNotificationRead(...)`, `loginWithPassword(...)`.
- Backend services return domain objects or serializable summaries rather than leaving callers with raw query results. Examples: `Conversation.to_dict()` in `backend/models/conversation.py`, `McpServerRecord.to_public_dict()` in `backend/services/mcp_registry.py`.

## Module Design

**Exports:**
- Frontend modules prefer named exports. `frontend/src/stores/chat.ts` is the main public store entry point and also re-exports shared types via `export * from './chat/types'`.
- Backend uses selective barrel exports for major boundaries only. `backend/models/__init__.py` collects ORM models, and `backend/utils/logger.py` exports a single shared `logger`.
- New backend modules should remain importable with the existing top-level style, such as `from services...` and `from models...`, rather than switching to package-relative imports.

**Barrel Files:**
- Use existing barrels where they already define the public surface:
  - `frontend/src/stores/chat.ts`
  - `backend/models/__init__.py`
- Do not introduce broad new barrel files for every folder. The current repo uses them sparingly and only at major boundaries.

---

*Convention analysis: 2026-03-18*
