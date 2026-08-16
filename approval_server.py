# -*- coding: utf-8 -*-
"""
人工审批 Web 服务（零依赖）

读取 output/pending_approvals.json 暴露审批接口，审批结果写入
output/approval_decisions.json。前端页面为 docs/approval.html。

运行: python approval_server.py [port]   # 默认 8080
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
PENDING_FILE = OUTPUT_DIR / "pending_approvals.json"
DECISIONS_FILE = OUTPUT_DIR / "approval_decisions.json"
UI_FILE = ROOT / "docs" / "approval.html"

SAMPLE_APPROVALS = [
    {
        "id": "demo-approval-001",
        "action": "process_refund",
        "reason": "订单 ORD20260816002 退款申请，金额 459.00 元，属于 L2 高风险操作",
        "risk_level": "L2",
        "status": "pending",
        "evidence": [
            {"step": 4, "desc": "执行退款(审批通过后)", "skill": "RefundProcess",
             "risk_level": "L2"},
            {"order": "ORD20260816002", "amount": 459.00, "refund_type": "原路返回"},
        ],
        "rollback_point": {"order_id": "ORD20260816002", "previous_status": "delivered"},
    }
]


def load_pending() -> list:
    if PENDING_FILE.exists():
        return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    return list(SAMPLE_APPROVALS)


def save_pending(approvals: list) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(approvals, ensure_ascii=False, indent=2), encoding="utf-8")


def record_decision(approval: Dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    decisions = []
    if DECISIONS_FILE.exists():
        decisions = json.loads(DECISIONS_FILE.read_text(encoding="utf-8"))
    decisions.append(approval)
    DECISIONS_FILE.write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")


class ApprovalHandler(BaseHTTPRequestHandler):

    def _send(self, code: int, payload: dict, content_type: str = "application/json") -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, code: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/approval.html"):
            if not UI_FILE.exists():
                self._send_text(404, "approval.html 未找到")
                return
            self._send_text(200, UI_FILE.read_text(encoding="utf-8"))
            return
        if path == "/api/approvals":
            self._send(200, {"approvals": load_pending()})
            return
        if path == "/api/decisions":
            decisions = []
            if DECISIONS_FILE.exists():
                decisions = json.loads(DECISIONS_FILE.read_text(encoding="utf-8"))
            self._send(200, {"decisions": decisions})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/decide":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send(400, {"error": "invalid json"})
            return

        approvals = load_pending()
        target = next((a for a in approvals if a["id"] == payload.get("approval_id")), None)
        if not target:
            self._send(404, {"error": "approval not found"})
            return

        target["status"] = "approved" if payload.get("approved") else "rejected"
        target["approved"] = bool(payload.get("approved"))
        target["approver"] = payload.get("approver") or "web_operator"
        target["reason"] = payload.get("reason") or ("审批通过" if target["approved"] else "审批拒绝")
        target["decided_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        record_decision(target)
        save_pending([a for a in approvals if a["id"] != target["id"]])
        self._send(200, {"decision": target})

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[approval-server] %s\n" % (fmt % args))


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = ThreadingHTTPServer(("127.0.0.1", port), ApprovalHandler)
    print(f"审批服务已启动: http://127.0.0.1:{port}/approval.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
