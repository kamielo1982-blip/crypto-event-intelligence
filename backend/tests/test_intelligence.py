from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.intelligence import (
    attach_moving_averages,
    build_factor_trend_series,
    calculate_kimchi_premium,
    calculate_live_kimchi_premium,
    calculate_supply_delta,
    normalize_market_chart_payload,
    normalize_ohlc_payload,
    score_kimchi_premium,
    score_news_impact,
)


class IntelligenceTests(unittest.TestCase):
    def test_normalize_ohlc_payload_keeps_candle_shape(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000

        rows = normalize_ohlc_payload([[ts, 100, 110, 95, 108]], "fixture")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open"], 100.0)
        self.assertEqual(rows[0]["high"], 110.0)
        self.assertEqual(rows[0]["low"], 95.0)
        self.assertEqual(rows[0]["close"], 108.0)
        self.assertEqual(rows[0]["source"], "fixture")

    def test_normalize_market_chart_payload_builds_daily_candle(self) -> None:
        ts1 = datetime(2026, 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
        ts2 = datetime(2026, 1, 1, 12, tzinfo=timezone.utc).timestamp() * 1000
        ts3 = datetime(2026, 1, 1, 23, tzinfo=timezone.utc).timestamp() * 1000

        rows = normalize_market_chart_payload(
            {"prices": [[ts1, 100], [ts2, 110], [ts3, 105]], "total_volumes": [[ts3, 5000]]},
            "fixture",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open"], 100)
        self.assertEqual(rows[0]["high"], 110)
        self.assertEqual(rows[0]["low"], 100)
        self.assertEqual(rows[0]["close"], 105)
        self.assertEqual(rows[0]["volume_usd"], 5000)

    def test_moving_averages_distinguish_missing_from_zero(self) -> None:
        candles = [
            {"opened_at": datetime(2026, 1, day, tzinfo=timezone.utc), "close": float(day)}
            for day in range(1, 22)
        ]

        rows = attach_moving_averages(candles)

        self.assertIsNone(rows[5]["ma7"])
        self.assertEqual(rows[6]["ma7"], 4.0)
        self.assertEqual(rows[19]["ma20"], 10.5)

    def test_supply_delta_uses_direct_mint_minus_burn_when_available(self) -> None:
        delta = calculate_supply_delta({"mint_amount": 120, "burn_amount": 20, "circulating_supply": 1000}, None)

        self.assertEqual(delta["method"], "direct")
        self.assertEqual(delta["net_change"], 100)
        self.assertEqual(delta["net_change_pct"], 10)

    def test_supply_delta_falls_back_to_circulating_proxy(self) -> None:
        delta = calculate_supply_delta(
            {"circulating_supply": 101_000_000, "mint_amount": None, "burn_amount": None},
            {"circulating_supply": 100_000_000},
        )

        self.assertEqual(delta["method"], "circulating_proxy")
        self.assertEqual(delta["net_change"], 1_000_000)
        self.assertEqual(delta["net_change_pct"], 1)

    def test_news_score_is_bounded_candidate_score(self) -> None:
        score = score_news_impact(news_count=8, signal_severity="high", proximity_hours=1, source_count=4)

        self.assertEqual(score, 100)

    def test_kimchi_premium_converts_krw_price_to_usd_gap(self) -> None:
        result = calculate_kimchi_premium(global_price_usd=100, korean_price_krw=140_000, usd_krw=1350)

        self.assertAlmostEqual(result["korean_price_usd"], 103.7037, places=4)
        self.assertAlmostEqual(result["premium_pct"], 3.7037, places=4)
        self.assertEqual(score_kimchi_premium(result["premium_pct"]), 46)

    def test_live_kimchi_premium_uses_live_fx_not_fixed_rate(self) -> None:
        result = calculate_live_kimchi_premium(
            global_price_usd=61_292.97,
            korean_price_krw=93_000_000,
            usd_krw=1545.528364,
            usdt_krw_reference=1518,
        )

        self.assertAlmostEqual(result["premium_pct"], -1.83, places=2)
        self.assertAlmostEqual(result["usdt_basis_premium_pct"], -0.05, places=2)

    def test_live_kimchi_premium_returns_missing_when_fx_is_missing(self) -> None:
        result = calculate_live_kimchi_premium(global_price_usd=61_292.97, korean_price_krw=93_000_000, usd_krw=None)

        self.assertIsNone(result["korean_price_usd"])
        self.assertIsNone(result["premium_pct"])

    def test_factor_trend_distinguishes_zero_from_missing(self) -> None:
        rows = [
            {
                "observed_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                "net_change": 100,
                "availability": "partial",
                "source": "fixture",
            },
            {
                "observed_at": datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
                "net_change": 0,
                "availability": "partial",
                "source": "fixture",
            },
            {
                "observed_at": datetime(2026, 1, 3, tzinfo=timezone.utc).isoformat(),
                "net_change": None,
                "availability": "partial",
                "source": "fixture",
            },
        ]

        series = build_factor_trend_series("supply", "net_change", "순공급 변화", "token", rows, "research_only")

        self.assertEqual(series["data_quality"], "research_only")
        self.assertEqual(series["points"][1]["value"], 0.0)
        self.assertEqual(series["points"][1]["delta_pct"], -100)
        self.assertIsNone(series["points"][2]["value"])
        self.assertIsNone(series["points"][2]["delta_pct"])

    def test_factor_trend_calculates_average_comparison_and_z_score(self) -> None:
        rows = [
            {
                "observed_at": datetime(2026, 1, day, tzinfo=timezone.utc).isoformat(),
                "active_addresses": float(day * 100),
                "availability": "complete",
                "source": "fixture",
            }
            for day in range(1, 9)
        ]

        series = build_factor_trend_series("onchain", "active_addresses", "활성 주소", "count", rows, "investor_grade")
        latest = series["points"][-1]

        self.assertAlmostEqual(latest["vs_7d_avg_pct"], 77.78, places=2)
        self.assertIsNotNone(latest["z_score_30d"])


if __name__ == "__main__":
    unittest.main()
