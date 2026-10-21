"""卸の調整在庫。Excel の ROUNDUP(SUM(G:K)/2, 0) と同じ。"""
from __future__ import annotations

INCLUDED = (120, 400, 405, 110, 150)


def adjusted_stock(warehouses: dict) -> int:
    """横浜・八尾・八尾2・西・東の合計を2で割り、端数を切り上げる。福岡(180)は入れない。"""
    total = sum(int(warehouses.get(code) or 0) for code in INCLUDED)
    return (total + 1) // 2
