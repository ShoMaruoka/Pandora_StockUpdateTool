"""認証フォルダの解決。settings.json と既定のフォールバック。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import secrets_dir  # noqa: E402


class SecretsDirTest(unittest.TestCase):
    def test_default_is_profile_ec_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as missing:
            settings = Path(missing) / "settings.json"
            self.assertEqual(
                secrets_dir.resolve_inventory_dir(settings),
                Path.home() / ".ec_inventory",
            )

    def test_settings_json_overrides_default(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            settings = Path(folder) / "settings.json"
            target = Path(folder) / "vault"
            settings.write_text(json.dumps({"EC_INVENTORY_DIR": str(target)}), encoding="utf-8")
            self.assertEqual(secrets_dir.resolve_inventory_dir(settings), target)

    def test_config_path_joins_filename(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            settings = Path(folder) / "settings.json"
            target = Path(folder) / "vault"
            settings.write_text(json.dumps({"EC_INVENTORY_DIR": str(target)}), encoding="utf-8")
            self.assertEqual(secrets_dir.config_path("sqlserver.json", settings), target / "sqlserver.json")


class AppRootTest(unittest.TestCase):
    def test_script_root_is_repository_and_settings_in_tools(self) -> None:
        self.assertEqual(secrets_dir.app_root(frozen=False), ROOT)
        self.assertEqual(secrets_dir.settings_file(frozen=False), ROOT / "tools" / "settings.json")

    def test_exe_root_and_settings_are_next_to_the_exe(self) -> None:
        exe = Path("D:/Tools/EC/nightly_amazon.exe")
        self.assertEqual(secrets_dir.app_root(frozen=True, executable=exe), exe.parent)
        self.assertEqual(secrets_dir.settings_file(frozen=True, executable=exe), exe.parent / "settings.json")

    def test_nightly_output_uses_app_root(self) -> None:
        sys.path.insert(0, str(ROOT / "全モール在庫更新ツール（EC_Inventory_App_v05_FIX）"))
        import nightly_amazon

        self.assertEqual(nightly_amazon.ROOT, secrets_dir.app_root())


if __name__ == "__main__":
    unittest.main()
