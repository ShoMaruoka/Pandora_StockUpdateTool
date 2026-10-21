"""Yahoo!ショッピングの在庫を数件読み、認証が通るか確認する。更新はしない。"""
from __future__ import annotations

import base64
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN_URL = "https://auth.login.yahoo.co.jp/yconnect/v2/token"
API_BASE = "https://circus.shopping.yahooapis.jp/ShoppingWebService/V1"
STORE_PATH = Path.home() / ".ec_inventory" / "yahoo_shopping.json"
SELLER_ID = "pandora"


def load_store() -> dict:
    if not STORE_PATH.exists():
        raise SystemExit(f"認証ファイルがありません: {STORE_PATH}")
    data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    missing = [key for key in ("client_id", "client_secret", "refresh_token") if not str(data.get(key) or "").strip()]
    if missing:
        raise SystemExit("不足しているキー: " + ", ".join(missing))
    data["seller_id"] = SELLER_ID
    return data


def save_store(data: dict) -> None:
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def redact(text: str, store: dict) -> str:
    for key in ("client_id", "client_secret", "refresh_token", "access_token"):
        value = str(store.get(key) or "")
        if value:
            text = text.replace(value, "***")
    return text


def refresh_access_token(store: dict) -> None:
    basic = base64.b64encode(
        f"{store['client_id']}:{store['client_secret']}".encode("utf-8")
    ).decode("ascii")
    body = urlencode(
        {"grant_type": "refresh_token", "refresh_token": store["refresh_token"]}
    ).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=body,
        headers={
            "Authorization": "Basic " + basic,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            token = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = redact(exc.read().decode("utf-8", errors="replace"), store)
        raise SystemExit(f"トークン更新に失敗しました ({exc.code}): {detail[:500]}") from exc
    access = str(token.get("access_token") or "")
    if not access:
        raise SystemExit("更新後のアクセストークンがありません。")
    store["access_token"] = access
    if token.get("refresh_token"):
        store["refresh_token"] = token["refresh_token"]
    store["token_type"] = token.get("token_type") or store.get("token_type") or ""
    store["expires_at"] = int(time.time()) + int(token.get("expires_in") or 0)
    save_store(store)


def ensure_access_token(store: dict) -> None:
    expires_at = int(store.get("expires_at") or 0)
    if not str(store.get("access_token") or "").strip() or expires_at < time.time() + 120:
        refresh_access_token(store)


def api_get(store: dict, path: str, params: dict) -> ET.Element:
    url = f"{API_BASE}/{path}?" + urlencode(params)
    request = Request(
        url,
        headers={"Authorization": "Bearer " + store["access_token"]},
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
    except HTTPError as exc:
        detail = redact(exc.read().decode("utf-8", errors="replace"), store)
        raise SystemExit(f"Yahoo! がエラーを返しました ({exc.code}): {detail[:800]}") from exc
    except URLError as exc:
        raise SystemExit(f"Yahoo! へ接続できません: {exc.reason}") from exc
    try:
        return ET.fromstring(body)
    except ET.ParseError as exc:
        text = redact(body.decode("utf-8", errors="replace"), store)
        raise SystemExit(f"XML を読めませんでした: {text[:500]}") from exc


def text_of(node: ET.Element, name: str) -> str:
    child = node.find(name)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def main() -> None:
    store = load_store()
    save_store(store)
    ensure_access_token(store)
    categories = api_get(store, "stCategoryList", {"seller_id": SELLER_ID})
    page_keys = []
    for result in categories.findall("Result"):
        page_key = text_of(result, "PageKey")
        if page_key:
            page_keys.append((page_key, text_of(result, "Name")))
    if not page_keys:
        raise SystemExit("ストアカテゴリがありません。ストアアカウントが違う可能性があります。")
    print(f"ストアアカウント: {SELLER_ID}")
    print(f"カテゴリ数: {categories.attrib.get('totalResultsAvailable', str(len(page_keys)))}")
    shown = 0
    for page_key, category_name in page_keys:
        if shown >= 5:
            break
        time.sleep(1.1)
        items = api_get(
            store,
            "myItemList",
            {
                "seller_id": SELLER_ID,
                "stcat_key": page_key,
                "stock": "true",
                "results": "5",
            },
        )
        for result in items.findall("Result"):
            if shown >= 5:
                break
            code = text_of(result, "ItemCode")
            if not code:
                continue
            name = text_of(result, "Name")
            quantity = text_of(result, "Quantity")
            has_sub = text_of(result, "HasSubCode")
            quantity_label = quantity if quantity else ("個別商品コードあり" if has_sub == "1" else "空")
            print(f"{code}\t{quantity_label}\t{category_name}\t{name}")
            shown += 1
    if shown == 0:
        raise SystemExit("カテゴリは取得できましたが、商品が返りませんでした。")
    print(f"取得件数: {shown}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("中断しました。")
