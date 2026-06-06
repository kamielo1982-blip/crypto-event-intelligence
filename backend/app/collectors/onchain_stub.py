from __future__ import annotations

import random
from datetime import datetime, timezone


def demo_onchain_payload(symbol: str) -> dict:
    seed = int(datetime.now(timezone.utc).strftime("%Y%m%d%H")) + sum(ord(char) for char in symbol)
    rng = random.Random(seed)
    return {
        "active_addresses": rng.randint(30_000, 1_200_000),
        "transaction_count": rng.randint(80_000, 2_400_000),
        "fees_usd": round(rng.uniform(20_000, 8_000_000), 2),
        "exchange_netflow_usd": round(rng.uniform(-80_000_000, 80_000_000), 2),
        "source": "demo_fallback",
        "availability": "partial",
        "raw_payload": {"source_note": "deterministic demo fallback"},
    }
