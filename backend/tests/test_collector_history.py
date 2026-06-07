from __future__ import annotations

import unittest

from app.workers.collector import _demo_history_days, _history_days


class CollectorHistoryTests(unittest.TestCase):
    def test_history_days_accepts_integer_days(self) -> None:
        self.assertEqual(_history_days("365"), 365)
        self.assertEqual(_history_days("1"), 1)

    def test_history_days_accepts_max_for_paid_api_configs(self) -> None:
        self.assertEqual(_history_days("max"), "max")
        self.assertEqual(_history_days("MAX"), "max")

    def test_demo_history_caps_max_to_one_year(self) -> None:
        self.assertEqual(_demo_history_days("max"), 365)
        self.assertEqual(_demo_history_days(180), 180)


if __name__ == "__main__":
    unittest.main()
