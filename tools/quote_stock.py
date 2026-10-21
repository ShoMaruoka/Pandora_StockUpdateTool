"""7桁の見積SKU。対象明細の販売可能在庫の最小を数量にする。"""
from __future__ import annotations

CUSTOMER_CD = 300
EXCLUDED_CODES = frozenset(
    {
        "0010000000000",
        "0011000000000",
        "0020000000000",
        "0030000000000",
    }
)
QUOTE_SQL = """
SELECT h.見積番号, h.得意先CD, d.行番号, d.区分, d.商品CD, g.WebCD,
       CASE WHEN v.商品CD IS NULL THEN 0 ELSE 1 END AS in_view
FROM dbo.T720見積 AS h
INNER JOIN dbo.T721見積明細 AS d ON h.見積番号 = d.見積番号
LEFT JOIN dbo.T410商品 AS g ON d.商品CD = g.商品CD
LEFT JOIN (SELECT DISTINCT 商品CD FROM dbo.VO0507在庫出力) AS v ON d.商品CD = v.商品CD
WHERE h.見積番号 IN ({marks})
"""


def quote_quantity(header: dict | None, lines: list[dict], available: dict) -> dict | None:
    """数量が決められないときは None。明細の数量では割らない。"""
    if not header or int(header.get("得意先CD") or 0) != CUSTOMER_CD:
        return None
    chosen = []
    for line in lines:
        code = str(line.get("商品CD") or "").strip()
        webcd = _webcd(line.get("webcd"))
        if not code or not webcd or code in EXCLUDED_CODES:
            continue
        if not line.get("in_view"):
            return None
        chosen.append((max(0, int(available.get(webcd) or 0)), int(line["行番号"]), webcd))
    if not chosen:
        return None
    quantity, line_no, webcd = min(chosen)
    return {"quantity": quantity, "webcd": webcd, "行番号": line_no}


def rows_to_quotes(rows) -> dict:
    quotes: dict[str, dict] = {}
    for row in rows:
        number = str(int(row[0]))
        bucket = quotes.setdefault(
            number,
            {"header": {"見積番号": number, "得意先CD": int(row[1] or 0)}, "lines": []},
        )
        bucket["lines"].append(
            {
                "行番号": int(row[2]),
                "区分": "" if row[3] is None else str(row[3]).strip(),
                "商品CD": "" if row[4] is None else str(row[4]).strip(),
                "webcd": _webcd(row[5]),
                "in_view": bool(int(row[6] or 0)),
            }
        )
    return quotes


def fetch_quotes(config: dict, numbers: list[str]) -> dict:
    import pyodbc

    from wholesale_stock import _connection_string, redact

    wanted = [int(str(number)) for number in numbers if str(number).strip().isdigit()]
    if not wanted:
        return {}
    try:
        connection = pyodbc.connect(_connection_string(config), timeout=30)
        try:
            cursor = connection.cursor()
            cursor.execute(QUOTE_SQL.format(marks=",".join("?" * len(wanted))), wanted)
            return rows_to_quotes(cursor.fetchall())
        finally:
            connection.close()
    except Exception as exc:
        raise SystemExit(redact(str(exc), config)) from exc


def _webcd(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return str(value).strip()
