# -*- coding: utf-8 -*-
"""
全链路回放

读取 output/ 下已生成的会话与 Trace，按「输入 → 任务拆解 → 工具调用 →
审批/证据 → 输出 → 满意度」还原一次自主闭环，用于评审与审计回放。

运行: python replay.py [session_id]
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_session(session_id: str = None) -> Dict[str, Any]:
    path = OUTPUT_DIR / f"{session_id}-session.json" if session_id else OUTPUT_DIR / "session.json"
    if not path.exists():
        raise FileNotFoundError(f"未找到会话证据: {path}")
    return _read(path)


def load_trace(session_id: str = None, trace_id: str = None) -> List[Dict[str, Any]]:
    path = OUTPUT_DIR / f"{session_id}-trace.jsonl" if session_id else OUTPUT_DIR / "trace.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"未找到 Trace 证据: {path}")
    spans = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        span = json.loads(line)
        if not trace_id or span.get("trace_id") == trace_id:
            spans.append(span)
    return spans


def replay(session_id: str = None) -> None:
    session = load_session(session_id)
    trace = load_trace(session_id, session.get("trace_id"))
    print("=" * 64)
    print("ServicePilot 全链路回放")
    print(f"Session: {session.get('session_id')} | Trace: {session.get('trace_id')}")
    print("=" * 64)

    user_msgs = [m.get("content") for m in session.get("messages", []) if m.get("role") == "user"]
    print(f"\n[输入] {user_msgs[0] if user_msgs else '-'}")
    print(f"[意图] {session.get('intent')} | 情绪 {session.get('sentiment')} | "
          f"紧急度 {session.get('urgency')} | 风险 {session.get('risk_level')}")
    print(f"[RAG] 置信度 {session.get('retrieval_confidence')}")

    plans = [e.get("attributes", {}).get("plan") for e in trace
             if e.get("name") == "TaskPlanner" and e.get("attributes", {}).get("plan")]
    if plans:
        print("\n[任务拆解]")
        for step in plans[0]:
            print(f"  - Step {step.get('step')} [{step.get('risk_level')}] "
                  f"{step.get('desc')} -> {step.get('skill') or step.get('action')}")

    tool_spans = [e for e in trace if e.get("type") == "mcp.tool"]
    if tool_spans:
        print("\n[工具调用]")
        for span in tool_spans:
            attrs = span.get("attributes", {})
            mark = "成功" if attrs.get("success") else "失败"
            print(f"  - {attrs.get('skill')} [{attrs.get('risk_level')}] {mark} "
                  f"{span.get('duration_ms')}ms")

    approvals = session.get("approval_history", [])
    if approvals:
        print("\n[审批]")
        for app in approvals:
            print(f"  - {app.get('action')} -> {app.get('status')} | "
                  f"审批人 {app.get('approver')} | 原因 {app.get('reason')}")

    print(f"\n[输出] {session.get('final_reply')}")
    print(f"[验证] {'已解决' if session.get('issue_resolved') else '未解决，转人工'} | "
          f"满意度 {session.get('satisfaction')}")
    tickets = session.get("tickets", [])
    if tickets:
        print(f"[工单] {', '.join(t.get('ticket_id', '') for t in tickets)}")

    metrics_path = OUTPUT_DIR / f"{session_id}-metrics.json" if session_id else OUTPUT_DIR / "metrics.json"
    if metrics_path.exists():
        metrics = _read(metrics_path)
        print(f"\n[Metrics] e2e {metrics.get('e2e_latency_ms')}ms | "
              f"工具调用 {metrics.get('mcp_calls')} | LLM {metrics.get('llm_calls')} | "
              f"Token {metrics.get('total_tokens')}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    session_id = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        replay(session_id)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
