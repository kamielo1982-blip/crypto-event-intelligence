from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.collectors.binance import normalize_klines
from app.collectors.bithumb import normalize_candlesticks
from app.collectors.upbit import normalize_day_candles


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


if __name__ == "__main__":
    unittest.main()
