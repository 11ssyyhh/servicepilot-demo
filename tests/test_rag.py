# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skills import FAQRetrieval  # noqa: E402


class RAGTest(unittest.TestCase):

    def setUp(self):
        self.skill = FAQRetrieval()

    def test_refund_query_has_meaningful_confidence(self):
        result = self.skill.execute(
            "我要退款，订单ORD20260816001不想要了",
            intent_hint="refund",
        )
        self.assertGreaterEqual(result["confidence"], 0.4)
        self.assertEqual(result["result"][0]["category"], "refund")
        self.assertIn("source", result["result"][0])

    def test_order_query_has_meaningful_confidence(self):
        result = self.skill.execute(
            "我的订单ORD20260816001现在什么状态了？帮我查一下",
            intent_hint="order_query",
        )
        self.assertGreaterEqual(result["confidence"], 0.4)
        self.assertEqual(result["result"][0]["category"], "order_query")

    def test_unknown_query_returns_low_confidence(self):
        result = self.skill.execute("今天天气怎么样", intent_hint="other")
        self.assertLess(result["confidence"], 0.4)


if __name__ == "__main__":
    unittest.main()
