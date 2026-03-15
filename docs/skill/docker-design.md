# Docker 远程排障技能设计说明

## 1. Skill 定位

`docker` Skill 用于通过 Docker CLI 连接远程 Docker Engine 管理端口，对容器、镜像、网络和卷做只读诊断与问题定位。

它聚焦的是“容器运行时问题”，而不是通用主机问题或 Kubernetes 层问题。

## 2. 设计目标

- 在不登录宿主机的情况下快速排查远程 Docker 问题。
- 通过标准 CLI 和脚本沉淀排障流程。
- 把危险的变更操作与只读诊断清晰分离。

## 3. 连接与目标发现

远程端点采用三级发现顺序：

1. 用户显式提供
2. 环境变量 `DOCKER_HOST`
3. `./skills/docker/endpoint`

如果地址缺少协议，例如 `10.0.0.8:2375`，则自动补全为 `tcp://10.0.0.8:2375`。

如果远程端启用 TLS，则额外依赖：

- `DOCKER_TLS_VERIFY=1`
- `DOCKER_CERT_PATH=<cert目录>`

## 4. 标准执行流程

```text
确认 docker CLI 和远程端点
  -> 获取 version / info
  -> 执行基线巡检
  -> 若有目标容器，进一步 inspect / logs / top
  -> 输出结论、证据和建议
```

### 4.1 基线巡检

基线巡检关注：

- 容器列表
- 镜像列表
- 网络列表
- 卷列表
- 资源快照

它的作用是先建立“远程 Docker 当前全貌”，再进入具体故障分支。

### 4.2 深入排障

若用户提供容器名或容器 ID，可进一步查看：

- `inspect`
- `logs`
- `top`

## 5. 依赖资产

该 Skill 当前依赖：

- `backend/skills/docker/SKILL.md`
- `backend/skills/docker/scripts/docker_readonly_diagnose.sh`
- `backend/skills/docker/references/troubleshooting.md`

其中：

- `scripts/` 负责快速只读诊断。
- `references/` 负责常见容器异常模式的检查清单。

## 6. 典型故障模式

Skill 特别适合以下问题：

- 容器反复重启
- 容器启动失败
- 端口已映射但服务不可达
- 日志报错
- 镜像拉取失败
- 容器资源异常

## 7. 安全边界

### 7.1 只读优先

默认优先使用：

- `ps`
- `logs`
- `inspect`
- `stats`
- `images`
- `network ls`
- `volume ls`

### 7.2 写操作确认

以下动作必须先确认：

- `restart`
- `stop`
- `rm`
- `rmi`
- `kill`
- `compose down`

确认前需要说明命令和影响范围，执行后应给出恢复建议或后续观察项。

### 7.3 敏感信息保护

回答中不得泄露：

- registry 凭据
- token
- 私钥
- TLS 证书私密内容

## 8. 与其他 Skill 的边界

- 当问题是远程主机本身，例如磁盘、systemd、网络栈问题，应切到 `remote-ops`。
- 当问题已经上升到 Kubernetes 工作负载或 Service/Ingress 层，应切到 `kubernetes`。
- 当用户只是要查看本地项目文件或配置，不应使用该 Skill。

## 9. 失败场景与回退

- CLI 不存在时应直接报环境问题。
- 远程端点不可达时应停在连接层，不继续猜测容器状态。
- 当问题范围过大时，优先执行只读诊断脚本，再决定是否深入。

## 10. 设计取舍

- 直接使用 `docker -H`，部署轻量，但前提是远程 Engine 暴露了可访问接口。
- 只读优先降低风险，但某些修复动作必须另行确认，无法“一步到位”。
