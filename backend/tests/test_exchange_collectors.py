from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.collectors.binance import normalize_klines, normalize_ticker_price
from app.collectors.bithumb import normalize_candlesticks, normalize_ticker as normalize_bithumb_ticker
from app.collectors.fx import normalize_open_er_rate
from app.collectors.upbit import normalize_day_candles, normalize_ticker as normalize_upbit_ticker


class ExchangeCollectorTests(unittest.TestCase):
    def test_binance_kline_normalizer_maps_ohlcv_fields(self) -> None:
        ts = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        rows = normalize_klines(
            [[ts, "100", "110", "95", "108", "12.5", ts + 86_399_999, "1350", 10, "0", "0", "0"]],
            "BTCUSDT",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["exchange"], "binance")
        self.assertEqual(rows[0]["market"], "BTCUSDT")
        self.assertEqual(rows[0]["quote_currency"], "USDT")
        self.assertEqual(rows[0]["open"], 100.0)
        self.assertEqual(rows[0]["volume_quote"], 1350.0)

    def test_upbit_day_normalizer_maps_krw_candle(self) -> None:
        rows = normalize_day_candles(
            [
                {
                    "market": "KRW-BTC",
                    "candle_date_time_utc": "2026-01-01T00:00:00",
                    "opening_price": 140_000_000,
                    "high_price": 145_000_000,
                    "low_price": 138_000_000,
                    "trade_price": 142_000_000,
                    "candle_acc_trade_price": 100_000_000_000,
                    "candle_acc_trade_volume": 710,
                }
            ],
            "KRW-BTC",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["exchange"], "upbit")
        self.assertEqual(rows[0]["quote_currency"], "KRW")
        self.assertEqual(rows[0]["close"], 142_000_000.0)

    def test_bithumb_candlestick_normalizer_maps_public_array_shape(self) -> None:
        ts = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        rows = normalize_candlesticks({"status": "0000", "data": [[ts, "140000000", "142000000", "145000000", "138000000", "710"]]}, "BTC_KRW")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["exchange"], "bithumb")
        self.assertEqual(rows[0]["market"], "BTC_KRW")
        self.assertEqual(rows[0]["quote_currency"], "KRW")
        self.assertEqual(rows[0]["high"], 145_000_000.0)
        self.assertEqual(rows[0]["low"], 138_000_000.0)

    def test_binance_ticker_normalizer_maps_live_price(self) -> None:
        observed_at = datetime(2026, 6, 7, 12, tzinfo=timezone.utc)

        row = normalize_ticker_price({"symbol": "BTCUSDT", "price": "61292.97000000"}, "BTCUSDT", observed_at=observed_at)

        self.assertEqual(row["exchange"], "binance")
        self.assertEqual(row["base_currency"], "BTC")
        self.assertEqual(row["quote_currency"], "USDT")
        self.assertEqual(row["price"], 61292.97)
        self.assertEqual(row["observed_at"], observed_at)

    def test_upbit_ticker_normalizer_maps_trade_price_and_timestamp(self) -> None:
        ts = int(datetime(2026, 6, 7, 12, tzinfo=timezone.utc).timestamp() * 1000)

        row = normalize_upbit_ticker([{"market": "KRW-BTC", "trade_price": 93_000_000, "timestamp": ts}], "KRW-BTC")

        self.assertEqual(row["exchange"], "upbit")
        self.assertEqual(row["base_currency"], "BTC")
        self.assertEqual(row["quote_currency"], "KRW")
        self.assertEqual(row["price"], 93_000_000.0)
        self.assertEqual(row["observed_at"], datetime(2026, 6, 7, 12, tzinfo=timezone.utc))

    def test_bithumb_ticker_normalizer_maps_closing_price_and_date(self) -> None:
        ts = int(datetime(2026, 6, 7, 12, tzinfo=timezone.utc).timestamp() * 1000)

        row = normalize_bithumb_ticker({"status": "0000", "data": {"closing_price": "92999000", "date": str(ts)}}, "BTC_KRW")

        self.assertEqual(row["exchange"], "bithumb")
        self.assertEqual(row["base_currency"], "BTC")
        self.assertEqual(row["quote_currency"], "KRW")
        self.assertEqual(row["price"], 92_999_000.0)
        self.assertEqual(row["observed_at"], datetime(2026, 6, 7, 12, tzinfo=timezone.utc))

    def test_open_er_fx_normalizer_maps_krw_rate(self) -> None:
        row = normalize_open_er_rate(
            {
                "base_code": "USD",
                "time_last_update_unix": 1_780_819_351,
                "rates": {"KRW": 1545.528364},
            },
            observed_at=datetime(2026, 6, 7, 12, tzinfo=timezone.utc),
        )

        self.assertEqual(row["base_currency"], "USD")
        self.assertEqual(row["quote_currency"], "KRW")
        self.assertEqual(row["rate"], 1545.528364)
        self.assertEqual(row["source"], "open_er_api")


if __name__ == "__main__":
    unittest.main()
