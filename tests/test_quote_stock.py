"""見積SKUの数量。外部APIとSQL Serverには接続しない。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"))

from amazon_gate import decide  # noqa: E402
from engine import build_master  # noqa: E402
from quote_stock import QUOTE_SQL, quote_quantity, rows_to_quotes  # noqa: E402


def header(customer: int = 300) -> dict:
    return {"見積番号": "2003739", "得意先CD": customer}


def line(line_no: int, code: str, webcd: str, in_view: bool = True, kind: str = "1", qty: int = 2) -> dict:
    return {"行番号": line_no, "区分": kind, "商品CD": code, "webcd": webcd, "in_view": in_view, "数量": qty}


class QuoteStockTest(unittest.TestCase):
    def test_quantity_is_minimum_available_stock(self) -> None:
        result = quote_quantity(
            header(),
            [line(1, "4902380211495", "499119"), line(2, "4902380221883", "524640", kind="2")],
            {"499119": 6, "524640": 2},
        )
        self.assertEqual(result, {"quantity": 2, "webcd": "524640", "行番号": 2})

    def test_line_quantity_does_not_divide_stock(self) -> None:
        result = quote_quantity(header(), [line(1, "4902380211495", "499119", qty=10)], {"499119": 4})
        self.assertEqual(result["quantity"], 4)

    def test_same_minimum_keeps_smaller_line_number(self) -> None:
        result = quote_quantity(
            header(),
            [line(4, "4902380222064", "548678"), line(1, "4902380211495", "499119")],
            {"548678": 3, "499119": 3},
        )
        self.assertEqual(result["webcd"], "499119")
        self.assertEqual(result["行番号"], 1)

    def test_special_codes_and_blank_webcd_are_ignored(self) -> None:
        result = quote_quantity(
            header(),
            [
                line(1, "0030000000000", "219611"),
                line(2, "4902380211495", ""),
                line(3, "4902380221883", "524640"),
            ],
            {"219611": 0, "524640": 5},
        )
        self.assertEqual(result["quantity"], 5)
        self.assertEqual(result["webcd"], "524640")

    def test_missing_view_row_does_not_decide_quantity(self) -> None:
        result = quote_quantity(
            header(),
            [line(1, "4959431111846", "218559", in_view=False), line(2, "4902380221883", "524640")],
            {"218559": 9, "524640": 2},
        )
        self.assertIsNone(result)

    def test_known_zero_is_the_minimum(self) -> None:
        result = quote_quantity(
            header(),
            [line(1, "4902380211495", "499119"), line(2, "4902380221883", "524640")],
            {"499119": 6},
        )
        self.assertEqual(result["quantity"], 0)
        self.assertEqual(result["webcd"], "524640")

    def test_wrong_customer_or_no_lines_do_not_decide(self) -> None:
        rows = [line(1, "4902380211495", "499119")]
        self.assertIsNone(quote_quantity(None, rows, {"499119": 4}))
        self.assertIsNone(quote_quantity(header(100), rows, {"499119": 4}))
        self.assertIsNone(quote_quantity(header(), [line(1, "0030000000000", "219611")], {"219611": 1}))

    def test_rows_keep_customer_and_view_flag(self) -> None:
        parsed = rows_to_quotes([(2003739, 300, 1, "1", "4902380211495", 499119, 1)])
        self.assertEqual(parsed["2003739"]["header"]["得意先CD"], 300)
        self.assertEqual(parsed["2003739"]["lines"][0]["webcd"], "499119")
        self.assertTrue(parsed["2003739"]["lines"][0]["in_view"])

    def test_sql_is_select_only(self) -> None:
        statement = " ".join(QUOTE_SQL.split()).upper()
        self.assertTrue(statement.startswith("SELECT "))
        for word in ("INSERT", "UPDATE", "DELETE", "MERGE", "ALTER", "DROP", "EXEC"):
            self.assertNotIn(word, statement)

    def test_decided_quote_can_hold_the_batch(self) -> None:
        listings = [
            {"sku": "2003739", "default_quantity": 20},
            {"sku": "263860", "default_quantity": 1},
        ]
        quotes = {"2003739": {"quantity": 2, "webcd": "524640", "行番号": 2}}
        result = decide(listings, build_master({"263860": 3}, {}), declared_count=2, quotes=quotes)
        self.assertEqual(result.action, "sent")
        self.assertEqual(result.updates, [{"sku": "263860", "quantity": 3, "channel": "DEFAULT"}])
        self.assertEqual([row["sku"] for row in result.held], ["2003739"])

    def test_undecided_quote_skips_only_itself(self) -> None:
        listings = [
            {"sku": "2003739", "default_quantity": 20},
            {"sku": "263860", "default_quantity": 1},
        ]
        result = decide(listings, build_master({"263860": 3}, {}), declared_count=2, quotes={})
        self.assertEqual(result.action, "sent")
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.updates, [{"sku": "263860", "quantity": 3, "channel": "DEFAULT"}])


if __name__ == "__main__":
    unittest.main()
