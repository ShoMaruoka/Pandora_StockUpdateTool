"""出品一覧と在庫計算から、Amazonへ送るかどうかを決める。"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine import calc, parse_sku

# 急減は、前回数量がこの数以上で、DROP_PERCENT 以上減ったときだけ。少ない数量からの 0 は止めない。
HOLD_MIN_PREVIOUS = 10
DROP_PERCENT = 80


@dataclass
class AmazonRun:
    action: str
    listed: int
    sent: int
    skipped: int
    reason: str
    updates: list = field(default_factory=list)
    held: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)  # 前回と同じ数量で送らない SKU


def decide(listings: list[dict], master: dict, declared_count: int, quotes: dict | None = None) -> AmazonRun:
    rows = list(listings)
    if declared_count != len(rows):
        return AmazonRun("failed", len(rows), 0, 0, "出品一覧が不足しています")

    quotes = quotes or {}
    updates = []
    held = []
    unchanged = []
    skipped = 0
    for row in rows:
        planned = merchant_update(row, master, quotes)
        if planned is None:
            skipped += 1
            continue
        old = int(row["default_quantity"])
        new = int(planned["quantity"])
        if new == old:
            # 絶対値で送るので、同じ値を送っても Amazon 上は変わらない。
            unchanged.append(planned["sku"])
        elif old >= HOLD_MIN_PREVIOUS and (old - new) * 100 >= old * DROP_PERCENT:
            held.append(planned)
        else:
            updates.append(planned)

    reason = f"急減 {len(held)}件" if held else ""
    return AmazonRun("sent", len(rows), len(updates), skipped, reason, updates, held, unchanged)


def merchant_update(row: dict, master: dict, quotes: dict) -> dict | None:
    """1 SKUの出品者出荷数量。決まらないときは None。急減では止めない。"""
    if row.get("default_quantity") is None:
        return None
    sku = str(row["sku"])
    parsed = parse_sku(sku)
    if parsed.operation == "quote":
        found = quotes.get(sku)
        new = None if found is None else int(found["quantity"])
    else:
        new, _status, _info = calc(parsed, master)
    if new is None:
        return None
    return {"sku": sku, "quantity": int(new), "channel": "DEFAULT"}
