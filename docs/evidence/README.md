# 运行证据样例

以下文件来自本地 `python main.py 1`、`python evaluate.py` 与 `python resume_approval.py` 的真实运行输出（脱敏后提交）。
当前 7 个演示场景、12/12 Golden/Badcase 评估通过、28 项自动化测试通过。

| 文件 | 说明 |
|---|---|
| `trace.jsonl` | 审批后续跑会话全链路 Span（Agent/Skill/MCP/LLM/RAG/审批） |
| `logs.jsonl` | 审批后续跑会话结构化日志 |
| `metrics.json` | 审批后续跑会话聚合指标 |
| `session.json` | 审批后续跑会话状态快照（消息已脱敏） |
| `summary.json` | 审批后续跑会话服务报告 |
| `eval_report.json` | Golden/Badcase 评估报告（12/12 通过） |
| `pending_approvals.json` | 审批拒绝场景的待审批样例 |
| `approval_decisions.json` | 人工审批台写入的审批决策（用于续跑） |
| `refund-approval-trace.jsonl` | 退款审批通过场景 Trace |
| `refund-approval-logs.jsonl` | 退款审批通过场景日志 |
| `refund-approval-metrics.json` | 退款审批通过场景指标 |
| `refund-approval-session.json` | 退款审批通过场景会话快照 |
| `refund-approval-summary.json` | 退款审批通过场景服务报告 |
| `screenshots/demo-home.png` | 在线 Demo 界面截图 |
| `screenshots/approval-ui.png` | 人工审批台界面截图 |
| `screenshots/slide-cover.png` | 初赛作品说明封面截图 |

本地复现：

```bash
python main.py 1
python evaluate.py
python replay.py
python approval_server.py 8080
python resume_approval.py
```

人工审批续跑链路：`python main.py 1` 产生 `pending_approvals.json` 与待审批会话；审批台通过/拒绝后写入
`approval_decisions.json`；`resume_approval.py` 将决策写回共享状态，从 ToolExecutor 继续执行并刷新全部证据。
