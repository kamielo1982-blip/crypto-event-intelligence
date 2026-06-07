from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.collectors.coingecko import BASE_PRICES


def fetch_klines(
    symbol: str,
    interval: str = "1d",
    limit: int = 365,
    timeout_seconds: int = 20,
    api_base_url: str = "https://data-api.binance.vision",
) -> tuple[list[list], float]:
    params = urlencode({"symbol": symbol.upper(), "interval": interval, "limit": min(max(limit, 1), 1000)})
    url = f"{api_base_url.rstrip('/')}/api/v3/klines?{params}"
    request = Request(url, headers=_headers())
    started = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000
    return payload, latency_ms


def normalize_klines(payload: list[list], symbol: str, source: str = "binance") -> list[dict]:
    candles = []
    for row in payload:
        if len(row) < 8:
            continue
        opened_at = datetime.fromtimestamp(float(row[0]) / 1000, tz=timezone.utc)
        candles.append(
            {
                "exchange": "binance",
                "market": symbol.upper(),
                "quote_currency": _quote_currency(symbol),
                "timeframe": "1d",
                "opened_at": opened_at,
                "open": _safe_float(row[1]),
                "high": _safe_float(row[2]),
                "low": _safe_float(row[3]),
                "close": _safe_float(row[4]),
                "volume_base": _safe_float(row[5]),
                "volume_quote": _safe_float(row[7]),
                "source": source,
                "raw_payload": {"kline": row},
            }
        )
    return sorted(candles, key=lambda item: item["opened_at"])


def demo_klines(symbol: str, days: int = 365) -> list[list]:
    base_symbol = symbol.upper().replace("USDT", "")
    base = _base_price(base_symbol)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    trend_rng = random.Random(f"exchange-demo-trend-{base_symbol}-{today}-{days}")
    rng = random.Random(f"binance-{symbol}-{today}-{days}")
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    close = base * trend_rng.uniform(0.82, 1.16)
    rows = []
    for index in range(days):
        opened_at = start + timedelta(days=index)
        open_price = close
        close = max(open_price * (1 + trend_rng.uniform(-0.045, 0.052)), 0.000001)
        spread = rng.uniform(0.006, 0.026)
        high = max(open_price, close) * (1 + spread)
        low = min(open_price, close) * (1 - spread)
        volume_base = rng.uniform(30_000, 220_000) if base_symbol == "BTC" else rng.uniform(250_000, 9_000_000)
        volume_quote = volume_base * close
        close_time = opened_at + timedelta(days=1) - timedelta(milliseconds=1)
        rows.append(
            [
                int(opened_at.timestamp() * 1000),
                f"{open_price:.8f}",
                f"{high:.8f}",
                f"{low:.8f}",
                f"{close:.8f}",
                f"{volume_base:.8f}",
                int(close_time.timestamp() * 1000),
                f"{volume_quote:.8f}",
                0,
                "0",
                "0",
                "0",
            ]
        )
    return rows


def _headers() -> dict[str, str]:
    return {"accept": "application/json", "user-agent": "crypto-intel-mvp/0.1"}


def _quote_currency(symbol: str) -> str:
    normalized = symbol.upper()
    for quote in ("USDT", "USDC", "BTC", "ETH", "BNB"):
        if normalized.endswith(quote):
            return quote
    return "UNKNOWN"


def _base_price(symbol: str) -> float:
    lookup = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "BNB": "binancecoin",
        "SOL": "solana",
        "XRP": "ripple",
        "DOGE": "dogecoin",
        "ADA": "cardano",
        "TRX": "tron",
        "TON": "the-open-network",
        "AVAX": "avalanche-2",
    }
    return BASE_PRICES.get(lookup.get(symbol, ""), 100)


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
