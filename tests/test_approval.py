# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers import make_manager  # noqa: E402
from shared_state import SharedState  # noqa: E402


class ApprovalTest(unittest.TestCase):

    def test_approval_requires_high_risk_token(self):
        manager = make_manager()
        state = manager.run("我要退款，订单ORD20260816001不想要了", auto_approve=True)
        approval = state.approval_history[0]
        self.assertEqual(approval["action"], "process_refund")
        self.assertEqual(approval["risk_level"], "L2")
        self.assertTrue(approval["approved"])
        self.assertIn("evidence", approval)
        self.assertTrue(any(e["event"] == "approval.decided" for e in state.audit_events))

    def test_rejected_approval_has_audit_and_ticket(self):
        manager = make_manager()
        state = manager.run("我要退款，订单ORD20260816002不想要了", auto_approve=False)
        self.assertEqual(state.pending_approvals[0]["status"], "pending")
        self.assertFalse(any(r.skill_name == "RefundProcess" for r in state.execution_records))
        self.assertTrue(state.tickets_created)

    def test_refund_idempotency(self):
        from mock_systems import MockBusinessSystems
        mock = MockBusinessSystems()
        r1 = mock.process_refund("ORD20260816001", "测试", idempotency_key="idem-test-1")
        r2 = mock.process_refund("ORD20260816001", "测试", idempotency_key="idem-test-1")
        self.assertTrue(r1["success"])
        self.assertTrue(r2["success"])
        self.assertEqual(r1["data"]["refund_id"], r2["data"]["refund_id"])
        self.assertTrue(r2["data"]["duplicate"])

    def test_rollback_restores_status(self):
        from mock_systems import MockBusinessSystems
        mock = MockBusinessSystems()
        before = mock.query_order("ORD20260816001")["data"]["status"]
        refund = mock.process_refund("ORD20260816001", "测试", idempotency_key="idem-rb-1")
        rollback = mock.rollback_refund("ORD20260816001", refund["data"]["refund_id"])
        self.assertTrue(rollback["success"])
        after = mock.query_order("ORD20260816001")["data"]["status"]
        self.assertEqual(after, before)

    def test_resume_after_manual_decision_executes_refund(self):
        manager = make_manager()
        state = manager.run("我要退款，订单ORD20260816001不想要了", auto_approve=False)
        approval = state.pending_approvals[0]
        self.assertEqual(approval["status"], "pending")

        state.approve(approval["id"], approved=True,
                      approver="web_operator", reason="人工审批通过")
        manager.resume(state, start_at="ToolExecutor")

        self.assertTrue(any(r.skill_name == "RefundProcess" and r.success
                            for r in state.execution_records))
        self.assertTrue(state.issue_resolved)
        self.assertIn("approved", approval["status"])

    def test_state_roundtrip_preserves_plan_and_execution(self):
        manager = make_manager()
        state = manager.run("我的订单ORD20260816001现在什么状态了？帮我查一下")
        snapshot = state.to_dict(full=True)
        restored = SharedState.from_dict(snapshot)

        self.assertEqual(restored.session_id, state.session_id)
        self.assertEqual(len(restored.task_plan), len(state.task_plan))
        self.assertEqual(len(restored.execution_records), len(state.execution_records))
        self.assertEqual(restored.final_reply, state.final_reply)


if __name__ == "__main__":
    unittest.main()
