"""指定した1 SKUだけを更新する。Amazonへは接続しない。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"))

from amazon_gate import AmazonRun  # noqa: E402
from amazon_patch import fulfillment_patch, one_update  # noqa: E402
from nightly_amazon import run  # noqa: E402


def sent_run() -> AmazonRun:
    return AmazonRun(
        "sent",
        2,
        2,
        0,
        "",
        [
            {"sku": "485706", "quantity": 26, "channel": "DEFAULT"},
            {"sku": "307679", "quantity": 4, "channel": "DEFAULT"},
        ],
    )


class AmazonPatchTest(unittest.TestCase):
    def test_only_the_named_sku_is_chosen(self) -> None:
        self.assertEqual(
            one_update(sent_run(), "485706"),
            {"sku": "485706", "quantity": 26, "channel": "DEFAULT"},
        )

    def test_held_chooses_nothing(self) -> None:
        held = AmazonRun("held", 2, 0, 0, "急減 1件", [])
        self.assertIsNone(one_update(held, "485706"))

    def test_unknown_quantity_chooses_nothing(self) -> None:
        self.assertIsNone(one_update(sent_run(), "2003739"))

    def test_patch_is_merchant_quantity_only(self) -> None:
        body = fulfillment_patch(26, "PRODUCT", "A1VC38T7YXB528")
        self.assertEqual(body["productType"], "PRODUCT")
        value = body["patches"][0]["value"]
        self.assertEqual(
            value,
            [{"fulfillment_channel_code": "DEFAULT", "quantity": 26, "marketplace_id": "A1VC38T7YXB528"}],
        )
        self.assertNotIn("AMAZON", str(body))

    def test_named_sku_sends_one_request(self) -> None:
        sent = []

        def send(updates):
            sent.append(list(updates))

        with tempfile.TemporaryDirectory() as folder:
            code = run(
                Path(folder),
                dry_run=False,
                sku="307679",
                fetch_wholesale=lambda: {"307679": {120: 5}, "263860": {120: 4}},
                fetch_free=lambda: {},
                fetch_listings=lambda: {
                    "complete": True,
                    "declared": 2,
                    "listings": [
                        {"sku": "307679", "default_quantity": 1},
                        {"sku": "263860", "default_quantity": 2},
                    ],
                },
                fetch_quotes=lambda _numbers: {},
                send=send,
            )
        self.assertEqual(code, 0)
        self.assertEqual(sent, [[{"sku": "307679", "quantity": 3, "channel": "DEFAULT"}]])

    def test_named_sku_is_not_sent_when_that_sku_drops(self) -> None:
        sent = []

        def send(updates):
            sent.append(list(updates))

        with tempfile.TemporaryDirectory() as folder:
            code = run(
                Path(folder),
                dry_run=False,
                sku="307679",
                fetch_wholesale=lambda: {"307679": {120: 5}, "263860": {120: 4}},
                fetch_free=lambda: {},
                fetch_listings=lambda: {
                    "complete": True,
                    "declared": 2,
                    "listings": [
                        {"sku": "307679", "default_quantity": 20},
                        {"sku": "263860", "default_quantity": 2},
                    ],
                },
                fetch_quotes=lambda _numbers: {},
                send=send,
            )
            audit_path = next(Path(folder).glob("amazon_audit_*.csv"))
            with audit_path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(__import__("csv").DictReader(handle))
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])
        by_sku = {row["出品者SKU"]: row["送るかどうか"] for row in rows}
        self.assertEqual(by_sku, {"307679": "送らない", "263860": "送らない"})

    def test_named_sku_sends_when_only_another_sku_drops(self) -> None:
        sent = []

        def send(updates):
            sent.append(list(updates))

        with tempfile.TemporaryDirectory() as folder:
            code = run(
                Path(folder),
                dry_run=False,
                sku="263860",
                fetch_wholesale=lambda: {"307679": {120: 5}, "263860": {120: 4}},
                fetch_free=lambda: {},
                fetch_listings=lambda: {
                    "complete": True,
                    "declared": 2,
                    "listings": [
                        {"sku": "307679", "default_quantity": 20},
                        {"sku": "263860", "default_quantity": 1},
                    ],
                },
                fetch_quotes=lambda _numbers: {},
                send=send,
            )
        self.assertEqual(code, 0)
        self.assertEqual(sent, [[{"sku": "263860", "quantity": 2, "channel": "DEFAULT"}]])

    def test_failed_named_sku_sends_nothing(self) -> None:
        sent = []

        def send(updates):
            sent.append(list(updates))

        with tempfile.TemporaryDirectory() as folder:
            code = run(
                Path(folder),
                dry_run=False,
                sku="307679",
                fetch_wholesale=lambda: {"307679": {120: 5}},
                fetch_free=lambda: {},
                fetch_listings=lambda: {
                    "complete": False,
                    "declared": 2,
                    "listings": [{"sku": "307679", "default_quantity": 1}],
                },
                fetch_quotes=lambda _numbers: {},
                send=send,
            )
        self.assertEqual(code, 1)
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
