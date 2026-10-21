"""出品レポートの取得と解析、レポートとAPI一覧から対象SKUを決める。数量は更新しない。"""
from __future__ import annotations

import csv
import gzip
import io
import json
import time
from pathlib import Path
from urllib.request import urlopen

REPORT_TYPE = "GET_MERCHANT_LISTINGS_ALL_DATA"
POLL_SECONDS = 30
POLL_LIMIT = 60
DROP_PERCENT = 10

# 日本の出品レポートは見出しが日本語のことがある。英語名と両方で探す。
COLUMNS = {
    "sku": ("seller-sku", "出品者SKU"),
    "quantity": ("quantity", "数量"),
    "channel": ("fulfillment-channel", "フルフィルメント・チャネル", "フルフィルメント・チャンネル", "フルフィルメントチャネル"),
    "status": ("status", "ステータス"),
    "name": ("item-name", "商品名"),
}


def decode_report(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", errors="replace")


def parse_report(text: str) -> list[dict]:
    """タブ区切りのレポートを、行ごとの SKU、数量、チャネルにする。"""
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    headers = next(reader, [])
    index = {}
    for key, names in COLUMNS.items():
        for name in names:
            if name in headers:
                index[key] = headers.index(name)
                break
    if "sku" not in index:
        raise SystemExit("レポートに出品者SKUの列がありません。見出し: " + ", ".join(headers))
    rows = []
    for values in reader:
        if not any(values):
            continue

        def cell(key: str) -> str:
            pos = index.get(key)
            return values[pos].strip() if pos is not None and pos < len(values) else ""

        rows.append(
            {
                "sku": cell("sku"),
                "quantity": cell("quantity"),
                "channel": cell("channel"),
                "status": cell("status"),
                "name": cell("name"),
            }
        )
    return rows


def fetch_report(store: dict) -> dict:
    """レポートを作って読む。作れなかったときは state にその理由を入れ、rows は空にする。"""
    import amazon_listings as al

    try:
        body = {"reportType": REPORT_TYPE, "marketplaceIds": [al.MARKETPLACE_ID]}
        created = al._sp_json(store, "POST", "/reports/2021-06-30/reports", body)
        report_id = str(created.get("reportId") or "")
        if not report_id:
            return {"state": "NO_REPORT_ID", "rows": []}
        document_id = ""
        state = "TIMEOUT"
        for _ in range(POLL_LIMIT):
            time.sleep(POLL_SECONDS)
            status = al._sp_get(store, f"/reports/2021-06-30/reports/{report_id}")
            state = str(status.get("processingStatus") or "")
            if state == "DONE":
                document_id = str(status.get("reportDocumentId") or "")
                break
            if state in ("CANCELLED", "FATAL"):
                return {"state": state, "rows": []}
        else:
            return {"state": "TIMEOUT", "rows": []}
        document = al._sp_get(store, f"/reports/2021-06-30/documents/{document_id}")
        # 署名付きURLなので、アクセストークンは付けない。
        with urlopen(str(document["url"]), timeout=120) as response:
            raw = response.read()
        if document.get("compressionAlgorithm") == "GZIP":
            raw = gzip.decompress(raw)
        return {"state": "DONE", "rows": parse_report(decode_report(raw)), "raw": raw}
    except SystemExit as exc:
        return {"state": "ERROR", "rows": [], "error": str(exc.code)}
    except (OSError, ValueError, KeyError) as exc:
        return {"state": "ERROR", "rows": [], "error": type(exc).__name__}


def _dropped(previous: int | None, current: int) -> bool:
    """前回の値から 10% 以上減っているか。前回が無い、または 0 のときは見ない。"""
    return bool(previous) and (previous - current) * 100 >= previous * DROP_PERCENT


def _report_listings(rows: list[dict]) -> dict:
    """出品者出荷（DEFAULT）の行だけを SKU ごとの {数量, 商品名} にする。FBA の行は使わない。"""
    found: dict = {}
    for row in rows:
        if row.get("channel") != "DEFAULT":
            continue
        sku = str(row.get("sku") or "")
        if not sku or sku in found:
            continue
        quantity = str(row.get("quantity") or "").strip()
        found[sku] = {
            "quantity": int(quantity) if quantity.lstrip("-").isdigit() else None,
            "name": str(row.get("name") or ""),
        }
    return found


def choose_listings(report: dict | None, api: dict | None, previous: dict) -> dict:
    """レポートと API 一覧の和集合を作る。使えない側の理由は notes に残す。

    api が None のときは、API の検索がエラーで止まったことを表す。
    """
    notes: list[str] = []
    if api is None:
        return _result("failed", [], False, False, ["API の検索が失敗しました"])

    rows = list((report or {}).get("rows") or [])
    report_used = False
    if report is None:
        notes.append("レポートが使えません（取得できませんでした）")
    elif report.get("state") != "DONE":
        notes.append(f"レポートが使えません（状態 {report.get('state')}）")
    elif _dropped(previous.get("report_rows"), len(rows)):
        notes.append(f"レポートが使えません（行数 {len(rows)} 件、前回 {previous['report_rows']} 件から {DROP_PERCENT}% 以上減少）")
    else:
        report_used = True

    api_rows = list(api.get("listings") or [])
    declared = int(api.get("declared") or 0)
    api_used = False
    if not api.get("complete") or len(api_rows) != declared:
        notes.append(f"API 一覧が不足しています（取得 {len(api_rows)} 件、宣言 {declared} 件）")
    elif _dropped(previous.get("api_declared"), declared):
        notes.append(f"API 一覧が使えません（宣言 {declared} 件、前回 {previous['api_declared']} 件から {DROP_PERCENT}% 以上減少）")
    else:
        api_used = True

    if not report_used and not api_used:
        return _result("failed", [], False, False, notes)

    listings = []
    seen = set()
    from_report = _report_listings(rows) if report_used else {}
    for row in api_rows:
        sku = str(row.get("sku") or "")
        source = "both" if sku in from_report else "api"
        name = str(row.get("name") or "") or (from_report.get(sku) or {}).get("name", "")
        listed = {"sku": sku, "default_quantity": row.get("default_quantity"), "source": source, "name": name}
        if row.get("product_type"):
            listed["product_type"] = str(row["product_type"])
        listings.append(listed)
        seen.add(sku)
    for sku, found in from_report.items():
        if sku not in seen:
            listings.append({"sku": sku, "default_quantity": found["quantity"], "source": "report", "name": found["name"]})
    return _result("ok", listings, report_used, api_used, notes)


def _result(action: str, listings: list[dict], report_used: bool, api_used: bool, notes: list[str]) -> dict:
    return {"action": action, "listings": listings, "report_used": report_used, "api_used": api_used, "notes": notes}


def next_counts(previous: dict, *, report_used: bool, report_rows: int, api_used: bool, api_declared: int) -> dict:
    """使えた側だけ今夜の件数にする。使えなかった側は、前回の値を残す。"""
    counts = dict(previous)
    if report_used:
        counts["report_rows"] = int(report_rows)
    if api_used:
        counts["api_declared"] = int(api_declared)
    return counts


def load_counts(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: int(data[key]) for key in ("report_rows", "api_declared") if isinstance(data.get(key), int)}


def save_counts(path: Path, counts: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counts, ensure_ascii=False), encoding="utf-8")
