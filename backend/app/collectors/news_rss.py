from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

from app.services.news import dedupe_news_items, duplicate_key, infer_related_symbols


DEFAULT_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def fetch_rss_news(known_symbols: list[str], timeout_seconds: int = 15) -> tuple[list[dict], float]:
    started = time.perf_counter()
    items: list[dict] = []
    for source, url in DEFAULT_FEEDS:
        request = Request(url, headers={"user-agent": "crypto-intel-mvp/0.1"})
        with urlopen(request, timeout=timeout_seconds) as response:
            root = ET.fromstring(response.read())
        for item in root.findall(".//item")[:30]:
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            summary = item.findtext("description")
            related_symbols = infer_related_symbols(title, summary, known_symbols)
            if not related_symbols:
                continue
            payload = {
                "source": source,
                "title": title.strip(),
                "url": link.strip(),
                "summary": summary,
                "published_at": _parse_datetime(item.findtext("pubDate")),
                "related_symbols": related_symbols,
                "duplicate_key": duplicate_key(title, link),
                "raw_payload": {"feed": url},
            }
            items.append(payload)
    return dedupe_news_items(items), (time.perf_counter() - started) * 1000


def demo_news_payload(known_symbols: list[str]) -> list[dict]:
    now = datetime.now(timezone.utc)
    samples = [
        ("BTC", "Bitcoin holds range as ETF flows return to focus", "https://example.com/btc-etf"),
        ("ETH", "Ethereum fees rise while exchange balances continue to fall", "https://example.com/eth-fees"),
        ("SOL", "Solana ecosystem activity accelerates after new app launch", "https://example.com/sol-activity"),
        ("XRP", "XRP volatility increases around regulatory headlines", "https://example.com/xrp-news"),
        ("DOGE", "DOGE social activity spikes during broad meme-coin rally", "https://example.com/doge-social"),
    ]
    return [
        {
            "source": "demo_fallback",
            "title": title,
            "url": url,
            "summary": title,
            "published_at": now,
            "related_symbols": [symbol] if symbol in known_symbols else [],
            "duplicate_key": duplicate_key(title, url),
            "raw_payload": {"source_note": "deterministic demo fallback"},
        }
        for symbol, title, url in samples
        if symbol in known_symbols
    ]
