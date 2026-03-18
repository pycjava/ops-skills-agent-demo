# Testing Patterns

**Analysis Date:** 2026-03-18

## Test Framework

**Runner:**
- Frontend: `vitest` `^2.1.8` from `frontend/package.json`, configured in `frontend/vite.config.ts`.
- Frontend config details in `frontend/vite.config.ts`: `environment: 'jsdom'`, `globals: true`, `fileParallelism: false`, `maxWorkers: 1`.
- Backend: `pytest>=8.3.0` and `pytest-asyncio>=0.24.0` from `backend/requirements.txt`.
- Backend config in `backend/pytest.ini`: `asyncio_mode = auto` and `testpaths = tests`.

**Assertion Library:**
- Frontend: Vitest `expect` with `@vue/test-utils` mount helpers.
- Backend: plain pytest assertions, `pytest.raises(...)`, and FastAPI `TestClient` response assertions.

**Run Commands:**
```bash
cd frontend && npm run test   # Run the Vitest suite documented in `README.md`
cd backend && pytest          # Run the pytest suite documented in `README.md`
# Watch mode: Not configured in package scripts
# Coverage: Not configured in package scripts or dependencies
```

## Test File Organization

**Location:**
- Frontend tests are co-located with source files under `frontend/src`. Twenty-four `*.test.ts` files are present.
- Backend tests live in a dedicated `backend/tests` package. Thirty-six `test_*.py` files are present, plus shared fixtures in `backend/tests/conftest.py`.
- Backend also tests build and packaging assets from the same suite. Examples: `backend/tests/test_backend_dockerfile.py`, `backend/tests/test_backend_requirements.py`.

**Naming:**
- Frontend uses `SameName.test.ts` next to the source module. Examples: `frontend/src/components/MessageBubble.vue` + `frontend/src/components/MessageBubble.test.ts`, `frontend/src/stores/chat/socket.ts` + `frontend/src/stores/chat/socket.test.ts`.
- Backend uses `test_<feature>.py`. Examples: `backend/tests/test_conversations_router.py`, `backend/tests/test_mcp_registry.py`, `backend/tests/test_task_notifications_service.py`.
- Large frontend containers can split tests by concern instead of keeping one file. Example: `frontend/src/App.test.ts` and `frontend/src/App.task-run-stream.test.ts`.

**Structure:**
```text
frontend/src/components/ConversationTitleEditor.vue
frontend/src/components/ConversationTitleEditor.test.ts
frontend/src/stores/chat/auth.ts
frontend/src/stores/chat/auth.test.ts
backend/tests/conftest.py
backend/tests/test_conversations_router.py
backend/tests/test_task_notifications_service.py
```

## Test Structure

**Suite Organization:**
```typescript
describe('createAuthDomain', () => {
  test('fetchAuthStatus stores the backend auth payload and sends cookies', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({ ... }) }))
    vi.stubGlobal('fetch', fetchMock)

    const domain = createAuthDomain({ ... })
    await domain.fetchAuthStatus()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/auth/me',
      expect.objectContaining({ credentials: 'include' }),
    )
  })
})
```

```python
@pytest.mark.asyncio
async def test_get_messages_returns_attachment_snapshot(session_factory, seeded_conversation):
    async with session_factory() as session:
        session.add(Message(...))
        await session.commit()

    client = create_test_client(session_factory)
    response = client.get(f"/api/conversations/{seeded_conversation.id}/messages")

    assert response.status_code == 200
    assert response.json()[0]["attachments_snapshot"]
```

**Patterns:**
- Frontend tests keep factories and mocks at the top of the file, then use `describe(...)` and `test(...)` blocks. Examples: `frontend/src/App.test.ts`, `frontend/src/stores/chat/auth.test.ts`, `frontend/src/stores/chat/socket.test.ts`.
- Backend mixes sync `def test_...` and async `@pytest.mark.asyncio` tests in the same file based on the unit under test. Examples: `backend/tests/test_conversations_router.py`, `backend/tests/test_auth_rbac.py`, `backend/tests/test_mcp_registry.py`.
- Frontend setup is usually local to each file via `beforeEach(...)` and resettable mocks. Example: `frontend/src/App.test.ts`.
- Backend shared setup uses fixtures from `backend/tests/conftest.py`, then file-local helpers like `create_test_client(...)` and `create_notification(...)`.
- Assertions focus on behavior rather than snapshots: emitted events, CSS classes, status codes, JSON payloads, DB rows, and side-effect calls.

## Mocking

**Framework:** Vitest mocks on the frontend; pytest `monkeypatch` and fake objects on the backend.

**Patterns:**
```typescript
vi.mock('./stores/chat', () => ({
  useChatStore: () => chatStoreMock,
}))

vi.stubGlobal('fetch', fetchMock)
vi.stubGlobal('WebSocket', FakeWebSocket)
```

```python
monkeypatch.setenv("AUTH_ENABLED", "true")
monkeypatch.setattr(auth_service, "fetch_userinfo", fake_fetch_userinfo)
monkeypatch.setitem(sys.modules, "agent", stub_agent)
```

**What to Mock:**
- Frontend mocks `fetch`, `WebSocket`, router dependencies, Pinia stores, and composables. Examples: `frontend/src/router.test.ts`, `frontend/src/stores/chat/auth.test.ts`, `frontend/src/stores/chat/socket.test.ts`, `frontend/src/App.test.ts`.
- Frontend container tests often `shallow: true` mount the parent component and assert on child props and emitted events instead of rendering the whole subtree. Example: `frontend/src/App.test.ts`.
- Backend mocks external integrations and process state with `monkeypatch`: OIDC calls in `backend/tests/test_auth_rbac.py`, LangChain/MCP behavior in `backend/tests/test_mcp_router.py`, filesystem roots in `backend/tests/test_assistant_images_service.py`, and agent runtime functions in `backend/tests/test_agent_error_handling.py`.
- Backend service tests also use small fake classes instead of heavy mocks when a protocol is simple. Examples: `FakeEmbeddingClient` and `FakeIndexBackend` in `backend/tests/test_rag_service.py`, `FakeRagService` in `backend/tests/test_rag_router.py`.

**What NOT to Mock:**
- Frontend pure utilities are tested directly without a mock wrapper. Examples: `frontend/src/utils/taskIntent.test.ts`, `frontend/src/utils/mysqlInspection.test.ts`.
- Frontend style regressions for memory components read the real `.vue` source and assert on CSS tokens or selectors instead of mocking styles. Examples: `frontend/src/components/MemoryPanelStyles.test.ts`, `frontend/src/components/MemoryTreeNode.test.ts`.
- Backend router tests usually use a real `FastAPI()` app with a real temporary SQLite database instead of mocking persistence. Examples: `backend/tests/test_conversations_router.py`, `backend/tests/test_task_notifications_router.py`, `backend/tests/test_auth_rbac.py`.

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(...)
    ...
    yield factory
    await engine.dispose()
```

```typescript
function createUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: 'user-1',
    subject: 'oidc-user-1',
    ...
    ...overrides,
  }
}
```

**Location:**
- Shared backend fixtures live in `backend/tests/conftest.py`. The core ones are `session_factory` and `seeded_conversation`.
- Backend files usually add local helpers beside the tests they support. Examples: `create_test_client(...)` in `backend/tests/test_conversations_router.py`, `create_notification(...)` in `backend/tests/test_task_notifications_router.py`.
- Frontend does not have a shared fixture library. Most test data builders stay local to each file. Examples: `createUser` in `frontend/src/stores/chat/auth.test.ts`, `createAttachment` in `frontend/src/stores/chat/socket.test.ts`, `createCloudResolution` in `frontend/src/App.test.ts`.

## Coverage

**Requirements:** None enforced.

- No `pytest-cov` dependency is listed in `backend/requirements.txt`.
- No Vitest coverage config or `coverage` script exists in `frontend/package.json` or `frontend/vite.config.ts`.
- The only explicit coverage annotation observed is `# pragma: no cover` in `backend/agents/loader.py` for a Python-version compatibility branch.

**View Coverage:**
```bash
Not configured
```

## Test Types

**Unit Tests:**
- Frontend pure utility and composable tests: `frontend/src/utils/taskIntent.test.ts`, `frontend/src/utils/mysqlInspection.test.ts`, `frontend/src/composables/useChatComposer.test.ts`.
- Backend pure helper or service tests: `backend/tests/test_browser_runtime_service.py`, `backend/tests/test_mcp_registry.py`, `backend/tests/test_conversation_state.py`, `backend/tests/test_agent_event_identity.py`.
- Build and packaging smoke tests: `backend/tests/test_backend_dockerfile.py`, `backend/tests/test_backend_requirements.py`, `backend/tests/test_agent_manager_module_syntax.py`.

**Integration Tests:**
- Frontend component-boundary tests mount components with real props and event flows in JSDOM. Examples: `frontend/src/components/TaskDrawer.test.ts`, `frontend/src/views/LoginPage.test.ts`, `frontend/src/App.test.ts`.
- Backend router tests create a real `FastAPI()` instance, include the router under test, and drive it through `TestClient`. Examples: `backend/tests/test_conversations_router.py`, `backend/tests/test_task_notifications_router.py`, `backend/tests/test_rag_router.py`, `backend/tests/test_mcp_router.py`.
- Backend service tests frequently use real temporary SQLite sessions to validate persistence, not just pure mocks. Examples: `backend/tests/test_inspection_tasks_service.py`, `backend/tests/test_task_notifications_service.py`, `backend/tests/test_conversation_messages.py`.

**E2E Tests:**
- Not used.
- No Playwright, Cypress, Selenium, or browser automation test config is detected in the repository.

## Common Patterns

**Async Testing:**
```typescript
await wrapper.get('form').trigger('submit.prevent')
await flushPromises()
```

```python
@pytest.mark.asyncio
async def test_password_login_creates_local_admin_user_record(session_factory, monkeypatch):
    ...
    response = client.post("/api/auth/login/password", json={...})
    assert response.status_code == 200
```

**Error Testing:**
```python
with pytest.raises(ValueError, match="mcpServers"):
    await service.save_config_text('{"mcpServers":[]}')
```

```typescript
expect(wrapper.get('[data-testid="save-title-btn"]').attributes('disabled')).toBeDefined()
expect(chatStoreMock.sendMessage).not.toHaveBeenCalled()
```

## Missing or Thin Areas

- Full frontend task-creation flows in `frontend/src/App.test.ts` still have three skipped tests: the direct task-creation path, the non-task fallback path, and the incomplete-schedule draft path.
- No true frontend/backend end-to-end suite exists for login, websocket chat, uploads, or task scheduling. Current tests stop at JSDOM component boundaries or FastAPI router boundaries.
- Several frontend modules have no dedicated test file: `frontend/src/components/SkillPanel.vue`, `frontend/src/composables/useAppChrome.ts`, `frontend/src/stores/chat/memory.ts`, `frontend/src/stores/chat/tasks.ts`, `frontend/src/stores/chat.ts`, and `frontend/src/main.ts`.
- Backend startup and infrastructure modules are only indirectly covered. No direct tests target `backend/main.py`, `backend/utils/logger.py`, or `backend/config.py`.
- Coverage reporting and thresholds are absent, so breadth can only be inferred from file presence and not from measured percentages.

---

*Testing analysis: 2026-03-18*
