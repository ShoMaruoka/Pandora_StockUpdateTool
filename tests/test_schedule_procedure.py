"""タスク スケジューラの手順に、dry-run の実行条件が書いてあること。"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCEDURE = ROOT / "docs" / "夜間在庫更新_実行手順.md"


class ScheduleProcedureTest(unittest.TestCase):
    def test_procedure_registers_dry_run_for_this_user(self) -> None:
        text = PROCEDURE.read_text(encoding="utf-8")
        self.assertIn("MARUOKA-PC", text)
        self.assertIn("s.maruoka", text)
        self.assertIn("EC_INVENTORY_DIR", text)
        self.assertIn("settings.json", text)
        self.assertIn("03:00", text)
        command = _scheduled_command(text)
        self.assertIn("--dry-run", command)
        self.assertIn("nightly_amazon.py", command)
        self.assertNotIn("--sku", command)


def _scheduled_command(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("schtasks "):
            return line
    return ""


if __name__ == "__main__":
    unittest.main()
