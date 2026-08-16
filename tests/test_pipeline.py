# -*- coding: utf-8 -*-

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers import make_manager  # noqa: E402


class PipelineTest(unittest.TestCase):

    def test_order_query_closed_loop(self):
        manager = make_manager()
        state = manager.run("我的订单ORD20260816001现在什么状态了？帮我查一下")
        self.assertEqual(state.intent, "order_query")
        self.assertTrue(state.issue_resolved)
        self.assertGreaterEqual(state.retrieval_confidence, 0.3)
        self.assertTrue(any(r.skill_name == "OrderQuery" and r.success
                            for r in state.execution_records))

    def test_refund_approved_flow(self):
        manager = make_manager()
        state = manager.run("我要退款，订单ORD20260816001不想要了", auto_approve=True)
        self.assertEqual(state.intent, "refund")
        self.assertTrue(state.issue_resolved)
        self.assertTrue(any(a["status"] == "approved" for a in state.approval_history))
        refund = next(r for r in state.execution_records
                      if r.skill_name == "RefundProcess")
        self.assertTrue(refund.success)
        self.assertIsNotNone(refund.idempotency_key)
        self.assertIsNotNone(refund.rollback_point)

    def test_refund_rejected_goes_human(self):
        manager = make_manager()
        state = manager.run("我要退款，订单ORD20260816002不想要了", auto_approve=False)
        self.assertEqual(state.intent, "refund")
        self.assertFalse(state.issue_resolved)
        self.assertTrue(state.pending_approvals)
        self.assertTrue(state.tickets_created)

    def test_address_failure_goes_human(self):
        manager = make_manager()
        state = manager.run("帮我把订单ORD20260816001的收货地址改成南京市玄武区zzz路3号")
        self.assertEqual(state.intent, "address_change")
        self.assertFalse(state.issue_resolved)
        self.assertTrue(any(r.skill_name == "AddressUpdate" and not r.success
                            for r in state.execution_records))
        self.assertTrue(state.tickets_created)

    def test_complaint_creates_high_priority_ticket(self):
        manager = make_manager()
        state = manager.run("你们什么垃圾客服！等了三天都没解决问题，我要投诉！")
        self.assertEqual(state.intent, "complaint")
        self.assertTrue(state.issue_resolved)
        self.assertTrue(any(t.get("priority") == "high" for t in state.tickets_created))

    def test_evidence_files_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_manager(tmp_path=tmp)
            manager.run("我的订单ORD20260816001现在什么状态了？帮我查一下")
            out = Path(tmp)
            for name in ("trace.jsonl", "logs.jsonl", "metrics.json",
                         "session.json", "summary.json"):
                self.assertTrue((out / name).exists(), f"{name} 未生成")


if __name__ == "__main__":
    unittest.main()
