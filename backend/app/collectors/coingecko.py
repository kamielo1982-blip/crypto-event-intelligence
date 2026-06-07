from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_PRICES = {
    "bitcoin": 98000,
    "ethereum": 3600,
    "binancecoin": 690,
    "solana": 180,
    "ripple": 2.2,
    "dogecoin": 0.19,
    "cardano": 0.72,
    "tron": 0.29,
    "the-open-network": 5.4,
    "avalanche-2": 42,
    "tether": 1.0,
    "usd-coin": 1.0,
}


def fetch_coin_markets(
    coingecko_ids: list[str],
    timeout_seconds: int = 20,
    api_base_url: str = "https://api.coingecko.com/api/v3",
    api_key: str | None = None,
    api_key_header: str = "x-cg-demo-api-key",
) -> tuple[list[dict], float]:
    params = urlencode(
        {
            "vs_currency": "usd",
            "ids": ",".join(coingecko_ids),
            "order": "market_cap_desc",
            "per_page": len(coingecko_ids),
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
    )
    url = f"{api_base_url.rstrip('/')}/coins/markets?{params}"
    request = Request(url, headers=_headers(api_key, api_key_header))
    started = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000
    return payload, latency_ms


def fetch_coin_ohlc(
    coingecko_id: str,
    days: int | str = 90,
    timeout_seconds: int = 20,
    api_base_url: str = "https://api.coingecko.com/api/v3",
    api_key: str | None = None,
    api_key_header: str = "x-cg-demo-api-key",
) -> tuple[list[list[float]], float]:
    params = urlencode({"vs_currency": "usd", "days": days})
    url = f"{api_base_url.rstrip('/')}/coins/{coingecko_id}/ohlc?{params}"
    request = Request(url, headers=_headers(api_key, api_key_header))
    started = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000
    return payload, latency_ms


def fetch_coin_market_chart(
    coingecko_id: str,
    days: int | str = 365,
    timeout_seconds: int = 20,
    interval: str | None = "daily",
    api_base_url: str = "https://api.coingecko.com/api/v3",
    api_key: str | None = None,
    api_key_header: str = "x-cg-demo-api-key",
) -> tuple[dict, float]:
    params = {"vs_currency": "usd", "days": days}
    if interval:
        params["interval"] = interval
    url = f"{api_base_url.rstrip('/')}/coins/{coingecko_id}/market_chart?{urlencode(params)}"
    request = Request(url, headers=_headers(api_key, api_key_header))
    started = time.perf_counter()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latency_ms = (time.perf_counter() - started) * 1000
    return payload, latency_ms


def demo_market_payload(assets: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    seed = int(now.strftime("%Y%m%d%H"))
    rng = random.Random(seed)
    payload = []
    for index, asset in enumerate(assets):
        coin_id = asset["coingecko_id"]
        base = BASE_PRICES.get(coin_id, 100)
        move = rng.uniform(-0.045, 0.055) if asset["group"] != "stablecoin" else rng.uniform(-0.001, 0.001)
        price = base * (1 + move)
        volume = base * rng.uniform(5_000_000, 40_000_000)
        supply = rng.uniform(20_000_000, 150_000_000_000)
        payload.append(
            {
                "id": coin_id,
                "symbol": asset["symbol"].lower(),
                "name": asset["name"],
                "current_price": price,
                "market_cap": price * supply,
                "total_volume": volume,
                "price_change_percentage_24h": move * 100,
                "circulating_supply": supply,
                "total_supply": supply * rng.uniform(1.0, 1.12),
                "max_supply": supply * rng.uniform(1.0, 1.5),
                "source_note": "deterministic demo fallback",
            }
        )
    return payload


def demo_ohlc_payload(coingecko_id: str, days: int = 90) -> list[list[float]]:
    rng = random.Random(f"{coingecko_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{days}")
    base = BASE_PRICES.get(coingecko_id, 100)
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    close = base * rng.uniform(0.82, 1.12)
    rows = []
    for index in range(days):
        opened_at = start + timedelta(days=index)
        open_price = close
        move = rng.uniform(-0.045, 0.052)
        close = max(open_price * (1 + move), 0.000001)
        spread = rng.uniform(0.006, 0.028)
        high = max(open_price, close) * (1 + spread)
        low = min(open_price, close) * (1 - spread)
        rows.append([opened_at.timestamp() * 1000, open_price, high, low, close])
    return rows


def demo_market_chart_payload(coingecko_id: str, days: int = 90) -> dict:
    rng = random.Random(f"{coingecko_id}-volume-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{days}")
    base = BASE_PRICES.get(coingecko_id, 100)
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    prices = []
    volumes = []
    price = base * rng.uniform(0.82, 1.12)
    for index in range(days):
        observed_at = start + timedelta(days=index)
        price = max(price * (1 + rng.uniform(-0.045, 0.052)), 0.000001)
        volume = base * rng.uniform(4_000_000, 34_000_000)
        prices.append([observed_at.timestamp() * 1000, price])
        volumes.append([observed_at.timestamp() * 1000, volume])
    return {"prices": prices, "total_volumes": volumes, "source_note": "deterministic demo fallback"}


def _headers(api_key: str | None, api_key_header: str) -> dict[str, str]:
    headers = {"accept": "application/json", "user-agent": "crypto-intel-mvp/0.1"}
    if api_key:
        headers[api_key_header] = api_key
    return headers
