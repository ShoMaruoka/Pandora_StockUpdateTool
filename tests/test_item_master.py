"""販売管理 T410商品 の定番在庫の参照。SQL Server には接続しない。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from item_master import REGULAR_SQL, read_regular, webcd_key  # noqa: E402


class FakeCursor:
    def __init__(self, table: dict) -> None:
        self.table = table
        self.calls = []
        self.rows = []

    def execute(self, sql, params):
        self.calls.append((sql, list(params)))
        self.rows = [(webcd, self.table[webcd]) for webcd in params if webcd in self.table]

    def fetchall(self):
        return self.rows


class ItemMasterTest(unittest.TestCase):
    def test_reads_regular_flag_by_numeric_webcd(self) -> None:
        cursor = FakeCursor({15694: 2, 307679: 1})
        result = read_regular(cursor, ["015694", "307679", "999999"])
        self.assertEqual(result, {"15694": 2, "307679": 1})
        self.assertEqual(cursor.calls[0][1], [15694, 307679, 999999])

    def test_empty_or_non_numeric_webcd_does_not_query(self) -> None:
        cursor = FakeCursor({})
        self.assertEqual(read_regular(cursor, ["", "ABC"]), {})
        self.assertEqual(cursor.calls, [])

    def test_large_lists_are_split_under_the_parameter_limit(self) -> None:
        cursor = FakeCursor({})
        read_regular(cursor, [str(n) for n in range(1, 2501)])
        self.assertEqual([len(params) for _sql, params in cursor.calls], [1000, 1000, 500])

    def test_duplicates_are_queried_once(self) -> None:
        cursor = FakeCursor({1: 2})
        read_regular(cursor, ["1", "01", "1"])
        self.assertEqual(cursor.calls[0][1], [1])

    def test_sql_is_select_only(self) -> None:
        upper = REGULAR_SQL.upper()
        self.assertIn("SELECT", upper)
        for word in ("INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "EXEC"):
            self.assertNotIn(word, upper)

    def test_webcd_key_ignores_leading_zeros(self) -> None:
        self.assertEqual(webcd_key("015694"), "15694")
        self.assertEqual(webcd_key(15694), "15694")
        self.assertEqual(webcd_key("ABC"), "")
        self.assertEqual(webcd_key(None), "")


if __name__ == "__main__":
    unittest.main()
