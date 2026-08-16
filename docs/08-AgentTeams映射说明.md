# AgentTeams 能力映射说明

本赛道要求以 AgentTeams（原名 Hiclaw）作为多 Agent 协同设计基点。下表将 AgentTeams 关键能力与 ServicePilot 设计逐项映射。

| AgentTeams 能力 | ServicePilot 映射 | 落地机制 |
|---|---|---|
| 角色编排 | 7 个职能 Agent 按「意图路由 → 知识检索 → 任务规划 → 工具执行 → 质量风控 → 效果验证 → 记忆沉淀」组织 | Agent Identity 清单、Skill 绑定、决策边界、L0-L3 审批边界 |
| 任务拆解 | Manager 按闭环流水线调度，Agent 读写共享状态 | `SharedState` 状态机、`task_plan`、全链路 `trace_id` |
| 上下文传递 | `intent`、`retrieved_answers`、`task_plan`、`approval_history`、`execution_records` 结构化传递 | 统一 Schema、共享状态契约、Trace 关联 |
| 协同执行 | 串行编排 + 高风险审批门禁 + 幂等执行 + 回滚补偿 | `ToolExecutor`、`RefundProcess`、`RollbackOperation`、幂等键与回滚点 |
| 状态追踪 | 会话、审批、执行、验证、工单全链路可追踪、可回放 | `SharedState` + `output/trace.jsonl` + `replay.py` |

## 部署映射（agentteams/）

- `team.yaml`：Team 资源，定义 Manager 与 7 个 Worker、共享存储、可观测与安全策略。
- `workers.yaml`：Worker 资源，包含系统提示词、Skill、MCP Server 与资源配额。

## 阿里云官方用云 Skills 接入规划

- 用途：云资源查询与配置治理类能力由官方用云 Skills 提供；客服业务能力由自定义 Skill 沉淀。
- 鉴权：官方用云 Skills 使用 AK/SK 或托管凭据，按 Agent 角色最小权限，密钥不进入提示词或日志。
- 编排：官方用云 Skills 作为 Skill 能力层的一部分，与自定义 Skill 共用输入输出与审计链路。
- 端到端：所有 Skill 调用统一记录 Trace/Log/Metrics。

## 评审口径

- AgentTeams 是设计基点：架构、事件流、状态机与附录清单均体现其能力映射。
- Skill 是必选项：17 个 Skill 均含输入输出、失败处理、安全边界与复用价值。
- 推荐产品按必要性说明：Nacos 管理策略/资源，Higress 统一入口，PolarDB 向量与审计，RocketMQ 事件流转，AgentLoop 可观测。
