# 运行证据样例

以下文件来自本地 `python main.py 1` 与 `python evaluate.py` 的真实运行输出（脱敏后提交）：

| 文件 | 说明 |
|---|---|
| `trace.jsonl` | 最新会话全链路 Span（Agent/Skill/MCP/LLM/RAG/审批） |
| `logs.jsonl` | 最新会话结构化日志 |
| `metrics.json` | 最新会话聚合指标 |
| `session.json` | 最新会话状态快照（消息已脱敏） |
| `summary.json` | 最新会话服务报告 |
| `eval_report.json` | Golden/Badcase 评估报告（6/6 通过） |
| `pending_approvals.json` | 审批拒绝场景的待审批样例 |
| `refund-approval-trace.jsonl` | 退款审批通过场景 Trace |
| `refund-approval-logs.jsonl` | 退款审批通过场景日志 |
| `refund-approval-metrics.json` | 退款审批通过场景指标 |
| `refund-approval-session.json` | 退款审批通过场景会话快照 |
| `refund-approval-summary.json` | 退款审批通过场景服务报告 |

本地复现：

```bash
python main.py 1
python evaluate.py
python replay.py
```
