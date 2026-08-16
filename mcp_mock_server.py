# -*- coding: utf-8 -*-
"""
MCP 等价 Mock Server

用 HTTP + JSON-RPC 形式暴露与 MCP 同构的工具契约：tools/list、tools/call。
复赛接入真实系统时仅替换 transport/backend，调用链 Schema 不变。

运行: python mcp_mock_server.py [port]   # 默认 8001
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict
from urllib.parse import urlparse

from mock_systems import MockBusinessSystems


class MCPMockServer:
    """工具注册表 + 调用分发"""

    def __init__(self):
        self.mock = MockBusinessSystems()
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._register()

    def _register_tool(self, name: str, description: str, handler: Callable,
                       input_schema: Dict, risk_level: str = "L0") -> None:
        self.tools[name] = {
            "name": name,
            "description": description,
            "risk_level": risk_level,
            "inputSchema": input_schema,
            "handler": handler,
        }

    def _register(self) -> None:
        self._register_tool(
            "order_system.query_order", "查询订单状态",
            lambda args: self.mock.query_order(args.get("order_id"), args.get("phone")),
            {"type": "object", "required": ["order_id"],
             "properties": {"order_id": {"type": "string"}, "phone": {"type": "string"}}},
            risk_level="L0",
        )
        self._register_tool(
            "order_system.update_address", "修改收货地址（仅未发货订单）",
            lambda args: self.mock.update_address(args.get("order_id"), args.get("new_address")),
            {"type": "object", "required": ["order_id", "new_address"],
             "properties": {"order_id": {"type": "string"},
                            "new_address": {"type": "string"},
                            "idempotency_key": {"type": "string"}}},
            risk_level="L1",
        )
        self._register_tool(
            "order_system.process_refund", "处理退款（L2，需审批令牌）",
            lambda args: self.mock.process_refund(
                args.get("order_id"), args.get("reason"), args.get("amount"),
                args.get("idempotency_key")),
            {"type": "object", "required": ["order_id", "reason", "approval_id"],
             "properties": {"order_id": {"type": "string"},
                            "reason": {"type": "string"},
                            "amount": {"type": "number"},
                            "approval_id": {"type": "string"},
                            "idempotency_key": {"type": "string"}}},
            risk_level="L2",
        )
        self._register_tool(
            "order_system.rollback_refund", "回滚退款",
            lambda args: self.mock.rollback_refund(
                args.get("order_id"), args.get("refund_id"), args.get("idempotency_key")),
            {"type": "object", "required": ["order_id"],
             "properties": {"order_id": {"type": "string"},
                            "refund_id": {"type": "string"},
                            "idempotency_key": {"type": "string"}}},
            risk_level="L2",
        )
        self._register_tool(
            "ticket_system.create_ticket", "创建人工工单",
            lambda args: self.mock.create_ticket(
                args.get("problem_desc"), args.get("priority", "normal"),
                args.get("idempotency_key")),
            {"type": "object", "required": ["problem_desc"],
             "properties": {"problem_desc": {"type": "string"},
                            "priority": {"type": "string", "enum": ["normal", "high"]},
                            "idempotency_key": {"type": "string"}}},
            risk_level="L0",
        )
        self._register_tool(
            "payment_system.query_payment", "查询支付状态",
            lambda args: self.mock.query_payment(args.get("order_id")),
            {"type": "object", "required": ["order_id"],
             "properties": {"order_id": {"type": "string"}}},
            risk_level="L0",
        )
        self._register_tool(
            "logistics_system.query_logistics", "查询物流轨迹",
            lambda args: self.mock.query_logistics(args.get("tracking_no")),
            {"type": "object", "required": ["tracking_no"],
             "properties": {"tracking_no": {"type": "string"}}},
            risk_level="L0",
        )

    def list_tools(self) -> list:
        return [
            {"name": name, "description": tool["description"],
             "risk_level": tool["risk_level"], "inputSchema": tool["inputSchema"]}
            for name, tool in self.tools.items()
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any],
                  idempotency_key: str = None) -> Dict[str, Any]:
        tool = self.tools.get(name)
        if not tool:
            return {"success": False, "error": f"tool not found: {name}"}
        args = dict(arguments or {})
        if idempotency_key and name in ("order_system.update_address",
                                         "order_system.process_refund",
                                         "order_system.rollback_refund",
                                         "ticket_system.create_ticket"):
            args["idempotency_key"] = idempotency_key
        result = tool["handler"](args)
        return result


class MCPHandler(BaseHTTPRequestHandler):
    server: "MCPMockHTTPServer"

    def _send(self, code: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._send(200, {"status": "ok", "mock_mode": True,
                             "tools": len(self.server.mcp.list_tools())})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/mcp":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            request = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            return

        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {}) or {}
        if method == "tools/list":
            self._send(200, {"jsonrpc": "2.0", "id": request_id,
                             "result": {"tools": self.server.mcp.list_tools()}})
            return
        if method == "tools/call":
            result = self.server.mcp.call_tool(
                params.get("name"), params.get("arguments", {}),
                params.get("idempotency_key"),
            )
            self._send(200, {"jsonrpc": "2.0", "id": request_id, "result": result})
            return
        self._send(200, {"jsonrpc": "2.0", "id": request_id,
                         "error": {"code": -32601, "message": "method not found"}})

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[mcp-mock] %s\n" % (fmt % args))


class MCPMockHTTPServer(ThreadingHTTPServer):
    def __init__(self, addr, handler):
        super().__init__(addr, handler)
        self.mcp = MCPMockServer()


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    server = MCPMockHTTPServer(("127.0.0.1", port), MCPHandler)
    print(f"MCP Mock Server 已启动: http://127.0.0.1:{port}/mcp")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
