from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from app.collectors.binance import _base_price


def fetch_candlesticks(
    order_currency: str,
    payment_currency: str = "KRW",
    chart_interval: str = "24h",
    timeout_seconds: int = 20,
    api_base_url: str = "https://api.bithumb.com",
) -> tuple[dict, float]:
    pair = f"{order_currency.upper()}_{payment_currency.upper()}"
    url = f"{api_base_url.rstrip('/')}/public/candlestick/{pair}/{chart_interval}"
    request = Request(url, headers=_headers())
    started = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000
    return payload, latency_ms


def fetch_ticker(
    order_currency: str,
    payment_currency: str = "KRW",
    timeout_seconds: int = 10,
    api_base_url: str = "https://api.bithumb.com",
) -> tuple[dict, float]:
    pair = f"{order_currency.upper()}_{payment_currency.upper()}"
    url = f"{api_base_url.rstrip('/')}/public/ticker/{pair}"
    request = Request(url, headers=_headers())
    started = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000
    return payload, latency_ms


def normalize_candlesticks(payload: dict | list, market: str, source: str = "bithumb", limit: int | None = None) -> list[dict]:
    rows = payload.get("data", []) if isinstance(payload, dict) else payload
    if limit is not None:
        rows = rows[-limit:]
    candles = []
    for row in rows:
        parsed = _parse_row(row)
        if parsed is None:
            continue
        opened_at, open_price, close_price, high_price, low_price, volume_base = parsed
        candles.append(
            {
                "exchange": "bithumb",
                "market": market.upper(),
                "quote_currency": _quote_currency(market),
                "timeframe": "1d",
                "opened_at": opened_at.replace(hour=0, minute=0, second=0, microsecond=0),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume_base": volume_base,
                "volume_quote": close_price * volume_base if close_price is not None and volume_base is not None else None,
                "source": source,
                "raw_payload": {"candlestick": row},
            }
        )
    return sorted(candles, key=lambda item: item["opened_at"])


def normalize_ticker(payload: dict, market: str, source: str = "bithumb") -> dict:
    row = payload.get("data", {}) if isinstance(payload, dict) else {}
    if not isinstance(row, dict):
        row = {}
    normalized_market = market.upper()
    return {
        "exchange": "bithumb",
        "market": normalized_market,
        "base_currency": _base_currency(normalized_market),
        "quote_currency": _quote_currency(normalized_market),
        "price": _safe_float(row.get("closing_price")),
        "observed_at": _datetime_from_any(row.get("date")) or datetime.now(timezone.utc),
        "source": source,
        "raw_payload": payload,
    }


def demo_candlesticks(market: str, days: int = 365, usd_krw: float = 1350.0) -> dict:
    symbol = market.upper().replace("_KRW", "")
    base = _base_price(symbol)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    trend_rng = random.Random(f"exchange-demo-trend-{symbol}-{today}-{days}")
    rng = random.Random(f"bithumb-{market}-{today}-{days}")
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    usd_close = base * trend_rng.uniform(0.82, 1.16)
    close = usd_close * usd_krw * (1 + rng.uniform(-0.005, 0.045))
    rows = []
    for index in range(days):
        opened_at = start + timedelta(days=index)
        open_price = close
        usd_close = max(usd_close * (1 + trend_rng.uniform(-0.045, 0.052)), 0.000001)
        premium = 0.015 + rng.uniform(-0.018, 0.025)
        close = max(usd_close * usd_krw * (1 + premium), 0.000001)
        spread = rng.uniform(0.006, 0.028)
        high = max(open_price, close) * (1 + spread)
        low = min(open_price, close) * (1 - spread)
        volume_base = rng.uniform(8_000, 75_000) if symbol == "BTC" else rng.uniform(60_000, 2_000_000)
        rows.append(
            [
                int(opened_at.timestamp() * 1000),
                f"{open_price:.8f}",
                f"{close:.8f}",
                f"{high:.8f}",
                f"{low:.8f}",
                f"{volume_base:.8f}",
            ]
        )
    return {"status": "0000", "data": rows, "source_note": "deterministic demo fallback"}


def _headers() -> dict[str, str]:
    return {"accept": "application/json", "user-agent": "crypto-intel-mvp/0.1"}


def _parse_row(row: object) -> tuple[datetime, float | None, float | None, float | None, float | None, float | None] | None:
    if isinstance(row, dict):
        opened_at = _datetime_from_any(row.get("time") or row.get("timestamp") or row.get("opening_time"))
        if opened_at is None:
            return None
        return (
            opened_at,
            _safe_float(row.get("open") or row.get("opening_price")),
            _safe_float(row.get("close") or row.get("trade_price")),
            _safe_float(row.get("high") or row.get("high_price")),
            _safe_float(row.get("low") or row.get("low_price")),
            _safe_float(row.get("volume") or row.get("candle_acc_trade_volume")),
        )
    if not isinstance(row, (list, tuple)) or len(row) < 6:
        return None
    opened_at = _datetime_from_any(row[0])
    if opened_at is None:
        return None
    return (
        opened_at,
        _safe_float(row[1]),
        _safe_float(row[2]),
        _safe_float(row[3]),
        _safe_float(row[4]),
        _safe_float(row[5]),
    )


def _datetime_from_any(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return _datetime_from_any(float(stripped))
        normalized = stripped[:-1] + "+00:00" if stripped.endswith("Z") else stripped
        if "+" not in normalized and normalized.count(":") >= 2:
            normalized = f"{normalized}+00:00"
        try:
            return datetime.fromisoformat(normalized).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _quote_currency(market: str) -> str:
    if "_" in market:
        return market.split("_", 1)[1].upper()
    return "KRW"


def _base_currency(market: str) -> str:
    if "_" in market:
        return market.split("_", 1)[0].upper()
    return market.upper()


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
