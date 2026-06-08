from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.signal_engine import build_market_signals, build_news_signals, build_onchain_signals, build_supply_signals, pct_change


class SignalEngineTests(unittest.TestCase):
    def test_pct_change_handles_missing_and_zero_previous(self) -> None:
        self.assertEqual(pct_change(110, 100), 10)
        self.assertIsNone(pct_change(110, 0))
        self.assertIsNone(pct_change(None, 100))

    def test_market_thresholds_create_price_and_volume_signals(self) -> None:
        current = {"price_usd": 106, "volume_24h_usd": 1800, "market_cap_usd": 10000, "source": "fixture"}
        previous = {"price_usd": 100, "volume_24h_usd": 1000, "market_cap_usd": 9800, "source": "fixture"}

        signals = build_market_signals("BTC", current, previous)

        self.assertEqual([signal.signal_type for signal in signals], ["price_move", "volume_change"])
        self.assertEqual(signals[0].severity, "high")
        self.assertEqual(signals[1].severity, "high")

    def test_news_cluster_requires_three_related_items(self) -> None:
        news = [{"title": f"BTC item {index}", "url": f"https://example.com/{index}", "source": "fixture"} for index in range(3)]

        signals = build_news_signals("BTC", news, datetime.now(timezone.utc))

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "news_cluster")
        self.assertEqual(signals[0].severity, "medium")

    def test_supply_change_uses_inflation_threshold_for_complete_data(self) -> None:
        signals = build_supply_signals(
            "SOL",
            {"circulating_supply": 101_000_000, "availability": "complete", "source": "fixture"},
            {"circulating_supply": 100_000_000, "availability": "complete", "source": "fixture"},
        )

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "supply_change")
        self.assertEqual(signals[0].severity, "medium")

    def test_partial_and_demo_onchain_supply_do_not_create_investor_events(self) -> None:
        partial_onchain = build_onchain_signals(
            "BTC",
            {"active_addresses": 200, "transaction_count": 400, "availability": "partial", "source": "fixture"},
            {"active_addresses": 100, "transaction_count": 200, "availability": "partial", "source": "fixture"},
        )
        demo_supply = build_supply_signals(
            "BTC",
            {"circulating_supply": 102, "availability": "complete", "source": "demo_fallback"},
            {"circulating_supply": 100, "availability": "complete", "source": "demo_fallback"},
        )

        self.assertEqual(partial_onchain, [])
        self.assertEqual(demo_supply, [])


if __name__ == "__main__":
    unittest.main()
