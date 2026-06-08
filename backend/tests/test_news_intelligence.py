from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Base, NewsAnalysis, NewsItem
from app.services.news_intelligence import ensure_news_analyses, parse_news_analysis_payload


class NewsIntelligenceTests(unittest.TestCase):
    def test_parser_validates_stance_and_rejects_advice(self) -> None:
        payload = {
            "summary_ko": "BTC 매수 기회입니다.",
            "stance": "positive_candidate",
            "stance_confidence": 0.8,
            "reason_ko": "가격에 긍정적입니다.",
        }

        with self.assertRaises(ValueError):
            parse_news_analysis_payload(payload, model="fixture", analysis_source="fixture")

    def test_parser_normalizes_unknown_stance_and_confidence(self) -> None:
        payload = {
            "summary_ko": "관련 뉴스 후보입니다.",
            "stance": "certainly_good",
            "stance_confidence": 80,
            "reason_ko": "강한 단정은 피합니다.",
        }

        parsed = parse_news_analysis_payload(payload, model="fixture", analysis_source="fixture")

        self.assertEqual(parsed.stance, "unavailable")
        self.assertEqual(parsed.stance_label_ko, "판단 보류")
        self.assertEqual(parsed.stance_confidence, 0.8)

    def test_news_analysis_cache_reuses_existing_rows(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        settings = Settings(
            database_url="sqlite+pysqlite:///:memory:",
            admin_password="news-password",
            session_secret="news-secret-with-enough-length-32",
        )
        with Session(engine) as session:
            session.add(
                NewsItem(
                    source="fixture",
                    title="Bitcoin ETF inflows return",
                    url="https://example.com/btc-etf",
                    published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    summary="ETF inflows return",
                    related_symbols=["BTC"],
                    duplicate_key="fixture-key",
                )
            )
            session.commit()

            first = ensure_news_analyses(session, settings)
            second = ensure_news_analyses(session, settings)

            self.assertEqual(first["created"], 1)
            self.assertEqual(second["created"], 0)
            self.assertEqual(second["reused"], 1)
            analysis = session.scalar(select(NewsAnalysis))
            self.assertIsNotNone(analysis)
            self.assertEqual(analysis.language, "ko")
            self.assertEqual(analysis.stance, "positive_candidate")
            self.assertEqual(analysis.analysis_source, "local_fallback")

    def test_openai_failure_falls_back_to_cached_local_analysis(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        settings = Settings(
            database_url="sqlite+pysqlite:///:memory:",
            admin_password="news-password",
            session_secret="news-secret-with-enough-length-32",
            openai_api_key="test-key",
            openai_model="gpt-test",
        )
        with Session(engine) as session:
            session.add(
                NewsItem(
                    source="fixture",
                    title="Exchange hack pressures Bitcoin sentiment",
                    url="https://example.com/btc-hack",
                    published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    summary="Hack headline",
                    related_symbols=["BTC"],
                    duplicate_key="fixture-key-2",
                )
            )
            session.commit()

            with patch("app.services.news_intelligence._analyze_with_openai", side_effect=RuntimeError("network")):
                result = ensure_news_analyses(session, settings)

            self.assertEqual(result["created"], 1)
            analysis = session.scalar(select(NewsAnalysis))
            self.assertEqual(analysis.analysis_source, "local_fallback")
            self.assertEqual(analysis.stance, "negative_candidate")


if __name__ == "__main__":
    unittest.main()
