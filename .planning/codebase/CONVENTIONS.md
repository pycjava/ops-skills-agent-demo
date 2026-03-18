# 编码约定

**分析日期：** 2026-03-18

## 命名模式

**文件命名：**
- 前端 Vue 组件、页面和较大的 UI 模块使用 `PascalCase.vue`，并常配套 `PascalCase.test.ts`，例如 `frontend/src/components/TaskDrawer.vue` 与 `frontend/src/components/TaskDrawer.test.ts`。
- 前端 composable 使用 `useX.ts` 模式，例如 `frontend/src/composables/useChatComposer.ts`、`frontend/src/composables/useAppChrome.ts`。
- 前端 store domain 与 helper 模块在 `frontend/src/stores/chat/` 下多使用小写或 lower camel case，例如 `frontend/src/stores/chat/auth.ts`、`frontend/src/stores/chat/helpers.ts`。
- 前端工具模块通常也是 lower camel case 文件名，例如 `frontend/src/utils/conversationTitle.ts`、`frontend/src/utils/mysqlInspection.ts`、`frontend/src/utils/taskIntent.ts`。
- 后端 Python 模块统一使用 `snake_case.py`；测试文件统一使用 `test_*.py`，例如 `backend/services/conversation_messages.py`、`backend/tests/test_conversations_router.py`。
- ORM 模型文件通常使用单数资源名，例如 `backend/models/conversation.py`、`backend/models/task_notification.py`、`backend/models/conversation_attachment.py`。

**函数命名：**
- TypeScript 函数与方法使用 `camelCase`，例如 `createAppRouter`、`resolveBackendPath`、`streamInspectionTaskRunConversation`。
- Vue 组件触发的事件名使用 kebab-case 字符串，例如 `save-draft`、`open-conversation`、`delete-task`。
- Python 函数包括异步服务函数统一使用 `snake_case`，例如 `create_conversation`、`update_conversation_title`、`save_config_text`。

**变量命名：**
- 布尔型 `ref` / `computed` 值通常以 `is`、`has`、`can` 开头，例如 `isAuthLoading`、`hasMessages`、`canWriteTasks`。
- 共享常量使用 `UPPER_SNAKE_CASE`，例如 `CHAT_ENTRY_AGENT_ID`、`TITLE_MAX_LENGTH`、`DEFAULT_SQLITE_PATH`。
- 测试中的轻量工厂函数常使用 `createX` 命名，例如 `createUser`、`createNotification`。

**类型命名：**
- TypeScript 的 interface、type alias、union 使用 `PascalCase`，例如 `AuthStatusResponse`、`InspectionTaskRunConversationStreamEvent`、`TaskDrawerTab`。
- SQLAlchemy 模型、dataclass 和服务记录对象也使用 `PascalCase`，例如 `Conversation`、`AuthSettings`、`McpServerRecord`。
- 当结构稳定时，项目偏好使用字面量联合类型而不是任意字符串，例如 `ArtifactKind`、`McpTransport`、`McpTestStatus`。

## 代码风格

**格式习惯：**
- 前端未发现独立的格式化或 lint 配置；仓库中没有 `eslint.config.*`、`.eslintrc*`、`.prettierrc*`、`biome.json`。
- 虽然没有显式配置，`frontend/src` 代码仍大体遵循 Prettier 风格：2 空格缩进、不写分号、多行数组/对象保留尾逗号、导入组之间留空行。
- Vue 单文件组件通常采用 `<script setup lang="ts">`、`<template>`、`<style scoped>` 的顺序。
- 后端也未发现 `ruff`、`flake8`、`mypy` 或 `pyproject.toml` 配置。
- Python 代码总体遵循手写但稳定的风格：4 空格缩进、标准库/第三方/本地导入分组、极少使用内联注释。

**静态检查：**
- 前端主要依赖 `frontend/tsconfig.app.json` 的 TypeScript 严格检查，而不是 ESLint。
- 新增前端代码应继续兼容现有 TS 编译选项，例如 `strict`、`noUnusedLocals`、`noUnusedParameters`、`noFallthroughCasesInSwitch`。
- 后端没有同等级别的自动 lint 门禁，因此新增 Python 代码应尽量贴合现有风格，不要引入孤立的格式化偏好。

## 导入组织

**顺序：**
1. 标准库或框架导入优先。
2. 第三方依赖其次。
3. 项目内模块最后，并与前两组留空行分隔。

**已观察到的模式：**
- 前端常把 `vue`、`pinia`、`vue-router` 等框架导入放在最前面。
- 前端类型导入会显式使用 `import type`。
- 后端普遍遵循 `stdlib -> third-party -> local` 的三段式导入。

**路径别名：**
- 未发现统一路径别名。
- 前端大量使用相对路径，例如 `../stores/chat`、`./helpers`、`../../utils/conversationTitle`。
- 后端在 `backend/` 目录内部以顶层包方式导入，例如 `from services.mcp_registry import McpRegistryService`、`from models import Conversation`。
- 后端测试通过 `backend/tests/conftest.py` 把 `backend/` 加入 `sys.path`，从而让测试导入方式与运行时保持一致。

## 类型约定

**前端 TypeScript：**
- 优先复用 `frontend/src/stores/chat/types.ts` 中的明确接口和联合类型，而不是在局部堆匿名对象类型。
- 组件 props 与 emits 常通过 `defineProps<...>()` 和 `defineEmits<...>()` 内联声明。
- domain factory 的入参通常是由 `Ref`、`ComputedRef` 组成的依赖对象，而不是一长串位置参数。
- API 返回值一般在 `res.json()` 后只做一次类型断言，然后再用严格类型继续处理。

**后端 Python：**
- 优先使用现代 Python 类型语法，例如 `str | None`、`list[str]`、`dict[str, Any]`。
- 较新的后端服务文件在需要前向引用时会使用 `from __future__ import annotations`。
- ORM 模型使用 SQLAlchemy 2 风格的 `Mapped[...]` 和 `mapped_column(...)`。
- 对结构稳定的 DTO 类对象，项目更偏好 dataclass 而不是松散的字典。
- 在 HTTP 边界，当请求结构稳定时会定义小型 Pydantic 模型。

## 错误处理

**常见模式：**
- 前端 domain 模块通常更偏好“设置错误状态 + 返回 `false`/`null`”而不是一律抛异常。
- `frontend/src/stores/chat/helpers.ts` 中的 `readErrorMessage(...)` 用于统一响应错误解析，应优先复用。
- 可恢复的前端错误通常会写入某个 `error` ref，并配合 `console.warn(...)` 记录。
- 只有调用方确实需要分支处理时，前端函数才会抛异常，例如登录和会话重命名。
- 后端服务层普遍用异常类型来表达失败语义：
  - `ValueError` 表示输入无效或配置非法
  - `LookupError` 表示持久化数据不存在
  - `HTTPException` 主要用于已经和 HTTP 强绑定的服务模块
- API 路由会在边界处把服务异常转换为 HTTP 状态码。
- 长流程执行中，后端倾向于把异常降级为结构化错误事件而不是直接让进程崩溃，例如 `backend/agent.py`、`backend/api/ws/chat.py`、`backend/services/inspection_scheduler.py`。

## 日志约定

**日志框架：**
- 后端统一使用 `backend/utils/logger.py` 导出的 `loguru` `logger`。

**使用方式：**
- 模块中优先 `from utils.logger import logger`，而不是自己新建 logger。
- 生命周期事件使用 `logger.info(...)`。
- 可恢复问题使用 `logger.warning(...)`。
- 更底层的跟踪信息使用 `logger.debug(...)`。
- 需要保留堆栈时使用 `logger.exception(...)`。
- 前端没有统一日志抽象，非致命错误基本使用 `console.warn(...)`。

## 注释风格

**什么时候写注释：**
- 后端基础设施模块会保留简短模块 docstring 或函数 docstring，例如 `backend/config.py`、`backend/utils/logger.py`、`backend/db/session.py`。
- 内联注释比较少，只在兼容性补丁、启动逻辑或明显不直观的地方出现。
- 前端源码几乎不靠注释解释业务，更多依赖清晰的 helper 名称和类型定义。

**JSDoc / TSDoc：**
- 在 `frontend/src` 中几乎未见系统性使用。
- 若新增模块不算特别晦涩，一般不建议突然引入大块注释文档。

## 配置访问方式

- 前端环境变量读取集中在 `frontend/src/stores/chat.ts`，通过 `import.meta.env.VITE_WS_URL` 与 `import.meta.env.VITE_API_BASE_URL` 完成。
- 下游前端 domain 模块通过构造参数接收 `backendUrl` 和 `wsUrl`，而不是各自直接读取环境变量。
- 后端环境变量访问集中在 `backend/config.py` 与 `backend/auth/config.py`。
- 认证配置通过 `backend/auth/config.py` 中的 `@lru_cache` 缓存；相关测试会主动清缓存以保证行为稳定。

## 函数设计

**规模控制：**
- 小型归一化/校验函数通常写在导出的工厂或处理函数之前，例如 `sanitizeNextPath`、`normalizeAttachmentSnapshots`、`normalize_conversation_title`。
- 更大的编排模块是允许的，但通常也会把通用 helper 先抽出来，例如 `frontend/src/stores/chat.ts`、`frontend/src/App.vue`、`backend/services/inspection_tasks.py`。

**参数设计：**
- 前端 factory 倾向接收单个依赖对象，而不是长位置参数列表。
- 后端在需要传入可选协作者或上下文时，常通过 `*` 后的 keyword-only 参数增加可读性。

**返回值设计：**
- 前端处理函数经常返回 `boolean`、`null` 或类型化 payload，让调用方决定 UI 是否继续推进。
- 后端服务倾向返回领域对象或可序列化摘要，而不是把原始查询结果直接甩给调用方。

## 模块设计

**导出方式：**
- 前端以命名导出为主；`frontend/src/stores/chat.ts` 同时承担统一入口与共享类型转发。
- 后端只在少数大边界使用 barrel，例如 `backend/models/__init__.py`。
- 新增后端模块最好继续保持现有顶层导入风格，不要突然切成包内相对导入。

**barrel 文件：**
- 当前仓库只在真正的公共边界使用 barrel：
  - `frontend/src/stores/chat.ts`
  - `backend/models/__init__.py`
- 不建议为每个目录额外引入新的 barrel 文件，和现有风格不一致。

---

*编码约定分析：2026-03-18*
