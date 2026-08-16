# Skill 清单

Skill 是任务能力抽象层：标准输入输出、失败处理、安全边界与复用价值。Agent 只负责判断与编排，不裸调业务系统；写操作通过 MCP 等价契约完成。

当前注册 17 个 Skill，覆盖诊断、知识、执行、治理、记忆五类。

## 核心 Skill（9 个，含完整规格）

### 1. IntentClassifier 意图分类

- **类型**：诊断 / 规则分类
- **输入**：`message: str`
- **输出**：`intent`、`confidence`、`all_scores`
- **失败处理**：无关键词命中时返回 `other`，由 LLM 意图校验兜底
- **安全边界**：只读；投诉类意图优先级最高
- **复用价值**：任意多分类客服路由

### 2. FAQRetrieval 知识检索

- **类型**：知识 / RAG（中文 n-gram + 关键词 + 意图类目加权）
- **输入**：`query: str`、`intent_hint: str`、`top_k: int`
- **输出**：候选 `question/answer/category/score/source/evidence`、`confidence`
- **失败处理**：置信度低于阈值时建议转人工，不编造答案
- **安全边界**：只读；证据带来源
- **复用价值**：FAQ、Runbook、政策检索

### 3. ProductDocRAG 产品文档检索

- **类型**：知识 / RAG
- **输入**：`query: str`
- **输出**：文档片段、来源、相关性得分、`confidence`
- **失败处理**：无命中返回空结果并提示证据缺口
- **安全边界**：只读；仅返回知识库内内容
- **复用价值**：产品文档、帮助中心检索

### 4. RiskEscalation 风险分级

- **类型**：治理 / 规则引擎
- **输入**：`action: str`、`amount: float`、`user_level: str`
- **输出**：`risk_level`（L0-L3）、`need_approval`
- **失败处理**：规则未覆盖时按 L1 保守处理
- **安全边界**：L2/L3 必须审批；VIP 用户可降一级
- **复用价值**：退款、销户、转账等风险策略

### 5. RefundProcess 退款处理

- **类型**：执行 / 高风险写操作（L2）
- **输入**：`order_id`、`reason`、`approved`、`idempotency_key`、`approval_id`
- **输出**：退款单号、金额、到账时间、回滚点、幂等键
- **失败处理**：无审批令牌直接拒绝；重复幂等键返回同一结果
- **安全边界**：必须审批；记录回滚点；可调用 `RollbackOperation` 回滚
- **复用价值**：任何需审批的资金类操作

### 6. AddressUpdate 地址修改

- **类型**：执行 / 低风险写操作（L1）
- **输入**：`order_id`、`new_address`、`idempotency_key`
- **输出**：新旧地址、更新时间、回滚点
- **失败处理**：已发货订单拒绝并转人工
- **安全边界**：仅未发货订单可改；留痕
- **复用价值**：收货信息变更

### 7. TicketCreate 工单创建

- **类型**：执行 / 人工转接
- **输入**：`problem_desc`、`priority`、`idempotency_key`
- **输出**：工单号、优先级、响应时限
- **失败处理**：重复调用幂等；创建失败记录错误
- **安全边界**：转人工必经审计
- **复用价值**：多渠道工单入口

### 8. ComplianceCheck 合规检查

- **类型**：治理 / 规则引擎
- **输入**：`text: str`
- **输出**：`passed`、`violations`
- **失败处理**：命中广告法禁词时拦截输出
- **安全边界**：只读文本
- **复用价值**：营销文案、客服回复审核

### 9. KnowledgeUpdate 知识库更新建议

- **类型**：记忆 / 草案生成
- **输入**：`intent`、`issue_resolved`、`summary`
- **输出**：`suggestions`、`requires_review: true`
- **失败处理**：无摘要时不生成无依据建议
- **安全边界**：仅生成草案，发布需人工审核
- **复用价值**：案例沉淀、FAQ 补全

## 其余 Skill

| Skill | 类型 | 说明 |
|---|---|---|
| SentimentDetector | 诊断 | 5 级情绪识别，负面触发升级 |
| ProblemTypeRouter | 诊断 | 售前/售后/投诉/咨询路由 |
| HistoryCaseSearch | 知识 | 历史工单相似案例检索 |
| OrderQuery | 执行 | L0 只读订单查询 |
| RollbackOperation | 执行 | L2 回滚退款等业务操作 |
| SensitiveWordFilter | 治理 | 敏感词过滤 |
| ConversationSummary | 记忆 | 对话结构化摘要 |
| ServiceReport | 记忆 | 服务报告生成 |

## 与多 Agent 协同流程的关系

`IntentRouter` 使用诊断类 Skill → `KnowledgeRetriever` 使用知识类 Skill → `TaskPlanner` 与 `ToolExecutor` 使用执行/治理类 Skill → `QualityGuard` 使用治理类 Skill → `MemoryScribe` 使用记忆类 Skill。所有 Skill 调用都进入全链路 Trace。
