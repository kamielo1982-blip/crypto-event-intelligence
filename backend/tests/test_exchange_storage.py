from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Asset, Base, CollectionRun, ExchangeCandle, ExchangeTickerSnapshot, FxRateSnapshot, KimchiPremiumSnapshot, LiveKimchiPremiumSnapshot
from app.services.dashboard import asset_overview
from app.workers.collector import _upsert_exchange_candles, _upsert_exchange_ticker, _upsert_fx_rate_snapshot, _upsert_kimchi_history, _upsert_live_kimchi_snapshot


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

    def test_live_tickers_fx_and_kimchi_premium_are_stored_for_overview(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        observed_at = datetime(2026, 6, 7, 12, tzinfo=timezone.utc)
        with Session(engine) as session:
            asset = Asset(symbol="BTC", name="Bitcoin", coingecko_id="bitcoin", group="investable", rank=1)
            run = CollectionRun(status="running", trigger="test")
            session.add_all([asset, run])
            session.commit()

            binance = {
                "exchange": "binance",
                "market": "BTCUSDT",
                "base_currency": "BTC",
                "quote_currency": "USDT",
                "price": 61_292.97,
                "observed_at": observed_at,
                "source": "fixture",
                "raw_payload": {},
            }
            upbit = {
                "exchange": "upbit",
                "market": "KRW-BTC",
                "base_currency": "BTC",
                "quote_currency": "KRW",
                "price": 93_000_000.0,
                "observed_at": observed_at,
                "source": "fixture",
                "raw_payload": {},
            }
            bithumb = {
                "exchange": "bithumb",
                "market": "BTC_KRW",
                "base_currency": "BTC",
                "quote_currency": "KRW",
                "price": 93_000_000.0,
                "observed_at": observed_at,
                "source": "fixture",
                "raw_payload": {},
            }
            usdt_reference = {
                "exchange": "upbit",
                "market": "KRW-USDT",
                "base_currency": "USDT",
                "quote_currency": "KRW",
                "price": 1518.0,
                "observed_at": observed_at,
                "source": "fixture",
                "raw_payload": {},
            }
            fx = {
                "base_currency": "USD",
                "quote_currency": "KRW",
                "rate": 1545.528364,
                "observed_at": observed_at,
                "source_updated_at": observed_at,
                "source": "open_er_api",
                "raw_payload": {},
            }

            _upsert_exchange_ticker(session, run, asset, binance)
            _upsert_exchange_ticker(session, run, asset, upbit)
            _upsert_exchange_ticker(session, run, asset, bithumb)
            _upsert_fx_rate_snapshot(session, run, fx)
            availability = _upsert_live_kimchi_snapshot(
                session,
                run,
                asset,
                binance,
                upbit,
                fx,
                [usdt_reference],
                Settings(
                    database_url="sqlite+pysqlite:///:memory:",
                    admin_password="storage-password",
                    session_secret="storage-secret-with-enough-length-32",
                ),
            )
            _upsert_live_kimchi_snapshot(
                session,
                run,
                asset,
                binance,
                bithumb,
                fx,
                [usdt_reference],
                Settings(
                    database_url="sqlite+pysqlite:///:memory:",
                    admin_password="storage-password",
                    session_secret="storage-secret-with-enough-length-32",
                ),
            )
            session.commit()

            self.assertEqual(availability, "complete")
            self.assertEqual(session.scalar(select(func.count(ExchangeTickerSnapshot.id))), 3)
            self.assertEqual(session.scalar(select(func.count(FxRateSnapshot.id))), 1)
            premium = session.scalar(select(LiveKimchiPremiumSnapshot).where(LiveKimchiPremiumSnapshot.korean_exchange == "upbit"))
            self.assertIsNotNone(premium)
            self.assertAlmostEqual(premium.premium_pct, -1.83, places=2)
            self.assertNotEqual(premium.usd_krw, 1350.0)

            overview = asset_overview(session, "BTC", "7d")
            self.assertIsNotNone(overview)
            latest = overview["kimchi_premium_latest"]
            self.assertEqual(latest["availability"], "complete")
            self.assertEqual(latest["basis"], "usd_krw_live_fx")
            self.assertAlmostEqual(latest["average_premium_pct"], -1.83, places=2)
            self.assertEqual(latest["usd_krw"], 1545.528364)
            self.assertEqual(len(latest["exchanges"]), 2)


if __name__ == "__main__":
    unittest.main()
