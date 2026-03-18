# 测试模式

**分析日期：** 2026-03-18

## 测试框架

**执行器：**
- 前端使用 `vitest` `^2.1.8`，定义在 `frontend/package.json`，配置位于 `frontend/vite.config.ts`。
- 前端测试环境设置包括：`environment: 'jsdom'`、`globals: true`、`fileParallelism: false`、`maxWorkers: 1`。
- 后端使用 `pytest>=8.3.0` 与 `pytest-asyncio>=0.24.0`，依赖定义在 `backend/requirements.txt`。
- 后端配置位于 `backend/pytest.ini`，当前开启 `asyncio_mode = auto` 且 `testpaths = tests`。

**断言风格：**
- 前端主要依赖 Vitest 的 `expect`，配合 `@vue/test-utils` 的 mount 能力。
- 后端主要使用原生 pytest 断言、`pytest.raises(...)` 与 FastAPI `TestClient` 响应断言。

**运行命令：**
```bash
cd frontend && npm run test   # 运行 Vitest 测试集
cd backend && pytest          # 运行 pytest 测试集
# 未发现 watch 模式脚本
# 未发现覆盖率脚本或依赖
```

## 测试文件组织

**位置：**
- 前端测试与源码就近放置在 `frontend/src` 下，目前可见 24 个 `*.test.ts` 文件。
- 后端测试集中放在 `backend/tests/`，目前可见 36 个 `test_*.py` 文件，并通过 `backend/tests/conftest.py` 提供共享 fixture。
- 后端还会在同一测试集里验证构建和打包资产，例如 `backend/tests/test_backend_dockerfile.py`、`backend/tests/test_backend_requirements.py`。

**命名：**
- 前端采用 `SameName.test.ts`，与源文件同目录放置。
- 后端采用 `test_<feature>.py` 命名。
- 较大的前端容器组件会按关注点拆分多份测试，例如 `frontend/src/App.test.ts` 与 `frontend/src/App.task-run-stream.test.ts`。

**典型结构：**
```text
frontend/src/components/ConversationTitleEditor.vue
frontend/src/components/ConversationTitleEditor.test.ts
frontend/src/stores/chat/auth.ts
frontend/src/stores/chat/auth.test.ts
backend/tests/conftest.py
backend/tests/test_conversations_router.py
backend/tests/test_task_notifications_service.py
```

## 测试结构

**前端典型写法：**
```typescript
describe('createAuthDomain', () => {
  test('fetchAuthStatus 会保存后端认证结果并携带 cookie', async () => {
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

**后端典型写法：**
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

**共性模式：**
- 前端测试通常先在文件顶部准备 factory 和 mock，再用 `describe(...)` 与 `test(...)` 组织用例。
- 后端会在同一个文件中混用同步 `def test_...` 与 `@pytest.mark.asyncio` 异步测试，取决于被测对象。
- 前端的初始化与重置大多局部放在 `beforeEach(...)`。
- 后端共享初始化通过 `backend/tests/conftest.py` 提供，文件内部再补充专用 helper。
- 断言重点通常放在行为而不是 snapshot：例如事件流、状态码、JSON 结构、数据库行、副作用调用等。

## Mock 策略

**使用框架：**
- 前端：Vitest mock、`vi.stubGlobal(...)`、`vi.mock(...)`
- 后端：pytest `monkeypatch`、fake object、小型 stub 类

**常见模式：**
```typescript
vi.mock('./stores/chat', () => ({
  useChatStore: () => chatStoreMock,
}))

vi.stubGlobal('fetch', fetchMock)
vi.stubGlobal('WebSocket', FakeWebSocket)
```

```python
monkeypatch.setenv('AUTH_ENABLED', 'true')
monkeypatch.setattr(auth_service, 'fetch_userinfo', fake_fetch_userinfo)
monkeypatch.setitem(sys.modules, 'agent', stub_agent)
```

**哪些地方会被 mock：**
- 前端常 mock `fetch`、`WebSocket`、router 依赖、Pinia store 和 composable。
- 前端容器测试常用 `shallow: true`，重点验证对子组件传参和事件传递，而不是渲染整棵树。
- 后端会 mock 外部集成和进程状态，例如 OIDC、LangChain/MCP、文件系统根路径与 Agent runtime 函数。
- 后端服务测试在协议简单时更偏好自己写轻量 fake 类，而不是堆复杂 mock。

**哪些地方通常不 mock：**
- 前端纯工具函数会直接测试真实逻辑，例如 `frontend/src/utils/taskIntent.test.ts`、`frontend/src/utils/mysqlInspection.test.ts`。
- 前端某些样式回归测试会读取真实 `.vue` 源码并断言 CSS token 或 selector，而不是 mock 样式。
- 后端路由测试通常会使用真实的临时 SQLite 数据库和真实 `FastAPI()` 应用，而不是完全 mock 持久化层。

## Fixtures 与工厂函数

**测试数据方式：**
```python
@pytest.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / 'test.db'
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
    ...overrides,
  }
}
```

**放置位置：**
- 后端共享 fixture 在 `backend/tests/conftest.py`，最核心的是 `session_factory` 与 `seeded_conversation`。
- 后端测试文件通常会在本地继续定义 helper，例如 `create_test_client(...)`、`create_notification(...)`。
- 前端没有统一的 fixture 库，大多数 builder 都局部定义在各自测试文件中。

## 覆盖率

**当前状态：**
- 没有强制覆盖率门槛。
- `backend/requirements.txt` 未发现 `pytest-cov`。
- `frontend/package.json` 与 `frontend/vite.config.ts` 未发现覆盖率脚本或配置。
- 唯一显式的覆盖率标记是 `backend/agents/loader.py` 中的 `# pragma: no cover`。

**查看覆盖率：**
```bash
当前仓库未配置覆盖率输出
```

## 测试类型

**单元测试：**
- 前端纯工具与 composable，例如 `frontend/src/utils/taskIntent.test.ts`、`frontend/src/utils/mysqlInspection.test.ts`、`frontend/src/composables/useChatComposer.test.ts`。
- 后端纯 helper 或服务，例如 `backend/tests/test_browser_runtime_service.py`、`backend/tests/test_mcp_registry.py`、`backend/tests/test_conversation_state.py`、`backend/tests/test_agent_event_identity.py`。
- 构建/打包烟雾测试，例如 `backend/tests/test_backend_dockerfile.py`、`backend/tests/test_backend_requirements.py`、`backend/tests/test_agent_manager_module_syntax.py`。

**集成测试：**
- 前端组件边界测试会在 JSDOM 中挂载真实组件并走真实 props / 事件流。
- 后端路由测试通常创建真实 `FastAPI()` 实例，挂载目标 router，再通过 `TestClient` 驱动。
- 后端服务测试也经常用真实临时 SQLite session 去验证持久化，而不只是 mock。

**端到端测试：**
- 未发现 Playwright、Cypress、Selenium 或其它浏览器自动化 E2E 配置。
- 现阶段测试主要停在前端 JSDOM 边界和后端 API / service 边界。

## 常见模式

**异步测试：**
```typescript
await wrapper.get('form').trigger('submit.prevent')
await flushPromises()
```

```python
@pytest.mark.asyncio
async def test_password_login_creates_local_admin_user_record(session_factory, monkeypatch):
    ...
    response = client.post('/api/auth/login/password', json={...})
    assert response.status_code == 200
```

**错误路径测试：**
```python
with pytest.raises(ValueError, match='mcpServers'):
    await service.save_config_text('{"mcpServers":[]}')
```

```typescript
expect(wrapper.get('[data-testid="save-title-btn"]').attributes('disabled')).toBeDefined()
expect(chatStoreMock.sendMessage).not.toHaveBeenCalled()
```

## 薄弱或缺失区域

- `frontend/src/App.test.ts` 里仍有 3 个任务创建相关测试被跳过：直接创建任务路径、非任务消息回退路径、以及日程不完整时进入草稿路径。
- 没有真正跨前后端的 E2E 测试来覆盖登录、WebSocket 聊天、附件上传和任务调度。
- 一些前端模块没有专门测试文件，例如 `frontend/src/components/SkillPanel.vue`、`frontend/src/composables/useAppChrome.ts`、`frontend/src/stores/chat/memory.ts`、`frontend/src/stores/chat/tasks.ts`、`frontend/src/stores/chat.ts`、`frontend/src/main.ts`。
- 后端启动与基础设施模块主要靠间接覆盖，没有直接测试 `backend/main.py`、`backend/utils/logger.py`、`backend/config.py`。
- 因为缺乏覆盖率报告，当前只能通过文件存在与否大致推断覆盖面，无法得到量化百分比。

---

*测试模式分析：2026-03-18*
