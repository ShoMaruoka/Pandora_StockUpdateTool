"""営業日の判定。土日、国民の祝日、会社休業日のどれかに当たる日は休業日。

会社休業日は販売管理の dbo.T007CM休業日 から読む。書き込み SQL は持たない。
"""
from __future__ import annotations

from datetime import date
from typing import Callable

WEEKEND = {5: "土曜", 6: "日曜"}
CLOSED_SQL = "SELECT 1 FROM dbo.T007CM休業日 WHERE 非営業日 = ?"
# 接続先やユーザー名がエラーの中身に入ることがあるので、読めなかったときはこの文言だけを出す。
UNREADABLE = "休業日（T007CM休業日）を読めなかったため、在庫を更新していません"


def closed_reason(day: date, is_company_closed: Callable[[date], bool]) -> str | None:
    """休業日なら理由、営業日なら None。

    土日と祝日は日付だけで決まるので、会社休業日の問い合わせ（DB）は呼ばない。
    問い合わせが失敗したら、その例外をそのまま上げる。営業日とはみなさない。
    """
    if day.weekday() in WEEKEND:
        return WEEKEND[day.weekday()]
    import jpholiday

    holiday = jpholiday.is_holiday_name(day)
    if holiday:
        return f"祝日 {holiday}"
    if is_company_closed(day):
        return "会社休業日"
    return None


def read_closed(cursor, day: date) -> bool:
    """T007CM休業日 に day があるか。"""
    cursor.execute(CLOSED_SQL, day)
    return cursor.fetchone() is not None


def is_company_closed(day: date, *, load=None, connect=None) -> bool:
    """会社休業日かどうか。読めないときは、決まった文言の SystemExit にする（営業日とはみなさない）。"""
    try:
        from wholesale_stock import _connection_string, load_config

        config = (load or load_config)()
        if connect is None:
            import pyodbc

            connect = pyodbc.connect
        connection = connect(_connection_string(config), timeout=30)
        try:
            return read_closed(connection.cursor(), day)
        finally:
            connection.close()
    except (Exception, SystemExit):
        raise SystemExit(UNREADABLE) from None
