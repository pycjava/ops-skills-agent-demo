# AgentWeave 认证与权限子系统设计

## 1. 背景与设计目标

认证与权限子系统负责为 AgentWeave 提供可选的登录认证和 RBAC 权限控制。它的目标不是构建复杂 IAM 平台，而是在不破坏本地开发体验的前提下，为 Web 工作台和 WebSocket 对话提供一套统一、明确、可扩展的安全边界。

当前设计目标包括：

- 支持可开关的认证模式
- 同时兼容 OIDC/SSO 和本地固定管理员账号登录
- 用角色和权限保护 REST 与 WebSocket
- 让前端能够感知当前登录状态和可用权限

## 2. 子系统边界

该子系统覆盖：

- 认证配置读取
- SessionMiddleware 会话承载
- OIDC 登录、回调和注销
- 本地管理员账号密码登录
- 角色、权限、用户的种子数据与同步
- REST 和 WebSocket 的权限校验
- 前端认证状态与登录页面

不属于本子系统的内容：

- 云凭证内容本身的安全管理
- 外部 IdP 的实现
- 细粒度业务审计系统

## 3. 模块职责划分

### 3.1 配置层

`auth/config.py` 负责从环境变量构建 `AuthSettings`，主要包括：

- `AUTH_ENABLED`
- OIDC 配置
- 角色映射与默认角色
- 本地管理员登录配置
- Session cookie 配置

当前认证系统是显式开关式设计：当 `AUTH_ENABLED=false` 时，应用会整体退化为“无认证模式”。

### 3.2 权限定义层

`auth/permissions.py` 负责定义：

- 角色说明
- 权限说明
- 角色与权限的映射关系

当前内置角色包括：

- `viewer`
- `operator`
- `admin`

### 3.3 服务层

`auth/service.py` 负责：

- 生成认证状态响应
- 组装 OIDC 授权 URL
- 获取 OIDC 配置、换取 token、请求 userinfo
- 将外部 claims 映射为本地角色
- 校验本地管理员账号密码
- 初始化权限和角色种子数据
- 同步 OIDC 用户或本地管理员用户到本地数据库

### 3.4 请求依赖层

`auth/dependencies.py` 负责：

- 从 Session 中解析当前用户
- 提供 `require_permission(...)` 保护 REST 路由
- 提供 `ensure_websocket_permission(...)` 保护 WebSocket

它的核心特点是：认证关闭时直接放行；认证启用后再进入用户解析和权限校验。

### 3.5 路由层

`api/routers/auth.py` 负责：

- `GET /api/auth/me`
- `GET /api/auth/login`
- `GET /api/auth/callback`
- `POST /api/auth/login/password`
- `GET /api/auth/logout`

### 3.6 数据模型层

`models/auth.py` 定义了：

- `User`
- `Role`
- `Permission`
- `user_roles` / `role_permissions` 关联表

它们共同组成当前本地 RBAC 模型。

### 3.7 前端状态与登录体验

- `stores/chat/auth.ts` 负责拉取认证状态、保存权限集、执行跳转登录和密码登录
- `views/LoginPage.vue` 负责展示本地登录和 SSO 登录入口
- 前端所有能力入口通过 `chatStore.hasPermission(...)` 做显示和交互控制

## 4. 关键流程

### 4.1 无认证模式

当 `AUTH_ENABLED=false` 时：

- `GET /api/auth/me` 返回未认证状态，但前端会把系统视为可用
- `require_permission(...)` 和 `ensure_websocket_permission(...)` 直接放行
- 前端 `hasPermission(...)` 默认返回 `true`

这使得本地开发和最小演示场景不必依赖外部认证系统。

### 4.2 OIDC 登录

OIDC 登录链路如下：

1. 前端访问 `/api/auth/login?next=...`
2. 后端拉取 OIDC discovery 文档
3. 生成随机 state，并将 state 与跳转路径写入 session
4. 重定向到外部 IdP 授权地址
5. 回调时校验 state、交换 token、拉取 userinfo
6. 将外部 claims 同步为本地用户与角色
7. 在 session 中写入本地用户 ID，并跳回原页面

### 4.3 本地管理员登录

当启用 `LOCAL_AUTH_ENABLED=true` 且配置了管理员用户名密码时：

- 前端登录页展示账号密码表单
- 后端使用常量时间比较校验用户名密码
- 成功后同步本地管理员用户，并赋予 `admin` 角色
- 将用户 ID 写入 session，返回认证状态与跳转目标

### 4.4 REST 权限保护

各 REST router 通过 `Depends(require_permission(...))` 进行保护：

- 认证关闭时，依赖直接放行
- 认证开启但未登录时，返回 401
- 已登录但缺少权限时，返回 403

### 4.5 WebSocket 权限保护

`/ws/chat` 在握手前调用 `ensure_websocket_permission(ws, "conversations:write")`：

- 未登录时关闭连接并返回 4401
- 权限不足时关闭连接并返回 4403

这保证了 WebSocket 不会绕过 REST 的安全边界。

## 5. 数据 / 接口映射

### 5.1 Session 关键键

- `user_id`
- `oidc_state`
- `post_auth_redirect`
- `oidc_id_token`

### 5.2 认证状态响应

`build_auth_response_payload(...)` 当前会返回：

- 是否启用认证
- 是否已认证
- 可用登录方式
- 当前用户信息
- 当前权限集合
- 系统可用权限全集

### 5.3 主要接口

- `GET /api/auth/me`
- `GET /api/auth/login`
- `GET /api/auth/callback`
- `POST /api/auth/login/password`
- `GET /api/auth/logout`

## 6. 异常与默认策略

- 认证关闭时，整体退化为无认证模式。
- OIDC 配置不完整时，OIDC 登录入口不可用。
- OIDC state 校验失败时，回调直接拒绝。
- token 响应缺少 `access_token` 时返回 502。
- Session 中用户不存在或已停用时，会清空 session 并视为未登录。
- 本地密码登录只用于固定管理员入口，不是通用用户体系。

## 7. 设计取舍

- 采用 Session + 服务端权限校验，简单直接，适合当前平台和 WebSocket 场景。
- 角色与权限在应用启动后按需种子化，降低了手工初始化成本，但权限模型变更仍依赖代码发布。
- 同时支持 OIDC 和本地管理员账号，提升了本地部署可用性，但也增加了两套登录入口的维护成本。
- 前端做权限感知用于界面控制，但真正的安全边界仍在后端。

## 8. 演进方向

- 增强敏感操作的审计能力和权限说明。
- 进一步统一各子系统对权限的命名和边界。
- 为未来更细粒度的角色模型或隔离模型预留扩展空间。
- 逐步收敛“能看、能改、能测试、能执行”这几类权限语义。
