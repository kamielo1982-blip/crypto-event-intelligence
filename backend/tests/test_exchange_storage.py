from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import Asset, Base, CollectionRun, ExchangeCandle, KimchiPremiumSnapshot
from app.workers.collector import _upsert_exchange_candles, _upsert_kimchi_history


class ExchangeStorageTests(unittest.TestCase):
    def test_exchange_candles_and_kimchi_premium_are_upserted(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        opened_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with Session(engine) as session:
            asset = Asset(symbol="BTC", name="Bitcoin", coingecko_id="bitcoin", group="investable", rank=1)
            run = CollectionRun(status="running", trigger="test")
            session.add_all([asset, run])
            session.commit()

            binance = [
                {
                    "exchange": "binance",
                    "market": "BTCUSDT",
                    "quote_currency": "USDT",
                    "timeframe": "1d",
                    "opened_at": opened_at,
                    "open": 100.0,
                    "high": 110.0,
                    "low": 95.0,
                    "close": 100.0,
                    "volume_base": 10.0,
                    "volume_quote": 1000.0,
                    "source": "fixture",
                    "raw_payload": {},
                }
            ]
            upbit = [
                {
                    "exchange": "upbit",
                    "market": "KRW-BTC",
                    "quote_currency": "KRW",
                    "timeframe": "1d",
                    "opened_at": opened_at,
                    "open": 140_000.0,
                    "high": 145_000.0,
                    "low": 138_000.0,
                    "close": 140_000.0,
                    "volume_base": 2.0,
                    "volume_quote": 280_000.0,
                    "source": "fixture",
                    "raw_payload": {},
                }
            ]

            self.assertEqual(_upsert_exchange_candles(session, run, asset, binance), 1)
            self.assertEqual(_upsert_exchange_candles(session, run, asset, upbit), 1)
            self.assertEqual(_upsert_kimchi_history(session, run, asset, binance, upbit, 1350.0), 1)
            session.commit()

            self.assertEqual(session.scalar(select(func.count(ExchangeCandle.id))), 2)
            premium = session.scalar(select(KimchiPremiumSnapshot))
            self.assertIsNotNone(premium)
            self.assertAlmostEqual(premium.premium_pct, 3.7037, places=4)


if __name__ == "__main__":
    unittest.main()
