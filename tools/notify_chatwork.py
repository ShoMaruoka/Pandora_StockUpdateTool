"""Chatwork への結果通知。在庫の再送はしない。"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.chatwork.com/v2"
FILE_LIMIT = 5 * 1024 * 1024
UPDATED_COLUMNS = ["出品者SKU", "WebCD", "商品名", "更新前数量", "更新後数量"]
REJECTED_COLUMNS = UPDATED_COLUMNS + ["理由"]
from secrets_dir import config_path

CONFIG_PATH = config_path("chatwork.json")


def build_notice(*, dry_run, action, reason, sent_count, audit_rows, notify_held=False, stamp="20261009_030000", limited=False) -> dict | None:
    """更新結果の1投稿。dry-run は None。"""
    if dry_run or action == "held":
        return None
    if action == "failed":
        return {
            "message": f"夜間在庫更新が失敗しました。送った件数 {sent_count}。理由: {reason}",
            "csv": None,
            "filename": None,
        }
    if action != "sent":
        return None
    updated = [row for row in audit_rows if row.get("送るかどうか") == "送る"]
    if not updated:
        return None
    payload = _csv_bytes(updated)
    message = f"夜間在庫更新が完了しました。更新 {len(updated)} 件。"
    if limited:
        message += "指定したSKUだけを更新しました。"
    if len(payload) > FILE_LIMIT:
        message += "CSVが5MBを超えたため、ファイルは添付していません。"
        return {"message": message, "csv": None, "filename": None}
    return {"message": message, "csv": payload, "filename": f"amazon_updated_{stamp}.csv"}


def zeroed_rows(audit_rows) -> list[dict]:
    """実際に送った行のうち、更新前 1 以上から 0 にした行。"""
    found = []
    for row in audit_rows:
        before = str(row.get("更新前数量") or "")
        after = str(row.get("更新後数量") or "")
        if row.get("送るかどうか") == "送る" and before.isdigit() and int(before) >= 1 and after == "0":
            found.append(row)
    return found


def format_elapsed(seconds: float) -> str:
    """処理時間を「1時間02分03秒」「12分34秒」「45秒」の形にする。"""
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}時間{minutes:02d}分{secs:02d}秒"
    if minutes:
        return f"{minutes}分{secs:02d}秒"
    return f"{secs}秒"


def with_elapsed(notice: dict, elapsed: str | None) -> dict:
    if elapsed:
        notice["message"] += f" 処理時間 {elapsed}"
    return notice


def build_notices(*, dry_run, action, reason, sent_count, audit_rows, held_skus=None, stamp="20261009_030000", requested_sku=None, limited=False, notes=None, zeroed_skus=None, elapsed=None, rejected_rows=None) -> list[dict]:
    """更新CSV、急減CSV、定番在庫以外で0にしたCSVを別投稿にする。失敗のときは文章だけ。

    notes は、出品レポートか API 一覧の片方が使えなかった理由など。最初の投稿に書き足す。
    zeroed_skus は、定番在庫以外の商品を 0 にした SKU。
    elapsed は処理時間の文字列。最初の投稿の最後に書き足す。
    rejected_rows は、Amazon が受け付けなかった SKU の行（「理由」つき）。
    投稿が1件も無い夜も、「更新 0 件」の文章を1件送る。
    """
    if dry_run:
        return []
    if action == "failed":
        failed = build_notice(
            dry_run=False,
            action="failed",
            reason=reason,
            sent_count=sent_count,
            audit_rows=audit_rows,
            stamp=stamp,
        )
        return [] if failed is None else [with_elapsed(failed, elapsed)]
    rows = list(audit_rows)
    drops = [row for row in rows if row.get("出品者SKU") in set(held_skus or ())]
    zeros = [row for row in zeroed_rows(rows) if row.get("出品者SKU") in set(zeroed_skus or ())]
    if requested_sku:
        rows = [row for row in rows if row.get("出品者SKU") == requested_sku]
        drops = [row for row in drops if row.get("出品者SKU") == requested_sku]
        zeros = [row for row in zeros if row.get("出品者SKU") == requested_sku]
    notices = []
    updated = build_notice(
        dry_run=False,
        action="sent",
        reason=reason,
        sent_count=sent_count,
        audit_rows=rows,
        stamp=stamp,
        limited=limited,
    )
    if updated is not None:
        notices.append(updated)
    held = _held_notice(drops, stamp)
    if held is not None:
        notices.append(held)
    zeroed = _list_notice(zeros, f"定番在庫以外の商品で、Amazon の在庫を 0 にしたSKUは {len(zeros)} 件です。", f"amazon_zeroed_{stamp}.csv")
    if zeroed is not None:
        notices.append(zeroed)
    rejected = list(rejected_rows or [])
    if requested_sku:
        rejected = [row for row in rejected if row.get("出品者SKU") == requested_sku]
    refused = _list_notice(
        rejected,
        f"Amazon が受け付けなかったSKUは {len(rejected)} 件です。理由は CSV の「理由」の列にあります。",
        f"amazon_rejected_{stamp}.csv",
        REJECTED_COLUMNS,
    )
    if refused is not None:
        notices.append(refused)
    if not notices:
        notices.append({"message": "夜間在庫更新が完了しました。更新 0 件。", "csv": None, "filename": None})
    if notes:
        notices[0]["message"] += " " + " ".join(notes)
    with_elapsed(notices[0], elapsed)
    return notices


def _held_notice(rows: list[dict], stamp: str) -> dict | None:
    return _list_notice(rows, f"急減のため送らなかったSKUは {len(rows)} 件です。", f"amazon_held_{stamp}.csv")


def _list_notice(rows: list[dict], message: str, filename: str, columns: list[str] = UPDATED_COLUMNS) -> dict | None:
    if not rows:
        return None
    payload = _csv_bytes(rows, columns)
    if len(payload) > FILE_LIMIT:
        message += "CSVが5MBを超えたため、ファイルは添付していません。"
        return {"message": message, "csv": None, "filename": None}
    return {"message": message, "csv": payload, "filename": filename}


def load_config(path=None) -> dict:
    config_path = Path(path) if path is not None else CONFIG_PATH
    if not config_path.exists():
        raise SystemExit(f"認証ファイルがありません: {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    missing = [key for key in ("api_token", "room_id") if not str(data.get(key) or "").strip()]
    if missing:
        raise SystemExit("不足しているキー: " + ", ".join(missing))
    return {
        "api_token": str(data["api_token"]),
        "room_id": str(data["room_id"]),
        "notify_held": data.get("notify_held") is True,
    }


def post_chatwork(config: dict, notice: dict, opener=None) -> None:
    """file があるときだけ CSV を同じ投稿に載せる。"""
    send = opener or urlopen
    token = str(config.get("api_token") or "")
    room = str(config.get("room_id") or "")
    if notice.get("csv") is None:
        payload = urlencode({"body": notice["message"]}).encode("utf-8")
        headers = {"X-ChatWorkToken": token, "Content-Type": "application/x-www-form-urlencoded"}
        url = f"{API}/rooms/{room}/messages"
    else:
        payload, content_type = _multipart(notice)
        headers = {"X-ChatWorkToken": token, "Content-Type": content_type}
        url = f"{API}/rooms/{room}/files"
    request = Request(url, data=payload, headers=headers, method="POST")
    try:
        with send(request) as response:
            response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit("Chatwork がエラーを返しました: " + _redact(detail, config)[:300]) from exc
    except URLError as exc:
        raise SystemExit("Chatwork へ接続できません: " + _redact(str(exc.reason), config)) from exc


def _csv_bytes(rows: list[dict], columns: list[str] = UPDATED_COLUMNS) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue().encode("utf-8-sig")


def _multipart(notice: dict) -> tuple[bytes, str]:
    boundary = "ecinventoryboundary"
    parts = [
        _part(boundary, "file", notice["csv"], notice["filename"]),
        _part(boundary, "message", notice["message"].encode("utf-8"), None),
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _part(boundary: str, name: str, content: bytes, filename: str | None) -> bytes:
    disposition = f'Content-Disposition: form-data; name="{name}"'
    if filename:
        disposition += f'; filename="{filename}"'
    header = f"--{boundary}\r\n{disposition}\r\n"
    if filename:
        header += "Content-Type: text/csv\r\n"
    header += "\r\n"
    return header.encode("utf-8") + content + b"\r\n"


def _redact(text: str, config: dict) -> str:
    hidden = text
    for key in ("api_token", "room_id"):
        value = str(config.get(key) or "")
        if value:
            hidden = hidden.replace(value, "***")
    return hidden
