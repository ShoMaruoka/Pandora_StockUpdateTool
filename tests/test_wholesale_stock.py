"""販売管理ビューの読み取り。接続先は使わず、列の対応と SQL の種類だけを確認する。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from adjusted_stock import adjusted_stock  # noqa: E402
from wholesale_stock import (  # noqa: E402
    WHOLESALE_SQL,
    load_config,
    redact,
    rows_to_stock,
)


class WholesaleStockTest(unittest.TestCase):
    def test_missing_config_names_the_file(self) -> None:
        missing = Path(__file__).resolve().parent / "no_such_dir" / "sqlserver.json"
        with self.assertRaises(SystemExit) as caught:
            load_config(missing)
        self.assertIn("認証ファイルがありません", str(caught.exception.code))
        self.assertIn("sqlserver.json", str(caught.exception.code))

    def test_sql_is_select_only(self) -> None:
        statement = " ".join(WHOLESALE_SQL.split()).upper()
        self.assertTrue(statement.startswith("SELECT "))
        for word in ("INSERT", "UPDATE", "DELETE", "MERGE", "ALTER", "DROP", "EXEC"):
            self.assertNotIn(word, statement)

    def test_rows_feed_adjusted_stock(self) -> None:
        rows = [("307679", 2, 1, 1, 1, 0, 50)]
        stock = rows_to_stock(rows)
        self.assertEqual(adjusted_stock(stock["307679"]), 3)
        self.assertEqual(stock["307679"][180], 50)

    def test_redact_removes_password_and_connection_text(self) -> None:
        config = {
            "driver": "ODBC Driver 18 for SQL Server",
            "server": "sql.example.internal",
            "database": "Medical",
            "uid": "ec_reader",
            "password": "secret-password",
        }
        message = (
            "Login failed for user ec_reader. "
            "DRIVER={ODBC Driver 18 for SQL Server};SERVER=sql.example.internal;"
            "DATABASE=Medical;UID=ec_reader;PWD=secret-password"
        )
        hidden = redact(message, config)
        self.assertNotIn("secret-password", hidden)
        self.assertNotIn("sql.example.internal", hidden)
        self.assertNotIn("ec_reader", hidden)


if __name__ == "__main__":
    unittest.main()
