# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from masking import mask_pii  # noqa: E402


class MaskingTest(unittest.TestCase):

    def test_phone_masked(self):
        text, hits = mask_pii("联系电话13812345678")
        self.assertIn("138****5678", text)
        self.assertNotIn("13812345678", text)
        self.assertEqual(hits["phone"], 1)

    def test_email_masked(self):
        text, hits = mask_pii("联系 test@example.com 处理")
        self.assertIn("te***@example.com", text)
        self.assertEqual(hits["email"], 1)

    def test_address_masked(self):
        text, hits = mask_pii("地址是江苏省南京市玄武区中山路1号")
        self.assertNotIn("中山路1号", text)
        self.assertGreaterEqual(hits["address"], 1)


if __name__ == "__main__":
    unittest.main()
