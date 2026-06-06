from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def fetch_coin_markets(coingecko_ids: list[str], timeout_seconds: int = 20) -> tuple[list[dict], float]:
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
    url = f"https://api.coingecko.com/api/v3/coins/markets?{params}"
    request = Request(url, headers={"accept": "application/json", "user-agent": "crypto-intel-mvp/0.1"})
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
    base_prices = {
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
    for index, asset in enumerate(assets):
        coin_id = asset["coingecko_id"]
        base = base_prices.get(coin_id, 100)
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
