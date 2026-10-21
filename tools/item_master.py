"""販売管理 dbo.T410商品 の定番在庫の参照。書き込み SQL は持たない。"""
from __future__ import annotations

REGULAR_SQL = """
SELECT WebCD, 定番在庫
FROM dbo.T410商品
WHERE WebCD IN ({marks})
"""
# SQL Server のパラメータ上限（2100）より少なく区切る。
CHUNK = 1000


def webcd_key(value) -> str:
    """WebCD を数値として比べるため、先頭の 0 を外した文字列にする。数字でなければ空。"""
    text = "" if value is None else str(value).strip()
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    return str(int(text)) if text.isdigit() else ""


def read_regular(cursor, webcds) -> dict:
    """WebCD ごとの定番在庫（1 定番在庫、2 定番在庫以外）を返す。T410商品 に無い WebCD は入らない。"""
    wanted = sorted({int(key) for key in (webcd_key(webcd) for webcd in webcds) if key})
    result = {}
    for start in range(0, len(wanted), CHUNK):
        part = wanted[start:start + CHUNK]
        cursor.execute(REGULAR_SQL.format(marks=",".join("?" * len(part))), part)
        for webcd, regular in cursor.fetchall():
            key = webcd_key(webcd)
            if key and regular is not None:
                result[key] = int(regular)
    return result


def fetch_regular(config: dict, webcds) -> dict:
    import pyodbc

    from wholesale_stock import _connection_string, redact

    try:
        connection = pyodbc.connect(_connection_string(config), timeout=30)
        try:
            return read_regular(connection.cursor(), webcds)
        finally:
            connection.close()
    except Exception as exc:
        raise SystemExit(redact(str(exc), config)) from exc
