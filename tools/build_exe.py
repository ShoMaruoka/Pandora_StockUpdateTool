"""夜間ジョブを1つの exe（dist/nightly_amazon.exe）にする。開発 PC で実行する。

ビルドの前にテストを流し、失敗したら exe は作らない。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"
NAME = "nightly_amazon"
# 関数の中で読み込むモジュール。exe に確実に入れる。
HIDDEN = (
    "amazon_listings",
    "amazon_report",
    "item_master",
    "logiless_stock",
    "notify_chatwork",
    "quote_stock",
    "wholesale_stock",
    "pyodbc",
)
REQUIRED = ("PyInstaller", "openpyxl", "pyodbc")


def main() -> int:
    missing = [name for name in REQUIRED if importlib.util.find_spec(name) is None]
    if missing:
        print("足りないパッケージ: " + ", ".join(missing))
        print("py -3 -m pip install pyinstaller openpyxl pyodbc")
        return 1
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT)
    if tests.returncode != 0:
        print("テストが失敗したため、exe は作りません。")
        return 1
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name",
        NAME,
        "--paths",
        str(ROOT / "tools"),
        "--paths",
        str(ENGINE_DIR),
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT / "build"),
    ]
    for module in HIDDEN:
        command += ["--hidden-import", module]
    command.append(str(ROOT / "tools" / "nightly_amazon.py"))
    built = subprocess.run(command, cwd=ROOT)
    if built.returncode != 0:
        print("exe の作成に失敗しました。")
        return 1
    print(f"作成しました: {ROOT / 'dist' / (NAME + '.exe')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
