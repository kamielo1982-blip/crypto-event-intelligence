from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def fetch_usd_rates(
    timeout_seconds: int = 10,
    api_base_url: str = "https://open.er-api.com/v6/latest",
) -> tuple[dict, float]:
    url = f"{api_base_url.rstrip('/')}/USD"
    request = Request(url, headers=_headers())
    started = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000
    return payload, latency_ms


def normalize_open_er_rate(
    payload: dict,
    quote_currency: str = "KRW",
    source: str = "open_er_api",
    observed_at: datetime | None = None,
) -> dict:
    base_currency = str(payload.get("base_code") or "USD").upper()
    quote = quote_currency.upper()
    rates = payload.get("rates") if isinstance(payload.get("rates"), dict) else {}
    return {
        "base_currency": base_currency,
        "quote_currency": quote,
        "rate": _safe_float(rates.get(quote)),
        "observed_at": observed_at or datetime.now(timezone.utc),
        "source_updated_at": _datetime_from_seconds(payload.get("time_last_update_unix")),
        "source": source,
        "raw_payload": payload,
    }


def _headers() -> dict[str, str]:
    return {"accept": "application/json", "user-agent": "crypto-intel-mvp/0.1"}


def _datetime_from_seconds(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
