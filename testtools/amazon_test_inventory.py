"""Amazon SP-API で日本店舗の出品在庫を数件読み、認証が通るか確認する。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
ENDPOINT = "https://sellingpartnerapi-fe.amazon.com"
MARKETPLACE_ID = "A1VC38T7YXB528"
STORE_PATH = Path.home() / ".ec_inventory" / "amazon_spapi.json"
USER_AGENT = "ECInventory/1.0 (Language=Python; Platform=Windows)"


def load_store() -> dict:
    if not STORE_PATH.exists():
        raise SystemExit(
            "認証ファイルがありません。次の場所に JSON を作り、チャットには貼らないでください。\n"
            f"{STORE_PATH}\n"
            "キー: client_id, client_secret, refresh_token, seller_id\n"
            "seller_id はセラーセントラルの出品者トークン（Merchant Token）です。"
        )
    data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    missing = [key for key in ("client_id", "client_secret", "refresh_token", "seller_id") if not str(data.get(key) or "").strip()]
    if missing:
        raise SystemExit("不足しているキー: " + ", ".join(missing))
    return data


def redact(text: str, store: dict) -> str:
    for key in ("client_id", "client_secret", "refresh_token", "access_token"):
        value = str(store.get(key) or "")
        if value:
            text = text.replace(value, "***")
    return text


def api_error(exc: HTTPError, store: dict) -> SystemExit:
    detail = redact(exc.read().decode("utf-8", errors="replace"), store)
    return SystemExit(f"Amazon がエラーを返しました ({exc.code}): {detail[:500]}")


def access_token(store: dict) -> str:
    body = urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": store["refresh_token"],
            "client_id": store["client_id"],
            "client_secret": store["client_secret"],
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            token = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise api_error(exc, store) from exc
    except URLError as exc:
        raise SystemExit(f"Amazon へ接続できません: {exc.reason}") from exc
    value = str(token.get("access_token") or "")
    if not value:
        raise SystemExit("アクセストークンが応答にありません。")
    store["access_token"] = value
    return value


def sp_get(store: dict, path: str) -> dict:
    request = Request(
        ENDPOINT + path,
        headers={
            "x-amz-access-token": store["access_token"],
            "x-amz-date": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "user-agent": USER_AGENT,
            "accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise api_error(exc, store) from exc
    except URLError as exc:
        raise SystemExit(f"Amazon へ接続できません: {exc.reason}") from exc


def quantity_of(item: dict) -> str:
    rows = item.get("fulfillmentAvailability") or []
    if not rows:
        return "なし"
    parts = []
    for row in rows:
        code = row.get("fulfillmentChannelCode") or ""
        qty = row.get("quantity")
        parts.append(f"{code}:{qty}")
    return ", ".join(parts)


def main() -> None:
    store = load_store()
    access_token(store)
    print("アクセストークンを取得しました。")
    participation = sp_get(store, "/sellers/v1/marketplaceParticipations")
    markets = []
    for row in participation.get("payload") or []:
        market = (row.get("marketplace") or {}).get("id")
        if market:
            markets.append(market)
    print("参加マーケットプレイス: " + (", ".join(markets) if markets else "応答なし"))
    query = urlencode(
        {
            "marketplaceIds": MARKETPLACE_ID,
            "includedData": "summaries,fulfillmentAvailability",
            "pageSize": 5,
            "sortBy": "lastUpdatedDate",
            "sortOrder": "DESC",
        }
    )
    seller = store["seller_id"]
    listings = sp_get(store, f"/listings/2021-08-01/items/{seller}?{query}")
    items = listings.get("items") or []
    print(f"出品在庫の取得件数（最大5件）: {len(items)}")
    for item in items:
        sku = item.get("sku") or ""
        print(f"SKU {sku} / 在庫 {quantity_of(item)}")
    if items:
        print("在庫情報の取得に成功しました。")
    else:
        print("認証は通りました。この条件の出品は0件でした。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("中断しました。")
