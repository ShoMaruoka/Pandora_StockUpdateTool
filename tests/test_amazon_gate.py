"""Amazonへ送るか止めるかの判断。外部APIには接続しない。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"))

from amazon_gate import decide  # noqa: E402
from engine import build_master  # noqa: E402


def master() -> dict:
    return build_master({"307679": 2, "263860": 3}, {})


class AmazonGateTest(unittest.TestCase):
    def test_severe_drop_skips_only_that_sku(self) -> None:
        listings = [
            {"sku": "307679", "default_quantity": 10},
            {"sku": "263860", "default_quantity": 1},
        ]
        result = decide(listings, master(), declared_count=2)
        self.assertEqual(result.action, "sent")
        self.assertEqual(result.updates, [{"sku": "263860", "quantity": 3, "channel": "DEFAULT"}])
        self.assertEqual([row["sku"] for row in result.held], ["307679"])
        self.assertEqual(result.sent, 1)

    def test_previous_under_ten_going_to_zero_is_sent(self) -> None:
        empty = build_master({"307679": 0}, {})
        result = decide([{"sku": "307679", "default_quantity": 9}], empty, declared_count=1)
        self.assertEqual(result.updates, [{"sku": "307679", "quantity": 0, "channel": "DEFAULT"}])
        self.assertEqual(result.held, [])

    def test_previous_ten_going_to_zero_is_held(self) -> None:
        empty = build_master({"307679": 0}, {})
        result = decide([{"sku": "307679", "default_quantity": 10}], empty, declared_count=1)
        self.assertEqual(result.updates, [])
        self.assertEqual([row["sku"] for row in result.held], ["307679"])

    def test_same_quantity_is_not_sent(self) -> None:
        listings = [
            {"sku": "307679", "default_quantity": 2},
            {"sku": "263860", "default_quantity": 4},
        ]
        result = decide(listings, master(), declared_count=2)
        self.assertEqual(result.updates, [{"sku": "263860", "quantity": 3, "channel": "DEFAULT"}])
        self.assertEqual(result.unchanged, ["307679"])
        self.assertEqual(result.sent, 1)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.held, [])

    def test_zero_to_zero_is_not_sent(self) -> None:
        empty = build_master({"307679": 0}, {})
        result = decide([{"sku": "307679", "default_quantity": 0}], empty, declared_count=1)
        self.assertEqual(result.updates, [])
        self.assertEqual(result.unchanged, ["307679"])

    def test_zero_previous_quantity_is_not_a_drop(self) -> None:
        stock = build_master({"307679": 3}, {})
        listings = [{"sku": "307679", "default_quantity": 0}]
        result = decide(listings, stock, declared_count=1)
        self.assertEqual(result.action, "sent")
        self.assertEqual(result.updates, [{"sku": "307679", "quantity": 3, "channel": "DEFAULT"}])
        self.assertEqual(result.held, [])

    def test_short_listing_fails_without_updates(self) -> None:
        listings = [{"sku": "263860", "default_quantity": 3}]
        result = decide(listings, master(), declared_count=2)
        self.assertEqual(result.action, "failed")
        self.assertEqual(result.updates, [])
        self.assertEqual(result.sent, 0)

    def test_quote_and_unknown_sku_are_skipped(self) -> None:
        listings = [
            {"sku": "2003739", "default_quantity": 20},
            {"sku": "999999", "default_quantity": 4},
            {"sku": "263860", "default_quantity": 1},
        ]
        result = decide(listings, master(), declared_count=3)
        self.assertEqual(result.action, "sent")
        self.assertEqual(result.skipped, 2)
        self.assertEqual(result.updates, [{"sku": "263860", "quantity": 3, "channel": "DEFAULT"}])
        self.assertTrue(all(row["channel"] == "DEFAULT" for row in result.updates))


if __name__ == "__main__":
    unittest.main()
