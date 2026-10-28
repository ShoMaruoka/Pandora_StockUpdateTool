"""Amazonの出品一覧を最後まで読む。数量は更新しない。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
ENDPOINT = "https://sellingpartnerapi-fe.amazon.com"
MARKETPLACE_ID = "A1VC38T7YXB528"
from secrets_dir import config_path

STORE_PATH = config_path("amazon_spapi.json")
USER_AGENT = "ECInventory/1.0 (Language=Python; Platform=Windows)"
PAGE_SIZE = 20
PAGE_CAP = 1000


def listings_from_pages(pages: list[dict]) -> dict:
    listings = []
    declared = 0
    for page in pages:
        declared = int(page.get("numberOfResults") or 0)
        for item in page.get("items") or []:
            row = {
                "sku": str(item.get("sku") or ""),
                "default_quantity": _merchant_quantity(item),
            }
            created = _created(item)
            if created:
                row["created"] = created
            name = _item_name(item)
            if name:
                row["name"] = name
            product_type = _product_type(item)
            if product_type:
                row["product_type"] = product_type
            listings.append(row)
        if (page.get("pagination") or {}).get("nextToken"):
            continue
        break
    unfinished = bool(pages) and bool((pages[-1].get("pagination") or {}).get("nextToken"))
    capped = not unfinished and len(listings) == PAGE_CAP and declared > PAGE_CAP
    complete = not unfinished and len(listings) == declared
    return {"complete": complete, "capped": capped, "declared": declared, "listings": listings}


def fetch_listings(get_page) -> dict:
    pages = []
    token = None
    while True:
        page = get_page(token)
        pages.append(page)
        token = (page.get("pagination") or {}).get("nextToken")
        if not token:
            break
    return listings_from_pages(pages)


def fetch_catalog(search) -> dict:
    """1回の検索は1000件で打ち切られる。作成日で区切って続きを読む。"""
    extra: dict = {}
    seen: dict = {}
    declared = 0
    boundary = None
    for _ in range(40):
        result = search(extra)
        if not extra:
            declared = result["declared"]
        for row in result["listings"]:
            seen[row["sku"]] = row
        if result["complete"]:
            return {
                "complete": len(seen) == declared,
                "declared": declared,
                "listings": list(seen.values()),
            }
        if not result.get("capped"):
            break
        nxt = result["listings"][-1].get("created") if result["listings"] else None
        if not nxt or nxt == boundary:
            break
        boundary = nxt
        extra = {"createdAfter": nxt}
    return {"complete": False, "declared": declared, "listings": list(seen.values())}


def fetch_all() -> dict:
    store = _load_store()
    _access_token(store)

    def search(extra: dict) -> dict:
        def get_page(token: str | None) -> dict:
            if token or extra:
                time.sleep(0.2)
            query = {
                "marketplaceIds": MARKETPLACE_ID,
                "includedData": "summaries,fulfillmentAvailability",
                "pageSize": PAGE_SIZE,
                "sortBy": "createdDate",
                "sortOrder": "ASC",
            }
            query.update(extra)
            if token:
                query["pageToken"] = token
            seller = store["seller_id"]
            return _sp_get(store, f"/listings/2021-08-01/items/{seller}?" + urlencode(query))

        return fetch_listings(get_page)

    return fetch_catalog(search)


def _created(item: dict) -> str | None:
    for summary in item.get("summaries") or []:
        created = summary.get("createdDate")
        if created:
            return str(created)
    return None


def make_reader():
    """SKU を1件ずつ読み、出品者出荷の数量を返す。出品が無い（404）ときと、数量が無いときは None。"""
    from urllib.parse import quote

    store = _load_store()
    _access_token(store)
    seller = quote(str(store["seller_id"]), safe="")
    query = urlencode({"marketplaceIds": MARKETPLACE_ID, "includedData": "summaries,fulfillmentAvailability"})

    def read(sku: str) -> int | None:
        time.sleep(0.2)
        try:
            item = _sp_get(store, f"/listings/2021-08-01/items/{seller}/{quote(str(sku), safe='')}?" + query)
        except SystemExit as exc:
            if isinstance(exc.code, str) and "(404)" in exc.code:
                return None
            raise
        return _merchant_quantity(item)

    return read


_quick_store: dict | None = None


def patch_quantity(sku: str, quantity: int, readback: bool = True, product_type: str = "") -> int | None:
    """指定SKUの出品者出荷数量を絶対値で更新する。readback のときは読み戻す。

    全件更新では readback=False にし、ACCEPTED だけを確かめる。認証は最初の1回だけ行う。
    product_type が分かっているときは、その SKU を読み直さない。
    """
    from urllib.parse import quote

    from amazon_patch import PatchRejected, ReadbackPending

    global _quick_store
    if readback or _quick_store is None:
        store = _load_store()
        _access_token(store)
        if not readback:
            _quick_store = store
    else:
        store = _quick_store
    seller = quote(str(store["seller_id"]), safe="")
    sku_path = quote(str(sku), safe="")
    query = urlencode({"marketplaceIds": MARKETPLACE_ID, "includedData": "summaries,fulfillmentAvailability"})
    path = f"/listings/2021-08-01/items/{seller}/{sku_path}?" + query
    try:
        if not product_type:
            product_type = _product_type(_sp_get(store, path))
        if not product_type:
            raise PatchRejected(sku, "商品タイプが取れないため、更新を送りません。")
        patch_path = f"/listings/2021-08-01/items/{seller}/{sku_path}?" + urlencode({"marketplaceIds": MARKETPLACE_ID})
        result = _send_patch(store, patch_path, sku, quantity, product_type)
        if result.get("status") != "ACCEPTED" and _invalid_product_type(result) and product_type != GENERIC_PRODUCT_TYPE:
            # 古い商品タイプ名（例: FOOD_AND_BEVERAGE）は今のマーケットプレイスで受け付けられない。
            # 在庫数だけの更新は、汎用の PRODUCT で受け付けられる。
            print(f"patch retry {sku} product type {product_type} -> {GENERIC_PRODUCT_TYPE}")
            product_type = GENERIC_PRODUCT_TYPE
            result = _send_patch(store, patch_path, sku, quantity, product_type)
    except PatchRejected:
        raise
    except SystemExit as exc:
        # 出品レポートにだけ残っている削除済みの SKU は 404 になる（2026-10-28 324566）。
        # その SKU だけを拒否として扱い、残りの SKU は送り続ける。
        if isinstance(exc.code, str) and "(404)" in exc.code:
            raise PatchRejected(sku, "Amazon に出品がありません (404)。最近削除された出品の可能性があります。") from exc
        raise
    if result.get("status") != "ACCEPTED":
        issues = "; ".join(
            f"{issue.get('code')} {_redact(str(issue.get('message') or ''), store)}" for issue in result.get("issues") or []
        )
        raise PatchRejected(sku, f"{result.get('status')} {issues} (商品タイプ {product_type})".replace("  ", " "))
    if not readback:
        time.sleep(0.25)
        return None
    got = _wait_quantity(store, path, int(quantity))
    if got != int(quantity):
        # ACCEPTED のあと反映に十数分かかることがある（2026-10-21 534174x24）。失敗とは分けて返す。
        raise ReadbackPending(sku, int(quantity), got)
    print(f"readback {got}")
    return int(got)


GENERIC_PRODUCT_TYPE = "PRODUCT"
INVALID_PRODUCT_TYPE = "4000003"


def _send_patch(store: dict, path: str, sku: str, quantity: int, product_type: str) -> dict:
    from amazon_patch import fulfillment_patch

    result = _sp_json(store, "PATCH", path, fulfillment_patch(quantity, product_type, MARKETPLACE_ID))
    print(f"patch {sku} status {result.get('status')} issues {len(result.get('issues') or [])}")
    for issue in result.get("issues") or []:
        print(f"patch issue {sku} {issue.get('code')} {_redact(str(issue.get('message') or ''), store)}")
    return result


def _invalid_product_type(result: dict) -> bool:
    return any(str(issue.get("code")) == INVALID_PRODUCT_TYPE for issue in result.get("issues") or [])


READBACK_TRIES = 20
READBACK_SECONDS = 30


def _wait_quantity(store: dict, path: str, expected: int) -> int | None:
    """在庫反映は遅れることがある。同じSKUだけを、最大 10 分読み直す。"""
    got = None
    for _ in range(READBACK_TRIES):
        got = _merchant_quantity(_sp_get(store, path))
        print(f"readback {got}")
        if got == expected:
            return got
        time.sleep(READBACK_SECONDS)
    return got


def _item_name(item: dict) -> str:
    for summary in item.get("summaries") or []:
        name = summary.get("itemName")
        if name:
            return str(name)
    return ""


def _product_type(item: dict) -> str:
    for summary in item.get("summaries") or []:
        product_type = summary.get("productType")
        if product_type:
            return str(product_type)
    return ""


def _merchant_quantity(item: dict) -> int | None:
    for row in item.get("fulfillmentAvailability") or []:
        if row.get("fulfillmentChannelCode") == "DEFAULT":
            return int(row.get("quantity") or 0)
    return None


def _load_store() -> dict:
    if not STORE_PATH.exists():
        raise SystemExit(f"認証ファイルがありません: {STORE_PATH}")
    data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    missing = [key for key in ("client_id", "client_secret", "refresh_token", "seller_id") if not str(data.get(key) or "").strip()]
    if missing:
        raise SystemExit("不足しているキー: " + ", ".join(missing))
    return data


def _redact(text: str, store: dict) -> str:
    for key in ("client_id", "client_secret", "refresh_token", "access_token", "seller_id"):
        value = str(store.get(key) or "")
        if value:
            text = text.replace(value, "***")
    return text


def _access_token(store: dict) -> None:
    body = urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": store["refresh_token"],
            "client_id": store["client_id"],
            "client_secret": store["client_secret"],
        }
    ).encode("utf-8")
    request = Request(TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            token = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = _redact(exc.read().decode("utf-8", errors="replace"), store)
        raise SystemExit(f"トークン取得に失敗しました ({exc.code}): {detail[:500]}") from exc
    except URLError as exc:
        raise SystemExit("Amazon へ接続できません: " + _redact(str(exc.reason), store)) from exc
    store["access_token"] = str(token.get("access_token") or "")
    if not store["access_token"]:
        raise SystemExit("アクセストークンが応答にありません。")


def _sp_json(store: dict, method: str, path: str, body: dict) -> dict:
    request = Request(
        ENDPOINT + path,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-amz-access-token": store["access_token"],
            "user-agent": USER_AGENT,
            "accept": "application/json",
            "content-type": "application/json",
        },
        method=method,
    )
    return _read_json(store, request)


def _sp_get(store: dict, path: str) -> dict:
    request = Request(
        ENDPOINT + path,
        headers={
            "x-amz-access-token": store["access_token"],
            "user-agent": USER_AGENT,
            "accept": "application/json",
        },
        method="GET",
    )
    return _read_json(store, request)


RETRY_WAITS = (2, 5, 10)


def _read_json(store: dict, request: Request) -> dict:
    """呼び出し回数の制限（429）のときだけ、待ってやり直す。"""
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429 and attempt < len(RETRY_WAITS):
                time.sleep(RETRY_WAITS[attempt])
                continue
            detail = _redact(exc.read().decode("utf-8", errors="replace"), store)
            raise SystemExit(f"Amazon がエラーを返しました ({exc.code}): {detail[:500]}") from exc
        except URLError as exc:
            raise SystemExit("Amazon へ接続できません: " + _redact(str(exc.reason), store)) from exc
    raise SystemExit("Amazon の呼び出し回数の制限が続いています。")
