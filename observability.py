# -*- coding: utf-8 -*-
"""
可观测模块

提供全链路 Trace / Log / Metrics 能力，覆盖 Agent、Skill、MCP 工具、LLM、
RAG 检索与审批事件。每次会话生成独立的 trace_id，最终产出：

    output/trace.jsonl     全链路 Span
    output/logs.jsonl      结构化日志
    output/metrics.json    聚合指标
    output/session.json    会话状态快照
    output/summary.json    服务报告摘要
"""

import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from masking import mask_state_snapshot


class Span:
    """一次调用/事件的追踪跨度"""

    def __init__(self, trace_id: str, parent_id: Optional[str], name: str,
                 span_type: str, attributes: Optional[Dict[str, Any]] = None):
        self.span_id = str(uuid.uuid4())[:8]
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.name = name
        self.span_type = span_type
        self.attributes = attributes or {}
        self.started_at = time.time()
        self.ended_at: Optional[float] = None
        self.duration_ms = 0.0
        self.status = "ok"

    def end(self, status: str = "ok") -> None:
        self.ended_at = time.time()
        self.duration_ms = round((self.ended_at - self.started_at) * 1000, 2)
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "type": self.span_type,
            "status": self.status,
            "started_at": round(self.started_at, 4),
            "ended_at": round(self.ended_at, 4) if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
        }


class Observability:
    """Trace/Log/Metrics 收集器"""

    SPAN_TYPES = ("agent", "skill", "mcp.tool", "llm", "rag.retrieve", "approval", "replay")

    def __init__(self, trace_id: Optional[str] = None, output_dir: Optional[Path] = None):
        self.trace_id = trace_id or str(uuid.uuid4())[:12]
        self.output_dir = Path(output_dir) if output_dir else None
        self.spans: List[Span] = []
        self.stack: List[Span] = []
        self.logs: List[Dict[str, Any]] = []
        self.metrics: Dict[str, Any] = {
            "conversations": 0,
            "agents_called": 0,
            "skill_calls": 0,
            "mcp_calls": 0,
            "llm_calls": 0,
            "approval_requests": 0,
            "approvals_granted": 0,
            "approvals_rejected": 0,
            "rollbacks": 0,
            "tickets_created": 0,
            "tool_successes": 0,
            "tool_failures": 0,
            "rag_retrievals": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "e2e_latency_ms": 0.0,
        }
        self.started_at = time.time()
        self.ended_at: Optional[float] = None

    def start_span(self, name: str, span_type: str = "agent",
                   attributes: Optional[Dict[str, Any]] = None) -> Span:
        parent = self.stack[-1] if self.stack else None
        span = Span(self.trace_id, parent.span_id if parent else None, name, span_type, attributes)
        self.spans.append(span)
        self.stack.append(span)
        return span

    def end_span(self, span: Optional[Span] = None, status: str = "ok") -> Optional[Span]:
        if span is None:
            span = self.stack.pop() if self.stack else None
        elif span in self.stack:
            self.stack.remove(span)
        if span is not None:
            span.end(status)
        return span

    @contextmanager
    def span(self, name: str, span_type: str = "agent",
             attributes: Optional[Dict[str, Any]] = None) -> Iterator[Span]:
        """以 context manager 方式记录一段 Span"""
        sp = self.start_span(name, span_type, attributes)
        try:
            yield sp
        except Exception:
            self.end_span(sp, status="error")
            raise
        else:
            self.end_span(sp, status="ok")

    def add_log(self, level: str, event: str, **attrs: Any) -> Dict[str, Any]:
        """记录结构化日志"""
        entry = {
            "trace_id": self.trace_id,
            "timestamp": round(time.time(), 4),
            "level": level,
            "event": event,
            "attributes": attrs,
        }
        self.logs.append(entry)
        return entry

    def inc(self, metric: str, value: float = 1.0) -> None:
        if metric in self.metrics:
            self.metrics[metric] += value
        else:
            self.metrics[metric] = value

    def record(self, metric: str, value: Any) -> None:
        self.metrics[metric] = value

    def mark_conversation(self) -> None:
        self.inc("conversations")

    def finalize(self) -> None:
        self.ended_at = time.time()
        self.metrics["e2e_latency_ms"] = round((self.ended_at - self.started_at) * 1000, 2)

    def write_evidence(self, state: Any) -> Dict[str, Path]:
        """把当前会话证据写入 output 目录，返回文件路径映射"""
        self.finalize()
        if self.output_dir is None:
            return {}

        out = self.output_dir
        out.mkdir(parents=True, exist_ok=True)

        session_id = getattr(state, "session_id", "latest")
        trace_path = out / "trace.jsonl"
        log_path = out / "logs.jsonl"
        metric_path = out / "metrics.json"
        session_path = out / "session.json"
        summary_path = out / "summary.json"
        per_session = {
            "trace": out / f"{session_id}-trace.jsonl",
            "logs": out / f"{session_id}-logs.jsonl",
            "metrics": out / f"{session_id}-metrics.json",
            "session": out / f"{session_id}-session.json",
            "summary": out / f"{session_id}-summary.json",
        }

        trace_text = "".join(
            json.dumps(span.to_dict(), ensure_ascii=False) + "\n"
            for span in self.spans
        )
        with trace_path.open("w", encoding="utf-8") as f:
            f.write(trace_text)
        with per_session["trace"].open("w", encoding="utf-8") as f:
            f.write(trace_text)

        log_text = "".join(
            json.dumps(entry, ensure_ascii=False) + "\n"
            for entry in self.logs
        )
        with log_path.open("w", encoding="utf-8") as f:
            f.write(log_text)
        with per_session["logs"].open("w", encoding="utf-8") as f:
            f.write(log_text)

        metric_text = json.dumps(self.metrics, ensure_ascii=False, indent=2)
        with metric_path.open("w", encoding="utf-8") as f:
            f.write(metric_text)
        with per_session["metrics"].open("w", encoding="utf-8") as f:
            f.write(metric_text)

        session = mask_state_snapshot(state.to_dict() if hasattr(state, "to_dict") else state)
        session["trace_id"] = self.trace_id
        session_text = json.dumps(session, ensure_ascii=False, indent=2)
        with session_path.open("w", encoding="utf-8") as f:
            f.write(session_text)
        with per_session["session"].open("w", encoding="utf-8") as f:
            f.write(session_text)

        summary = self.build_summary(state)
        summary_text = json.dumps(summary, ensure_ascii=False, indent=2)
        with summary_path.open("w", encoding="utf-8") as f:
            f.write(summary_text)
        with per_session["summary"].open("w", encoding="utf-8") as f:
            f.write(summary_text)

        # 会话清单，方便评审查看全部运行证据
        manifest_path = out / "evidence_manifest.json"
        manifest = {"latest": {"session_id": session_id, "trace_id": self.trace_id}}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
            manifest.setdefault("sessions", []).append({
                "session_id": session_id,
                "trace_id": self.trace_id,
                "files": {k: str(v.name) for k, v in per_session.items()},
            })
        else:
            manifest = {
                "latest": {"session_id": session_id, "trace_id": self.trace_id},
                "sessions": [{
                    "session_id": session_id,
                    "trace_id": self.trace_id,
                    "files": {k: str(v.name) for k, v in per_session.items()},
                }],
            }
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        self.add_log("info", "evidence.written",
                     files=[p.name for p in (trace_path, log_path, metric_path, session_path, summary_path)])
        return {
            "trace": trace_path,
            "logs": log_path,
            "metrics": metric_path,
            "session": session_path,
            "summary": summary_path,
        }

    def build_summary(self, state: Any) -> Dict[str, Any]:
        """生成与 ServiceReport 对齐的会话摘要"""
        return {
            "trace_id": self.trace_id,
            "session_id": getattr(state, "session_id", None),
            "intent": getattr(state, "intent", None),
            "risk_level": getattr(state, "overall_risk_level", "L0"),
            "issue_resolved": bool(getattr(state, "issue_resolved", False)),
            "satisfaction": round(float(getattr(state, "satisfaction_score", 0.0) or 0.0), 3),
            "retrieval_confidence": round(float(getattr(state, "retrieval_confidence", 0.0) or 0.0), 3),
            "approvals": [dict(a) for a in getattr(state, "approval_history", [])],
            "tickets": [dict(t) for t in getattr(state, "tickets_created", [])],
            "execution_records": [
                {
                    "skill": r.skill_name,
                    "success": r.success,
                    "risk_level": r.risk_level,
                    "idempotency_key": getattr(r, "idempotency_key", None),
                    "rollback_point": getattr(r, "rollback_point", None),
                    "duration_ms": getattr(r, "duration_ms", 0),
                }
                for r in getattr(state, "execution_records", [])
            ],
            "metrics": self.metrics,
        }
