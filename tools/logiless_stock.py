"""ロジレスのフリー在庫を全件取る。フリー在庫0も含める。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN_URL = "https://app2.logiless.com/oauth2/token"
from secrets_dir import config_path

STORE_PATH = config_path("logiless_oauth.json")
PAGE_LIMIT = 100


def items_to_stock(items: list[dict], total_count: int) -> dict[str, int]:
    stock: dict[str, int] = {}
    for item in items:
        article = item.get("article") or {}
        code = str(article.get("code") or "").strip()
        if not code:
            continue
        if code in stock:
            raise ValueError(f"商品コードが重複しています: {code}")
        stock[code] = int(item.get("free") or 0)
    if len(stock) != total_count:
        raise ValueError(f"件数が一致しません。API {total_count} 件、取得 {len(stock)} 件")
    return stock


def redact(message: str, store: dict) -> str:
    hidden = message
    values = [str(store.get(key) or "") for key in ("access_token", "refresh_token", "client_secret", "client_id")]
    for value in sorted(values, key=len, reverse=True):
        if value:
            hidden = hidden.replace(value, "***")
    return hidden


def page_path(page: int) -> str:
    query = urlencode({"limit": PAGE_LIMIT, "page": page, "min_free": 0, "layer": "Article"})
    return "/logical_inventory_summaries?" + query


def fetch_free_stock(store: dict, api_get, refresh) -> dict[str, int]:
    page = 1
    items: list[dict] = []
    total = 0
    while True:
        body = _get_page(store, api_get, refresh, page)
        chunk = body.get("data") or []
        total = int(body.get("total_count") or 0)
        items.extend(chunk)
        if not chunk or len(items) >= total:
            break
        page += 1
    return items_to_stock(items, total)


def load_store() -> dict:
    if not STORE_PATH.exists():
        raise SystemExit(f"認可ファイルがありません: {STORE_PATH}")
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def refresh_access_token(store: dict) -> None:
    body = urlencode(
        {
            "client_id": store["client_id"],
            "client_secret": store["client_secret"],
            "refresh_token": store["refresh_token"],
            "grant_type": "refresh_token",
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
        detail = redact(exc.read().decode("utf-8", errors="replace"), store)
        raise SystemExit(f"トークンの更新に失敗しました ({exc.code}): {detail}") from exc
    store["access_token"] = token.get("access_token") or ""
    if token.get("refresh_token"):
        store["refresh_token"] = token["refresh_token"]
    store["token_type"] = token.get("token_type") or store.get("token_type") or ""
    store["expires_at"] = int(time.time()) + int(token.get("expires_in") or 0)
    if not store["access_token"]:
        raise SystemExit("更新後のアクセストークンがありません。")
    STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def api_get(store: dict, path: str) -> dict:
    url = f"https://app2.logiless.com/api/v1/merchant/{store['merchant_id']}{path}"
    request = Request(url, headers={"Authorization": "Bearer " + store["access_token"]})
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError:
        raise
    except URLError as exc:
        raise SystemExit("ロジレスへ接続できません: " + redact(str(exc.reason), store)) from exc


def fetch_all() -> dict[str, int]:
    return fetch_free_stock(load_store(), api_get, refresh_access_token)


def _get_page(store: dict, api_get, refresh, page: int) -> dict:
    path = page_path(page)
    try:
        return api_get(store, path)
    except HTTPError as exc:
        if exc.code != 401:
            detail = redact(exc.read().decode("utf-8", errors="replace"), store)
            raise SystemExit(f"在庫取得に失敗しました ({exc.code}): {detail}") from exc
        refresh(store)
        try:
            return api_get(store, path)
        except HTTPError as retry_exc:
            detail = redact(retry_exc.read().decode("utf-8", errors="replace"), store)
            raise SystemExit(f"在庫取得に失敗しました ({retry_exc.code}): {detail}") from retry_exc
