from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.collectors.binance import _base_price


def fetch_day_candles(
    market: str,
    count: int = 200,
    to: str | None = None,
    timeout_seconds: int = 20,
    api_base_url: str = "https://api.upbit.com",
) -> tuple[list[dict], float]:
    params = {"market": market.upper(), "count": min(max(count, 1), 200)}
    if to:
        params["to"] = to
    url = f"{api_base_url.rstrip('/')}/v1/candles/days?{urlencode(params)}"
    request = Request(url, headers=_headers())
    started = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000
    return payload, latency_ms


def fetch_day_candle_history(
    market: str,
    days: int = 365,
    timeout_seconds: int = 20,
    api_base_url: str = "https://api.upbit.com",
) -> tuple[list[dict], float]:
    remaining = min(max(days, 1), 1000)
    rows: list[dict] = []
    to: str | None = None
    total_latency = 0.0
    while remaining > 0:
        payload, latency = fetch_day_candles(
            market,
            count=min(remaining, 200),
            to=to,
            timeout_seconds=timeout_seconds,
            api_base_url=api_base_url,
        )
        total_latency += latency
        if not payload:
            break
        rows.extend(payload)
        remaining -= len(payload)
        oldest = min((_parse_datetime(row.get("candle_date_time_utc")) for row in payload), default=None)
        if oldest is None or len(payload) < 200:
            break
        to = (oldest - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    return rows[:days], total_latency


def normalize_day_candles(payload: list[dict], market: str, source: str = "upbit") -> list[dict]:
    candles = []
    for row in payload:
        opened_at = _parse_datetime(row.get("candle_date_time_utc"))
        if opened_at is None:
            continue
        candles.append(
            {
                "exchange": "upbit",
                "market": market.upper(),
                "quote_currency": _quote_currency(market),
                "timeframe": "1d",
                "opened_at": opened_at.replace(hour=0, minute=0, second=0, microsecond=0),
                "open": _safe_float(row.get("opening_price")),
                "high": _safe_float(row.get("high_price")),
                "low": _safe_float(row.get("low_price")),
                "close": _safe_float(row.get("trade_price")),
                "volume_base": _safe_float(row.get("candle_acc_trade_volume")),
                "volume_quote": _safe_float(row.get("candle_acc_trade_price")),
                "source": source,
                "raw_payload": row,
            }
        )
    return sorted(candles, key=lambda item: item["opened_at"])


def demo_day_candles(market: str, days: int = 365, usd_krw: float = 1350.0) -> list[dict]:
    symbol = market.upper().replace("KRW-", "")
    base = _base_price(symbol)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    trend_rng = random.Random(f"exchange-demo-trend-{symbol}-{today}-{days}")
    rng = random.Random(f"upbit-{market}-{today}-{days}")
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    usd_close = base * trend_rng.uniform(0.82, 1.16)
    close = usd_close * usd_krw * (1 + rng.uniform(0.005, 0.055))
    rows = []
    for index in range(days):
        opened_at = start + timedelta(days=index)
        open_price = close
        usd_close = max(usd_close * (1 + trend_rng.uniform(-0.045, 0.052)), 0.000001)
        premium = 0.025 + rng.uniform(-0.018, 0.028)
        close = max(usd_close * usd_krw * (1 + premium), 0.000001)
        spread = rng.uniform(0.006, 0.028)
        high = max(open_price, close) * (1 + spread)
        low = min(open_price, close) * (1 - spread)
        volume_base = rng.uniform(10_000, 90_000) if symbol == "BTC" else rng.uniform(80_000, 2_500_000)
        rows.append(
            {
                "market": market.upper(),
                "candle_date_time_utc": opened_at.isoformat().replace("+00:00", ""),
                "opening_price": open_price,
                "high_price": high,
                "low_price": low,
                "trade_price": close,
                "candle_acc_trade_price": close * volume_base,
                "candle_acc_trade_volume": volume_base,
                "timestamp": int((opened_at + timedelta(days=1)).timestamp() * 1000),
                "source_note": "deterministic demo fallback",
            }
        )
    return rows


def _headers() -> dict[str, str]:
    return {"accept": "application/json", "user-agent": "crypto-intel-mvp/0.1"}


def _quote_currency(market: str) -> str:
    if "-" in market:
        return market.split("-", 1)[0].upper()
    return "KRW"


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    if "+" not in normalized and normalized.count(":") >= 2:
        normalized = f"{normalized}+00:00"
    try:
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError:
        return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
