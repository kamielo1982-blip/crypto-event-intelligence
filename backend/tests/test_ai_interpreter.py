from __future__ import annotations

import unittest

from app.services.ai_interpreter import LocalHeuristicInterpreter, parse_interpretation_payload


class AIInterpreterTests(unittest.TestCase):
    def test_parser_rejects_trading_advice_language(self) -> None:
        payload = {
            "summary": "BTC 매수 기회입니다.",
            "candidates": [],
            "caveats": [],
            "confidence": "high",
        }

        with self.assertRaises(ValueError):
            parse_interpretation_payload(payload)

    def test_parser_normalizes_unknown_confidence(self) -> None:
        payload = {
            "summary": "원인 후보가 있습니다.",
            "candidates": [],
            "caveats": [],
            "confidence": "certain",
        }

        parsed = parse_interpretation_payload(payload)

        self.assertEqual(parsed["confidence"], "low")

    def test_parser_allows_source_evidence_titles_with_market_language(self) -> None:
        payload = {
            "summary": "BTC 관련 뉴스 집중이 감지되었습니다.",
            "candidates": [
                {
                    "title": "뉴스 집중",
                    "rationale": "관련 기사 수가 증가했습니다.",
                    "evidence": {"items": [{"title": "Analyst says buy Bitcoin dips", "url": "https://example.com"}]},
                }
            ],
            "caveats": ["외부 기사 제목은 해석 문장이 아닙니다."],
            "confidence": "medium",
        }

        parsed = parse_interpretation_payload(payload)

        self.assertEqual(parsed["confidence"], "medium")

    def test_local_interpreter_returns_bounded_candidates(self) -> None:
        signals = [
            {"title": "가격 상승", "description": "직전 스냅샷 대비 상승", "severity": "high", "signal_type": "price_move", "evidence": {}},
            {"title": "거래량 증가", "description": "거래량 증가", "severity": "medium", "signal_type": "volume_change", "evidence": {}},
            {"title": "뉴스 집중", "description": "뉴스 집중", "severity": "medium", "signal_type": "news_cluster", "evidence": {}},
            {"title": "공급 변화", "description": "공급 변화", "severity": "low", "signal_type": "supply_change", "evidence": {}},
        ]

        result = LocalHeuristicInterpreter().interpret("BTC", signals)

        self.assertEqual(len(result.candidates), 3)
        self.assertIn(result.confidence, {"low", "medium", "high"})


if __name__ == "__main__":
    unittest.main()
