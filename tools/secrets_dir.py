"""認証ファイルと出力先の置き場所。settings.json の EC_INVENTORY_DIR を読む。

スクリプトのときは tools/settings.json とリポジトリ直下の output を使う。
exe のときは、exe と同じフォルダの settings.json と output を使う。exe の一時フォルダは使わない。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SETTINGS_KEY = "EC_INVENTORY_DIR"


def _frozen(frozen: bool | None) -> bool:
    return bool(getattr(sys, "frozen", False)) if frozen is None else frozen


def app_root(frozen: bool | None = None, executable: Path | None = None) -> Path:
    """output を置くフォルダ。exe なら exe の横、スクリプトならリポジトリ直下。"""
    if _frozen(frozen):
        return Path(executable or sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def settings_file(frozen: bool | None = None, executable: Path | None = None) -> Path:
    if _frozen(frozen):
        return app_root(True, executable) / "settings.json"
    return Path(__file__).resolve().parent / "settings.json"


SETTINGS_PATH = settings_file()


def resolve_inventory_dir(settings_path: Path | None = None) -> Path:
    """settings.json があれば EC_INVENTORY_DIR、なければ %USERPROFILE%\\.ec_inventory。"""
    path = SETTINGS_PATH if settings_path is None else Path(settings_path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        configured = str(data.get(SETTINGS_KEY) or "").strip()
        if configured:
            return Path(configured)
    return Path.home() / ".ec_inventory"


def config_path(name: str, settings_path: Path | None = None) -> Path:
    return resolve_inventory_dir(settings_path) / name
