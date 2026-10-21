"""夜間ジョブの dry-run。外部APIには接続しない。"""
from __future__ import annotations

import codecs
import csv
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"))

from amazon_patch import PatchRejected, ReadbackPending  # noqa: E402
from amazon_report import load_counts, save_counts  # noqa: E402
import nightly_amazon  # noqa: E402
from nightly_amazon import run  # noqa: E402


def listings() -> dict:
    return {
        "complete": True,
        "declared": 3,
        "listings": [
            {"sku": "307679", "default_quantity": 1},
            {"sku": "2003739", "default_quantity": 20},
            {"sku": "NODEFLT", "default_quantity": None},
        ],
    }


def sources():
    sent = []

    def send(updates):
        sent.append(list(updates))

    return {
        "fetch_wholesale": lambda: {"307679": {120: 5, 180: 100}},
        "fetch_free": lambda: {"307679": 1},
        "fetch_listings": listings,
        "send": send,
        "sent": sent,
    }


def read_csv_file(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_audit(folder: Path) -> list[dict]:
    path = next(folder.glob("amazon_audit_*.csv"))
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class NightlyAmazonTest(unittest.TestCase):
    def setUp(self) -> None:
        # main() のログと output を、リポジトリではなく一時フォルダに書かせる。
        self._root = tempfile.TemporaryDirectory()
        self.addCleanup(self._root.cleanup)
        patcher = mock.patch.object(nightly_amazon, "ROOT", Path(self._root.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def logs(self) -> list[Path]:
        return sorted((Path(self._root.name) / "output" / "logs").glob("nightly_*.log"))

    def test_dry_run_writes_audit_and_sends_nothing(self) -> None:
        src = sources()
        with tempfile.TemporaryDirectory() as folder:
            code = run(Path(folder), dry_run=True, now=datetime(2026, 10, 8, 3, 0), **{
                key: src[key] for key in ("fetch_wholesale", "fetch_free", "fetch_listings", "send")
            })
            self.assertEqual(code, 0)
            self.assertEqual(src["sent"], [])
            rows = {row["出品者SKU"]: row for row in read_audit(Path(folder))}
            self.assertEqual(
                rows["307679"],
                {
                    "出品者SKU": "307679",
                    "WebCD": "307679",
                    "商品名": "",
                    "更新前数量": "1",
                    "更新後数量": "4",
                    "送るかどうか": "送る",
                },
            )
            self.assertEqual(rows["2003739"]["送るかどうか"], "送らない")
            self.assertEqual(rows["2003739"]["更新後数量"], "20")
            self.assertEqual(rows["NODEFLT"]["送るかどうか"], "送らない")
            self.assertEqual(rows["NODEFLT"]["更新後数量"], "")
            adjusted = next(Path(folder).glob("adjusted_stock_*.csv"))
            with adjusted.open(encoding="utf-8-sig", newline="") as handle:
                stock = list(csv.DictReader(handle))
            self.assertEqual(stock, [{"WebCD": "307679", "調整在庫": "3"}])

    def test_quote_minimum_is_written_and_not_sent_in_dry_run(self) -> None:
        src = sources()
        src["fetch_wholesale"] = lambda: {
            "307679": {120: 5, 180: 100},
            "499119": {120: 4},
            "524640": {120: 1},
        }
        src["fetch_free"] = lambda: {"307679": 1, "499119": 1}
        src["fetch_listings"] = lambda: {
            "complete": True,
            "declared": 2,
            "listings": [
                {"sku": "307679", "default_quantity": 1},
                {"sku": "2003739", "default_quantity": 4},
            ],
        }
        src["fetch_quotes"] = lambda numbers: {
            "2003739": {
                "header": {"見積番号": "2003739", "得意先CD": 300},
                "lines": [
                    {"行番号": 1, "区分": "1", "商品CD": "4902380211495", "webcd": "499119", "in_view": True},
                    {"行番号": 2, "区分": "2", "商品CD": "4902380221883", "webcd": "524640", "in_view": True},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as folder:
            code = run(Path(folder), dry_run=True, **{
                key: src[key] for key in ("fetch_wholesale", "fetch_free", "fetch_listings", "fetch_quotes", "send")
            })
            self.assertEqual(code, 0)
            self.assertEqual(src["sent"], [])
            rows = {row["出品者SKU"]: row for row in read_audit(Path(folder))}
            self.assertEqual(rows["2003739"]["WebCD"], "524640")
            self.assertEqual(rows["2003739"]["更新前数量"], "4")
            self.assertEqual(rows["2003739"]["更新後数量"], "1")
            self.assertEqual(rows["2003739"]["送るかどうか"], "送る")

    def test_held_and_failed_send_nothing(self) -> None:
        held = sources()
        held["fetch_listings"] = lambda: {
            "complete": True,
            "declared": 1,
            "listings": [{"sku": "307679", "default_quantity": 20}],
        }
        failed = sources()
        failed["fetch_listings"] = lambda: {
            "complete": False,
            "declared": 2,
            "listings": [{"sku": "307679", "default_quantity": 1}],
        }
        with tempfile.TemporaryDirectory() as held_dir, tempfile.TemporaryDirectory() as failed_dir:
            held_code = run(Path(held_dir), dry_run=True, **{
                key: held[key] for key in ("fetch_wholesale", "fetch_free", "fetch_listings", "send")
            })
            failed_code = run(Path(failed_dir), dry_run=True, **{
                key: failed[key] for key in ("fetch_wholesale", "fetch_free", "fetch_listings", "send")
            })
            self.assertEqual(held_code, 0)
            self.assertEqual(failed_code, 1)
            self.assertEqual(held["sent"], [])
            self.assertEqual(failed["sent"], [])
            held_row = read_audit(Path(held_dir))[0]
            self.assertEqual(held_row["送るかどうか"], "送らない")
            self.assertEqual(held_row["更新後数量"], "4")

    def test_dry_run_marks_only_the_severe_sku(self) -> None:
        src = sources()
        src["fetch_wholesale"] = lambda: {"307679": {120: 5}, "263860": {120: 4}}
        src["fetch_free"] = lambda: {}
        src["fetch_listings"] = lambda: {
            "complete": True,
            "declared": 2,
            "listings": [
                {"sku": "307679", "default_quantity": 20},
                {"sku": "263860", "default_quantity": 1},
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            code = run(Path(folder), dry_run=True, **{
                key: src[key] for key in ("fetch_wholesale", "fetch_free", "fetch_listings", "send")
            })
            rows = {row["出品者SKU"]: row["送るかどうか"] for row in read_audit(Path(folder))}
        self.assertEqual(code, 0)
        self.assertEqual(rows, {"307679": "送らない", "263860": "送る"})
        self.assertEqual(src["sent"], [])

    def union_run(self, folder, *, report, api_rows, verify=None, previous=None, dry_run=True, sku=None, notify=None):
        """レポートあり（和集合）の実行。counts は folder 内の記録ファイルを使う。"""
        src = sources()
        src["fetch_wholesale"] = lambda: {"307679": {120: 5}, "263860": {120: 4}}
        src["fetch_free"] = lambda: {}
        counts_path = Path(folder) / "amazon_counts.json"
        if previous is not None:
            save_counts(counts_path, previous)
        verified = []

        def verify_listing(seller_sku):
            verified.append(seller_sku)
            return (verify or {}).get(seller_sku)

        code = run(
            Path(folder),
            dry_run=dry_run,
            sku=sku,
            fetch_wholesale=src["fetch_wholesale"],
            fetch_free=src["fetch_free"],
            fetch_listings=lambda: {"complete": True, "declared": len(api_rows), "listings": api_rows},
            fetch_report=lambda: report,
            counts_path=counts_path,
            verify_listing=verify_listing,
            send=src["send"],
            notify=notify,
        )
        return code, src["sent"], verified, counts_path

    def test_union_audits_report_only_sku_and_rereads_only_api_only_sku(self) -> None:
        report = {
            "state": "DONE",
            "rows": [
                {"sku": "307679", "quantity": "1", "channel": "DEFAULT"},
                {"sku": "263860", "quantity": "7", "channel": "DEFAULT"},
            ],
        }
        api_rows = [{"sku": "307679", "default_quantity": 1}, {"sku": "350980", "default_quantity": 3}]
        with tempfile.TemporaryDirectory() as folder:
            code, sent, verified, _ = self.union_run(folder, report=report, api_rows=api_rows, verify={"350980": 3})
            rows = {row["出品者SKU"]: row for row in read_audit(Path(folder))}
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])
        self.assertEqual(verified, ["350980"])
        self.assertEqual(rows["263860"]["更新前数量"], "7")
        self.assertEqual(rows["263860"]["更新後数量"], "2")
        self.assertEqual(rows["263860"]["送るかどうか"], "送る")
        self.assertEqual(rows["350980"]["更新前数量"], "3")

    def test_audit_has_item_name_right_after_webcd(self) -> None:
        report = {"state": "DONE", "rows": [{"sku": "263860", "quantity": "7", "channel": "DEFAULT", "name": "レポート名"}]}
        api_rows = [{"sku": "307679", "default_quantity": 1, "name": "API名"}]
        with tempfile.TemporaryDirectory() as folder:
            self.union_run(folder, report=report, api_rows=api_rows, verify={})
            path = next(Path(folder).glob("amazon_audit_*.csv"))
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = {row["出品者SKU"]: row["商品名"] for row in reader}
                header = reader.fieldnames
        self.assertEqual(header[:3], ["出品者SKU", "WebCD", "商品名"])
        self.assertEqual(rows, {"307679": "API名", "263860": "レポート名"})

    def test_api_only_sku_without_listing_is_not_sent(self) -> None:
        report = {"state": "DONE", "rows": [{"sku": "307679", "quantity": "1", "channel": "DEFAULT"}]}
        api_rows = [{"sku": "307679", "default_quantity": 1}, {"sku": "263860", "default_quantity": 4}]
        with tempfile.TemporaryDirectory() as folder:
            code, _sent, verified, _ = self.union_run(folder, report=report, api_rows=api_rows, verify={})
            rows = {row["出品者SKU"]: row for row in read_audit(Path(folder))}
        self.assertEqual(code, 0)
        self.assertEqual(verified, ["263860"])
        self.assertEqual(rows["263860"]["送るかどうか"], "送らない")
        self.assertEqual(rows["307679"]["送るかどうか"], "送る")

    def test_api_only_sku_uses_the_reread_quantity(self) -> None:
        report = {"state": "DONE", "rows": [{"sku": "307679", "quantity": "1", "channel": "DEFAULT"}]}
        api_rows = [{"sku": "307679", "default_quantity": 1}, {"sku": "263860", "default_quantity": 4}]
        with tempfile.TemporaryDirectory() as folder:
            _code, _sent, _verified, _ = self.union_run(folder, report=report, api_rows=api_rows, verify={"263860": 9})
            rows = {row["出品者SKU"]: row for row in read_audit(Path(folder))}
        self.assertEqual(rows["263860"]["更新前数量"], "9")

    def test_report_unusable_night_does_not_reread(self) -> None:
        report = {"state": "FATAL", "rows": []}
        api_rows = [{"sku": "307679", "default_quantity": 1}, {"sku": "263860", "default_quantity": 4}]
        with tempfile.TemporaryDirectory() as folder:
            code, _sent, verified, _ = self.union_run(folder, report=report, api_rows=api_rows)
            rows = {row["出品者SKU"]: row for row in read_audit(Path(folder))}
        self.assertEqual(code, 0)
        self.assertEqual(verified, [])
        self.assertEqual(rows["307679"]["送るかどうか"], "送る")

    def test_both_unusable_fails_and_sends_nothing(self) -> None:
        report = {"state": "CANCELLED", "rows": []}
        with tempfile.TemporaryDirectory() as folder:
            src = sources()
            code = run(
                Path(folder),
                dry_run=True,
                fetch_wholesale=src["fetch_wholesale"],
                fetch_free=src["fetch_free"],
                fetch_listings=lambda: {"complete": False, "declared": 5, "listings": [{"sku": "307679", "default_quantity": 1}]},
                fetch_report=lambda: report,
                counts_path=Path(folder) / "amazon_counts.json",
                verify_listing=lambda _sku: None,
                send=src["send"],
            )
            self.assertEqual(code, 1)
            self.assertEqual(src["sent"], [])
            self.assertTrue(all(row["送るかどうか"] == "送らない" for row in read_audit(Path(folder))))

    def test_report_fetch_exception_is_treated_as_unusable_report(self) -> None:
        def broken():
            raise RuntimeError("down")

        src = sources()
        with tempfile.TemporaryDirectory() as folder:
            code = run(
                Path(folder),
                dry_run=True,
                fetch_wholesale=src["fetch_wholesale"],
                fetch_free=src["fetch_free"],
                fetch_listings=listings,
                fetch_report=broken,
                counts_path=Path(folder) / "amazon_counts.json",
                verify_listing=lambda _sku: None,
                send=src["send"],
            )
        self.assertEqual(code, 0)

    def test_counts_are_recorded_and_unusable_side_keeps_previous(self) -> None:
        report = {"state": "FATAL", "rows": []}
        api_rows = [{"sku": "307679", "default_quantity": 1}]
        with tempfile.TemporaryDirectory() as folder:
            _code, _sent, _verified, counts_path = self.union_run(
                folder, report=report, api_rows=api_rows, previous={"report_rows": 100, "api_declared": 1}
            )
            self.assertEqual(load_counts(counts_path), {"report_rows": 100, "api_declared": 1})
        good = {"state": "DONE", "rows": [{"sku": "307679", "quantity": "1", "channel": "DEFAULT"}]}
        with tempfile.TemporaryDirectory() as folder:
            _code, _sent, _verified, counts_path = self.union_run(
                folder, report=good, api_rows=api_rows, previous={"report_rows": 1, "api_declared": 1}
            )
            self.assertEqual(load_counts(counts_path), {"report_rows": 1, "api_declared": 1})

    def test_report_drop_makes_report_unusable_and_notice_says_why(self) -> None:
        report = {"state": "DONE", "rows": [{"sku": "263860", "quantity": "2", "channel": "DEFAULT"}]}
        api_rows = [{"sku": "307679", "default_quantity": 1}]
        notices = []
        with tempfile.TemporaryDirectory() as folder:
            code, sent, verified, counts_path = self.union_run(
                folder,
                report=report,
                api_rows=api_rows,
                previous={"report_rows": 100},
                dry_run=False,
                sku="307679",
                notify=lambda notice: notices.append(notice),
            )
            self.assertEqual(load_counts(counts_path)["report_rows"], 100)
        self.assertEqual(code, 0)
        self.assertEqual(verified, [])
        self.assertEqual(sent, [[{"sku": "307679", "quantity": 3, "channel": "DEFAULT"}]])
        self.assertIn("レポートが使えません", notices[0]["message"])
        self.assertIn("10%", notices[0]["message"])

    def zero_run(self, folder, *, regular, dry_run=False):
        """前回 5 の SKU を 0 にする実行。--sku で1件だけ送る。"""
        events = []
        notices = []

        def fetch_regular(webcds):
            events.append(("regular", list(webcds)))
            if isinstance(regular, Exception):
                raise regular
            return regular

        code = run(
            Path(folder),
            dry_run=dry_run,
            sku=None if dry_run else "307679",
            fetch_wholesale=lambda: {"307679": {120: 0}, "263860": {120: 4}},
            fetch_free=lambda: {},
            fetch_listings=lambda: {
                "complete": True,
                "declared": 2,
                "listings": [
                    {"sku": "307679", "default_quantity": 5, "name": "取り寄せ品"},
                    {"sku": "263860", "default_quantity": 1},
                ],
            },
            fetch_regular=fetch_regular,
            send=lambda updates: events.append(("send", [row["sku"] for row in updates])),
            notify=None if dry_run else notices.append,
        )
        return code, events, notices

    def test_irregular_item_set_to_zero_gets_its_own_post_after_sending(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            code, events, notices = self.zero_run(folder, regular={"307679": 2})
        self.assertEqual(code, 0)
        self.assertEqual(events, [("send", ["307679"]), ("regular", ["307679"])])
        self.assertEqual(len(notices), 2)
        self.assertEqual(notices[1]["filename"].split("_")[1], "zeroed")
        self.assertIn("取り寄せ品", notices[1]["csv"].decode("utf-8-sig"))

    def test_regular_item_set_to_zero_is_not_listed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            _code, _events, notices = self.zero_run(folder, regular={"307679": 1})
        self.assertEqual(len(notices), 1)
        self.assertNotIn("zeroed", str(notices[0]["filename"]))

    def test_master_read_failure_keeps_the_send_and_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            code, events, notices = self.zero_run(folder, regular=RuntimeError("db down"))
        self.assertEqual(code, 0)
        self.assertEqual(events[0], ("send", ["307679"]))
        self.assertEqual(len(notices), 1)
        self.assertIn("定番在庫を読めなかった", notices[0]["message"])

    def test_dry_run_reads_master_but_posts_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            code, events, notices = self.zero_run(folder, regular={"307679": 2}, dry_run=True)
        self.assertEqual(code, 0)
        self.assertEqual(events, [("regular", ["307679"])])
        self.assertEqual(notices, [])

    def test_dry_run_saves_the_csvs_it_would_post(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.zero_run(folder, regular={"307679": 2}, dry_run=True)
            updated = read_csv_file(next(Path(folder).glob("amazon_updated_*.csv")))
            zeroed = read_csv_file(next(Path(folder).glob("amazon_zeroed_*.csv")))
            self.assertEqual(list(Path(folder).glob("amazon_held_*.csv")), [])
        self.assertEqual(sorted(row["出品者SKU"] for row in updated), ["263860", "307679"])
        self.assertEqual([row["出品者SKU"] for row in zeroed], ["307679"])
        self.assertEqual(zeroed[0]["商品名"], "取り寄せ品")

    def test_live_run_does_not_save_notice_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.zero_run(folder, regular={"307679": 2})
            self.assertEqual(list(Path(folder).glob("amazon_updated_*.csv")), [])

    def test_same_quantity_sku_is_not_sent_or_listed(self) -> None:
        src = sources()
        src["fetch_listings"] = lambda: {
            "complete": True,
            "declared": 1,
            "listings": [{"sku": "307679", "default_quantity": 4}],
        }
        notices = []
        with tempfile.TemporaryDirectory() as folder:
            code = run(Path(folder), dry_run=False, sku="307679", notify=notices.append, **{
                key: src[key] for key in ("fetch_wholesale", "fetch_free", "fetch_listings", "send")
            })
            row = read_audit(Path(folder))[0]
        self.assertEqual(code, 0)
        self.assertEqual(src["sent"], [])
        self.assertEqual(len(notices), 1)
        self.assertIsNone(notices[0]["csv"])
        self.assertIn("更新 0 件", notices[0]["message"])
        self.assertEqual((row["更新前数量"], row["更新後数量"], row["送るかどうか"]), ("4", "4", "送らない"))

    def test_dry_run_failure_prints_the_reason(self) -> None:
        stdout = io.StringIO()
        broken = mock.Mock(side_effect=SystemExit("認証ファイルがありません: X:\secrets\sqlserver.json"))
        with mock.patch.object(nightly_amazon, "_fetch_wholesale", broken), mock.patch.object(nightly_amazon, "_notify") as notify:
            with redirect_stdout(stdout):
                code = nightly_amazon.main(["--dry-run"])
        self.assertEqual(code, 1)
        self.assertIn("失敗しました", stdout.getvalue())
        self.assertIn("認証ファイルがありません", stdout.getvalue())
        notify.assert_not_called()

    def test_unexpected_error_prints_only_the_error_type(self) -> None:
        stdout = io.StringIO()
        broken = mock.Mock(side_effect=RuntimeError("secret-token-value"))
        with mock.patch.object(nightly_amazon, "_fetch_wholesale", broken), redirect_stdout(stdout):
            code = nightly_amazon.main(["--dry-run"])
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", stdout.getvalue())
        self.assertNotIn("secret-token-value", stdout.getvalue())

    def test_run_adds_elapsed_to_first_post_and_prints_it_in_dry_run(self) -> None:
        notices = []
        src = sources()
        keys = ("fetch_wholesale", "fetch_free", "fetch_listings", "send")
        with tempfile.TemporaryDirectory() as folder:
            run(Path(folder), dry_run=False, sku="307679", notify=notices.append, elapsed=lambda: 754, **{k: src[k] for k in keys})
        self.assertTrue(notices[0]["message"].endswith("処理時間 12分34秒"))
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(stdout):
            run(Path(folder), dry_run=True, elapsed=lambda: 5, **{k: src[k] for k in keys})
        self.assertIn("elapsed 5秒", stdout.getvalue())
        self.assertIn("処理時間 5秒", stdout.getvalue())

    def test_main_failure_text_has_elapsed(self) -> None:
        notices = []
        broken = mock.Mock(side_effect=SystemExit("認証ファイルがありません: X"))
        with mock.patch.object(nightly_amazon, "_fetch_wholesale", broken), mock.patch.object(
            nightly_amazon, "_notify", side_effect=notices.append
        ), redirect_stdout(io.StringIO()):
            code = nightly_amazon.main(["--sku", "307679"])
        self.assertEqual(code, 1)
        self.assertIn("処理時間", notices[0]["message"])

    def all_run(self, folder, *, fail_on=None, reject_on=()):
        """引数なし（全件更新）の実行。fail_on 回目の送信で失敗、reject_on の回で拒否させる。"""
        attempts = []
        notices = []

        def send(updates):
            attempts.append([dict(row) for row in updates])
            if fail_on is not None and len(attempts) == fail_on:
                raise SystemExit("Amazon がエラーを返しました (500): x")
            if len(attempts) in reject_on:
                raise PatchRejected(updates[0]["sku"], "90000900 価格が不正です")

        code = run(
            Path(folder),
            dry_run=False,
            fetch_wholesale=lambda: {
                "307679": {120: 5},
                "263860": {120: 4},
                "111111": {120: 8},
                "222222": {120: 0},
            },
            fetch_free=lambda: {},
            fetch_listings=lambda: {
                "complete": True,
                "declared": 5,
                "listings": [
                    {"sku": "307679", "default_quantity": 1, "name": "商品A", "product_type": "T"},
                    {"sku": "263860", "default_quantity": 1},
                    {"sku": "222222", "default_quantity": 20},
                    {"sku": "111111", "default_quantity": 1},
                    {"sku": "999999", "default_quantity": 3},
                ],
            },
            send=send,
            notify=notices.append,
        )
        return code, attempts, notices

    def test_full_update_sends_each_planned_sku_once_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            code, attempts, notices = self.all_run(folder)
            sent_rows = read_csv_file(next(Path(folder).glob("amazon_sent_*.csv")))
        self.assertEqual(code, 0)
        self.assertEqual([[row["sku"] for row in call] for call in attempts], [["307679"], ["263860"], ["111111"]])
        self.assertEqual([row["出品者SKU"] for row in sent_rows], ["307679", "263860", "111111"])
        self.assertEqual(list(sent_rows[0]), ["出品者SKU", "WebCD", "商品名", "更新前数量", "更新後数量"])
        self.assertEqual(sent_rows[0]["商品名"], "商品A")
        self.assertIn("更新 3 件", notices[0]["message"])

    def test_full_update_passes_known_product_type_only(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            _code, attempts, _notices = self.all_run(folder)
        self.assertEqual(attempts[0][0]["product_type"], "T")
        self.assertNotIn("product_type", attempts[1][0])
        self.assertEqual(attempts[0][0]["quantity"], 3)

    def test_full_update_stops_at_the_first_failure(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            code, attempts, notices = self.all_run(folder, fail_on=2)
            sent_rows = read_csv_file(next(Path(folder).glob("amazon_sent_*.csv")))
        self.assertEqual(code, 1)
        self.assertEqual(len(attempts), 2)
        self.assertEqual([row["出品者SKU"] for row in sent_rows], ["307679"])
        self.assertEqual(len(notices), 1)
        self.assertIsNone(notices[0]["csv"])
        self.assertIn("送った件数 1", notices[0]["message"])
        self.assertIn("未送信 2 件", notices[0]["message"])

    def test_rejected_sku_is_skipped_and_the_rest_are_sent(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            code, attempts, notices = self.all_run(folder, reject_on=(2,))
            sent_rows = read_csv_file(next(Path(folder).glob("amazon_sent_*.csv")))
            rejected = read_csv_file(next(Path(folder).glob("amazon_rejected_*.csv")))
        self.assertEqual(code, 0)
        self.assertEqual(len(attempts), 3)
        self.assertEqual([row["出品者SKU"] for row in sent_rows], ["307679", "111111"])
        self.assertEqual([row["出品者SKU"] for row in rejected], ["263860"])
        self.assertEqual(rejected[0]["理由"], "90000900 価格が不正です")
        self.assertIn("更新 2 件", notices[0]["message"])
        updated = notices[0]["csv"].decode("utf-8-sig")
        self.assertNotIn("263860", updated)
        self.assertEqual(notices[-1]["filename"].split("_")[1], "rejected")

    def test_too_many_rejections_stop_the_run(self) -> None:
        with mock.patch.object(nightly_amazon, "MAX_REJECTED", 1):
            with tempfile.TemporaryDirectory() as folder:
                code, attempts, notices = self.all_run(folder, reject_on=(1, 2))
        self.assertEqual(code, 1)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(len(notices), 1)
        self.assertIn("受け付けなかった", notices[0]["message"])
        self.assertIn("未送信 1 件", notices[0]["message"])

    def test_named_sku_with_slow_readback_is_completed_with_a_note(self) -> None:
        notices = []

        def send(updates):
            raise ReadbackPending(updates[0]["sku"], 4, 1)

        src = sources()
        keys = ("fetch_wholesale", "fetch_free", "fetch_listings")
        with tempfile.TemporaryDirectory() as folder:
            code = run(Path(folder), dry_run=False, sku="307679", send=send, notify=notices.append, **{k: src[k] for k in keys})
        self.assertEqual(code, 0)
        self.assertEqual(len(notices), 1)
        message = notices[0]["message"]
        self.assertIn("完了しました", message)
        self.assertNotIn("失敗", message)
        self.assertIn("307679", message)
        self.assertIn("反映を確認できませんでした", message)
        self.assertIsNotNone(notices[0]["csv"])

    def test_named_sku_rejection_fails(self) -> None:
        notices = []

        def send(updates):
            raise PatchRejected(updates[0]["sku"], "90000900 x")

        src = sources()
        keys = ("fetch_wholesale", "fetch_free", "fetch_listings")
        with tempfile.TemporaryDirectory() as folder:
            code = run(Path(folder), dry_run=False, sku="307679", send=send, notify=notices.append, **{k: src[k] for k in keys})
        self.assertEqual(code, 1)
        self.assertIn("90000900", notices[0]["message"])

    def test_full_update_with_no_changes_writes_no_sent_file(self) -> None:
        src = sources()
        src["fetch_listings"] = lambda: {"complete": True, "declared": 1, "listings": [{"sku": "307679", "default_quantity": 4}]}
        with tempfile.TemporaryDirectory() as folder:
            code = run(Path(folder), dry_run=False, **{k: src[k] for k in ("fetch_wholesale", "fetch_free", "fetch_listings", "send")})
            self.assertEqual(list(Path(folder).glob("amazon_sent_*.csv")), [])
        self.assertEqual(code, 0)
        self.assertEqual(src["sent"], [])

    def test_main_without_arguments_runs_the_full_update(self) -> None:
        with mock.patch.object(nightly_amazon, "run", return_value=0) as fake_run, mock.patch.object(nightly_amazon, "_held_enabled", return_value=False):
            code = nightly_amazon.main([])
        self.assertEqual(code, 0)
        kwargs = fake_run.call_args.kwargs
        self.assertFalse(kwargs["dry_run"])
        self.assertIsNone(kwargs["sku"])
        self.assertIs(kwargs["send"], nightly_amazon._send_all)

    def test_main_dry_run_and_sku_keep_their_senders(self) -> None:
        with mock.patch.object(nightly_amazon, "run", return_value=0) as fake_run:
            nightly_amazon.main(["--dry-run"])
        self.assertIs(fake_run.call_args.kwargs["send"], nightly_amazon._refuse_send)
        with mock.patch.object(nightly_amazon, "run", return_value=0) as fake_run, mock.patch.object(nightly_amazon, "_held_enabled", return_value=False):
            nightly_amazon.main(["--sku", "485706"])
        self.assertIs(fake_run.call_args.kwargs["send"], nightly_amazon._send_one)

    def test_main_writes_what_it_prints_to_a_log_file(self) -> None:
        stdout = io.StringIO()
        broken = mock.Mock(side_effect=SystemExit("認証ファイルがありません: X"))
        with mock.patch.object(nightly_amazon, "_fetch_wholesale", broken), redirect_stdout(stdout):
            code = nightly_amazon.main(["--dry-run"])
        self.assertEqual(code, 1)
        logs = self.logs()
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0].read_bytes().startswith(codecs.BOM_UTF8))
        text = logs[0].read_text(encoding="utf-8-sig")
        self.assertIn("start", text)
        self.assertIn("args --dry-run", text)
        self.assertIn("失敗しました: 認証ファイルがありません: X", text)
        self.assertIn("exit 1", text)
        self.assertIn("失敗しました", stdout.getvalue())

    def test_log_keeps_the_location_of_an_unexpected_error_but_not_its_message(self) -> None:
        broken = mock.Mock(side_effect=RuntimeError("secret-token-value"))
        with mock.patch.object(nightly_amazon, "_fetch_wholesale", broken), redirect_stdout(io.StringIO()):
            nightly_amazon.main(["--dry-run"])
        text = self.logs()[0].read_text(encoding="utf-8")
        self.assertIn("RuntimeError", text)
        self.assertIn("nightly_amazon.py", text)
        self.assertNotIn("secret-token-value", text)

    def test_bad_arguments_are_logged_and_return_failure(self) -> None:
        with redirect_stdout(io.StringIO()):
            code = nightly_amazon.main(["--sku"])
        self.assertEqual(code, 1)
        self.assertIn("--sku の値を指定してください", self.logs()[0].read_text(encoding="utf-8"))

    def test_run_continues_when_the_log_cannot_be_written(self) -> None:
        (Path(self._root.name) / "output").write_text("not a folder", encoding="utf-8")
        stdout = io.StringIO()
        with mock.patch.object(nightly_amazon, "run", return_value=0) as fake_run, redirect_stdout(stdout):
            code = nightly_amazon.main(["--dry-run"])
        self.assertEqual(code, 0)
        fake_run.assert_called_once()
        self.assertIn("ログを書けません", stdout.getvalue())

    def test_console_errors_do_not_stop_the_log(self) -> None:
        class BrokenConsole(io.StringIO):
            def write(self, text):
                raise UnicodeEncodeError("cp932", "x", 0, 1, "bad")

        with mock.patch.object(nightly_amazon, "run", return_value=0), redirect_stdout(BrokenConsole()):
            code = nightly_amazon.main(["--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("exit 0", self.logs()[0].read_text(encoding="utf-8"))

    def test_module_does_not_call_other_malls(self) -> None:
        source = (ROOT / "tools" / "nightly_amazon.py").read_text(encoding="utf-8").lower()
        for name in ("rakuten", "yahoo", "mercari", "itemrobot", "ir-selection"):
            self.assertNotIn(name, source)


if __name__ == "__main__":
    unittest.main()
