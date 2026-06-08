from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def fetch_coingecko_global(
    timeout_seconds: int = 20,
    api_base_url: str = "https://api.coingecko.com/api/v3",
    api_key: str | None = None,
    api_key_header: str = "x-cg-demo-api-key",
) -> tuple[dict, float]:
    request = Request(f"{api_base_url.rstrip('/')}/global", headers=_headers(api_key, api_key_header))
    return _fetch_json(request, timeout_seconds)


def fetch_fear_greed(
    timeout_seconds: int = 20,
    api_base_url: str = "https://api.alternative.me",
) -> tuple[dict, float]:
    params = urlencode({"limit": 1, "format": "json"})
    request = Request(f"{api_base_url.rstrip('/')}/fng/?{params}", headers=_headers(None, ""))
    return _fetch_json(request, timeout_seconds)


def fetch_binance_premium_index(
    symbol: str = "BTCUSDT",
    timeout_seconds: int = 20,
    api_base_url: str = "https://fapi.binance.com",
) -> tuple[dict, float]:
    request = Request(f"{api_base_url.rstrip('/')}/fapi/v1/premiumIndex?{urlencode({'symbol': symbol})}", headers=_headers(None, ""))
    return _fetch_json(request, timeout_seconds)


def fetch_binance_open_interest(
    symbol: str = "BTCUSDT",
    timeout_seconds: int = 20,
    api_base_url: str = "https://fapi.binance.com",
) -> tuple[dict, float]:
    request = Request(f"{api_base_url.rstrip('/')}/fapi/v1/openInterest?{urlencode({'symbol': symbol})}", headers=_headers(None, ""))
    return _fetch_json(request, timeout_seconds)


def fetch_binance_long_short_ratio(
    symbol: str = "BTCUSDT",
    period: str = "5m",
    timeout_seconds: int = 20,
    api_base_url: str = "https://fapi.binance.com",
) -> tuple[list[dict], float]:
    params = urlencode({"symbol": symbol, "period": period, "limit": 1})
    request = Request(f"{api_base_url.rstrip('/')}/futures/data/globalLongShortAccountRatio?{params}", headers=_headers(None, ""))
    return _fetch_json(request, timeout_seconds)


def normalize_coingecko_global(payload: dict) -> dict:
    data = payload.get("data") if isinstance(payload, dict) else {}
    total_market_cap = data.get("total_market_cap") if isinstance(data, dict) else {}
    total_volume = data.get("total_volume") if isinstance(data, dict) else {}
    dominance = data.get("market_cap_percentage") if isinstance(data, dict) else {}
    return {
        "btc_dominance_pct": _safe_float((dominance or {}).get("btc")),
        "total_market_cap_usd": _safe_float((total_market_cap or {}).get("usd")),
        "total_volume_usd": _safe_float((total_volume or {}).get("usd")),
        "total_market_cap_change_24h_pct": _safe_float(data.get("market_cap_change_percentage_24h_usd") if isinstance(data, dict) else None),
        "raw_payload": payload,
    }


def normalize_fear_greed(payload: dict) -> dict:
    items = payload.get("data") if isinstance(payload, dict) else []
    item = items[0] if isinstance(items, list) and items else {}
    timestamp = _timestamp(item.get("timestamp") if isinstance(item, dict) else None)
    return {
        "fear_greed_value": _safe_float(item.get("value") if isinstance(item, dict) else None),
        "fear_greed_label": item.get("value_classification") if isinstance(item, dict) else None,
        "observed_at": timestamp,
        "raw_payload": payload,
    }


def normalize_binance_premium_index(payload: dict) -> dict:
    return {
        "btc_funding_rate": _safe_float(payload.get("lastFundingRate") if isinstance(payload, dict) else None),
        "mark_price": _safe_float(payload.get("markPrice") if isinstance(payload, dict) else None),
        "observed_at": _timestamp_ms(payload.get("time") if isinstance(payload, dict) else None),
        "raw_payload": payload,
    }


def normalize_binance_open_interest(payload: dict, mark_price: float | None = None) -> dict:
    open_interest_contracts = _safe_float(payload.get("openInterest") if isinstance(payload, dict) else None)
    return {
        "btc_open_interest_contracts": open_interest_contracts,
        "btc_open_interest_usd": open_interest_contracts * mark_price if open_interest_contracts is not None and mark_price is not None else None,
        "observed_at": _timestamp_ms(payload.get("time") if isinstance(payload, dict) else None),
        "raw_payload": payload,
    }


def normalize_binance_long_short_ratio(payload: list[dict] | dict) -> dict:
    item = payload[0] if isinstance(payload, list) and payload else payload if isinstance(payload, dict) else {}
    return {
        "btc_long_short_ratio": _safe_float(item.get("longShortRatio") if isinstance(item, dict) else None),
        "observed_at": _timestamp_ms(item.get("timestamp") if isinstance(item, dict) else None),
        "raw_payload": payload,
    }


def _fetch_json(request: Request, timeout_seconds: int) -> tuple[dict | list[dict], float]:
    started = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000
    return payload, latency_ms


def _headers(api_key: str | None, api_key_header: str) -> dict[str, str]:
    headers = {"accept": "application/json", "user-agent": "crypto-intel-mvp/0.1"}
    if api_key and api_key_header:
        headers[api_key_header] = api_key
    return headers


def _safe_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value: object) -> datetime | None:
    numeric = _safe_float(value)
    if numeric is None:
        return None
    return datetime.fromtimestamp(numeric, tz=timezone.utc)


def _timestamp_ms(value: object) -> datetime | None:
    numeric = _safe_float(value)
    if numeric is None:
        return None
    return datetime.fromtimestamp(numeric / 1000, tz=timezone.utc)
