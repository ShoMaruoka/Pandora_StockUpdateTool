"""営業日の判定。SQL Server には接続しない。"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from business_day import CLOSED_SQL, UNREADABLE, closed_reason, is_company_closed, read_closed  # noqa: E402

# 2026-10-23 に dbo.T007CM休業日 で確認した、2026年の平日の休業日。
COMPANY_CLOSED_2026 = {
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 12), date(2026, 2, 11), date(2026, 2, 23),
    date(2026, 3, 20), date(2026, 4, 29), date(2026, 5, 4), date(2026, 5, 5), date(2026, 5, 6),
    date(2026, 7, 20), date(2026, 8, 11), date(2026, 8, 13), date(2026, 8, 14), date(2026, 9, 21),
    date(2026, 9, 22), date(2026, 9, 23), date(2026, 10, 12), date(2026, 11, 3), date(2026, 11, 23),
}


class Recorder:
    """会社休業日の問い合わせ。呼ばれた日付を残す。"""

    def __init__(self, closed=()) -> None:
        self.closed = set(closed)
        self.calls: list[date] = []

    def __call__(self, day: date) -> bool:
        self.calls.append(day)
        return day in self.closed


class ClosedReasonTest(unittest.TestCase):
    def test_saturday_is_closed_without_asking_the_company_calendar(self) -> None:
        ask = Recorder()
        self.assertEqual(closed_reason(date(2026, 10, 24), ask), "土曜")
        self.assertEqual(ask.calls, [])

    def test_sunday_is_closed_without_asking_the_company_calendar(self) -> None:
        ask = Recorder()
        self.assertEqual(closed_reason(date(2026, 10, 25), ask), "日曜")
        self.assertEqual(ask.calls, [])

    def test_national_holiday_is_closed_with_its_name_without_asking(self) -> None:
        ask = Recorder()
        self.assertEqual(closed_reason(date(2026, 11, 3), ask), "祝日 文化の日")
        self.assertEqual(ask.calls, [])

    def test_substitute_holiday_is_a_holiday(self) -> None:
        reason = closed_reason(date(2026, 5, 6), Recorder())
        self.assertTrue(reason.startswith("祝日"), reason)

    def test_citizens_holiday_between_two_holidays_is_a_holiday(self) -> None:
        reason = closed_reason(date(2026, 9, 22), Recorder())
        self.assertTrue(reason.startswith("祝日"), reason)

    def test_weekday_in_company_calendar_is_closed(self) -> None:
        for day in (date(2026, 1, 2), date(2026, 8, 13)):
            with self.subTest(day=day):
                self.assertEqual(closed_reason(day, Recorder({day})), "会社休業日")

    def test_ordinary_weekday_is_a_business_day(self) -> None:
        ask = Recorder()
        self.assertIsNone(closed_reason(date(2026, 10, 23), ask))
        self.assertEqual(ask.calls, [date(2026, 10, 23)])

    def test_christmas_and_setsubun_are_business_days(self) -> None:
        for day in (date(2026, 12, 25), date(2026, 2, 3)):
            with self.subTest(day=day):
                self.assertIsNone(closed_reason(day, Recorder()))

    def test_failure_of_the_company_calendar_is_not_treated_as_a_business_day(self) -> None:
        def broken(day: date) -> bool:
            raise SystemExit("読めません")

        with self.assertRaises(SystemExit):
            closed_reason(date(2026, 10, 23), broken)

    def test_failure_of_the_company_calendar_is_not_reached_on_weekends_and_holidays(self) -> None:
        def broken(day: date) -> bool:
            raise SystemExit("読めません")

        self.assertEqual(closed_reason(date(2026, 10, 24), broken), "土曜")
        self.assertEqual(closed_reason(date(2026, 11, 3), broken), "祝日 文化の日")

    def test_every_2026_weekday_holiday_is_also_in_the_company_calendar(self) -> None:
        import jpholiday

        weekday_holidays = {
            day
            for day, _name in jpholiday.year_holidays(2026)
            if day.weekday() < 5
        }
        self.assertEqual(len(weekday_holidays), 17)
        self.assertLessEqual(weekday_holidays, COMPANY_CLOSED_2026)


class FakeCursor:
    def __init__(self, closed=()) -> None:
        self.closed = set(closed)
        self.calls = []
        self.rows = []

    def execute(self, sql, *params):
        self.calls.append((sql, params))
        self.rows = [(1,)] if params and params[0] in self.closed else []

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, cursor) -> None:
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self) -> None:
        self.closed = True


CONFIG = {"driver": "DRV", "server": "SECRET-SERVER", "database": "DB", "uid": "SECRET-USER", "password": "SECRET-PASS"}


class ReadClosedTest(unittest.TestCase):
    def test_returns_true_when_the_day_is_in_the_table(self) -> None:
        cursor = FakeCursor({date(2026, 11, 3)})
        self.assertTrue(read_closed(cursor, date(2026, 11, 3)))

    def test_returns_false_when_the_day_is_not_in_the_table(self) -> None:
        cursor = FakeCursor({date(2026, 11, 3)})
        self.assertFalse(read_closed(cursor, date(2026, 10, 23)))

    def test_day_is_passed_as_a_parameter_not_formatted_into_sql(self) -> None:
        cursor = FakeCursor()
        read_closed(cursor, date(2026, 10, 23))
        sql, params = cursor.calls[0]
        self.assertEqual(params, (date(2026, 10, 23),))
        self.assertNotIn("2026", sql)
        self.assertIn("?", sql)

    def test_sql_is_select_only(self) -> None:
        upper = CLOSED_SQL.upper()
        self.assertIn("SELECT", upper)
        self.assertIn("T007CM休業日", CLOSED_SQL)
        for word in ("INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "EXEC"):
            self.assertNotIn(word, upper)


class IsCompanyClosedTest(unittest.TestCase):
    def test_reads_through_the_connection_and_closes_it(self) -> None:
        connection = FakeConnection(FakeCursor({date(2026, 11, 3)}))
        result = is_company_closed(date(2026, 11, 3), load=lambda: CONFIG, connect=lambda text, timeout: connection)
        self.assertTrue(result)
        self.assertTrue(connection.closed)

    def test_connection_failure_becomes_the_fixed_message_without_details(self) -> None:
        def connect(text, timeout):
            raise RuntimeError("login failed for SECRET-USER on SECRET-SERVER")

        with self.assertRaises(SystemExit) as caught:
            is_company_closed(date(2026, 10, 23), load=lambda: CONFIG, connect=connect)
        self.assertEqual(caught.exception.code, UNREADABLE)

    def test_query_failure_closes_the_connection_and_uses_the_fixed_message(self) -> None:
        class Broken(FakeCursor):
            def execute(self, sql, *params):
                raise RuntimeError("Invalid object name SECRET-PASS")

        connection = FakeConnection(Broken())
        with self.assertRaises(SystemExit) as caught:
            is_company_closed(date(2026, 10, 23), load=lambda: CONFIG, connect=lambda text, timeout: connection)
        self.assertEqual(caught.exception.code, UNREADABLE)
        self.assertTrue(connection.closed)

    def test_missing_config_becomes_the_fixed_message(self) -> None:
        def load():
            raise SystemExit("認証ファイルがありません: C:/secret/sqlserver.json")

        with self.assertRaises(SystemExit) as caught:
            is_company_closed(date(2026, 10, 23), load=load)
        self.assertEqual(caught.exception.code, UNREADABLE)

    def test_fixed_message_says_stock_was_not_updated(self) -> None:
        self.assertEqual(UNREADABLE, "休業日（T007CM休業日）を読めなかったため、在庫を更新していません")


if __name__ == "__main__":
    unittest.main()
