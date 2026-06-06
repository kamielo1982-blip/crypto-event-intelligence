from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.collectors.coingecko import demo_market_payload, fetch_coin_markets
from app.collectors.news_rss import demo_news_payload, fetch_rss_news
from app.collectors.onchain_stub import demo_onchain_payload
from app.config import Settings
from app.models import (
    AIInterpretation,
    Asset,
    CollectionRun,
    MarketSnapshot,
    NewsItem,
    OnchainSnapshot,
    SignalEvent,
    SourceHealth,
    SupplySnapshot,
    utcnow,
)
from app.seed import seed_defaults
from app.services.ai_interpreter import LocalHeuristicInterpreter
from app.services.news import dedupe_news_items
from app.services.signal_engine import build_market_signals, build_news_signals, build_onchain_signals, build_supply_signals


def run_collection_once(session: Session, settings: Settings, trigger: str = "manual") -> CollectionRun:
    seed_defaults(session, settings)
    run = CollectionRun(status="running", trigger=trigger)
    session.add(run)
    session.commit()

    assets = session.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.group, Asset.rank)).all()
    summary = {"market": "pending", "news": "pending", "onchain": "pending"}
    try:
        market_payload, market_source, market_latency = _collect_market_data(assets, settings)
        _store_market_snapshots(session, run, assets, market_payload, market_source)
        _record_source_health(session, "coingecko_market", True, market_latency, f"{len(market_payload)} assets")
        summary["market"] = market_source
    except Exception as exc:
        _record_source_health(session, "coingecko_market", False, None, str(exc))
        summary["market"] = "failed"

    try:
        news_payload, news_source, news_latency = _collect_news_data(assets, settings)
        _store_news(session, news_payload)
        _record_source_health(session, "rss_news", True, news_latency, f"{len(news_payload)} items")
        summary["news"] = news_source
    except Exception as exc:
        _record_source_health(session, "rss_news", False, None, str(exc))
        summary["news"] = "failed"

    _store_onchain_and_supply(session, run, assets)
    summary["onchain"] = "demo_partial"
    _record_source_health(session, "onchain_supply_demo", True, None, "partial MVP availability")

    created_signals = _generate_signals(session, run, assets)
    try:
        created_interpretations = _generate_interpretations(session, run, assets)
        _record_source_health(session, "ai_interpretation", True, None, f"{created_interpretations} interpretations")
        summary["ai"] = "local-heuristic"
    except Exception as exc:
        created_interpretations = 0
        _record_source_health(session, "ai_interpretation", False, None, str(exc))
        summary["ai"] = "failed"

    run.status = "success" if "failed" not in summary.values() else "partial"
    run.finished_at = utcnow()
    run.raw_summary = {**summary, "signals": created_signals, "interpretations": created_interpretations}
    run.message = f"signals={created_signals}, interpretations={created_interpretations}"
    session.commit()
    return run


def regenerate_interpretations_for_latest_run(session: Session) -> dict:
    run = session.scalar(select(CollectionRun).order_by(desc(CollectionRun.started_at)).limit(1))
    if not run:
        return {"id": None, "status": "no_run", "message": "No collection run exists.", "summary": {}}

    assets = session.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.group, Asset.rank)).all()
    session.execute(delete(AIInterpretation).where(AIInterpretation.collection_run_id == run.id))
    session.commit()

    try:
        created = _generate_interpretations(session, run, assets)
        _record_source_health(session, "ai_interpretation", True, None, f"regenerated {created} interpretations")
        run.raw_summary = {**(run.raw_summary or {}), "interpretations": created, "ai": "regenerated"}
        run.message = f"regenerated_interpretations={created}"
        session.commit()
        return {"id": run.id, "status": "success", "message": run.message, "summary": run.raw_summary}
    except Exception as exc:
        _record_source_health(session, "ai_interpretation", False, None, str(exc))
        return {"id": run.id, "status": "failed", "message": str(exc), "summary": run.raw_summary or {}}


def _collect_market_data(assets: list[Asset], settings: Settings) -> tuple[list[dict], str, float]:
    ids = [asset.coingecko_id for asset in assets if asset.coingecko_id]
    try:
        payload, latency = fetch_coin_markets(ids)
        return payload, "coingecko", latency
    except Exception:
        if not settings.enable_demo_data:
            raise
        started = time.perf_counter()
        payload = demo_market_payload(
            [
                {"symbol": asset.symbol, "name": asset.name, "coingecko_id": asset.coingecko_id, "group": asset.group}
                for asset in assets
                if asset.coingecko_id
            ]
        )
        return payload, "demo_fallback", (time.perf_counter() - started) * 1000


def _collect_news_data(assets: list[Asset], settings: Settings) -> tuple[list[dict], str, float]:
    symbols = [asset.symbol for asset in assets if asset.group == "investable"]
    try:
        payload, latency = fetch_rss_news(symbols)
        return payload, "rss", latency
    except Exception:
        if not settings.enable_demo_data:
            raise
        started = time.perf_counter()
        return demo_news_payload(symbols), "demo_fallback", (time.perf_counter() - started) * 1000


def _store_market_snapshots(session: Session, run: CollectionRun, assets: list[Asset], payload: list[dict], source: str) -> None:
    by_id = {asset.coingecko_id: asset for asset in assets}
    for row in payload:
        asset = by_id.get(row.get("id"))
        if not asset:
            continue
        session.add(
            MarketSnapshot(
                asset_id=asset.id,
                collection_run_id=run.id,
                price_usd=row.get("current_price"),
                market_cap_usd=row.get("market_cap"),
                volume_24h_usd=row.get("total_volume"),
                price_change_24h_pct=row.get("price_change_percentage_24h"),
                circulating_supply=row.get("circulating_supply"),
                total_supply=row.get("total_supply"),
                source=source,
                raw_payload=row,
            )
        )
    session.commit()


def _store_news(session: Session, payload: list[dict]) -> None:
    for row in dedupe_news_items(payload):
        exists = session.scalar(select(NewsItem).where(NewsItem.duplicate_key == row["duplicate_key"], NewsItem.source == row["source"]))
        if exists:
            continue
        session.add(NewsItem(**row))
    session.commit()


def _store_onchain_and_supply(session: Session, run: CollectionRun, assets: list[Asset]) -> None:
    for asset in assets:
        if asset.group != "investable":
            continue
        onchain = demo_onchain_payload(asset.symbol)
        session.add(OnchainSnapshot(asset_id=asset.id, collection_run_id=run.id, **onchain))
        latest_market = session.scalar(
            select(MarketSnapshot).where(MarketSnapshot.asset_id == asset.id).order_by(desc(MarketSnapshot.observed_at)).limit(1)
        )
        session.add(
            SupplySnapshot(
                asset_id=asset.id,
                collection_run_id=run.id,
                circulating_supply=latest_market.circulating_supply if latest_market else None,
                total_supply=latest_market.total_supply if latest_market else None,
                max_supply=(latest_market.raw_payload or {}).get("max_supply") if latest_market else None,
                burn_amount=None,
                mint_amount=None,
                source=latest_market.source if latest_market else "unavailable",
                availability="partial" if latest_market else "unavailable",
                raw_payload=latest_market.raw_payload if latest_market else None,
            )
        )
    session.commit()


def _generate_signals(session: Session, run: CollectionRun, assets: list[Asset]) -> int:
    created = 0
    for asset in assets:
        if asset.group != "investable":
            continue
        market_rows = session.scalars(
            select(MarketSnapshot).where(MarketSnapshot.asset_id == asset.id).order_by(desc(MarketSnapshot.observed_at)).limit(2)
        ).all()
        current_market = _market_dict(market_rows[0]) if market_rows else None
        previous_market = _market_dict(market_rows[1]) if len(market_rows) > 1 else None
        drafts = build_market_signals(asset.symbol, current_market or {}, previous_market)

        candidate_news = session.scalars(select(NewsItem).order_by(desc(NewsItem.published_at)).limit(120)).all()
        news_rows = [item for item in candidate_news if asset.symbol in (item.related_symbols or [])][:20]
        drafts.extend(build_news_signals(asset.symbol, [_news_dict(row) for row in news_rows], datetime.now(timezone.utc)))

        onchain_rows = session.scalars(
            select(OnchainSnapshot).where(OnchainSnapshot.asset_id == asset.id).order_by(desc(OnchainSnapshot.observed_at)).limit(2)
        ).all()
        if len(onchain_rows) >= 2:
            drafts.extend(build_onchain_signals(asset.symbol, _onchain_dict(onchain_rows[0]), _onchain_dict(onchain_rows[1])))

        supply_rows = session.scalars(
            select(SupplySnapshot).where(SupplySnapshot.asset_id == asset.id).order_by(desc(SupplySnapshot.observed_at)).limit(2)
        ).all()
        if len(supply_rows) >= 2:
            drafts.extend(build_supply_signals(asset.symbol, _supply_dict(supply_rows[0]), _supply_dict(supply_rows[1])))

        for draft in drafts:
            session.add(
                SignalEvent(
                    asset_id=asset.id,
                    collection_run_id=run.id,
                    signal_type=draft.signal_type,
                    severity=draft.severity,
                    title=draft.title,
                    description=draft.description,
                    value=draft.value,
                    source=draft.source,
                    evidence=draft.evidence,
                )
            )
            created += 1
    session.commit()
    return created


def _generate_interpretations(session: Session, run: CollectionRun, assets: list[Asset]) -> int:
    interpreter = LocalHeuristicInterpreter()
    created = 0
    for asset in assets:
        if asset.group != "investable":
            continue
        existing = session.scalar(
            select(AIInterpretation).where(
                AIInterpretation.asset_id == asset.id,
                AIInterpretation.collection_run_id == run.id,
                AIInterpretation.prompt_version == "v1",
            )
        )
        if existing:
            continue
        signals = session.scalars(
            select(SignalEvent).where(SignalEvent.asset_id == asset.id, SignalEvent.collection_run_id == run.id).order_by(desc(SignalEvent.occurred_at))
        ).all()
        signal_dicts = [_signal_dict(item) for item in signals]
        caveats = _data_quality_caveats(session, asset.id)
        result = interpreter.interpret(asset.symbol, signal_dicts, caveats)
        session.add(
            AIInterpretation(
                asset_id=asset.id,
                collection_run_id=run.id,
                prompt_version="v1",
                model=result.model,
                summary=result.summary,
                candidates=result.candidates,
                caveats=result.caveats,
                confidence=result.confidence,
                evidence_signal_ids=[item.id for item in signals],
                raw_output=result.raw_output,
            )
        )
        created += 1
    session.commit()
    return created


def _record_source_health(session: Session, source: str, ok: bool, latency_ms: float | None, message: str) -> None:
    item = session.scalar(select(SourceHealth).where(SourceHealth.source == source))
    now = utcnow()
    if not item:
        item = SourceHealth(source=source)
        session.add(item)
    item.status = "ok" if ok else "failed"
    item.last_success_at = now if ok else item.last_success_at
    item.last_failure_at = now if not ok else item.last_failure_at
    item.success_rate_24h = 1.0 if ok else 0.0
    item.latency_ms = latency_ms
    item.message = message
    item.updated_at = now
    session.commit()


def _data_quality_caveats(session: Session, asset_id: int) -> list[str]:
    latest_onchain = session.scalar(
        select(OnchainSnapshot).where(OnchainSnapshot.asset_id == asset_id).order_by(desc(OnchainSnapshot.observed_at)).limit(1)
    )
    latest_supply = session.scalar(
        select(SupplySnapshot).where(SupplySnapshot.asset_id == asset_id).order_by(desc(SupplySnapshot.observed_at)).limit(1)
    )
    caveats = []
    if not latest_onchain or latest_onchain.availability != "complete":
        caveats.append("온체인 데이터는 MVP에서 부분 제공 상태입니다.")
    if not latest_supply or latest_supply.availability != "complete":
        caveats.append("공급/소각 데이터는 source availability에 따라 제한됩니다.")
    return caveats


def _market_dict(row: MarketSnapshot) -> dict:
    return {
        "price_usd": row.price_usd,
        "volume_24h_usd": row.volume_24h_usd,
        "market_cap_usd": row.market_cap_usd,
        "source": row.source,
        "observed_at": row.observed_at.isoformat(),
    }


def _news_dict(row: NewsItem) -> dict:
    return {"title": row.title, "url": row.url, "source": row.source, "published_at": row.published_at.isoformat() if row.published_at else None}


def _onchain_dict(row: OnchainSnapshot) -> dict:
    return {
        "active_addresses": row.active_addresses,
        "transaction_count": row.transaction_count,
        "fees_usd": row.fees_usd,
        "exchange_netflow_usd": row.exchange_netflow_usd,
        "availability": row.availability,
    }


def _supply_dict(row: SupplySnapshot) -> dict:
    return {
        "circulating_supply": row.circulating_supply,
        "total_supply": row.total_supply,
        "availability": row.availability,
    }


def _signal_dict(row: SignalEvent) -> dict:
    return {
        "id": row.id,
        "signal_type": row.signal_type,
        "severity": row.severity,
        "title": row.title,
        "description": row.description,
        "value": row.value,
        "source": row.source,
        "evidence": row.evidence,
    }
