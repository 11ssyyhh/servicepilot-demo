# -*- coding: utf-8 -*-

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluate import run_evaluation  # noqa: E402


class EvalTest(unittest.TestCase):

    def test_evaluation_passes_golden_dataset(self):
        report = run_evaluation()
        self.assertEqual(report["pass_rate"], 1.0)
        self.assertEqual(report["intent_accuracy"], 1.0)
        self.assertEqual(report["resolution_accuracy"], 1.0)
        report_path = ROOT / "output" / "eval_report.json"
        self.assertTrue(report_path.exists())
        data = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["cases"]), 12)


if __name__ == "__main__":
    unittest.main()
