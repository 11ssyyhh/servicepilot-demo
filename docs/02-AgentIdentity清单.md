# Agent Identity 清单

系统共 7 个职能 Agent，以 AgentTeams Manager-Workers 为编排基点。共享状态 `SharedState` 由 Manager 维护，Agent 间通过结构化上下文协作；每次 Agent/Skill/工具/LLM 调用均写入 Trace/Log/Metrics。

## 1. IntentRouter 意图路由 Agent

- **Role**：接收用户进线，识别意图、情绪、紧急度并路由任务。
- **Capabilities**：20 类意图分类、5 级情绪识别、问题类型路由、紧急度分级。
- **Inputs**：用户原始消息。
- **Outputs**：`intent`、`sentiment`、`urgency`、`problem_type`。
- **Dependencies**：Skill `IntentClassifier`、`SentimentDetector`、`ProblemTypeRouter`；LLM 意图校验。
- **DecisionBoundary**：仅做路由，不生成最终回复；极负面情绪或投诉类问题强制标记高紧急度。
- **Trace**：记录意图、情绪、紧急度与审计事件。

## 2. KnowledgeRetriever 知识检索 Agent

- **Role**：RAG 检索 FAQ、产品文档、历史案例，返回带置信度与证据引用的候选答案。
- **Capabilities**：中文 n-gram 相关性评分、意图类目加权、多源证据合并。
- **Inputs**：用户消息、意图提示。
- **Outputs**：Top-K 候选答案、`retrieval_confidence`、证据来源与得分。
- **Dependencies**：Skill `FAQRetrieval`、`ProductDocRAG`、`HistoryCaseSearch`。
- **DecisionBoundary**：仅检索不决策；置信度低于阈值时建议转人工。
- **Trace**：记录 RAG 检索次数、证据与置信度。

## 3. TaskPlanner 任务规划 Agent

- **Role**：拆解复杂问题，规划多步执行计划并预判风险等级。
- **Capabilities**：问题拆解、工具选择、L0-L3 风险预判、审批节点标注。
- **Inputs**：意图、订单号提取、知识检索结果。
- **Outputs**：`task_plan`（步骤、Skill、参数、风险等级）、`overall_risk_level`。
- **Dependencies**：Skill 注册表、风险等级配置。
- **DecisionBoundary**：只规划不执行；L2/L3 操作必须标注审批节点。
- **Trace**：记录完整执行计划。

## 4. ToolExecutor 工具执行 Agent

- **Role**：按计划调用业务系统工具，执行 L0-L3 风险管控。
- **Capabilities**：订单查询、退款处理、地址修改、工单创建、回滚操作；幂等键生成与审批令牌校验。
- **Inputs**：`task_plan`、审批记录。
- **Outputs**：`execution_records`（状态、幂等键、回滚点、耗时）、审计事件。
- **Dependencies**：Skill `OrderQuery`、`RefundProcess`、`AddressUpdate`、`TicketCreate`、`RollbackOperation`；MCP Mock Server。
- **DecisionBoundary**：L1 以下自动执行；L2 必须持有审批记录；失败自动创建转人工工单。
- **Trace**：每次工具调用记录参数、结果、耗时与幂等键。

## 5. QualityGuard 质量风控 Agent

- **Role**：审核回复内容，执行敏感词过滤、合规检查与风险升级。
- **Capabilities**：广告法合规、敏感词过滤、LLM 回复润色、审批提示。
- **Inputs**：草稿回复、执行记录、风险等级。
- **Outputs**：`final_reply`、`quality_check_passed`、`quality_issues`。
- **Dependencies**：Skill `SensitiveWordFilter`、`ComplianceCheck`；LLM 适配器。
- **DecisionBoundary**：有权拦截任何输出；高风险动作必须提示用户确认。
- **Trace**：记录审核结论与问题清单。

## 6. Verifier 效果验证 Agent

- **Role**：验证问题是否解决，未解决自动转人工。
- **Capabilities**：按意图核验执行结果、满意度评估、转人工工单创建。
- **Inputs**：`execution_records`、审批状态、RAG 置信度。
- **Outputs**：`issue_resolved`、`satisfaction_score`、转人工工单。
- **Dependencies**：Skill `TicketCreate`。
- **DecisionBoundary**：仅验证不执行；未解决或审批未通过时强制转人工。
- **Trace**：记录验证结论与工单号。

## 7. MemoryScribe 记忆沉淀 Agent

- **Role**：生成对话摘要、知识库更新建议与服务报告。
- **Capabilities**：结构化摘要、知识更新草案、服务报告生成、LLM 摘要润色。
- **Inputs**：完整会话、验证结果。
- **Outputs**：`conversation_summary`、`knowledge_update_suggestions`、`service_report`。
- **Dependencies**：Skill `ConversationSummary`、`KnowledgeUpdate`、`ServiceReport`；LLM 适配器。
- **DecisionBoundary**：仅生成草案；正式知识库更新需人工审核。
- **Trace**：记录摘要、建议与报告。
