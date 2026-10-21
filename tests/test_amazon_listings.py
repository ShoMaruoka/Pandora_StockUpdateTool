"""Amazon出品一覧の読み取り。更新リクエストは作らない。"""
from __future__ import annotations

import io
import sys
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"))

import amazon_listings  # noqa: E402
from amazon_listings import fetch_catalog, fetch_listings, listings_from_pages  # noqa: E402


def item(sku: str, default: int | None, fba: int | None = None) -> dict:
    rows = []
    if default is not None:
        rows.append({"fulfillmentChannelCode": "DEFAULT", "quantity": default})
    if fba is not None:
        rows.append({"fulfillmentChannelCode": "AMAZON_JP", "quantity": fba})
    return {"sku": sku, "fulfillmentAvailability": rows}


class AmazonListingsTest(unittest.TestCase):
    def test_missing_page_is_incomplete(self) -> None:
        page = {
            "numberOfResults": 2,
            "pagination": {"nextToken": "more"},
            "items": [item("307679", 1, 9)],
        }
        result = listings_from_pages([page])
        self.assertFalse(result["complete"])
        self.assertEqual(result["declared"], 2)

    def test_item_name_is_kept_when_the_api_returns_it(self) -> None:
        named = dict(item("307679", 1), summaries=[{"itemName": "シャワーチェア"}])
        result = listings_from_pages([{"numberOfResults": 2, "items": [named, item("263860", 2)]}])
        self.assertEqual(result["listings"][0]["name"], "シャワーチェア")
        self.assertNotIn("name", result["listings"][1])

    def test_quantity_is_merchant_fulfilled_only(self) -> None:
        page = {
            "numberOfResults": 1,
            "items": [item("307679", 1, 9)],
        }
        result = listings_from_pages([page])
        self.assertTrue(result["complete"])
        self.assertEqual(result["listings"], [{"sku": "307679", "default_quantity": 1}])

    def test_fetch_does_not_update(self) -> None:
        calls = []

        def get_page(token: str | None) -> dict:
            calls.append(token)
            if token is None:
                return {
                    "numberOfResults": 2,
                    "pagination": {"nextToken": "page-2"},
                    "items": [item("307679", 1, 4)],
                }
            return {"numberOfResults": 2, "items": [item("263860", 3)]}

        result = fetch_listings(get_page)
        self.assertEqual(calls, [None, "page-2"])
        self.assertTrue(result["complete"])
        self.assertEqual(
            result["listings"],
            [
                {"sku": "307679", "default_quantity": 1},
                {"sku": "263860", "default_quantity": 3},
            ],
        )
        self.assertNotIn("updates", result)

    def test_thousand_cap_is_visible(self) -> None:
        items = [item(f"{i:06d}", 1) for i in range(1000)]
        result = listings_from_pages([{"numberOfResults": 1002, "items": items}])
        self.assertFalse(result["complete"])
        self.assertTrue(result["capped"])
        self.assertEqual(len(result["listings"]), 1000)

    def test_catalog_continues_after_thousand_cap(self) -> None:
        calls = []

        def search(extra: dict) -> dict:
            calls.append(extra)
            if not extra:
                oldest = [
                    {"sku": f"{i:06d}", "default_quantity": 1, "created": "2020-01-01T00:00:00Z"}
                    for i in range(999)
                ]
                oldest.append({"sku": "000999", "default_quantity": 1, "created": "2020-06-01T00:00:00Z"})
                return {"complete": False, "capped": True, "declared": 1002, "listings": oldest}
            return {
                "complete": True,
                "capped": False,
                "declared": 3,
                "listings": [
                    {"sku": "000999", "default_quantity": 1, "created": "2020-06-01T00:00:00Z"},
                    {"sku": "001000", "default_quantity": 2, "created": "2021-01-01T00:00:00Z"},
                    {"sku": "001001", "default_quantity": 3, "created": "2021-02-01T00:00:00Z"},
                ],
            }

        result = fetch_catalog(search)
        self.assertEqual(calls, [{}, {"createdAfter": "2020-06-01T00:00:00Z"}])
        self.assertTrue(result["complete"])
        self.assertEqual(result["declared"], 1002)
        self.assertEqual(len(result["listings"]), 1002)
        self.assertNotIn("updates", result)

    def reader(self, responses: dict):
        """sku ごとの応答（dict か SystemExit の文言）を返す偽の GET で、1件読み直す関数を作る。"""
        seen = []

        def fake_get(_store, path):
            seen.append(path)
            value = responses[path.split("?")[0].rsplit("/", 1)[1]]
            if isinstance(value, str):
                raise SystemExit(value)
            return value

        with mock.patch.object(amazon_listings, "_load_store", return_value={"seller_id": "S1"}), mock.patch.object(
            amazon_listings, "_access_token"
        ), mock.patch.object(amazon_listings, "_sp_get", fake_get), mock.patch.object(amazon_listings.time, "sleep"):
            read = amazon_listings.make_reader()
        return read, fake_get, seen

    def test_reader_returns_merchant_quantity_and_only_reads(self) -> None:
        read, fake_get, seen = self.reader({"A": item("A", 3, 9), "B": item("B", None, 9)})
        with mock.patch.object(amazon_listings, "_sp_get", fake_get), mock.patch.object(amazon_listings.time, "sleep"):
            self.assertEqual(read("A"), 3)
            self.assertIsNone(read("B"))
        self.assertEqual(len(seen), 2)
        self.assertTrue(all("fulfillmentAvailability" in path for path in seen))

    def test_reader_returns_none_when_the_listing_is_gone(self) -> None:
        read, fake_get, _seen = self.reader({"A": "Amazon がエラーを返しました (404): NOT_FOUND"})
        with mock.patch.object(amazon_listings, "_sp_get", fake_get), mock.patch.object(amazon_listings.time, "sleep"):
            self.assertIsNone(read("A"))

    def test_reader_does_not_hide_other_errors(self) -> None:
        read, fake_get, _seen = self.reader({"A": "Amazon がエラーを返しました (429): QuotaExceeded"})
        with mock.patch.object(amazon_listings, "_sp_get", fake_get), mock.patch.object(amazon_listings.time, "sleep"):
            with self.assertRaises(SystemExit):
                read("A")

    def test_product_type_is_kept_when_the_api_returns_it(self) -> None:
        typed = dict(item("307679", 1), summaries=[{"productType": "BATH_SAFETY_SEATING"}])
        result = listings_from_pages([{"numberOfResults": 2, "items": [typed, item("263860", 2)]}])
        self.assertEqual(result["listings"][0]["product_type"], "BATH_SAFETY_SEATING")
        self.assertNotIn("product_type", result["listings"][1])

    def patch_mocks(self, accepted=True, responses=None):
        calls = {"get": [], "patch": []}
        queue = list(responses or [])

        def fake_get(_store, path):
            calls["get"].append(path)
            return {"summaries": [{"productType": "READ_TYPE"}], "fulfillmentAvailability": [{"fulfillmentChannelCode": "DEFAULT", "quantity": 5}]}

        def fake_json(_store, method, path, body):
            calls["patch"].append((method, body["productType"], body["patches"][0]["value"][0]["quantity"]))
            if queue:
                return queue.pop(0)
            return {"status": "ACCEPTED" if accepted else "INVALID", "issues": []}

        patches = [
            mock.patch.object(amazon_listings, "_load_store", return_value={"seller_id": "S1"}),
            mock.patch.object(amazon_listings, "_access_token"),
            mock.patch.object(amazon_listings, "_sp_get", fake_get),
            mock.patch.object(amazon_listings, "_sp_json", fake_json),
            mock.patch.object(amazon_listings.time, "sleep"),
            mock.patch.object(amazon_listings, "_quick_store", None),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        return calls

    def test_quick_patch_uses_known_product_type_and_does_not_read_back(self) -> None:
        calls = self.patch_mocks()
        with mock.patch("builtins.print"):
            amazon_listings.patch_quantity("307679", 5, readback=False, product_type="KNOWN")
        self.assertEqual(calls["get"], [])
        self.assertEqual(calls["patch"], [("PATCH", "KNOWN", 5)])

    def test_quick_patch_reads_product_type_only_when_missing(self) -> None:
        calls = self.patch_mocks()
        with mock.patch("builtins.print"):
            amazon_listings.patch_quantity("307679", 5, readback=False)
        self.assertEqual(len(calls["get"]), 1)
        self.assertEqual(calls["patch"], [("PATCH", "READ_TYPE", 5)])

    def test_quick_patch_stops_when_not_accepted(self) -> None:
        self.patch_mocks(accepted=False)
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            amazon_listings.patch_quantity("307679", 5, readback=False, product_type="KNOWN")

    def invalid_type(self) -> dict:
        return {"status": "INVALID", "issues": [{"code": "4000003", "message": "指定したAmazonの商品タイプが無効です"}]}

    def test_invalid_product_type_is_retried_once_as_generic_product(self) -> None:
        calls = self.patch_mocks(responses=[self.invalid_type(), {"status": "ACCEPTED", "issues": []}])
        with mock.patch("builtins.print"):
            amazon_listings.patch_quantity("534174x24", 2, readback=False, product_type="FOOD_AND_BEVERAGE")
        self.assertEqual(calls["patch"], [("PATCH", "FOOD_AND_BEVERAGE", 2), ("PATCH", "PRODUCT", 2)])

    def test_generic_product_that_is_still_invalid_stops_with_the_sku(self) -> None:
        calls = self.patch_mocks(responses=[self.invalid_type(), self.invalid_type()])
        with mock.patch("builtins.print"), self.assertRaises(SystemExit) as caught:
            amazon_listings.patch_quantity("534174x24", 2, readback=False, product_type="FOOD_AND_BEVERAGE")
        self.assertEqual(len(calls["patch"]), 2)
        self.assertIn("534174x24", str(caught.exception.code))

    def test_other_rejections_are_not_retried(self) -> None:
        other = {"status": "INVALID", "issues": [{"code": "90000900", "message": "x"}]}
        calls = self.patch_mocks(responses=[other])
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            amazon_listings.patch_quantity("307679", 5, readback=False, product_type="KNOWN")
        self.assertEqual(len(calls["patch"]), 1)

    def test_rejection_is_a_sku_level_error_with_the_reason(self) -> None:
        from amazon_patch import PatchRejected

        other = {"status": "INVALID", "issues": [{"code": "90000900", "message": "価格が不正です"}]}
        self.patch_mocks(responses=[other])
        with mock.patch("builtins.print"), self.assertRaises(PatchRejected) as caught:
            amazon_listings.patch_quantity("307679", 5, readback=False, product_type="KNOWN")
        self.assertEqual(caught.exception.sku, "307679")
        self.assertIn("90000900", caught.exception.reason)
        self.assertIn("価格が不正です", caught.exception.reason)

    def test_http_errors_are_not_sku_level_rejections(self) -> None:
        from amazon_patch import PatchRejected

        opener = mock.Mock(side_effect=[self.http_error(500)])
        with mock.patch.object(amazon_listings, "urlopen", opener), mock.patch.object(amazon_listings.time, "sleep"):
            with self.assertRaises(SystemExit) as caught:
                amazon_listings._read_json({}, Request("https://example"))
        self.assertNotIsInstance(caught.exception, PatchRejected)

    def test_slow_readback_is_reported_as_pending_not_as_a_failure(self) -> None:
        from amazon_patch import PatchRejected, ReadbackPending

        self.patch_mocks()
        with mock.patch("builtins.print"), self.assertRaises(ReadbackPending) as caught:
            amazon_listings.patch_quantity("534174x24", 7, readback=True, product_type="KNOWN")
        self.assertEqual((caught.exception.sku, caught.exception.expected, caught.exception.actual), ("534174x24", 7, 5))
        self.assertNotIsInstance(caught.exception, PatchRejected)

    def test_readback_waits_up_to_ten_minutes(self) -> None:
        self.assertEqual(amazon_listings.READBACK_TRIES * amazon_listings.READBACK_SECONDS, 600)

    def test_patch_log_lines_name_the_sku(self) -> None:
        self.patch_mocks()
        with mock.patch("builtins.print") as printed:
            amazon_listings.patch_quantity("307679", 5, readback=False, product_type="KNOWN")
        self.assertIn("307679", " ".join(str(call.args[0]) for call in printed.call_args_list))

    def http_error(self, code: int) -> HTTPError:
        return HTTPError("https://example", code, "x", {}, io.BytesIO(b"{}"))

    def test_throttled_request_is_retried(self) -> None:
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b'{"ok": 1}'
        opener = mock.Mock(side_effect=[self.http_error(429), self.http_error(429), ok])
        with mock.patch.object(amazon_listings, "urlopen", opener), mock.patch.object(amazon_listings.time, "sleep") as sleep:
            result = amazon_listings._read_json({}, Request("https://example"))
        self.assertEqual(result, {"ok": 1})
        self.assertEqual(opener.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_throttling_gives_up_after_three_retries(self) -> None:
        opener = mock.Mock(side_effect=[self.http_error(429)] * 4)
        with mock.patch.object(amazon_listings, "urlopen", opener), mock.patch.object(amazon_listings.time, "sleep"):
            with self.assertRaises(SystemExit) as caught:
                amazon_listings._read_json({}, Request("https://example"))
        self.assertEqual(opener.call_count, 4)
        self.assertIn("429", str(caught.exception.code))

    def test_other_errors_are_not_retried(self) -> None:
        opener = mock.Mock(side_effect=[self.http_error(400)])
        with mock.patch.object(amazon_listings, "urlopen", opener), mock.patch.object(amazon_listings.time, "sleep"):
            with self.assertRaises(SystemExit):
                amazon_listings._read_json({}, Request("https://example"))
        self.assertEqual(opener.call_count, 1)

    def test_module_does_not_read_item_robot_files(self) -> None:
        source = (ROOT / "tools" / "amazon_listings.py").read_text(encoding="utf-8")
        self.assertNotIn("ir-selection", source)
        self.assertNotIn("itemrobot", source.lower())


if __name__ == "__main__":
    unittest.main()
