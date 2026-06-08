from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import pstdev


SEVERITY_WEIGHT = {"high": 25, "medium": 15, "low": 6}


def normalize_ohlc_payload(payload: list[list[float | int]], source: str) -> list[dict]:
    candles = []
    for row in payload:
        if len(row) < 5:
            continue
        opened_at = datetime.fromtimestamp(float(row[0]) / 1000, tz=timezone.utc)
        candles.append(
            {
                "opened_at": opened_at,
                "open": _safe_float(row[1]),
                "high": _safe_float(row[2]),
                "low": _safe_float(row[3]),
                "close": _safe_float(row[4]),
                "volume_usd": None,
                "source": source,
                "raw_payload": {"ohlc": row},
            }
        )
    return sorted(candles, key=lambda item: item["opened_at"])


def normalize_market_chart_payload(payload: dict, source: str) -> list[dict]:
    grouped: dict[datetime, list[tuple[datetime, float]]] = {}
    for row in payload.get("prices", []):
        if len(row) < 2:
            continue
        observed_at = datetime.fromtimestamp(float(row[0]) / 1000, tz=timezone.utc)
        bucket = observed_at.replace(hour=0, minute=0, second=0, microsecond=0)
        grouped.setdefault(bucket, []).append((observed_at, float(row[1])))

    volume_by_day = {}
    for row in payload.get("total_volumes", []):
        if len(row) < 2:
            continue
        observed_at = datetime.fromtimestamp(float(row[0]) / 1000, tz=timezone.utc)
        bucket = observed_at.replace(hour=0, minute=0, second=0, microsecond=0)
        volume_by_day[bucket] = float(row[1])

    candles = []
    for opened_at, prices in sorted(grouped.items()):
        ordered = sorted(prices, key=lambda item: item[0])
        values = [price for _, price in ordered]
        candles.append(
            {
                "opened_at": opened_at,
                "open": values[0],
                "high": max(values),
                "low": min(values),
                "close": values[-1],
                "volume_usd": volume_by_day.get(opened_at),
                "source": source,
                "raw_payload": {"market_chart_points": len(values), "market_chart_volume": volume_by_day.get(opened_at)},
            }
        )
    return candles


def attach_moving_averages(candles: list[dict]) -> list[dict]:
    rows = sorted(candles, key=lambda item: item["opened_at"])
    closes: list[float | None] = [row.get("close") for row in rows]
    enriched = []
    for index, row in enumerate(rows):
        enriched.append(
            {
                **row,
                "ma7": _average_window(closes, index, 7),
                "ma20": _average_window(closes, index, 20),
            }
        )
    return enriched


def calculate_supply_delta(current: dict, previous: dict | None) -> dict:
    mint_amount = current.get("mint_amount")
    burn_amount = current.get("burn_amount")
    if mint_amount is not None or burn_amount is not None:
        mint = float(mint_amount or 0)
        burn = float(burn_amount or 0)
        net_change = mint - burn
        circulating = current.get("circulating_supply")
        net_change_pct = (net_change / circulating * 100) if circulating not in (None, 0) else None
        return {"net_change": net_change, "net_change_pct": net_change_pct, "method": "direct"}

    if previous is None:
        return {"net_change": None, "net_change_pct": None, "method": "unavailable"}

    current_supply = current.get("circulating_supply")
    previous_supply = previous.get("circulating_supply")
    if current_supply is None or previous_supply is None:
        return {"net_change": None, "net_change_pct": None, "method": "unavailable"}

    net_change = float(current_supply) - float(previous_supply)
    net_change_pct = (net_change / float(previous_supply) * 100) if previous_supply != 0 else None
    return {"net_change": net_change, "net_change_pct": net_change_pct, "method": "circulating_proxy"}


def score_news_impact(
    news_count: int,
    signal_severity: str | None,
    proximity_hours: float | None,
    source_count: int,
) -> int:
    count_score = min(news_count * 12, 50)
    severity_score = SEVERITY_WEIGHT.get(signal_severity or "", 0)
    proximity_score = 0 if proximity_hours is None else max(0, 20 - int(proximity_hours * 2))
    diversity_score = min(source_count * 5, 10)
    return min(100, count_score + severity_score + proximity_score + diversity_score)


def score_abs_change(value: float | None, medium: float, high: float) -> int:
    if value is None:
        return 0
    absolute = abs(value)
    if absolute >= high:
        return 100
    if absolute <= 0:
        return 0
    return min(100, round((absolute / high) * 100))


def calculate_kimchi_premium(global_price_usd: float | None, korean_price_krw: float | None, usd_krw: float | None) -> dict:
    if global_price_usd in (None, 0) or korean_price_krw is None or usd_krw in (None, 0):
        return {"korean_price_usd": None, "premium_pct": None}
    korean_price_usd = float(korean_price_krw) / float(usd_krw)
    premium_pct = ((korean_price_usd - float(global_price_usd)) / float(global_price_usd)) * 100
    return {"korean_price_usd": korean_price_usd, "premium_pct": premium_pct}


def calculate_live_kimchi_premium(
    global_price_usd: float | None,
    korean_price_krw: float | None,
    usd_krw: float | None,
    usdt_krw_reference: float | None = None,
) -> dict:
    primary = calculate_kimchi_premium(global_price_usd, korean_price_krw, usd_krw)
    usdt_basis = calculate_kimchi_premium(global_price_usd, korean_price_krw, usdt_krw_reference)
    return {
        **primary,
        "usdt_basis_premium_pct": usdt_basis["premium_pct"],
    }


def score_kimchi_premium(premium_pct: float | None) -> int:
    return score_abs_change(premium_pct, medium=2.0, high=8.0)


def build_factor_trend_series(
    factor: str,
    metric: str,
    label: str,
    unit: str,
    rows: list[dict],
    data_quality: str = "unavailable",
) -> dict:
    ordered = sorted(rows, key=lambda item: _parse_time(item.get("observed_at")) or datetime.min.replace(tzinfo=timezone.utc))
    return {
        "factor": factor,
        "metric": metric,
        "label": label,
        "unit": unit,
        "data_quality": data_quality,
        "points": _trend_points(ordered, metric),
    }


def _trend_points(rows: list[dict], metric: str) -> list[dict]:
    points = []
    previous_value = None
    observed_rows = [(row, _parse_time(row.get("observed_at"))) for row in rows]
    for row, observed_at in observed_rows:
        value = _safe_float(row.get(metric))
        avg_7d = _average_since(observed_rows, metric, observed_at, days=7)
        avg_30d = _average_since(observed_rows, metric, observed_at, days=30)
        std_30d = _std_since(observed_rows, metric, observed_at, days=30)
        z_score = ((value - avg_30d) / std_30d) if value is not None and avg_30d is not None and std_30d not in (None, 0) else None
        points.append(
            {
                "observed_at": row.get("observed_at"),
                "value": value,
                "delta_pct": _pct_delta(value, previous_value),
                "vs_7d_avg_pct": _pct_delta(value, avg_7d),
                "vs_30d_avg_pct": _pct_delta(value, avg_30d),
                "z_score_30d": round(z_score, 4) if z_score is not None else None,
                "direction": _trend_direction(value, previous_value),
                "availability": row.get("availability") or "unavailable",
                "source": row.get("source") or "unknown",
            }
        )
        if value is not None:
            previous_value = value
    return points


def _average_window(values: list[float | None], index: int, window: int) -> float | None:
    if index + 1 < window:
        return None
    window_values = values[index + 1 - window : index + 1]
    if any(value is None for value in window_values):
        return None
    return sum(value for value in window_values if value is not None) / window


def _safe_float(value: float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _parse_time(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        normalized = value if value.lower().endswith("z") or "+" in value[-6:] else f"{value}Z"
        try:
            return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _average_since(rows: list[tuple[dict, datetime | None]], metric: str, observed_at: datetime | None, days: int) -> float | None:
    values = _values_since(rows, metric, observed_at, days)
    return (sum(values) / len(values)) if values else None


def _std_since(rows: list[tuple[dict, datetime | None]], metric: str, observed_at: datetime | None, days: int) -> float | None:
    values = _values_since(rows, metric, observed_at, days)
    if len(values) < 2:
        return None
    return pstdev(values)


def _values_since(rows: list[tuple[dict, datetime | None]], metric: str, observed_at: datetime | None, days: int) -> list[float]:
    if observed_at is None:
        return []
    start = observed_at - timedelta(days=days)
    values = []
    for row, row_time in rows:
        if row_time is None or row_time < start or row_time > observed_at:
            continue
        value = _safe_float(row.get(metric))
        if value is not None:
            values.append(value)
    return values


def _pct_delta(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline in (None, 0):
        return None
    return ((value - baseline) / baseline) * 100


def _trend_direction(value: float | None, previous: float | None) -> str:
    if value is None or previous is None or value == previous:
        return "neutral"
    return "up" if value > previous else "down"
