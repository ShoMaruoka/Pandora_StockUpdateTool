"""夜間の Amazon 在庫更新。dry-run は監査までで、数量は送らない。"""
from __future__ import annotations

import csv
import re
import sys
import time
import traceback
from collections import Counter
from datetime import date, datetime
from pathlib import Path

# スクリプトとして動かすときの読み込み先。exe では中に入っているので使わない。
SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adjusted_stock import adjusted_stock  # noqa: E402
from amazon_gate import AmazonRun, decide  # noqa: E402
from amazon_patch import PatchRejected, ReadbackPending, one_update  # noqa: E402
from amazon_report import choose_listings, load_counts, next_counts, save_counts  # noqa: E402
from business_day import closed_reason, is_company_closed  # noqa: E402
from engine import build_master, calc, parse_sku  # noqa: E402
from item_master import webcd_key  # noqa: E402
from notify_chatwork import REJECTED_COLUMNS, UPDATED_COLUMNS, build_notice, build_notices, format_elapsed, with_elapsed, zeroed_rows  # noqa: E402
from quote_stock import quote_quantity  # noqa: E402
from secrets_dir import app_root  # noqa: E402

# output を置くフォルダ。exe のときは exe の横。
ROOT = app_root()

EXIT = {"sent": 0, "held": 2, "failed": 1}
# Amazon が SKU 単位で拒否した件数がこれを超えたら、異常とみなして止める。
MAX_REJECTED = 20
AUDIT_COLUMNS = ["出品者SKU", "WebCD", "商品名", "更新前数量", "更新後数量", "送るかどうか"]
STOCK_COLUMNS = ["WebCD", "調整在庫"]


def run(output_dir, *, dry_run, fetch_wholesale, fetch_free, fetch_listings, send, fetch_quotes=None, sku=None, now=None, notify=None, notify_held=False, fetch_report=None, counts_path=None, verify_listing=None, fetch_regular=None, elapsed=None) -> int:
    """在庫と出品を読み、監査 CSV を書いてから送る。dry-run は送らない。sku があればその1件だけ送る。

    fetch_report があるとき、出品一覧は出品レポートと API 一覧の和集合にする。
    verify_listing は、API にだけある SKU の出品者出荷数量を読み直す（出品が無ければ None）。
    fetch_regular は、WebCD ごとの定番在庫（T410商品）を読む。送信のあとに、0 にした SKU の分だけ呼ぶ。
    elapsed は、起動からの秒数を返す。最初の投稿に処理時間として書く。
    """
    output_dir = Path(output_dir)
    warehouses = fetch_wholesale()
    free = fetch_free()
    catalog = fetch_listings()
    adjusted = {str(webcd): adjusted_stock(rows) for webcd, rows in warehouses.items()}
    master = build_master(adjusted, free)
    listings = list(catalog.get("listings") or [])
    declared = int(catalog.get("declared") or 0)
    list_ok = bool(catalog.get("complete"))
    list_reason = "出品一覧が不足しています"
    notes: list[str] = []
    if fetch_report is not None:
        previous = {} if counts_path is None else load_counts(counts_path)
        try:
            report = fetch_report()
        except (Exception, SystemExit):
            report = None
        choice = choose_listings(report, catalog, previous)
        notes = list(choice["notes"])
        if counts_path is not None:
            save_counts(
                counts_path,
                next_counts(
                    previous,
                    report_used=choice["report_used"],
                    report_rows=len((report or {}).get("rows") or []),
                    api_used=choice["api_used"],
                    api_declared=declared,
                ),
            )
        list_ok = choice["action"] == "ok"
        list_reason = "; ".join(notes) or "出品一覧が使えません"
        if list_ok:
            listings = choice["listings"]
            declared = len(listings)
            if choice["report_used"] and verify_listing is not None:
                for row in listings:
                    if row.get("source") == "api":
                        row["default_quantity"] = verify_listing(str(row["sku"]))
            print(
                "list report={0} api={1} union={2} report_only={3} api_only={4}".format(
                    choice["report_used"],
                    choice["api_used"],
                    len(listings),
                    sum(1 for row in listings if row.get("source") == "report"),
                    sum(1 for row in listings if row.get("source") == "api" and choice["report_used"]),
                )
            )
        for note in notes:
            print(f"note {note}")
    quote_numbers = [str(row.get("sku") or "") for row in listings if parse_sku(str(row.get("sku") or "")).operation == "quote"]
    bundles = {} if fetch_quotes is None else fetch_quotes(quote_numbers)
    available = {key: int(info["available"]) for key, info in master.items()}
    quotes = {}
    for number in quote_numbers:
        bundle = bundles.get(number)
        result = quote_quantity(
            None if bundle is None else bundle["header"],
            [] if bundle is None else bundle["lines"],
            available,
        )
        if result is not None:
            quotes[number] = result
    if list_ok:
        decision = decide(listings, master, declared, quotes)
    else:
        decision = AmazonRun("failed", len(listings), 0, 0, list_reason)

    target = _target_for_sku(decision, listings, master, quotes, sku)
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    stock_path = output_dir / f"adjusted_stock_{stamp}.csv"
    audit_path = output_dir / f"amazon_audit_{stamp}.csv"
    _write_csv(
        stock_path,
        STOCK_COLUMNS,
        [{"WebCD": webcd, "調整在庫": str(qty)} for webcd, qty in sorted(adjusted.items())],
    )
    send_sku = None if dry_run or target is None else str(sku)
    audit_rows = [
        _audit_row(row, master, decision, quotes, send_sku, requested_sku=sku, dry_run=dry_run) for row in listings
    ]
    _write_csv(audit_path, AUDIT_COLUMNS, audit_rows)
    shapes = Counter()
    for row in listings:
        seller_sku = str(row.get("sku") or "")
        if re.fullmatch(r"\d{6}", seller_sku):
            shapes["digit6"] += 1
        elif re.fullmatch(r"\d{7}", seller_sku):
            shapes["digit7"] += 1
        else:
            shapes[parse_sku(seller_sku).operation] += 1
    print(f"action {decision.action}")
    print(f"listed {decision.listed}")
    posted = 0
    attempted = 0
    remaining = 0
    send_error = None
    rejected: list[dict] = []
    if not dry_run and sku and target is not None:
        posted = 1
        attempted = 1
        try:
            send([target])
        except ReadbackPending as exc:
            # Amazon は受け付けている。反映が遅いだけなので失敗にはしない。
            notes.append(
                f"{exc.sku} は Amazon が受け付けましたが、待ち時間の間に反映を確認できませんでした"
                f"（送った数量 {exc.expected}、確認できた数量 {exc.actual}）。反映に十数分かかることがあるので、セラーセントラルで確認してください。"
            )
            print(f"note {exc}")
        except (Exception, SystemExit) as exc:
            send_error = exc
    elif not dry_run and not sku and decision.action == "sent":
        # 全件更新。1件ずつ送り、送れた SKU を追記する。
        # Amazon が SKU 単位で拒否したら飛ばして続ける。通信や認証の失敗、拒否の多すぎは残りを送らない。
        types = {str(row.get("sku") or ""): str(row.get("product_type") or "") for row in listings}
        audit_by_sku = {row["出品者SKU"]: row for row in audit_rows}
        sent_path = output_dir / f"amazon_sent_{stamp}.csv"
        rejected_path = output_dir / f"amazon_rejected_{stamp}.csv"
        for item in decision.updates:
            payload = dict(item)
            if types.get(item["sku"]):
                payload["product_type"] = types[item["sku"]]
            attempted += 1
            try:
                send([payload])
            except PatchRejected as exc:
                row = dict(audit_by_sku[item["sku"]], 理由=exc.reason)
                rejected.append(row)
                _append_csv(rejected_path, REJECTED_COLUMNS, row)
                if len(rejected) > MAX_REJECTED:
                    send_error = SystemExit(f"Amazon が受け付けなかった SKU が {MAX_REJECTED} 件を超えたため止めました")
                    break
                continue
            except (Exception, SystemExit) as exc:
                send_error = exc
                break
            posted += 1
            _append_csv(sent_path, UPDATED_COLUMNS, audit_by_sku[item["sku"]])
        remaining = len(decision.updates) - posted - len(rejected)
        print(f"sent {posted} rejected {len(rejected)} remaining {remaining}")
        if posted:
            print(f"sent file {sent_path}")
        if rejected:
            print(f"rejected file {rejected_path}")
    print(f"planned {decision.sent if decision.action == 'sent' else 0}")
    print(f"unchanged {len(decision.unchanged)}")
    print(f"requests {attempted}")
    if sku:
        print(f"target {sku} " + ("none" if target is None else f"quantity {target['quantity']}"))
    print(
        "sku digit6={0} digit7={1} direct={2} divide={3} multiply={4} manual={5}".format(
            shapes["digit6"],
            shapes["digit7"],
            shapes["direct"],
            shapes["divide"],
            shapes["multiply"],
            shapes["manual"],
        )
    )
    print(f"quote decided {len(quotes)} skipped {len(quote_numbers) - len(quotes)}")
    if decision.reason:
        print(f"reason {decision.reason}")
    print(f"audit {audit_path}")
    print(f"adjusted {stock_path}")
    # 通知に使う行。Amazon が拒否した SKU は、送っていないものとして扱う。
    refused = {row["出品者SKU"] for row in rejected}
    notice_rows = [dict(row, 送るかどうか="送らない") if row["出品者SKU"] in refused else row for row in audit_rows]
    zeroed_skus = set()
    candidates = zeroed_rows(notice_rows)
    if fetch_regular is not None and send_error is None and candidates:
        try:
            regular = fetch_regular([row["WebCD"] for row in candidates])
        except (Exception, SystemExit):
            notes.append("定番在庫を読めなかったため、定番在庫以外で 0 にした一覧は送っていません。")
            print("note 定番在庫を読めませんでした")
        else:
            zeroed_skus = {row["出品者SKU"] for row in candidates if regular.get(webcd_key(row["WebCD"])) == 2}
            print(f"zeroed irregular {len(zeroed_skus)} of {len(candidates)}")
    if send_error is not None:
        notice_action = "failed"
        notice_reason = _public_reason(send_error)
        if not sku:
            notice_reason += f" 未送信 {remaining} 件"
        exit_code = EXIT["failed"]
    elif not dry_run and target is not None:
        notice_action = "sent"
        notice_reason = ""
        exit_code = EXIT["sent"]
    elif sku and target is None and decision.action == "sent":
        if any(item["sku"] == str(sku) for item in decision.held) or str(sku) in decision.unchanged:
            notice_action = "sent"
            notice_reason = ""
            exit_code = EXIT["sent"]
        else:
            notice_action = "failed"
            notice_reason = "数量が決まらないSKUです"
            exit_code = EXIT["failed"]
    else:
        notice_action = decision.action
        notice_reason = decision.reason
        exit_code = EXIT[decision.action]
    # dry-run でも投稿の中身は作り、CSV を output に残す。投稿はしない。
    notices = build_notices(
        dry_run=False,
        action=notice_action,
        reason=notice_reason,
        sent_count=posted,
        audit_rows=notice_rows,
        held_skus={item["sku"] for item in decision.held},
        stamp=stamp,
        requested_sku=None if dry_run else sku,
        limited=bool(sku) and notice_action == "sent" and posted == 1,
        notes=notes,
        zeroed_skus=zeroed_skus,
        elapsed=_elapsed_text(elapsed),
        rejected_rows=rejected,
    )
    if dry_run:
        _save_preview(output_dir, notices)
        notices = []
    if notify is not None:
        for notice in notices:
            try:
                notify(notice)
            except (Exception, SystemExit):
                print("通知に失敗しました。在庫の再送はしません。")
                break
    return exit_code


def main(argv=None) -> int:
    """画面に出す内容を、output/logs/nightly_<日時>.log にも書く。タスク スケジューラでは画面が残らないため。"""
    args = list(sys.argv[1:] if argv is None else argv)
    log = _open_log(ROOT / "output" / "logs")
    console_out, console_err = sys.stdout, sys.stderr
    sys.stdout = _Tee(console_out, log)
    sys.stderr = _Tee(console_err, log)
    try:
        print(f"start {datetime.now():%Y-%m-%d %H:%M:%S} args {' '.join(args)}")
        if log is None:
            print("ログを書けません。画面にだけ出します。")
        code = _main(args)
        print(f"exit {code}")
        return code
    finally:
        sys.stdout, sys.stderr = console_out, console_err
        if log is not None:
            log.close()


class _Tee:
    """画面とログの両方に書く。片方で失敗しても、もう片方には書く。"""

    def __init__(self, *streams) -> None:
        self.streams = [stream for stream in streams if stream is not None]

    def write(self, text: str) -> int:
        for stream in self.streams:
            try:
                stream.write(text)
                stream.flush()
            except Exception:
                pass
        return len(text)

    def flush(self) -> None:
        for stream in self.streams:
            try:
                stream.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        return False


def _open_log(folder: Path):
    try:
        folder.mkdir(parents=True, exist_ok=True)
        # BOM 付きにして、メモ帳などで日本語が化けないようにする。
        return (folder / f"nightly_{datetime.now():%Y%m%d_%H%M%S}.log").open("a", encoding="utf-8-sig")
    except OSError:
        return None


def _main(args: list[str]) -> int:
    started = time.monotonic()

    def elapsed() -> float:
        return time.monotonic() - started

    try:
        sku = _option(args, "--sku")
    except SystemExit as exc:
        print(f"失敗しました: {exc.code}")
        return EXIT["failed"]
    # 引数なしは全件更新。--dry-run は送らない。--sku はその1件だけ送って読み戻す。
    dry_run = "--dry-run" in args
    try:
        # 休業日は何も取得せず、送らず、通知もせずに終わる。--force は判定しない。
        if "--force" in args:
            print("force 営業日の判定をしません")
        else:
            reason = _closed_today()
            if reason:
                print(f"skip 休業日（{reason}）")
                return 0
        return run(
            ROOT / "output",
            dry_run=dry_run,
            sku=sku,
            fetch_wholesale=_fetch_wholesale,
            fetch_free=_fetch_free,
            fetch_listings=_fetch_listings,
            fetch_quotes=_fetch_quotes,
            fetch_report=_fetch_report,
            counts_path=ROOT / "output" / "amazon_counts.json",
            verify_listing=_verify_listing,
            fetch_regular=_fetch_regular,
            send=_refuse_send if dry_run else (_send_one if sku else _send_all),
            notify=None if dry_run else _notify,
            notify_held=False if dry_run else _held_enabled(),
            elapsed=elapsed,
        )
    except (Exception, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code in (0, None):
            return 0
        # dry-run でも理由が分かるように表示する。想定外の例外は種類と場所だけで、中身は出さない。
        print(f"失敗しました: {_public_reason(exc)}")
        if not isinstance(exc, SystemExit):
            for frame in traceback.extract_tb(exc.__traceback__):
                print(f"  at {Path(frame.filename).name}:{frame.lineno} {frame.name}")
        if not dry_run:
            notice = build_notice(
                dry_run=False,
                action="failed",
                reason=_public_reason(exc),
                sent_count=0,
                audit_rows=[],
            )
            with_elapsed(notice, _elapsed_text(elapsed))
            try:
                _notify(notice)
            except (Exception, SystemExit):
                print("通知に失敗しました。在庫の再送はしません。")
        return EXIT["failed"]


def _closed_today(day: date | None = None) -> str | None:
    """今日が休業日なら理由。T007CM休業日を読めないときは SystemExit（営業日とはみなさない）。"""
    return closed_reason(day or date.today(), is_company_closed)


def _elapsed_text(elapsed) -> str | None:
    if elapsed is None:
        return None
    text = format_elapsed(elapsed())
    print(f"elapsed {text}")
    return text


def _public_reason(exc: BaseException) -> str:
    if isinstance(exc, SystemExit) and isinstance(exc.code, str):
        return exc.code
    return type(exc).__name__


def _notify(notice: dict) -> None:
    from notify_chatwork import load_config, post_chatwork

    post_chatwork(load_config(), notice)


def _held_enabled() -> bool:
    from notify_chatwork import load_config

    try:
        return bool(load_config()["notify_held"])
    except (Exception, SystemExit):
        return False


def _option(args: list[str], name: str) -> str | None:
    if name not in args:
        return None
    index = args.index(name)
    if index + 1 >= len(args):
        raise SystemExit(f"{name} の値を指定してください。")
    return args[index + 1]


def _target_for_sku(decision: AmazonRun, listings: list[dict], master: dict, quotes: dict, sku: str | None) -> dict | None:
    """指定SKUが更新リストにあるときだけ返す。急減や failed では返さない。"""
    if not sku or decision.action != "sent":
        return None
    return one_update(decision, sku)


def _audit_row(row: dict, master: dict, decision: AmazonRun, quotes: dict, send_sku: str | None = None, requested_sku: str | None = None, dry_run: bool = False) -> dict:
    sku = str(row.get("sku") or "")
    parsed = parse_sku(sku)
    old = row.get("default_quantity")
    if parsed.operation == "quote":
        found = quotes.get(sku)
        webcd = "" if found is None else found["webcd"]
        new = None if found is None else found["quantity"]
    else:
        webcd = parsed.webcd or ""
        new, _status, _info = calc(parsed, master)
    after = old if new is None else new
    in_updates = any(item["sku"] == sku for item in decision.updates)
    if requested_sku and not dry_run:
        will_send = bool(send_sku) and sku == send_sku
    else:
        will_send = decision.action == "sent" and in_updates
    return {
        "出品者SKU": sku,
        "WebCD": webcd,
        "商品名": str(row.get("name") or ""),
        "更新前数量": "" if old is None else str(old),
        "更新後数量": "" if after is None else str(after),
        "送るかどうか": "送る" if will_send else "送らない",
    }


def _save_preview(output_dir: Path, notices: list[dict]) -> None:
    """dry-run で、送るはずだった投稿の文面を表示し、CSV を同じファイル名で保存する。"""
    for notice in notices:
        print(f"notice {notice['message']}")
        if notice.get("csv") is not None:
            path = output_dir / str(notice["filename"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(notice["csv"])
            print(f"notice csv {path}")


def _append_csv(path: Path, headers: list[str], row: dict) -> None:
    """1行ずつ追記する。途中で止まっても、送れた分が残る。"""
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8-sig" if new else "utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in headers})


def _write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _fetch_wholesale() -> dict:
    from wholesale_stock import fetch_stock, load_config

    return fetch_stock(load_config())


def _fetch_free() -> dict:
    from logiless_stock import fetch_all

    return fetch_all()


def _fetch_listings() -> dict:
    from amazon_listings import fetch_all

    return fetch_all()


def _fetch_report() -> dict:
    import amazon_listings as al
    from amazon_report import fetch_report

    store = al._load_store()
    al._access_token(store)
    return fetch_report(store)


_reader = None


def _verify_listing(seller_sku: str):
    """API にだけある SKU を1件読み直す。最初の呼び出しで認証する。"""
    global _reader
    if _reader is None:
        from amazon_listings import make_reader

        _reader = make_reader()
    return _reader(seller_sku)


def _fetch_regular(webcds: list[str]) -> dict:
    from item_master import fetch_regular
    from wholesale_stock import load_config

    return fetch_regular(load_config(), webcds)


def _fetch_quotes(numbers: list[str]) -> dict:
    from quote_stock import fetch_quotes
    from wholesale_stock import load_config

    return fetch_quotes(load_config(), numbers)


def _refuse_send(_updates) -> None:
    raise SystemExit("dry-run では更新を送りません。")


def _send_all(updates: list[dict]) -> None:
    """全件更新の1件分。読み戻しはせず、ACCEPTED だけを確かめる。"""
    from amazon_listings import patch_quantity

    for row in updates:
        patch_quantity(str(row["sku"]), int(row["quantity"]), readback=False, product_type=str(row.get("product_type") or ""))


def _send_one(updates: list[dict]) -> None:
    from amazon_listings import patch_quantity

    if len(updates) != 1:
        raise SystemExit("指定した1件以外は送りません。")
    row = updates[0]
    patch_quantity(str(row["sku"]), int(row["quantity"]))


if __name__ == "__main__":
    raise SystemExit(main())
