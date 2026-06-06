from __future__ import annotations

import unittest

from app.services.news import canonical_url, dedupe_news_items, duplicate_key, infer_related_symbols


class NewsTests(unittest.TestCase):
    def test_canonical_url_removes_tracking_parts(self) -> None:
        self.assertEqual(canonical_url("HTTPS://Example.com/news/btc/?utm_source=x#fragment"), "https://example.com/news/btc")

    def test_dedupe_news_items_uses_duplicate_key(self) -> None:
        key = duplicate_key("Bitcoin ETF flow returns", "https://example.com/btc")
        items = [
            {"title": "Bitcoin ETF flow returns", "url": "https://example.com/btc", "source": "fixture", "duplicate_key": key},
            {"title": "Bitcoin ETF flow returns", "url": "https://example.com/btc?utm=x", "source": "fixture", "duplicate_key": key},
        ]

        self.assertEqual(len(dedupe_news_items(items)), 1)

    def test_infer_related_symbols_respects_symbol_boundaries(self) -> None:
        symbols = infer_related_symbols("ETH rises while Ethereum apps grow", None, ["ETH", "BTC"])

        self.assertEqual(symbols, ["ETH"])


if __name__ == "__main__":
    unittest.main()
