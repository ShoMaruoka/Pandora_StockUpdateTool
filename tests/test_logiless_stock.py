"""ロジレスのフリー在庫。0件も辞書に残し、APIへは接続しない。"""
from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from logiless_stock import fetch_free_stock, items_to_stock, redact  # noqa: E402


def article(code: str, free: int) -> dict:
    return {"article": {"code": code, "name": "sample"}, "free": free}


class LogilessStockTest(unittest.TestCase):
    def test_zero_free_stock_is_kept(self) -> None:
        stock = items_to_stock([article("307679", 0), article("263860", 4)], 2)
        self.assertEqual(stock, {"307679": 0, "263860": 4})

    def test_duplicate_code_fails(self) -> None:
        with self.assertRaises(ValueError):
            items_to_stock([article("307679", 1), article("307679", 0)], 2)

    def test_count_mismatch_fails(self) -> None:
        with self.assertRaises(ValueError):
            items_to_stock([article("307679", 0)], 2)

    def test_token_is_removed_from_messages(self) -> None:
        store = {"access_token": "access-secret", "refresh_token": "refresh-secret", "client_secret": "client-secret"}
        hidden = redact("Bearer access-secret refresh-secret client-secret", store)
        self.assertNotIn("access-secret", hidden)
        self.assertNotIn("refresh-secret", hidden)
        self.assertNotIn("client-secret", hidden)

    def test_unauthorized_refreshes_once_and_includes_zero(self) -> None:
        calls = {"count": 0}

        def api_get(store: dict, path: str) -> dict:
            calls["count"] += 1
            if calls["count"] == 1:
                raise HTTPError("https://example.test", 401, "unauthorized", {}, io.BytesIO(b""))
            self.assertIn("min_free=0", path)
            self.assertEqual(store["access_token"], "new-access")
            return {"total_count": 1, "data": [article("307679", 0)]}

        def refresh(store: dict) -> None:
            store["access_token"] = "new-access"

        stock = fetch_free_stock({"access_token": "old-access"}, api_get, refresh)
        self.assertEqual(stock, {"307679": 0})
        self.assertEqual(calls["count"], 2)

    def test_existing_export_still_uses_min_free_one(self) -> None:
        source = (ROOT / "testtools" / "logiless_export_stock.py").read_text(encoding="utf-8")
        self.assertIn('"min_free": 1', source)


if __name__ == "__main__":
    unittest.main()
