# -*- coding: utf-8 -*-

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers import make_manager  # noqa: E402


class ObservabilityTest(unittest.TestCase):

    def test_trace_log_metrics_session_summary_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_manager(tmp_path=tmp)
            manager.run("我的订单ORD20260816001现在什么状态了？帮我查一下")
            out = Path(tmp)

            trace = [json.loads(line) for line in
                     (out / "trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            names = {span["name"] for span in trace}
            self.assertIn("IntentRouter", names)
            self.assertIn("KnowledgeRetriever", names)
            self.assertIn("mcp.OrderQuery", names)

            logs = [(json.loads(line)["event"]) for line in
                    (out / "logs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertIn("intent.routed", logs)

            metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(metrics["agents_called"], 7)
            self.assertGreaterEqual(metrics["mcp_calls"], 1)
            self.assertGreaterEqual(metrics["llm_calls"], 1)

            session = json.loads((out / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(session["intent"], "order_query")
            self.assertTrue(session["issue_resolved"])

            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["trace_id"], session["trace_id"])

    def test_masking_applied_to_session_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_manager(tmp_path=tmp)
            manager.run("我手机号13812345678，帮我查订单ORD20260816001")
            session = json.loads(
                (Path(tmp) / "session.json").read_text(encoding="utf-8")
            )
            contents = [m["content"] for m in session["messages"] if m["role"] == "user"]
            self.assertTrue(all("1381234" not in c and "138****5678" in c for c in contents))


if __name__ == "__main__":
    unittest.main()
