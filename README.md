# ServicePilot — 智能客服多Agent自主闭环系统

> GOAI世界人工智能开源大赛 · Agent Infra赛道初赛作品
> 基于AgentTeams多Agent协同框架，实现智能客服全链路自主闭环

## 📋 项目简介

ServicePilot是一个企业级智能客服系统，通过7个职能Agent的分工协作，实现从用户进线到问题解决、知识沉淀的全链路自主闭环。解决传统单Bot客服无法处理复杂业务、人工介入率高的核心痛点。

## 🏗️ 架构设计

### Manager-Workers架构 (模拟AgentTeams)

```
用户入口
    ↓
┌─────────────────────────────────────────┐
│         Manager (编排器)                 │
│  任务拆解 | 状态管理 | Agent调度 | 异常处理 │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│           7个Worker Agent                │
│  IntentRouter | KnowledgeRetriever      │
│  TaskPlanner  | ToolExecutor            │
│  QualityGuard | Verifier | MemoryScribe │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│           15+ Skill体系                  │
│  诊断 | 知识 | 执行 | 治理 | 沉淀        │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│        MCP适配器 (Mock业务系统)          │
│  订单 | 工单 | 支付 | 物流 | 知识库      │
└─────────────────────────────────────────┘
```

### 自主闭环链路

```
用户进线 → 意图识别+情绪检测 → 知识库RAG检索 → 方案生成
    → 质量审核(L0-L3风险分级) → 工具执行(高风险需审批)
    → 效果验证 → 用户确认 → 工单关闭 + 知识沉淀 + 服务报告
```

## 🤖 7个职能Agent

| Agent | 职责 | 决策边界 |
|-------|------|---------|
| **IntentRouter** | 意图识别、情绪检测、紧急度分级、任务分发 | 仅做路由，不生成最终回复 |
| **KnowledgeRetriever** | FAQ检索、产品文档RAG、历史案例检索 | 仅检索不决策，置信度<0.6转人工 |
| **TaskPlanner** | 问题拆解、多步规划、工具选择、风险预判 | 规划但不执行，高风险标注审批节点 |
| **ToolExecutor** | 订单查询、退款处理、地址修改、工单创建 | L1以下自动执行，L2+需审批令牌 |
| **QualityGuard** | 内容审核、敏感词过滤、合规检查、风险升级 | 有权拦截任何输出，高风险强制转人工 |
| **Verifier** | 问题解决确认、满意度评估、未解决重规划 | 仅验证不执行，未解决自动转人工 |
| **MemoryScribe** | 对话摘要、知识库更新建议、服务报告 | 仅写入建议，正式更新需人工审核 |

## 🛠️ 核心Skill体系 (15+)

### 诊断类
- `IntentClassifier` - 20类客服意图分类
- `SentimentDetector` - 5级情绪识别
- `ProblemTypeRouter` - 问题类型路由

### 知识类
- `FAQRetrieval` - 常见问题向量检索
- `ProductDocRAG` - 产品文档RAG检索
- `HistoryCaseSearch` - 历史工单案例检索

### 执行类
- `OrderQuery` - 订单状态查询
- `RefundProcess` - 退款申请处理 (L2高风险)
- `AddressUpdate` - 收货地址修改 (L1低风险)
- `TicketCreate` - 人工工单创建

### 治理类
- `ComplianceCheck` - 合规性检查
- `SensitiveWordFilter` - 敏感词过滤
- `RiskEscalation` - 风险升级判断 (L0-L3)

### 沉淀类
- `ConversationSummary` - 对话摘要生成
- `ServiceReport` - 服务报告生成

## 🔐 安全边界 (L0-L3风险分级)

| 等级 | 名称 | 处理方式 | 典型操作 |
|------|------|---------|---------|
| **L0** | 只读诊断 | 自动执行 | 订单查询、物流查询 |
| **L1** | 低风险自动执行 | 自动执行+留痕 | 修改地址、发放优惠券 |
| **L2** | 灰度+审批 | 人工确认后执行 | 退款、销户、大额操作 |
| **L3** | 只生成方案 | 仅输出建议 | 极端风险操作 |

所有操作支持：审批记录、自动回滚、审计日志、可回放Trace。

## 🚀 快速开始

### 环境要求
- Python 3.8+
- 无外部依赖 (初赛Demo使用纯Python实现)

### 运行Demo

```bash
cd servicepilot-demo
python main.py
```

### 运行模式

1. **自动演示模式** (默认) - 依次运行4个场景
2. **交互模式** - 手动输入用户消息
3. **单场景模式** - 仅运行订单查询场景

```bash
python main.py 1  # 自动演示
python main.py 2  # 交互模式
python main.py 3  # 单场景
```

### Demo场景

| 场景 | 意图 | 风险等级 | 说明 |
|------|------|---------|------|
| 订单查询 | order_query | L0 | 只读，全自动执行 |
| 退款申请 | refund | L2 | 高风险，需审批 |
| 修改地址 | address_change | L1 | 低风险，自动执行 |
| 用户投诉 | complaint | high | 高紧急度，自动转人工 |

## 📁 项目结构

```
servicepilot-demo/
├── main.py                 # 入口，Demo场景演示
├── config.py               # 配置 (Agent定义、Skill注册、风险等级)
├── manager.py              # Manager (AgentTeams编排器)
├── agents.py               # 7个Agent实现
├── skills.py               # 15+ Skill实现
├── shared_state.py         # 共享状态 (Conversation State)
├── mock_systems.py         # Mock业务系统 (MCP适配器)
├── requirements.txt        # 依赖
├── README.md               # 本文档
└── agentteams/             # AgentTeams真实部署配置
    ├── team.yaml           # Team定义
    └── workers.yaml        # Worker定义
```

## 📊 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 多Agent框架 | AgentTeams (Hiclaw) | 必须，Manager-Workers架构 |
| Skill | 自定义Skill + 阿里云用云Skills | 必选，标准化能力封装 |
| 工具协议 | MCP (Model Context Protocol) | 推荐，业务系统对接 |
| AI网关 | Higress | 推荐，统一入口/鉴权/限流 |
| 资源治理 | Nacos | 推荐，Prompt/Skill/AgentSpec管理 |
| 数据存储 | PolarDB + pgvector | 推荐，RAG/长记忆/审计日志 |
| 消息队列 | RocketMQ | 推荐，事件驱动/Agent间通信 |
| 可观测 | AgentLoop / AgentScope Studio | 推荐，Trace/Log/Metrics |

## 🎯 创新点

1. **多Agent协同而非单Bot** - 7个专业角色模拟真实客服团队，复杂问题解决率提升40%
2. **L0-L3四级风险管控** - 低风险自动闭环，高风险人工审批，所有操作可追溯可回滚
3. **Skill标准化可迁移** - 客服经验封装为标准化Skill，支持跨行业快速迁移
4. **全链路可观测** - AgentLoop记录每次Agent/Skill/工具/LLM调用，可回放可审计

## 📈 量化目标

- 自动解决率：80%+ (常见问题)
- 平均响应时间：3分钟 → 30秒
- 客服人力成本：降低40%
- 关键操作审计：100%留痕

## 🔄 复赛计划

- [ ] 接入真实AgentTeams平台 (Docker/K8s部署)
- [ ] 对接真实业务系统API (订单/工单/支付/物流)
- [ ] 引入通义千问LLM (使用Token Plan月卡额度)
- [ ] 构建客服对话评估数据集 (Golden/Bad Case)
- [ ] 接入AgentLoop可观测看板
- [ ] 完善安全执行白名单和回滚机制

## 📄 开源计划

本项目将开源以下成果：
- 智能客服Agent角色模板 (7个Agent Identity定义)
- 15+核心Skill (标准化Schema + 实现)
- MCP适配器样例 (订单/工单/支付/物流)
- 客服对话评估数据集
- AgentTeams部署配置文件

## 📞 相关链接

- GOAI大赛官网: https://goaihz.com
- AgentTeams GitHub: https://github.com/agentscope-ai/AgentTeams
- 阿里云AgentTeams: https://www.aliyun.com/product/agentteams
- DataWhale夏令营: https://ailc.datawhale.cn

---

**GOAI Agent Infra赛道 · ServicePilot团队 · 2026年8月**
