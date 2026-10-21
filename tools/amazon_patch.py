"""指定した1件の出品者出荷数量だけを送るリクエストにする。"""
from __future__ import annotations

from amazon_gate import AmazonRun


class PatchRejected(SystemExit):
    """Amazon が1つの SKU の更新を受け付けなかった。通信や認証の失敗とは分けて扱う。"""

    def __init__(self, sku: str, reason: str) -> None:
        super().__init__(f"Amazon が更新を受け付けませんでした: {sku} {reason}")
        self.sku = str(sku)
        self.reason = reason


class ReadbackPending(SystemExit):
    """Amazon は更新を受け付けたが、待ち時間の間に反映を確認できなかった。失敗とは扱わない。"""

    def __init__(self, sku: str, expected: int, actual: int | None) -> None:
        super().__init__(f"反映を確認できませんでした: {sku} 送った数量 {expected} 今の数量 {actual}")
        self.sku = str(sku)
        self.expected = expected
        self.actual = actual


def one_update(decision: AmazonRun, sku: str) -> dict | None:
    """held や failed、数量が決まらない SKU は送らない。"""
    if decision.action != "sent":
        return None
    for row in decision.updates:
        if row.get("sku") == sku and row.get("channel") == "DEFAULT":
            return {"sku": sku, "quantity": int(row["quantity"]), "channel": "DEFAULT"}
    return None


def fulfillment_patch(quantity: int, product_type: str, marketplace_id: str) -> dict:
    return {
        "productType": product_type,
        "patches": [
            {
                "op": "replace",
                "path": "/attributes/fulfillment_availability",
                "value": [
                    {
                        "fulfillment_channel_code": "DEFAULT",
                        "quantity": int(quantity),
                        "marketplace_id": marketplace_id,
                    }
                ],
            }
        ],
    }
