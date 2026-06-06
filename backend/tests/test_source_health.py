from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.services.source_health import SourceAttempt, compute_success_rate, summarize_source


class SourceHealthTests(unittest.TestCase):
    def test_success_rate_uses_last_24_hours_only(self) -> None:
        now = datetime(2026, 6, 6, 12, tzinfo=timezone.utc)
        attempts = [
            SourceAttempt("rss", True, now - timedelta(hours=1)),
            SourceAttempt("rss", False, now - timedelta(hours=2)),
            SourceAttempt("rss", False, now - timedelta(days=2)),
        ]

        self.assertEqual(compute_success_rate(attempts, now), 0.5)

    def test_summary_marks_latest_failure_with_prior_success_as_degraded(self) -> None:
        now = datetime(2026, 6, 6, 12, tzinfo=timezone.utc)
        attempts = [
            SourceAttempt("rss", True, now - timedelta(hours=2), latency_ms=120),
            SourceAttempt("rss", False, now - timedelta(hours=1), message="timeout"),
        ]

        summary = summarize_source("rss", attempts, now)

        self.assertEqual(summary["status"], "degraded")
        self.assertEqual(summary["success_rate_24h"], 0.5)
        self.assertEqual(summary["message"], "timeout")


if __name__ == "__main__":
    unittest.main()
