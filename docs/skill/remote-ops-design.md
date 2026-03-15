# Remote-Ops SSH Skill 设计文档

## 1. Skill 定位

`remote-ops` 让 Agent 具备通过 SSH 在远程服务器执行运维排查命令的能力。它的本质不是新增一套远程执行 API，而是把“如何安全使用 SSH 做运维”固化为可复用流程。

## 2. 设计目标

- 用最少额外基础设施获得远程诊断能力。
- 优先执行只读运维动作，降低风险。
- 把提权边界从 Agent 逻辑下沉到操作系统的 sudo 白名单。

## 3. 连接模型

### 3.1 基本连接方式

Skill 约定使用项目内置私钥，通过如下模式连接：

```text
ssh -i ./skills/remote-ops/keys/agent_ops_key -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p <PORT> agent-ops@<HOST> "<COMMAND>"
```

### 3.2 端口策略

连接端口采用显式降级策略：

1. 优先尝试 `65300`
2. 失败后回退到 `22`

这样做是为了兼容部署环境中“非标准 SSH 端口优先”的场景。

### 3.3 身份模型

- 用户名固定为 `agent-ops`
- 登录用户是非 root
- 需要提权时走 `sudo`

## 4. 安全模型

该 Skill 的核心不是 SSH 本身，而是三层安全治理。

### 4.1 第一层：Skill 约束

Skill 明确禁止：

- 大范围删除
- 关机重启
- 磁盘破坏性命令
- 权限篡改
- 下载并执行远程脚本

同时要求：

- 优先只读命令
- 每步先说明意图
- 修改前先展示当前状态

### 4.2 第二层：受限 OS 用户

`agent-ops` 不是 root，因此就算 Skill 指令有误，大部分危险操作也不会直接成功。

### 4.3 第三层：sudo 白名单

`references/sudoers_whitelist.md` 定义可免密提权的命令集合。Skill 要求：

- 第一次使用 `sudo` 前必须先读取白名单。
- 不在白名单中的命令一律不加 `sudo`。

这把真正的高风险拦截放在操作系统层，而不是只依赖模型自觉。

## 5. 标准工作流

```text
用户提供目标主机
  -> 建立 SSH 连接
  -> 先执行只读命令收集状态
  -> 如需系统级信息，再在白名单内使用 sudo
  -> 基于证据输出结论
  -> 若需要写操作，先说明影响并征求确认
```

典型只读动作包括：

- `hostname`
- `df` / `free`
- `ps`
- `tail` / `grep`
- `systemctl status`

## 6. 依赖资产

该 Skill 当前依赖：

- `backend/skills/remote-ops/SKILL.md`
- `backend/skills/remote-ops/references/sudoers_whitelist.md`

SSH 私钥路径在 Skill 设计中是强约定，但密钥本身通常不提交到仓库，需要部署侧单独提供。

## 7. 与其他 Skill 的关系

`remote-ops` 是更底层的远程主机能力，和 `docker`、`kubernetes` 的关系是：

- `remote-ops` 更偏通用 Linux 主机排障。
- `docker` 聚焦容器引擎。
- `kubernetes` 聚焦集群和工作负载。

当问题本质是系统服务、磁盘、日志或主机资源时，应优先使用 `remote-ops`。

## 8. 写操作边界

涉及以下动作时必须二次确认：

- `systemctl restart`
- `kill` / `pkill`
- 配置文件修改
- 任何有状态服务重启或数据路径操作

确认前应说明：

- 将执行什么命令
- 影响哪些进程或服务
- 是否有回滚方案

## 9. 失败场景与回退

- SSH 65300 失败则回退 22。
- 无法连接时应回报连接问题，而不是继续猜测业务异常。
- 白名单外命令即便逻辑上有帮助，也不应强行提权执行。
- 如果问题已明确属于 Docker/Kubernetes，应切换到更专门的 Skill。

## 10. 设计取舍

- SSH Skill 零额外服务依赖，部署成本低，但审计和权限粒度不如专用远程控制服务。
- 用 sudo 白名单做硬隔离，安全性强，但可执行动作集合会受限。
