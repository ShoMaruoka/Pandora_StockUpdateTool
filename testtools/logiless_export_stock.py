"""ロジレスの論理在庫（フリー在庫1以上）をCSVへ保存する。"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOKEN_URL = "https://app2.logiless.com/oauth2/token"
STORE_PATH = Path.home() / ".ec_inventory" / "logiless_oauth.json"
OUT_DIR = Path(__file__).resolve().parents[1] / "output" / "logiless"
PAGE_LIMIT = 100


def load_store() -> dict:
    if not STORE_PATH.exists():
        raise SystemExit(f"認可ファイルがありません: {STORE_PATH}")
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def save_store(data: dict) -> None:
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_access_token(store: dict) -> dict:
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
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"トークンの更新に失敗しました ({exc.code}): {detail}") from exc
    expires_in = int(token.get("expires_in") or 0)
    store["access_token"] = token.get("access_token") or ""
    store["refresh_token"] = token.get("refresh_token") or store["refresh_token"]
    store["token_type"] = token.get("token_type") or store.get("token_type") or ""
    store["expires_at"] = int(time.time()) + expires_in
    if not store["access_token"]:
        raise SystemExit("更新後のアクセストークンがありません。")
    save_store(store)
    return store


def api_get(store: dict, path: str) -> dict:
    url = f"https://app2.logiless.com/api/v1/merchant/{store['merchant_id']}{path}"

    def call() -> dict:
        request = Request(url, headers={"Authorization": "Bearer " + store["access_token"]})
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        return call()
    except HTTPError as exc:
        if exc.code != 401:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"在庫取得に失敗しました ({exc.code}): {detail}") from exc
        refresh_access_token(store)
        try:
            return call()
        except HTTPError as retry_exc:
            detail = retry_exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"在庫取得に失敗しました ({retry_exc.code}): {detail}") from retry_exc
    except URLError as exc:
        raise SystemExit(f"ロジレスへ接続できません: {exc.reason}") from exc


def fetch_in_stock(store: dict) -> tuple[list[dict], int]:
    rows: list[dict] = []
    page = 1
    total = 0
    while True:
        query = urlencode({"limit": PAGE_LIMIT, "page": page, "min_free": 1, "layer": "Article"})
        body = api_get(store, "/logical_inventory_summaries?" + query)
        chunk = body.get("data") or []
        total = int(body.get("total_count") or 0)
        rows.extend(chunk)
        if not chunk or len(rows) >= total:
            break
        page += 1
    return rows, total


def to_csv_rows(items: list[dict]) -> list[dict]:
    out = []
    for item in items:
        article = item.get("article") or {}
        code = str(article.get("code") or "").strip()
        if not code:
            continue
        out.append(
            {
                "商品コード": code,
                "商品名": str(article.get("name") or ""),
                "フリー在庫": int(item.get("free") or 0),
            }
        )
    out.sort(key=lambda row: row["商品コード"])
    return out


def write_csv(rows: list[dict]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"logiless_在庫_{stamp}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["商品コード", "商品名", "フリー在庫"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    store = load_store()
    items, total = fetch_in_stock(store)
    rows = to_csv_rows(items)
    codes = [row["商品コード"] for row in rows]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        raise SystemExit("商品コードが重複しています: " + ", ".join(duplicates))
    if len(rows) != total:
        raise SystemExit(f"件数が一致しません。API {total} 件、CSV {len(rows)} 件")
    path = write_csv(rows)
    print(f"保存しました: {path}")
    print(f"件数: {len(rows)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("中断しました。")
