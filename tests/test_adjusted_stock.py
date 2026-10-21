"""調整在庫と、既存の販売可能在庫計算への受け渡し。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"))

from adjusted_stock import adjusted_stock  # noqa: E402
from engine import build_master, calc, parse_sku  # noqa: E402


class AdjustedStockTest(unittest.TestCase):
    def test_half_rounds_away_from_zero(self) -> None:
        self.assertEqual(adjusted_stock({120: 5}), 3)
        self.assertEqual(adjusted_stock({120: 4}), 2)
        self.assertEqual(adjusted_stock({120: 1}), 1)
        self.assertEqual(adjusted_stock({120: 0}), 0)

    def test_fukuoka_is_excluded(self) -> None:
        without = adjusted_stock({120: 3, 400: 2})
        with_fukuoka = adjusted_stock({120: 3, 400: 2, 180: 100})
        self.assertEqual(without, 3)
        self.assertEqual(with_fukuoka, without)

    def test_existing_sku_rules_use_adjusted_stock(self) -> None:
        wholesale = adjusted_stock({120: 2, 400: 1, 405: 1, 110: 1, 150: 0, 180: 50})
        master = build_master({"307679": wholesale}, {"307679": 4})

        direct, direct_status, _ = calc(parse_sku("307679"), master)
        quote, quote_status, _ = calc(parse_sku("2003739"), master)
        missing, missing_status, _ = calc(parse_sku("263860"), master)

        self.assertEqual(wholesale, 3)
        self.assertEqual((direct, direct_status), (7, "OK"))
        self.assertIsNone(quote)
        self.assertEqual(quote_status, "見積り構成未登録")
        self.assertIsNone(missing)
        self.assertEqual(missing_status, "WebCD未一致")


if __name__ == "__main__":
    unittest.main()
