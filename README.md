# ServicePilot — 智能客服多 Agent 自主闭环系统

> GOAI 世界人工智能开源大赛 · Agent Infra 赛道初赛作品
> 方向：Agent Infra / 智能客服自主闭环

[![CI](https://github.com/11ssyyhh/servicepilot-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/11ssyyhh/servicepilot-demo/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![在线 Demo](https://img.shields.io/badge/在线Demo-GitHub%20Pages-teal)](https://11ssyyhh.github.io/servicepilot-demo/)

ServicePilot 基于 AgentTeams Manager-Workers 架构，用 7 个职能 Agent 协同完成
「进线 → 意图识别 → RAG 检索 → 任务规划 → 工具执行 → 质量审核 → 效果验证 → 记忆沉淀」
的智能客服自主闭环，解决传统单 Bot 客服无法处理复杂业务、高风险操作依赖人工、
过程不可追溯的核心痛点。

## ✨ 核心能力

- **7 个职能 Agent**：IntentRouter / KnowledgeRetriever / TaskPlanner / ToolExecutor / QualityGuard / Verifier / MemoryScribe
- **17 个可复用 Skill**：诊断、知识、执行、治理、记忆五类，标准化输入输出与失败处理
- **L0-L3 风险管控**：低风险自动闭环，L2 退款必须人工审批，审批通过/拒绝双路径可审计
- **幂等 + 回滚**：写操作携带 `idempotency_key`，退款支持 `RollbackOperation` 回滚
- **MCP 等价契约**：HTTP + JSON-RPC Mock Server，覆盖订单/工单/支付/物流
- **全链路可观测**：Trace/Log/Metrics/Session/Summary 五类证据，支持回放
- **可插拔 LLM**：默认零依赖规则引擎，配置 `SERVICE_PILOT_LLM_API_KEY` 即切 OpenAI 兼容接口
- **评估回归**：Golden/Badcase 数据集 + `evaluate.py`，输出准确率与成本指标
- **人工审批台**：`approval_server.py` + 交互式 Web UI，通过/拒绝写入审计
- **数据合规**：手机号、邮箱、地址在证据文件中自动脱敏

## 🚀 快速开始

```bash
# 1. 运行 5 个场景闭环，生成 output/ 证据
python main.py 1

# 2. 运行 26 项测试
python -m unittest discover -s tests -t . -v

# 3. 运行评估
python evaluate.py

# 4. 回放最近一次会话
python replay.py

# 5. 人工审批台（浏览器打开 http://127.0.0.1:8080/approval.html）
python approval_server.py 8080

# 6. MCP 等价 Mock Server
python mcp_mock_server.py 8001

# 7. Docker 一键演示
docker compose up --build
```

在线交互 Demo：<https://11ssyyhh.github.io/servicepilot-demo/>

## 📋 Demo 场景

| 场景 | 意图 | 风险 | 闭环行为 |
|------|------|------|---------|
| 订单查询 | order_query | L0 | 自动查询并回复 |
| 退款申请 | refund | L2 | 审批通过 → 幂等执行退款 → 审计 |
| 退款申请 | refund | L2 | 审批拒绝 → 转人工工单 |
| 修改地址 | address_change | L1 | 执行失败 → 转人工工单 |
| 用户投诉 | complaint | high | 创建高优先级工单并安抚 |

## 📁 项目结构

```text
servicepilot-demo/
├── main.py                  # Demo 入口（5 场景）
├── manager.py               # AgentTeams Manager 编排器
├── agents.py                # 7 个职能 Agent
├── skills.py                # 17 个 Skill
├── shared_state.py          # 共享状态（审批/审计/执行记录）
├── mock_systems.py          # Mock 业务系统（幂等 + 回滚）
├── observability.py         # Trace / Log / Metrics
├── llm.py                   # 可插拔 LLM 适配器（规则引擎兜底）
├── masking.py               # PII 脱敏
├── evaluate.py              # Golden/Badcase 评估
├── eval_dataset.json        # 评估数据集
├── replay.py                # 全链路回放
├── approval_server.py       # 人工审批服务
├── mcp_mock_server.py       # MCP 等价 Mock Server
├── agentteams/              # AgentTeams 部署配置
├── docs/                    # 提交文档 + 在线 Demo + 审批台
├── tests/                   # 26 项测试
└── .github/workflows/ci.yml # CI
```

## 📊 可观测证据

运行后 `output/` 自动生成：

- `trace.jsonl`：Agent/Skill/MCP/LLM/RAG/审批全链路 Span
- `logs.jsonl`：结构化日志（意图路由、失败、审批、审计）
- `metrics.json`：会话数、工具成功率、Token、成本、端到端延迟
- `session.json`：脱敏会话快照
- `summary.json`：审批、工单、执行记录与服务报告
- `eval_report.json`：评估结果

样例证据见 [docs/evidence/](docs/evidence/)。

## 📚 提交文档

- [500 字作品简介](docs/01-作品简介.md)
- [Agent Identity 清单](docs/02-AgentIdentity清单.md)
- [Skill 清单](docs/03-Skill清单.md)
- [MCP 工具契约](docs/04-工具契约.md)
- [可观测与安全](docs/05-可观测与安全.md)
- [开放开源计划](docs/06-开放开源计划.md)
- [初赛检查清单](docs/07-初赛检查清单.md)
- [AgentTeams 映射说明](docs/08-AgentTeams映射说明.md)
- [人工审批台](docs/approval.html)

## 📈 量化目标

- 自动解决率：80%+（常见问题）
- 平均响应时间：3 分钟 → 30 秒
- 客服人力成本：降低 40%
- 关键操作审计：100% 留痕
- 评估通过率：Golden Case 100%（当前 6/6）

## 🔄 复赛计划

- [ ] 接入真实 AgentTeams 平台（Docker/K8s 部署）
- [ ] 对接真实业务系统 API（订单/工单/支付/物流）
- [ ] 接入通义千问 LLM（Token Plan 月卡额度）
- [ ] 扩充客服对话评估数据集
- [ ] 接入 AgentLoop 可观测看板
- [ ] 完善安全执行白名单和回滚机制

## 📄 开源计划

本项目将开源：7 个 Agent 模板、17 个 Skill、MCP Mock Server、评估数据集、
AgentTeams 部署配置，代码采用 MIT License。

## 📞 相关链接

- GOAI 大赛官网：<https://goaihz.com>
- AgentTeams：<https://github.com/agentscope-ai/AgentTeams>
- 阿里云 AgentTeams：<https://www.aliyun.com/product/agentteams>
- DataWhale 夏令营：<https://ailc.datawhale.cn>

---

**GOAI Agent Infra 赛道 · ServicePilot 团队 · 2026 年 8 月**
