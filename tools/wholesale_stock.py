"""販売管理 dbo.VO0507在庫出力 の参照。書き込み SQL は持たない。"""
from __future__ import annotations

import json
from pathlib import Path

from secrets_dir import config_path

CONFIG_PATH = config_path("sqlserver.json")
WHOLESALE_SQL = """
SELECT WebCD, 在庫横浜, 在庫八尾, 在庫八尾2, 在庫西, 在庫東, 在庫福岡
FROM dbo.VO0507在庫出力
"""
WAREHOUSE_CODES = (120, 400, 405, 110, 150, 180)


def rows_to_stock(rows) -> dict:
    """WebCD をキーに、倉庫CDごとの数量を返す。"""
    stock = {}
    for row in rows:
        webcd = _webcd(row[0])
        if not webcd:
            continue
        stock[webcd] = {
            code: int(row[index + 1] or 0) for index, code in enumerate(WAREHOUSE_CODES)
        }
    return stock


def read_stock(cursor) -> dict:
    cursor.execute(WHOLESALE_SQL)
    return rows_to_stock(cursor.fetchall())


def redact(message: str, config: dict) -> str:
    hidden = message
    values = [str(config.get(key) or "") for key in ("password", "uid", "server", "database", "driver")]
    for value in sorted(values, key=len, reverse=True):
        if value:
            hidden = hidden.replace(value, "***")
    return hidden


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not Path(path).exists():
        raise SystemExit(f"認証ファイルがありません: {path}")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [key for key in ("driver", "server", "database", "uid", "password") if not str(data.get(key) or "").strip()]
    if missing:
        raise SystemExit("不足しているキー: " + ", ".join(missing))
    return data


def fetch_stock(config: dict) -> dict:
    import pyodbc

    try:
        connection = pyodbc.connect(_connection_string(config), timeout=30)
        try:
            return read_stock(connection.cursor())
        finally:
            connection.close()
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(redact(str(exc), config)) from exc


def _connection_string(config: dict) -> str:
    return (
        f"DRIVER={{{config['driver']}}};"
        f"SERVER={config['server']};"
        f"DATABASE={config['database']};"
        f"UID={config['uid']};"
        f"PWD={config['password']}"
    )


def _webcd(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()
