# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mock_systems import MockBusinessSystems  # noqa: E402
from skills import (  # noqa: E402
    AddressUpdate,
    RefundProcess,
    RollbackOperation,
    register_all_skills,
)


class SkillsTest(unittest.TestCase):

    def setUp(self):
        self.mock = MockBusinessSystems()
        self.skills = register_all_skills(self.mock)

    def test_refund_requires_approval(self):
        result = self.skills["RefundProcess"].execute(
            order_id="ORD20260816001", reason="测试", approved=False
        )
        self.assertFalse(result["success"])
        self.assertTrue(result["need_approval"])
        self.assertEqual(result["risk_level"], "L2")

    def test_refund_with_approval_and_idempotency(self):
        skill = self.skills["RefundProcess"]
        r1 = skill.execute(order_id="ORD20260816001", reason="测试",
                           approved=True, idempotency_key="idem-skill-1",
                           approver="admin", approval_id="appr-1")
        r2 = skill.execute(order_id="ORD20260816001", reason="测试",
                           approved=True, idempotency_key="idem-skill-1",
                           approver="admin", approval_id="appr-1")
        self.assertTrue(r1["success"])
        self.assertTrue(r2["success"])
        self.assertEqual(r1["result"]["refund_id"], r2["result"]["refund_id"])
        self.assertIsNotNone(r1["rollback_point"])

    def test_address_update_fails_on_shipped_order(self):
        result = self.skills["AddressUpdate"].execute(
            order_id="ORD20260816001",
            new_address="江苏省南京市玄武区新街口1号",
            idempotency_key="idem-addr-1",
        )
        self.assertFalse(result["success"])
        self.assertIn("无法修改地址", result["error"])

    def test_rollback_skill_restores_status(self):
        refund = self.skills["RefundProcess"].execute(
            order_id="ORD20260816002", reason="测试",
            approved=True, idempotency_key="idem-rb-skill",
        )
        rollback = self.skills["RollbackOperation"].execute(
            order_id="ORD20260816002",
            refund_id=refund["result"]["refund_id"],
            idempotency_key="idem-rb-skill-2",
        )
        self.assertTrue(rollback["success"])
        self.assertEqual(self.mock.query_order("ORD20260816002")["data"]["status"], "delivered")


if __name__ == "__main__":
    unittest.main()
