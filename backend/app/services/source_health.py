from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SourceAttempt:
    source: str
    ok: bool
    observed_at: datetime
    latency_ms: float | None = None
    message: str | None = None


def compute_success_rate(attempts: list[SourceAttempt], now: datetime | None = None) -> float | None:
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(hours=24)
    recent = [attempt for attempt in attempts if attempt.observed_at >= window_start]
    if not recent:
        return None
    success = sum(1 for attempt in recent if attempt.ok)
    return round(success / len(recent), 4)


def summarize_source(source: str, attempts: list[SourceAttempt], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    source_attempts = [attempt for attempt in attempts if attempt.source == source]
    success_rate = compute_success_rate(source_attempts, now)
    last_success = max((a.observed_at for a in source_attempts if a.ok), default=None)
    last_failure = max((a.observed_at for a in source_attempts if not a.ok), default=None)
    latest = max(source_attempts, key=lambda item: item.observed_at, default=None)
    if latest is None:
        status = "unknown"
    elif latest.ok:
        status = "ok"
    elif success_rate and success_rate > 0:
        status = "degraded"
    else:
        status = "failed"
    return {
        "source": source,
        "status": status,
        "success_rate_24h": success_rate,
        "last_success_at": last_success,
        "last_failure_at": last_failure,
        "latency_ms": latest.latency_ms if latest else None,
        "message": latest.message if latest else None,
    }
