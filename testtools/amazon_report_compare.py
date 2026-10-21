"""出品レポートと出品API一覧を読み、SKUと出品者出荷数量を突き合わせる。数量は更新しない。"""
from __future__ import annotations

import csv
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import amazon_listings as al  # noqa: E402
from amazon_report import REPORT_TYPE, fetch_report  # noqa: E402

OUT_DIR = ROOT / "output" / "amazon_compare"
COMPARE_COLUMNS = ["出品者SKU", "区分", "レポート数量", "API数量", "レポートチャネル", "レポートステータス"]


def compare(report_rows: list[dict], api_rows: list[dict]) -> list[dict]:
    """SKUの有無と、出品者出荷数量の違いを1行ずつ返す。"""
    report = {}
    for row in report_rows:
        report.setdefault(row["sku"], row)
    api = {str(row["sku"]): row for row in api_rows}
    result = []
    for sku in sorted(set(report) | set(api)):
        r = report.get(sku)
        a = api.get(sku)
        r_qty = "" if r is None else r["quantity"]
        a_qty = "" if a is None or a.get("default_quantity") is None else str(a["default_quantity"])
        if r is None:
            kind = "APIだけ"
        elif a is None:
            kind = "レポートだけ"
        elif r_qty != a_qty:
            kind = "数量違い"
        else:
            kind = "一致"
        result.append(
            {
                "出品者SKU": sku,
                "区分": kind,
                "レポート数量": r_qty,
                "API数量": a_qty,
                "レポートチャネル": "" if r is None else r["channel"],
                "レポートステータス": "" if r is None else r["status"],
            }
        )
    return result


def fetch_api(store: dict) -> tuple[dict, list[dict]]:
    """今の夜間ジョブと同じ読み方。作成日で区切った各回の件数も残す。"""
    segments = []

    def search(extra: dict) -> dict:
        def get_page(token: str | None) -> dict:
            if token or extra:
                time.sleep(0.2)
            query = {
                "marketplaceIds": al.MARKETPLACE_ID,
                "includedData": "summaries,fulfillmentAvailability",
                "pageSize": al.PAGE_SIZE,
                "sortBy": "createdDate",
                "sortOrder": "ASC",
            }
            query.update(extra)
            if token:
                query["pageToken"] = token
            return al._sp_get(store, f"/listings/2021-08-01/items/{store['seller_id']}?" + urlencode(query))

        result = al.fetch_listings(get_page)
        segments.append(
            {
                "createdAfter": extra.get("createdAfter", ""),
                "declared": result["declared"],
                "rows": len(result["listings"]),
                "complete": result["complete"],
                "capped": result["capped"],
            }
        )
        return result

    return al.fetch_catalog(search), segments


def write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    store = al._load_store()
    al._access_token(store)

    fetched = fetch_report(store)
    print(f"レポート状態 {fetched['state']} ({REPORT_TYPE})")
    if fetched["state"] != "DONE":
        raise SystemExit("レポートが作れませんでした: " + str(fetched.get("error") or fetched["state"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUT_DIR / f"report_{stamp}.txt"
    raw_path.write_bytes(fetched["raw"])
    rows = fetched["rows"]
    skus = Counter(row["sku"] for row in rows)
    print(f"レポート 行数 {len(rows)} SKU {len(skus)} 重複SKU {sum(1 for n in skus.values() if n > 1)}")
    print("レポート チャネル別: " + ", ".join(f"{k or '空'}={v}" for k, v in Counter(r["channel"] for r in rows).most_common()))
    print("レポート ステータス別: " + ", ".join(f"{k or '空'}={v}" for k, v in Counter(r["status"] for r in rows).most_common()))
    print(f"レポート保存 {raw_path}")

    if "--report-only" in args:
        return 0

    catalog, segments = fetch_api(store)
    for seg in segments:
        print(
            "API検索 createdAfter={0} 宣言 {1} 取得 {2} complete={3} capped={4}".format(
                seg["createdAfter"] or "-", seg["declared"], seg["rows"], seg["complete"], seg["capped"]
            )
        )
    api_rows = catalog["listings"]
    print(f"API 宣言 {catalog['declared']} 取得SKU {len(api_rows)} complete={catalog['complete']}")
    print(f"API 出品者出荷の数量なし {sum(1 for r in api_rows if r.get('default_quantity') is None)}")

    result = compare(rows, api_rows)
    print("突き合わせ: " + ", ".join(f"{k}={v}" for k, v in Counter(r["区分"] for r in result).most_common()))
    compare_path = OUT_DIR / f"compare_{stamp}.csv"
    write_csv(compare_path, COMPARE_COLUMNS, result)
    print(f"突き合わせ保存 {compare_path}")
    print("数量違いは、レポート作成とAPI読み取りの間の受注でも起きる。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit("中断しました。")
