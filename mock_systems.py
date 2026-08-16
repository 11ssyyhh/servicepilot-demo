# -*- coding: utf-8 -*-
"""
Mock业务系统模块
模拟订单系统、工单系统、支付系统、物流系统
通过MCP适配器模式对接，初赛使用Mock，复赛接入真实系统
所有接口返回标准化结果，与真实API保持相同Schema
"""

import time
import uuid
from typing import Any, Dict, Optional


class MockOrderSystem:
    """模拟订单系统"""
    
    def __init__(self):
        # 模拟订单数据库
        self.orders = {
            "ORD20260816001": {
                "order_id": "ORD20260816001",
                "status": "shipped",  # pending / paid / shipped / delivered / cancelled
                "product": "智能蓝牙耳机 Pro",
                "amount": 299.00,
                "create_time": "2026-08-14 10:30:00",
                "address": "江苏省南京市江宁区xxx路1号",
                "phone": "138****8888",
                "logistics": {"company": "顺丰速运", "tracking_no": "SF1234567890", 
                              "status": "运输中", "last_update": "2026-08-15 18:00:00 已到达南京转运中心"},
            },
            "ORD20260816002": {
                "order_id": "ORD20260816002",
                "status": "delivered",
                "product": "机械键盘 RGB版",
                "amount": 459.00,
                "create_time": "2026-08-10 14:20:00",
                "address": "江苏省南京市鼓楼区yyy路2号",
                "phone": "139****9999",
                "logistics": {"company": "京东物流", "tracking_no": "JD9876543210",
                              "status": "已签收", "last_update": "2026-08-12 09:30:00 已签收"},
            },
        }
        # 幂等与回滚记录
        self.refund_records = {}
        self.refund_previous_status = {}
        self.rollback_records = []
    
    def query_order(self, order_id: str = None, phone: str = None) -> Dict[str, Any]:
        """查询订单"""
        time.sleep(0.1)  # 模拟网络延迟
        if order_id and order_id in self.orders:
            return {"success": True, "data": self.orders[order_id]}
        if phone:
            for o in self.orders.values():
                if phone in o["phone"]:
                    return {"success": True, "data": o}
        return {"success": False, "error": "订单不存在，请核对订单号"}
    
    def update_address(self, order_id: str, new_address: str) -> Dict[str, Any]:
        """修改收货地址 (仅未发货订单可改)"""
        time.sleep(0.1)
        if order_id not in self.orders:
            return {"success": False, "error": "订单不存在"}
        order = self.orders[order_id]
        if order["status"] != "pending":
            return {"success": False, "error": f"订单状态为{order['status']}，无法修改地址（仅未发货订单可修改）"}
        old_address = order["address"]
        order["address"] = new_address
        return {"success": True, "data": {"order_id": order_id, "old_address": old_address, 
                                          "new_address": new_address, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}}
    
    def process_refund(self, order_id: str, reason: str, amount: float = None,
                       idempotency_key: str = None) -> Dict[str, Any]:
        """处理退款 (高风险，需审批后调用)"""
        time.sleep(0.2)
        if order_id not in self.orders:
            return {"success": False, "error": "订单不存在"}
        # 幂等：同一幂等键重复调用返回同一结果
        if idempotency_key and idempotency_key in self.refund_records:
            record = dict(self.refund_records[idempotency_key])
            record["data"] = dict(record["data"])
            record["data"]["duplicate"] = True
            return record
        order = self.orders[order_id]
        refund_amount = amount or order["amount"]
        refund_id = "RF" + str(uuid.uuid4())[:8].upper()
        previous_status = order["status"]
        self.refund_previous_status[order_id] = previous_status
        order["status"] = "refunded"
        result = {
            "success": True,
            "data": {
                "refund_id": refund_id,
                "order_id": order_id,
                "amount": refund_amount,
                "reason": reason,
                "status": "processing",
                "expected_arrival": "1-3个工作日原路返回",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "rollback_point": {"order_id": order_id, "previous_status": previous_status},
                "idempotency_key": idempotency_key,
            },
        }
        if idempotency_key:
            self.refund_records[idempotency_key] = result
        return result

    def rollback_refund(self, order_id: str, refund_id: str = None,
                        idempotency_key: str = None) -> Dict[str, Any]:
        """回滚退款，恢复订单到退款前状态"""
        time.sleep(0.1)
        if order_id not in self.orders:
            return {"success": False, "error": "订单不存在"}
        previous = self.refund_previous_status.get(order_id)
        if not previous:
            return {"success": False, "error": "无可用回滚点"}
        if previous in ("pending", "paid", "shipped", "delivered"):
            self.orders[order_id]["status"] = previous
        rollback = {
            "rollback_id": "RB" + str(uuid.uuid4())[:8].upper(),
            "order_id": order_id,
            "refund_id": refund_id,
            "restored_status": previous,
            "idempotency_key": idempotency_key,
            "rolled_back_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.rollback_records.append(rollback)
        return {"success": True, "data": rollback}


class MockTicketSystem:
    """模拟工单系统"""
    
    def __init__(self):
        self.tickets = {}
        self.idempotency_records = {}
    
    def create_ticket(self, problem_desc: str, priority: str = "normal",
                      idempotency_key: str = None) -> Dict[str, Any]:
        """创建人工工单"""
        time.sleep(0.1)
        if idempotency_key and idempotency_key in self.idempotency_records:
            record = dict(self.idempotency_records[idempotency_key])
            record["data"] = dict(record["data"])
            record["data"]["duplicate"] = True
            return record
        ticket_id = "TK" + time.strftime("%Y%m%d") + str(len(self.tickets) + 1).zfill(3)
        ticket = {
            "ticket_id": ticket_id,
            "problem": problem_desc,
            "priority": priority,
            "status": "open",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expected_response": "2小时内" if priority == "high" else "24小时内",
            "idempotency_key": idempotency_key,
        }
        self.tickets[ticket_id] = ticket
        result = {"success": True, "data": ticket}
        if idempotency_key:
            self.idempotency_records[idempotency_key] = result
        return result


class MockPaymentSystem:
    """模拟支付系统"""
    
    def query_payment(self, order_id: str) -> Dict[str, Any]:
        """查询支付状态"""
        return {"success": True, "data": {"order_id": order_id, "paid": True, 
                                          "method": "微信支付", "paid_at": "2026-08-14 10:31:00"}}


class MockLogisticsSystem:
    """模拟物流系统"""
    
    def query_logistics(self, tracking_no: str) -> Dict[str, Any]:
        """查询物流轨迹"""
        time.sleep(0.1)
        return {
            "success": True,
            "data": {
                "tracking_no": tracking_no,
                "company": "顺丰速运",
                "status": "运输中",
                "traces": [
                    {"time": "2026-08-15 18:00:00", "location": "南京转运中心", "status": "到达"},
                    {"time": "2026-08-15 08:00:00", "location": "上海转运中心", "status": "发出"},
                    {"time": "2026-08-14 20:00:00", "location": "杭州仓库", "status": "揽收"},
                ]
            }
        }


class MockBusinessSystems:
    """
    业务系统聚合 - 模拟MCP适配器
    统一对接订单、工单、支付、物流系统
    真实环境中通过MCP协议调用，这里用Mock实现
    """
    
    def __init__(self):
        self.order_system = MockOrderSystem()
        self.ticket_system = MockTicketSystem()
        self.payment_system = MockPaymentSystem()
        self.logistics_system = MockLogisticsSystem()
    
    # 订单相关
    def query_order(self, order_id=None, phone=None):
        return self.order_system.query_order(order_id, phone)
    
    def update_address(self, order_id, new_address):
        return self.order_system.update_address(order_id, new_address)
    
    def process_refund(self, order_id, reason, amount=None, idempotency_key=None):
        return self.order_system.process_refund(order_id, reason, amount, idempotency_key)

    def rollback_refund(self, order_id, refund_id=None, idempotency_key=None):
        return self.order_system.rollback_refund(order_id, refund_id, idempotency_key)
    
    # 工单相关
    def create_ticket(self, problem_desc, priority="normal", idempotency_key=None):
        return self.ticket_system.create_ticket(problem_desc, priority, idempotency_key)
    
    # 支付相关
    def query_payment(self, order_id):
        return self.payment_system.query_payment(order_id)
    
    # 物流相关
    def query_logistics(self, tracking_no):
        return self.logistics_system.query_logistics(tracking_no)
    
    def get_system_status(self) -> Dict:
        """获取所有系统状态 (用于健康检查)"""
        return {
            "order_system": "healthy",
            "ticket_system": "healthy",
            "payment_system": "healthy",
            "logistics_system": "healthy",
            "mock_mode": True,
        }
