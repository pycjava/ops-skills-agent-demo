# Kubernetes 排障技能设计说明

## 1. Skill 定位

`kubernetes` Skill 用于通过 `kubectl` 和 kubeconfig 对 Kubernetes 集群进行只读诊断。它的核心目标是把常见集群排障路径固化为标准流程，而不是让 Agent 在大量 `kubectl` 命令间临场选择。

## 2. 设计目标

- 先建立集群基线，再进入具体故障分支。
- 对 Pod、网络、发布和调度类问题提供稳定诊断路径。
- 保证默认操作为只读，修改操作必须显式确认。

## 3. Kubeconfig 发现策略

该 Skill 设计了多级 kubeconfig 发现顺序：

1. 用户显式提供路径
2. `./skills/kubernetes/kubeconfig`
3. `./skills/kubernetes/kubeconfig.yaml`
4. `./skills/kubernetes/.kubeconfig`
5. 兼容旧路径的 `./skills/...`

设计原因：

- 兼容本项目的推荐目录。
- 同时兼容历史路径和不同部署方式。

## 4. 标准执行流程

```text
检查 kubectl 与 kubeconfig
  -> 获取 contexts 和 current-context
  -> 执行集群基线诊断
  -> 根据问题进入工作负载 / 网络 / 发布 / 资源分支
  -> 输出证据化结论和建议
```

### 4.1 基线诊断

基线诊断通常先看：

- `get nodes`
- `get ns`
- `get pods -A -o wide`

设计意图是：在排查单个 Pod 之前，先确定集群是否已经处于整体异常状态。

### 4.2 故障分支

Skill 将问题大致分为四类：

- 工作负载：Pod、Deployment、StatefulSet、DaemonSet
- 网络：Service、Endpoints、Ingress
- 发布：rollout 历史和状态
- 资源：Quota、Limits、调度与 Pending

## 5. 依赖资产

该 Skill 当前依赖：

- `backend/skills/kubernetes/SKILL.md`
- `backend/skills/kubernetes/scripts/k8s_readonly_diagnose.sh`
- `backend/skills/kubernetes/references/troubleshooting.md`

其中参考资料特别覆盖：

- `CrashLoopBackOff`
- `ImagePullBackOff`
- `Pending`
- `OOMKilled`

## 6. 输出结构

Skill 要求用证据化格式输出：

- 诊断结论
- 已执行命令
- 关键证据
- 下一步建议

这样的好处是，用户可以直接复查命令和依据，而不是只拿到黑箱结论。

## 7. 安全边界

### 7.1 默认只读

默认命令应集中在：

- `get`
- `describe`
- `logs`
- `config get-contexts`
- rollout 只读查询

### 7.2 写操作确认

以下命令必须用户确认后才执行：

- `apply`
- `delete`
- `patch`
- `scale`
- `rollout restart`

确认前应说明变更对象、命名空间和潜在影响。

### 7.3 敏感信息保护

回答中不得泄露 kubeconfig 中的：

- token
- key
- cert data

## 8. 与其他 Skill 的边界

- 如果问题实际停留在容器运行时，应切换到 `docker`。
- 如果问题是主机资源、SSH、systemd 或日志，应切换到 `remote-ops`。
- 如果问题只是阅读本地 YAML 或项目配置，不应直接进入集群排障流程。

## 9. 失败场景与回退

- `kubectl` 不存在时应明确反馈环境未满足。
- kubeconfig 缺失时应提示用户补充到约定目录。
- 集群不可访问时应终止后续故障分支，而不是继续推测应用级结论。
- 问题范围过大时，应优先执行只读诊断脚本建立全貌。

## 10. 设计取舍

- 把 K8s 排障沉淀为脚本和参考清单，可重复性强，但也要求这些清单持续维护。
- 只读优先提升安全性，但复杂修复场景仍需人工确认和介入。
