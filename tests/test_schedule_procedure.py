"""タスク スケジューラの手順に、dry-run の実行条件が書いてあること。"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCEDURE = ROOT / "docs" / "夜間在庫更新_実行手順.md"
SERVER_PROCEDURE = ROOT / "docs" / "夜間在庫更新_サーバー導入手順.md"


class ScheduleProcedureTest(unittest.TestCase):
    def test_procedure_registers_dry_run_for_this_user(self) -> None:
        text = PROCEDURE.read_text(encoding="utf-8")
        self.assertIn("MARUOKA-PC", text)
        self.assertIn("s.maruoka", text)
        self.assertIn("EC_INVENTORY_DIR", text)
        self.assertIn("settings.json", text)
        command = _scheduled_command(text)
        self.assertIn("--dry-run", command)
        self.assertIn("nightly_amazon.py", command)
        self.assertNotIn("--sku", command)

    def test_procedures_register_weekdays_at_1600(self) -> None:
        for path in (PROCEDURE, SERVER_PROCEDURE):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                command = _scheduled_command(text)
                self.assertIn("/SC WEEKLY", command)
                self.assertIn("/D MON,TUE,WED,THU,FRI", command)
                self.assertIn("/ST 16:00", command)
                self.assertNotIn("/SC DAILY", command)
                self.assertNotIn("03:00", text)

    def test_server_procedure_explains_closed_days(self) -> None:
        text = SERVER_PROCEDURE.read_text(encoding="utf-8")
        self.assertIn("skip 休業日", text)
        self.assertIn("--force", text)
        self.assertIn("T007CM休業日", text)


def _scheduled_command(text: str) -> str:
    for line in text.splitlines():
        if line.startswith('schtasks /Create /TN "ECInventoryAmazonDryRun"'):
            return line
    return ""


if __name__ == "__main__":
    unittest.main()
