from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Asset, Base, CollectionRun, LiveKimchiPremiumSnapshot, MarketSnapshot, NewsAnalysis, NewsItem, OnchainSnapshot, SignalEvent, SupplySnapshot
from app.services.dashboard import _kimchi_snapshot_to_dict, asset_overview, event_feed


class DashboardQualityTests(unittest.TestCase):
    def test_event_feed_excludes_research_only_by_default(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            asset = Asset(symbol="BTC", name="Bitcoin", coingecko_id="bitcoin", group="investable", rank=1)
            run = CollectionRun(status="success", trigger="test")
            session.add_all([asset, run])
            session.commit()
            session.add_all(
                [
                    SignalEvent(
                        asset_id=asset.id,
                        collection_run_id=run.id,
                        signal_type="price_move",
                        severity="high",
                        title="BTC 가격 상승",
                        description="fixture",
                        value=6.0,
                        source="market_snapshot",
                        evidence={"current": {"source": "fixture"}},
                    ),
                    SignalEvent(
                        asset_id=asset.id,
                        collection_run_id=run.id,
                        signal_type="onchain_change",
                        severity="high",
                        title="BTC 온체인 증가",
                        description="fixture",
                        value=80.0,
                        source="onchain_snapshot",
                        evidence={"current": {"availability": "partial", "source": "demo_fallback"}},
                    ),
                    SignalEvent(
                        asset_id=asset.id,
                        collection_run_id=run.id,
                        signal_type="news_cluster",
                        severity="medium",
                        title="BTC demo news",
                        description="fixture",
                        value=3.0,
                        source="news_items",
                        evidence={"items": [{"title": "demo", "url": "https://example.com", "source": "demo_fallback"}]},
                    ),
                ]
            )
            session.commit()

            default_rows = event_feed(session)
            research_rows = event_feed(session, include_research=True)

            self.assertEqual([row["signal_type"] for row in default_rows], ["price_move"])
            self.assertEqual(len(research_rows), 3)
            self.assertTrue(any(row["data_quality"] == "research_only" for row in research_rows))

    def test_partial_factor_scores_are_capped_at_30_low_confidence(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        now = datetime.now(timezone.utc)
        with Session(engine) as session:
            asset = Asset(symbol="BTC", name="Bitcoin", coingecko_id="bitcoin", group="investable", rank=1)
            run = CollectionRun(status="success", trigger="test")
            session.add_all([asset, run])
            session.commit()
            session.add(MarketSnapshot(asset_id=asset.id, collection_run_id=run.id, observed_at=now, price_usd=100, source="fixture"))
            session.add_all(
                [
                    OnchainSnapshot(
                        asset_id=asset.id,
                        collection_run_id=run.id,
                        observed_at=now - timedelta(days=1),
                        active_addresses=100,
                        transaction_count=100,
                        source="demo_fallback",
                        availability="partial",
                    ),
                    OnchainSnapshot(
                        asset_id=asset.id,
                        collection_run_id=run.id,
                        observed_at=now,
                        active_addresses=1_000,
                        transaction_count=1_000,
                        source="demo_fallback",
                        availability="partial",
                    ),
                    SupplySnapshot(
                        asset_id=asset.id,
                        collection_run_id=run.id,
                        observed_at=now - timedelta(days=1),
                        circulating_supply=100,
                        source="demo_fallback",
                        availability="partial",
                    ),
                    SupplySnapshot(
                        asset_id=asset.id,
                        collection_run_id=run.id,
                        observed_at=now,
                        circulating_supply=120,
                        source="demo_fallback",
                        availability="partial",
                    ),
                ]
            )
            session.commit()

            overview = asset_overview(session, "BTC", "30d")
            self.assertIsNotNone(overview)
            by_factor = {item["factor"]: item for item in overview["factor_impacts"]}

            self.assertLessEqual(by_factor["onchain"]["score"], 30)
            self.assertEqual(by_factor["onchain"]["confidence"], "low")
            self.assertEqual(by_factor["onchain"]["data_quality"], "research_only")
            self.assertLessEqual(by_factor["supply"]["score"], 30)
            self.assertEqual(by_factor["supply"]["confidence"], "low")

    def test_kimchi_freshness_uses_snapshot_age(self) -> None:
        now = datetime.now(timezone.utc)
        stale = LiveKimchiPremiumSnapshot(
            asset_id=1,
            observed_at=now - timedelta(hours=7),
            korean_exchange="upbit",
            korean_market="KRW-BTC",
            global_market="BTCUSDT",
            availability="complete",
        )
        outdated = LiveKimchiPremiumSnapshot(
            asset_id=1,
            observed_at=now - timedelta(hours=10),
            korean_exchange="upbit",
            korean_market="KRW-BTC",
            global_market="BTCUSDT",
            availability="complete",
        )

        self.assertEqual(_kimchi_snapshot_to_dict(stale)["freshness_status"], "stale")
        self.assertEqual(_kimchi_snapshot_to_dict(outdated)["freshness_status"], "outdated")

    def test_overview_returns_korean_news_analysis_and_factor_trends(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        now = datetime.now(timezone.utc)
        with Session(engine) as session:
            asset = Asset(symbol="BTC", name="Bitcoin", coingecko_id="bitcoin", group="investable", rank=1)
            run = CollectionRun(status="success", trigger="test")
            session.add_all([asset, run])
            session.commit()
            session.add(MarketSnapshot(asset_id=asset.id, collection_run_id=run.id, observed_at=now, price_usd=100, source="fixture"))
            news = NewsItem(
                source="fixture",
                title="Bitcoin ETF inflows return",
                url="https://example.com/btc-etf",
                published_at=now,
                summary="ETF inflows return",
                related_symbols=["BTC"],
                duplicate_key="fixture-news",
            )
            session.add(news)
            session.commit()
            session.add(
                NewsAnalysis(
                    news_item_id=news.id,
                    language="ko",
                    summary_ko="BTC ETF 유입이 다시 부각된 뉴스 후보입니다.",
                    stance="positive_candidate",
                    stance_label_ko="잠재적 호재",
                    stance_confidence=0.72,
                    reason_ko="ETF 유입은 수요 개선 가능성과 함께 해석될 수 있습니다.",
                    risk_notes=["확정적 원인은 아닙니다."],
                    model="fixture",
                    prompt_version="news-ko-v1",
                    analysis_source="fixture",
                )
            )
            session.add_all(
                [
                    OnchainSnapshot(
                        asset_id=asset.id,
                        collection_run_id=run.id,
                        observed_at=now - timedelta(days=1),
                        active_addresses=100,
                        source="fixture",
                        availability="complete",
                    ),
                    OnchainSnapshot(
                        asset_id=asset.id,
                        collection_run_id=run.id,
                        observed_at=now,
                        active_addresses=150,
                        source="fixture",
                        availability="complete",
                    ),
                ]
            )
            session.commit()

            overview = asset_overview(session, "BTC", "30d")

            self.assertIsNotNone(overview)
            item = overview["news_impacts"][0]["items"][0]
            self.assertEqual(item["summary_ko"], "BTC ETF 유입이 다시 부각된 뉴스 후보입니다.")
            self.assertEqual(item["stance"], "positive_candidate")
            self.assertEqual(overview["news_impacts"][0]["stance_counts"]["positive_candidate"], 1)
            self.assertIn("factor_trends", overview)
            active_addresses = [row for row in overview["factor_trends"] if row["metric"] == "active_addresses"][0]
            self.assertEqual(active_addresses["data_quality"], "investor_grade")
            self.assertEqual(active_addresses["points"][-1]["value"], 150.0)


if __name__ == "__main__":
    unittest.main()
