"""Chatwork 通知の文面と CSV。外部の Chatwork には接続しない。"""
from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"))

from nightly_amazon import run  # noqa: E402
from notify_chatwork import FILE_LIMIT, build_notice, build_notices, format_elapsed, load_config, post_chatwork, zeroed_rows  # noqa: E402

TOKEN = "secret-token-value"


def audit_rows() -> list[dict]:
    return [
        {"出品者SKU": "485706", "WebCD": "485706", "商品名": "商品A", "更新前数量": "0", "更新後数量": "26", "送るかどうか": "送る"},
        {"出品者SKU": "307679", "WebCD": "307679", "商品名": "商品,B", "更新前数量": "1", "更新後数量": "3", "送るかどうか": "送らない"},
        {"出品者SKU": "999999", "WebCD": "999999", "更新前数量": "4", "更新後数量": "4", "送るかどうか": "送らない"},
    ]


def read_csv(payload: bytes) -> list[dict]:
    text = payload.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


class NotifyChatworkTest(unittest.TestCase):
    def test_sent_notice_attaches_only_updated_rows(self) -> None:
        notice = build_notice(
            dry_run=False,
            action="sent",
            reason="",
            sent_count=1,
            audit_rows=audit_rows(),
            stamp="20261009_030000",
        )
        self.assertIn("完了", notice["message"])
        self.assertIn("更新 1 件", notice["message"])
        self.assertEqual(notice["filename"], "amazon_updated_20261009_030000.csv")
        rows = read_csv(notice["csv"])
        self.assertEqual(list(rows[0]), ["出品者SKU", "WebCD", "商品名", "更新前数量", "更新後数量"])
        self.assertEqual(rows, [{"出品者SKU": "485706", "WebCD": "485706", "商品名": "商品A", "更新前数量": "0", "更新後数量": "26"}])
        self.assertNotIn("307679", notice["csv"].decode("utf-8-sig"))
        self.assertNotIn("調整在庫", notice["csv"].decode("utf-8-sig"))
        self.assertNotIn(TOKEN, notice["message"])

    def test_failed_notice_is_text_with_count_and_reason(self) -> None:
        notice = build_notice(
            dry_run=False,
            action="failed",
            reason="出品一覧が不足しています",
            sent_count=0,
            audit_rows=audit_rows(),
        )
        self.assertIn("送った件数 0", notice["message"])
        self.assertIn("出品一覧が不足しています", notice["message"])
        self.assertIsNone(notice["csv"])

    def test_notes_are_appended_to_the_completion_message(self) -> None:
        notices = build_notices(
            dry_run=False,
            action="sent",
            reason="",
            sent_count=1,
            audit_rows=audit_rows(),
            notes=["API 一覧が不足しています（取得 1 件、宣言 2 件）"],
        )
        self.assertEqual(len(notices), 1)
        self.assertIn("更新 1 件", notices[0]["message"])
        self.assertIn("API 一覧が不足しています", notices[0]["message"])
        self.assertEqual([row["出品者SKU"] for row in read_csv(notices[0]["csv"])], ["485706"])

    def test_notes_alone_become_a_text_notice_when_nothing_was_updated(self) -> None:
        rows = [dict(row, 送るかどうか="送らない") for row in audit_rows()]
        notices = build_notices(
            dry_run=False, action="sent", reason="", sent_count=0, audit_rows=rows, notes=["レポートが使えません（状態 FATAL）"]
        )
        self.assertEqual(len(notices), 1)
        self.assertIsNone(notices[0]["csv"])
        self.assertIn("FATAL", notices[0]["message"])

    def test_zero_update_night_still_posts_one_text(self) -> None:
        rows = [dict(row, 送るかどうか="送らない") for row in audit_rows()]
        notices = build_notices(dry_run=False, action="sent", reason="", sent_count=0, audit_rows=rows)
        self.assertEqual(len(notices), 1)
        self.assertIsNone(notices[0]["csv"])
        self.assertIn("更新 0 件", notices[0]["message"])

    def test_elapsed_is_added_to_the_first_post_only(self) -> None:
        notices = build_notices(
            dry_run=False, action="sent", reason="", sent_count=1, audit_rows=audit_rows(), held_skus={"307679"}, elapsed="12分34秒"
        )
        self.assertEqual(len(notices), 2)
        self.assertTrue(notices[0]["message"].endswith("処理時間 12分34秒"))
        self.assertNotIn("処理時間", notices[1]["message"])

    def test_elapsed_is_added_to_failed_text(self) -> None:
        notices = build_notices(dry_run=False, action="failed", reason="x", sent_count=0, audit_rows=[], elapsed="5秒")
        self.assertIn("夜間在庫更新が失敗しました", notices[0]["message"])
        self.assertTrue(notices[0]["message"].endswith("処理時間 5秒"))

    def test_elapsed_comes_after_notes(self) -> None:
        notices = build_notices(
            dry_run=False, action="sent", reason="", sent_count=1, audit_rows=audit_rows(), notes=["NOTE"], elapsed="1秒"
        )
        message = notices[0]["message"]
        self.assertLess(message.index("NOTE"), message.index("処理時間 1秒"))

    def test_format_elapsed(self) -> None:
        self.assertEqual(format_elapsed(0), "0秒")
        self.assertEqual(format_elapsed(45.6), "45秒")
        self.assertEqual(format_elapsed(754), "12分34秒")
        self.assertEqual(format_elapsed(3723), "1時間02分03秒")

    def test_dry_run_with_notes_builds_nothing(self) -> None:
        self.assertEqual(
            build_notices(dry_run=True, action="sent", reason="", sent_count=0, audit_rows=audit_rows(), notes=["x"]), []
        )

    def zero_rows(self) -> list[dict]:
        def row(sku, before, after, send="送る"):
            return {"出品者SKU": sku, "WebCD": sku, "商品名": f"名{sku}", "更新前数量": before, "更新後数量": after, "送るかどうか": send}

        return [row("A", "3", "0"), row("B", "0", "0"), row("C", "5", "0", "送らない"), row("D", "3", "1"), row("E", "", "0")]

    def test_zeroed_rows_are_sent_rows_from_one_or_more_to_zero(self) -> None:
        self.assertEqual([row["出品者SKU"] for row in zeroed_rows(self.zero_rows())], ["A"])

    def test_zeroed_notice_is_a_separate_post_after_held(self) -> None:
        rows = self.zero_rows()
        notices = build_notices(
            dry_run=False, action="sent", reason="", sent_count=4, audit_rows=rows, held_skus={"C"}, zeroed_skus={"A"}, stamp="S"
        )
        self.assertEqual([n["filename"] for n in notices], ["amazon_updated_S.csv", "amazon_held_S.csv", "amazon_zeroed_S.csv"])
        self.assertIn("定番在庫以外", notices[2]["message"])
        self.assertIn("1 件", notices[2]["message"])
        zeroed = read_csv(notices[2]["csv"])
        self.assertEqual(list(zeroed[0]), ["出品者SKU", "WebCD", "商品名", "更新前数量", "更新後数量"])
        self.assertEqual([row["出品者SKU"] for row in zeroed], ["A"])

    def test_zeroed_notice_is_skipped_when_empty_or_failed_or_other_sku(self) -> None:
        rows = self.zero_rows()
        common = {"dry_run": False, "reason": "", "sent_count": 1, "audit_rows": rows}
        self.assertNotIn("amazon_zeroed", str(build_notices(action="sent", zeroed_skus=set(), **common)))
        self.assertNotIn("amazon_zeroed", str(build_notices(action="failed", zeroed_skus={"A"}, **common)))
        self.assertNotIn("amazon_zeroed", str(build_notices(action="sent", zeroed_skus={"A"}, requested_sku="D", **common)))
        self.assertEqual(build_notices(action="sent", zeroed_skus={"A"}, **dict(common, dry_run=True)), [])

    def test_rejected_skus_are_a_separate_post_with_reasons(self) -> None:
        rejected = [dict(audit_rows()[0], 理由="90000900 価格が不正です")]
        notices = build_notices(
            dry_run=False, action="sent", reason="", sent_count=1, audit_rows=audit_rows(), rejected_rows=rejected, stamp="S"
        )
        self.assertEqual([n["filename"] for n in notices], ["amazon_updated_S.csv", "amazon_rejected_S.csv"])
        self.assertIn("受け付けなかった", notices[1]["message"])
        self.assertIn("1 件", notices[1]["message"])
        rows = read_csv(notices[1]["csv"])
        self.assertEqual(list(rows[0]), ["出品者SKU", "WebCD", "商品名", "更新前数量", "更新後数量", "理由"])
        self.assertEqual(rows[0]["理由"], "90000900 価格が不正です")

    def test_dry_run_builds_nothing(self) -> None:
        self.assertIsNone(build_notice(dry_run=True, action="sent", reason="", sent_count=0, audit_rows=audit_rows()))
        self.assertEqual(
            build_notices(dry_run=True, action="sent", reason="", sent_count=0, audit_rows=audit_rows(), held_skus={"307679"}),
            [],
        )

    def test_update_and_severe_drop_are_separate_posts(self) -> None:
        notices = build_notices(
            dry_run=False,
            action="sent",
            reason="",
            sent_count=1,
            audit_rows=audit_rows(),
            held_skus={"307679"},
            stamp="20261013_030000",
        )
        self.assertEqual(len(notices), 2)
        self.assertEqual(notices[0]["filename"], "amazon_updated_20261013_030000.csv")
        self.assertEqual([row["出品者SKU"] for row in read_csv(notices[0]["csv"])], ["485706"])
        self.assertEqual(notices[1]["filename"], "amazon_held_20261013_030000.csv")
        self.assertIn("1 件", notices[1]["message"])
        held_rows = read_csv(notices[1]["csv"])
        self.assertEqual(list(held_rows[0]), ["出品者SKU", "WebCD", "商品名", "更新前数量", "更新後数量"])
        self.assertEqual(held_rows, [{"出品者SKU": "307679", "WebCD": "307679", "商品名": "商品,B", "更新前数量": "1", "更新後数量": "3"}])
        self.assertNotIn("999999", notices[1]["csv"].decode("utf-8-sig"))

    def test_named_sku_notice_ignores_other_drops(self) -> None:
        notices = build_notices(
            dry_run=False,
            action="sent",
            reason="",
            sent_count=1,
            audit_rows=audit_rows(),
            held_skus={"307679"},
            requested_sku="485706",
        )
        self.assertEqual(len(notices), 1)
        self.assertIn("485706", notices[0]["csv"].decode("utf-8-sig"))

    def test_failed_notice_omits_the_drop_csv(self) -> None:
        notices = build_notices(
            dry_run=False,
            action="failed",
            reason="出品一覧が不足しています",
            sent_count=0,
            audit_rows=audit_rows(),
            held_skus={"307679"},
        )
        self.assertEqual(len(notices), 1)
        self.assertIsNone(notices[0]["csv"])

    def test_oversized_csv_is_omitted_from_the_message(self) -> None:
        wide = dict(audit_rows()[0])
        wide["更新後数量"] = "9" * (FILE_LIMIT + 1)
        notice = build_notice(dry_run=False, action="sent", reason="", sent_count=1, audit_rows=[wide])
        self.assertIsNone(notice["csv"])
        self.assertIn("5MB", notice["message"])
        self.assertIn("更新 1 件", notice["message"])

    def test_post_uses_file_endpoint_for_csv_and_message_endpoint_without(self) -> None:
        seen = []

        def opener(request):
            seen.append(request)
            return io.BytesIO(b'{"message_id":"1","file_id":1}')

        sent = build_notice(dry_run=False, action="sent", reason="", sent_count=1, audit_rows=audit_rows())
        post_chatwork({"api_token": TOKEN, "room_id": "4242"}, sent, opener)
        failed = build_notice(
            dry_run=False, action="failed", reason="取得に失敗しました", sent_count=0, audit_rows=[]
        )
        post_chatwork({"api_token": TOKEN, "room_id": "4242"}, failed, opener)
        self.assertTrue(seen[0].full_url.endswith("/rooms/4242/files"))
        self.assertIn(b"485706", seen[0].data)
        self.assertIn("完了".encode("utf-8"), seen[0].data)
        self.assertTrue(seen[1].full_url.endswith("/rooms/4242/messages"))
        self.assertNotIn(b"485706", seen[1].data)
        self.assertEqual(seen[0].get_header("X-chatworktoken"), TOKEN)

    def test_post_error_hides_the_token(self) -> None:
        def opener(request):
            raise HTTPError(request.full_url, 401, "no", hdrs=None, fp=io.BytesIO(f"bad {TOKEN}".encode("utf-8")))

        notice = build_notice(dry_run=False, action="failed", reason="取得に失敗しました", sent_count=0, audit_rows=[])
        with self.assertRaises(SystemExit) as caught:
            post_chatwork({"api_token": TOKEN, "room_id": "4242"}, notice, opener)
        self.assertNotIn(TOKEN, str(caught.exception))

    def test_config_reads_token_and_room_without_enabling_held(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "chatwork.json"
            path.write_text(json.dumps({"api_token": TOKEN, "room_id": "4242"}), encoding="utf-8")
            config = load_config(path)
        self.assertEqual(config["room_id"], "4242")
        self.assertFalse(config["notify_held"])

    def test_dry_run_posts_nothing(self) -> None:
        notices = []
        with tempfile.TemporaryDirectory() as folder:
            code = run(
                Path(folder),
                dry_run=True,
                sku="485706",
                fetch_wholesale=lambda: {"485706": {120: 51}},
                fetch_free=lambda: {},
                fetch_listings=lambda: {
                    "complete": True,
                    "declared": 1,
                    "listings": [{"sku": "485706", "default_quantity": 0}],
                },
                fetch_quotes=lambda _numbers: {},
                send=lambda _updates: notices.append("sent-amazon"),
                notify=lambda notice: notices.append(notice),
            )
        self.assertEqual(code, 0)
        self.assertEqual(notices, [])

    def test_held_posts_nothing_by_default(self) -> None:
        notices = []
        sent = []
        with tempfile.TemporaryDirectory() as folder:
            code = run(
                Path(folder),
                dry_run=False,
                sku="000000",
                fetch_wholesale=lambda: {"307679": {120: 1}},
                fetch_free=lambda: {},
                fetch_listings=lambda: {
                    "complete": True,
                    "declared": 1,
                    "listings": [{"sku": "307679", "default_quantity": 20}],
                },
                fetch_quotes=lambda _numbers: {},
                send=lambda updates: sent.append(list(updates)),
                notify=lambda notice: notices.append(notice),
            )
        self.assertEqual(code, 1)
        self.assertEqual(sent, [])
        self.assertEqual(len(notices), 1)
        self.assertIsNone(notices[0]["csv"])
        self.assertNotIn("307679", notices[0]["message"])

    def test_failed_run_posts_text_and_does_not_send_stock(self) -> None:
        notices = []
        sent = []
        with tempfile.TemporaryDirectory() as folder:
            code = run(
                Path(folder),
                dry_run=False,
                sku="485706",
                fetch_wholesale=lambda: {"485706": {120: 51}},
                fetch_free=lambda: {},
                fetch_listings=lambda: {"complete": False, "declared": 2, "listings": [{"sku": "485706", "default_quantity": 0}]},
                fetch_quotes=lambda _numbers: {},
                send=lambda updates: sent.append(list(updates)),
                notify=lambda notice: notices.append(notice),
            )
        self.assertEqual(code, 1)
        self.assertEqual(sent, [])
        self.assertEqual(len(notices), 1)
        self.assertIsNone(notices[0]["csv"])
        self.assertIn("送った件数 0", notices[0]["message"])
        self.assertIn("出品一覧が不足しています", notices[0]["message"])

    def test_sent_sku_posts_only_that_row(self) -> None:
        notices = []
        sent = []
        with tempfile.TemporaryDirectory() as folder:
            code = run(Path(folder), dry_run=False, notify=lambda notice: notices.append(notice), send=lambda updates: sent.append(list(updates)), **_two_skus())
        self.assertEqual(code, 0)
        self.assertEqual(sent, [[{"sku": "485706", "quantity": 26, "channel": "DEFAULT"}]])
        self.assertEqual([row["出品者SKU"] for row in read_csv(notices[0]["csv"])], ["485706"])
        self.assertNotIn("307679", notices[0]["csv"].decode("utf-8-sig"))

    def test_notify_failure_does_not_send_stock_again(self) -> None:
        sent = []

        def notify(_notice):
            raise RuntimeError(TOKEN)

        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            with redirect_stdout(stdout):
                code = run(
                    Path(folder),
                    dry_run=False,
                    notify=notify,
                    send=lambda updates: sent.append(list(updates)),
                    **_two_skus(),
                )
        self.assertEqual(code, 0)
        self.assertEqual(len(sent), 1)
        self.assertNotIn(TOKEN, stdout.getvalue())
        self.assertIn("通知に失敗しました", stdout.getvalue())


def _two_skus() -> dict:
    return {
        "sku": "485706",
        "fetch_wholesale": lambda: {"485706": {120: 51}, "307679": {120: 4}},
        "fetch_free": lambda: {},
        "fetch_listings": lambda: {
            "complete": True,
            "declared": 2,
            "listings": [
                {"sku": "485706", "default_quantity": 0},
                {"sku": "307679", "default_quantity": 2},
            ],
        },
        "fetch_quotes": lambda _numbers: {},
    }


if __name__ == "__main__":
    unittest.main()
