# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm import RuleLLM, create_llm_client  # noqa: E402


class LLMTest(unittest.TestCase):

    def test_rule_engine_is_default_fallback(self):
        client = create_llm_client()
        self.assertIsInstance(client, RuleLLM)

    def test_rule_engine_returns_deterministic_intent(self):
        client = RuleLLM()
        result = client.complete("用户消息:我要退款\n候选意图:refund")
        self.assertEqual(result.text.strip(), "refund")
        self.assertGreater(result.total_tokens, 0)
        self.assertGreaterEqual(result.latency_ms, 0)

    def test_rule_engine_keeps_reply_draft(self):
        client = RuleLLM()
        result = client.complete("草稿回复:您好，正在为您处理。\n请润色")
        self.assertEqual(result.text, "您好，正在为您处理。")


if __name__ == "__main__":
    unittest.main()
