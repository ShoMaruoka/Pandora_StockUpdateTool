"""出品レポートと出品APIの一覧から、対象SKUを決める。外部APIには接続しない。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from amazon_report import (  # noqa: E402
    choose_listings,
    decode_report,
    load_counts,
    next_counts,
    parse_report,
    save_counts,
)


def report(rows: list[tuple], state: str = "DONE") -> dict:
    return {
        "state": state,
        "rows": [
            {"sku": sku, "quantity": qty, "channel": channel, "name": rest[0] if rest else ""}
            for sku, qty, channel, *rest in rows
        ],
    }


def api(rows: list[tuple], declared: int | None = None, complete: bool = True) -> dict:
    listings = [{"sku": sku, "default_quantity": qty} for sku, qty in rows]
    return {"complete": complete, "declared": len(listings) if declared is None else declared, "listings": listings}


def choose(rep, app, previous=None) -> dict:
    return choose_listings(rep, app, previous or {})


class ParseReportTest(unittest.TestCase):
    def test_reads_japanese_headers_in_cp932(self) -> None:
        text = "商品名\t出品者SKU\t数量\tフルフィルメント・チャネル\nA\t307679\t3\tDEFAULT\n"
        rows = parse_report(decode_report(text.encode("cp932")))
        self.assertEqual(rows, [{"sku": "307679", "quantity": "3", "channel": "DEFAULT", "status": "", "name": "A"}])

    def test_reads_english_headers(self) -> None:
        rows = parse_report("seller-sku\tquantity\tfulfillment-channel\n263860\t\tAMAZON_JP\n")
        self.assertEqual(rows, [{"sku": "263860", "quantity": "", "channel": "AMAZON_JP", "status": "", "name": ""}])

    def test_missing_sku_column_stops(self) -> None:
        with self.assertRaises(SystemExit):
            parse_report("item-name\tquantity\nA\t1\n")


class ChooseListingsTest(unittest.TestCase):
    def test_both_usable_gives_union(self) -> None:
        result = choose(
            report([("A", "3", "DEFAULT"), ("B", "5", "DEFAULT")]),
            api([("A", 3), ("C", 7)]),
        )
        self.assertEqual(result["action"], "ok")
        self.assertTrue(result["report_used"])
        self.assertTrue(result["api_used"])
        sources = {row["sku"]: row["source"] for row in result["listings"]}
        self.assertEqual(sources, {"A": "both", "C": "api", "B": "report"})

    def test_name_prefers_api_then_report(self) -> None:
        result = choose(
            report([("A", "1", "DEFAULT", "レポート名A"), ("B", "1", "DEFAULT", "レポート名B"), ("C", "1", "DEFAULT", "レポート名C")]),
            {
                "complete": True,
                "declared": 2,
                "listings": [
                    {"sku": "A", "default_quantity": 1, "name": "API名A"},
                    {"sku": "B", "default_quantity": 1},
                ],
            },
        )
        names = {row["sku"]: row["name"] for row in result["listings"]}
        self.assertEqual(names, {"A": "API名A", "B": "レポート名B", "C": "レポート名C"})

    def test_product_type_from_api_is_carried(self) -> None:
        result = choose(
            report([("B", "1", "DEFAULT")]),
            {"complete": True, "declared": 1, "listings": [{"sku": "A", "default_quantity": 1, "product_type": "T"}]},
        )
        rows = {row["sku"]: row for row in result["listings"]}
        self.assertEqual(rows["A"]["product_type"], "T")
        self.assertNotIn("product_type", rows["B"])

    def test_sku_in_both_uses_api_quantity(self) -> None:
        result = choose(report([("A", "15", "DEFAULT")]), api([("A", 14)]))
        self.assertEqual(result["listings"], [{"sku": "A", "default_quantity": 14, "source": "both", "name": ""}])

    def test_report_only_sku_uses_default_row_and_ignores_fba(self) -> None:
        result = choose(
            report([("A", "9", "AMAZON_JP"), ("A", "4", "DEFAULT"), ("F", "8", "AMAZON_JP")]),
            api([]),
        )
        rows = {row["sku"]: row for row in result["listings"]}
        self.assertEqual(rows["A"]["default_quantity"], 4)
        self.assertNotIn("F", rows)

    def test_report_only_sku_without_quantity_is_none(self) -> None:
        result = choose(report([("A", "", "DEFAULT")]), api([]))
        self.assertIsNone(result["listings"][0]["default_quantity"])

    def test_report_failed_uses_api_only(self) -> None:
        result = choose(report([("B", "5", "DEFAULT")], state="FATAL"), api([("A", 3)]))
        self.assertEqual(result["action"], "ok")
        self.assertFalse(result["report_used"])
        self.assertEqual([row["sku"] for row in result["listings"]], ["A"])
        self.assertIn("FATAL", result["notes"][0])

    def test_report_missing_uses_api_only(self) -> None:
        result = choose(None, api([("A", 3)]))
        self.assertEqual(result["action"], "ok")
        self.assertFalse(result["report_used"])

    def test_api_incomplete_keeps_fetched_rows_in_union(self) -> None:
        result = choose(
            report([("B", "5", "DEFAULT")]),
            api([("A", 3)], declared=10, complete=False),
        )
        self.assertEqual(result["action"], "ok")
        self.assertFalse(result["api_used"])
        self.assertEqual({row["sku"] for row in result["listings"]}, {"A", "B"})
        self.assertIn("API", result["notes"][0])
        self.assertIn("1", result["notes"][0])
        self.assertIn("10", result["notes"][0])

    def test_both_unusable_fails_with_no_listings(self) -> None:
        result = choose(
            report([("B", "5", "DEFAULT")], state="CANCELLED"),
            api([("A", 3)], declared=10, complete=False),
        )
        self.assertEqual(result["action"], "failed")
        self.assertEqual(result["listings"], [])

    def test_api_search_error_fails_even_if_report_is_usable(self) -> None:
        result = choose(report([("B", "5", "DEFAULT")]), None)
        self.assertEqual(result["action"], "failed")
        self.assertEqual(result["listings"], [])


class PreviousNightTest(unittest.TestCase):
    def rows(self, n: int) -> list[tuple]:
        return [(str(i), "1", "DEFAULT") for i in range(n)]

    def test_report_drop_of_10_percent_makes_report_unusable(self) -> None:
        result = choose(report(self.rows(90)), api([("A", 1)]), {"report_rows": 100})
        self.assertFalse(result["report_used"])
        self.assertEqual([row["sku"] for row in result["listings"]], ["A"])

    def test_report_drop_under_10_percent_is_usable(self) -> None:
        result = choose(report(self.rows(91)), api([("A", 1)]), {"report_rows": 100})
        self.assertTrue(result["report_used"])

    def test_api_drop_of_10_percent_makes_api_unusable_but_keeps_rows(self) -> None:
        listings = [(str(i), 1) for i in range(90)]
        result = choose(report([("B", "5", "DEFAULT")]), api(listings), {"api_declared": 100})
        self.assertFalse(result["api_used"])
        self.assertTrue(result["report_used"])
        self.assertEqual(len(result["listings"]), 91)

    def test_report_is_compared_with_report_and_api_with_api(self) -> None:
        result = choose(
            report(self.rows(100)),
            api([(str(i), 1) for i in range(50)]),
            {"report_rows": 100, "api_declared": 50},
        )
        self.assertTrue(result["report_used"])
        self.assertTrue(result["api_used"])

    def test_no_previous_record_skips_comparison(self) -> None:
        result = choose(report(self.rows(1)), api([("A", 1)]), {})
        self.assertTrue(result["report_used"])
        self.assertTrue(result["api_used"])

    def test_unusable_night_keeps_previous_counts(self) -> None:
        previous = {"report_rows": 100, "api_declared": 50}
        counts = next_counts(previous, report_used=False, report_rows=10, api_used=True, api_declared=55)
        self.assertEqual(counts, {"report_rows": 100, "api_declared": 55})

    def test_both_usable_updates_both_counts(self) -> None:
        counts = next_counts({"report_rows": 100}, report_used=True, report_rows=105, api_used=True, api_declared=60)
        self.assertEqual(counts, {"report_rows": 105, "api_declared": 60})

    def test_counts_round_trip_and_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "amazon_counts.json"
            self.assertEqual(load_counts(path), {})
            save_counts(path, {"report_rows": 3, "api_declared": 4})
            self.assertEqual(load_counts(path), {"report_rows": 3, "api_declared": 4})
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(load_counts(path), {})
            self.assertEqual(json.loads(json.dumps({"x": 1})), {"x": 1})


if __name__ == "__main__":
    unittest.main()
