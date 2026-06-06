from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import AIInterpretation, Asset, MarketSnapshot, SignalEvent, SourceHealth


def _latest_market(session: Session, asset_id: int) -> MarketSnapshot | None:
    return session.scalar(
        select(MarketSnapshot).where(MarketSnapshot.asset_id == asset_id).order_by(desc(MarketSnapshot.observed_at)).limit(1)
    )


def _previous_market(session: Session, asset_id: int, latest_id: int | None) -> MarketSnapshot | None:
    query = select(MarketSnapshot).where(MarketSnapshot.asset_id == asset_id).order_by(desc(MarketSnapshot.observed_at)).limit(1)
    if latest_id:
        query = query.where(MarketSnapshot.id != latest_id)
    return session.scalar(query)


def _latest_interpretation(session: Session, asset_id: int) -> AIInterpretation | None:
    return session.scalar(
        select(AIInterpretation).where(AIInterpretation.asset_id == asset_id).order_by(desc(AIInterpretation.generated_at)).limit(1)
    )


def _recent_signal_count(session: Session, asset_id: int) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    return session.scalar(
        select(func.count(SignalEvent.id)).where(SignalEvent.asset_id == asset_id, SignalEvent.occurred_at >= since)
    ) or 0


def market_brief(session: Session) -> dict:
    assets = session.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.group, Asset.rank)).all()
    investable = []
    stablecoins = []
    for asset in assets:
        latest = _latest_market(session, asset.id)
        previous = _previous_market(session, asset.id, latest.id if latest else None)
        interpretation = _latest_interpretation(session, asset.id)
        row = {
            "asset": {"symbol": asset.symbol, "name": asset.name, "group": asset.group, "rank": asset.rank},
            "latest_snapshot": snapshot_to_dict(latest),
            "previous_snapshot": snapshot_to_dict(previous),
            "signal_count_24h": _recent_signal_count(session, asset.id),
            "interpretation": interpretation_to_dict(interpretation),
        }
        if asset.group == "stablecoin":
            stablecoins.append(row)
        elif asset.group == "investable":
            investable.append(row)
    return {"investable": investable, "stablecoins": stablecoins, "generated_at": datetime.now(timezone.utc).isoformat()}


def asset_overview(session: Session, symbol: str) -> dict | None:
    asset = session.scalar(select(Asset).where(Asset.symbol == symbol.upper(), Asset.is_active.is_(True)))
    if not asset:
        return None
    snapshots = session.scalars(
        select(MarketSnapshot).where(MarketSnapshot.asset_id == asset.id).order_by(desc(MarketSnapshot.observed_at)).limit(80)
    ).all()
    signals = session.scalars(
        select(SignalEvent).where(SignalEvent.asset_id == asset.id).order_by(desc(SignalEvent.occurred_at)).limit(40)
    ).all()
    interpretation = _latest_interpretation(session, asset.id)
    return {
        "asset": {"symbol": asset.symbol, "name": asset.name, "group": asset.group, "rank": asset.rank},
        "snapshots": [snapshot_to_dict(item) for item in reversed(snapshots)],
        "signals": [signal_to_dict(item) for item in signals],
        "interpretation": interpretation_to_dict(interpretation),
    }


def event_feed(session: Session, symbol: str | None = None, signal_type: str | None = None, severity: str | None = None) -> list[dict]:
    query = select(SignalEvent, Asset).join(Asset, Asset.id == SignalEvent.asset_id).order_by(desc(SignalEvent.occurred_at)).limit(200)
    if symbol:
        query = query.where(Asset.symbol == symbol.upper())
    if signal_type:
        query = query.where(SignalEvent.signal_type == signal_type)
    if severity:
        query = query.where(SignalEvent.severity == severity)
    rows = session.execute(query).all()
    return [{**signal_to_dict(signal), "asset": {"symbol": asset.symbol, "name": asset.name}} for signal, asset in rows]


def source_health(session: Session) -> list[dict]:
    rows = session.scalars(select(SourceHealth).order_by(SourceHealth.source)).all()
    return [
        {
            "source": item.source,
            "status": item.status,
            "success_rate_24h": item.success_rate_24h,
            "latency_ms": item.latency_ms,
            "last_success_at": item.last_success_at.isoformat() if item.last_success_at else None,
            "last_failure_at": item.last_failure_at.isoformat() if item.last_failure_at else None,
            "message": item.message,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
        for item in rows
    ]


def snapshot_to_dict(snapshot: MarketSnapshot | None) -> dict | None:
    if not snapshot:
        return None
    return {
        "observed_at": snapshot.observed_at.isoformat(),
        "price_usd": snapshot.price_usd,
        "market_cap_usd": snapshot.market_cap_usd,
        "volume_24h_usd": snapshot.volume_24h_usd,
        "price_change_24h_pct": snapshot.price_change_24h_pct,
        "circulating_supply": snapshot.circulating_supply,
        "total_supply": snapshot.total_supply,
        "source": snapshot.source,
    }


def signal_to_dict(signal: SignalEvent) -> dict:
    return {
        "id": signal.id,
        "occurred_at": signal.occurred_at.isoformat(),
        "signal_type": signal.signal_type,
        "severity": signal.severity,
        "title": signal.title,
        "description": signal.description,
        "value": signal.value,
        "source": signal.source,
        "evidence": signal.evidence,
    }


def interpretation_to_dict(item: AIInterpretation | None) -> dict | None:
    if not item:
        return None
    return {
        "generated_at": item.generated_at.isoformat(),
        "summary": item.summary,
        "candidates": item.candidates,
        "caveats": item.caveats,
        "confidence": item.confidence,
        "model": item.model,
        "prompt_version": item.prompt_version,
    }
