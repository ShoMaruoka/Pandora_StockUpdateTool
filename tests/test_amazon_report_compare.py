"""出品レポートと出品API一覧の突き合わせ。外部APIは呼ばない。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "testtools"))

from amazon_report_compare import compare  # noqa: E402


class ReportCompareTest(unittest.TestCase):
    def test_compare_kinds(self) -> None:
        report = [
            {"sku": "1", "quantity": "3", "channel": "DEFAULT", "status": ""},
            {"sku": "2", "quantity": "5", "channel": "DEFAULT", "status": ""},
            {"sku": "3", "quantity": "1", "channel": "DEFAULT", "status": ""},
        ]
        api = [
            {"sku": "1", "default_quantity": 3},
            {"sku": "2", "default_quantity": 4},
            {"sku": "4", "default_quantity": 0},
        ]
        kinds = {row["出品者SKU"]: row["区分"] for row in compare(report, api)}
        self.assertEqual(kinds, {"1": "一致", "2": "数量違い", "3": "レポートだけ", "4": "APIだけ"})


if __name__ == "__main__":
    unittest.main()
