"""exe に入れるものの一覧。ビルドは動かさない。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_exe  # noqa: E402


class BuildExeTest(unittest.TestCase):
    def test_holiday_library_and_business_day_are_bundled(self) -> None:
        # jpholiday は business_day の関数の中で読み込むので、確実に入れる。
        self.assertIn("jpholiday", build_exe.HIDDEN)
        self.assertIn("business_day", build_exe.HIDDEN)

    def test_holiday_library_is_required_to_build(self) -> None:
        self.assertIn("jpholiday", build_exe.REQUIRED)

    def test_bundled_names_can_be_imported(self) -> None:
        import importlib.util

        for name in build_exe.HIDDEN:
            with self.subTest(name=name):
                self.assertIsNotNone(importlib.util.find_spec(name))


if __name__ == "__main__":
    unittest.main()
