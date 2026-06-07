from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.models import (
    AIInterpretation,
    Asset,
    ExchangeCandle,
    KimchiPremiumSnapshot,
    MarketSnapshot,
    NewsItem,
    OnchainSnapshot,
    PriceCandle,
    SignalEvent,
    SourceHealth,
    SupplySnapshot,
)
from app.services.intelligence import attach_moving_averages, calculate_supply_delta, score_abs_change, score_kimchi_premium, score_news_impact


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


def asset_overview(session: Session, symbol: str, window: str = "30d") -> dict | None:
    asset = session.scalar(select(Asset).where(Asset.symbol == symbol.upper(), Asset.is_active.is_(True)))
    if not asset:
        return None
    window_label, since = _window_scope(window)
    snapshots_query = select(MarketSnapshot).where(MarketSnapshot.asset_id == asset.id).order_by(desc(MarketSnapshot.observed_at)).limit(240)
    if since is not None:
        snapshots_query = snapshots_query.where(MarketSnapshot.observed_at >= since)
    snapshots = session.scalars(snapshots_query).all()
    if not snapshots:
        snapshots = session.scalars(
            select(MarketSnapshot).where(MarketSnapshot.asset_id == asset.id).order_by(desc(MarketSnapshot.observed_at)).limit(80)
        ).all()
    ordered_snapshots = list(reversed(snapshots))
    signals_query = (
        select(SignalEvent)
        .where(SignalEvent.asset_id == asset.id)
        .order_by(desc(SignalEvent.occurred_at))
        .limit(80)
    )
    if since is not None:
        signals_query = signals_query.where(SignalEvent.occurred_at >= since)
    signals = session.scalars(signals_query).all()
    if not signals:
        signals = session.scalars(
            select(SignalEvent).where(SignalEvent.asset_id == asset.id).order_by(desc(SignalEvent.occurred_at)).limit(40)
        ).all()
    interpretation = _latest_interpretation(session, asset.id)
    onchain_series = _onchain_series(session, asset.id, since)
    supply_series = _supply_series(session, asset.id, since)
    related_news = _related_news(session, asset.symbol, since)
    news_impacts = _news_impacts(asset.symbol, related_news, signals, since)
    kimchi_premium_series = _kimchi_premium_series(session, asset.id, since)
    kimchi_premium_latest = _kimchi_premium_latest(kimchi_premium_series)
    factor_impacts = _factor_impacts(ordered_snapshots, signals, onchain_series, supply_series, news_impacts, kimchi_premium_latest)
    return {
        "asset": {"symbol": asset.symbol, "name": asset.name, "group": asset.group, "rank": asset.rank},
        "window": window_label,
        "snapshots": [snapshot_to_dict(item) for item in ordered_snapshots],
        "market_snapshots": [snapshot_to_dict(item) for item in ordered_snapshots],
        "price_candles": _price_candles(session, asset.id, since, ordered_snapshots),
        "exchange_candles": _exchange_candle_series(session, asset.id, since),
        "kimchi_premium_series": kimchi_premium_series,
        "kimchi_premium_latest": kimchi_premium_latest,
        "onchain_series": onchain_series,
        "supply_series": supply_series,
        "news_impacts": news_impacts,
        "factor_impacts": factor_impacts,
        "timeline_events": _timeline_events(signals, news_impacts),
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


def _window_scope(window: str) -> tuple[str, datetime | None]:
    normalized = window.lower()
    if normalized == "max":
        return "max", None
    if normalized in ("365d", "1y"):
        days = 365
    elif normalized == "90d":
        days = 90
    elif normalized == "7d":
        days = 7
    else:
        days = 30
    return f"{days}d", datetime.now(timezone.utc) - timedelta(days=days)


def _price_candles(session: Session, asset_id: int, since: datetime | None, snapshots: list[MarketSnapshot]) -> list[dict]:
    query = (
        select(PriceCandle)
        .where(PriceCandle.asset_id == asset_id, PriceCandle.timeframe == "1d")
        .order_by(asc(PriceCandle.opened_at))
    )
    if since is not None:
        query = query.where(PriceCandle.opened_at >= since)
    rows = session.scalars(query).all()
    if rows:
        candles = [
            {
                "opened_at": row.opened_at,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume_usd": row.volume_usd,
                "source": row.source,
            }
            for row in rows
        ]
    else:
        candles = _candles_from_market_snapshots(snapshots)
    return [_candle_to_dict(row) for row in attach_moving_averages(candles)]


def _exchange_candle_series(session: Session, asset_id: int, since: datetime | None) -> list[dict]:
    query = (
        select(ExchangeCandle)
        .where(ExchangeCandle.asset_id == asset_id, ExchangeCandle.timeframe == "1d")
        .order_by(asc(ExchangeCandle.opened_at))
    )
    if since is not None:
        query = query.where(ExchangeCandle.opened_at >= since)
    rows = session.scalars(query).all()
    grouped: dict[tuple[str, str], list[ExchangeCandle]] = {}
    for row in rows:
        grouped.setdefault((row.exchange, row.market), []).append(row)

    series = []
    for (exchange, market), candles in sorted(grouped.items()):
        quote_currency = candles[-1].quote_currency if candles else "UNKNOWN"
        normalized = [
            {
                "opened_at": row.opened_at,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume_base": row.volume_base,
                "volume_quote": row.volume_quote,
                "quote_currency": row.quote_currency,
                "exchange": row.exchange,
                "market": row.market,
                "source": row.source,
            }
            for row in candles
        ]
        series.append(
            {
                "exchange": exchange,
                "market": market,
                "quote_currency": quote_currency,
                "timeframe": "1d",
                "candles": [_exchange_candle_to_dict(row) for row in attach_moving_averages(normalized)],
            }
        )
    return series


def _kimchi_premium_series(session: Session, asset_id: int, since: datetime | None) -> list[dict]:
    query = select(KimchiPremiumSnapshot).where(KimchiPremiumSnapshot.asset_id == asset_id).order_by(asc(KimchiPremiumSnapshot.observed_at))
    if since is not None:
        query = query.where(KimchiPremiumSnapshot.observed_at >= since)
    rows = session.scalars(query).all()
    return [_kimchi_snapshot_to_dict(row) for row in rows]


def _kimchi_premium_latest(points: list[dict]) -> dict | None:
    if not points:
        return None
    latest_at = max(point["observed_at"] for point in points)
    latest_points = [point for point in points if point["observed_at"] == latest_at and point["premium_pct"] is not None]
    if not latest_points:
        return None
    average = sum(point["premium_pct"] for point in latest_points) / len(latest_points)
    max_abs = max(latest_points, key=lambda point: abs(point["premium_pct"]))
    score = score_kimchi_premium(average)
    return {
        "observed_at": latest_at,
        "average_premium_pct": average,
        "max_abs_premium_pct": max_abs["premium_pct"],
        "score": score,
        "direction": _direction(average),
        "summary": _kimchi_summary(average),
        "exchanges": latest_points,
    }


def _candles_from_market_snapshots(snapshots: list[MarketSnapshot]) -> list[dict]:
    candles = []
    previous_close = None
    for row in snapshots:
        if row.price_usd is None:
            continue
        open_price = previous_close if previous_close is not None else row.price_usd
        high = max(open_price, row.price_usd)
        low = min(open_price, row.price_usd)
        candles.append(
            {
                "opened_at": row.observed_at,
                "open": open_price,
                "high": high,
                "low": low,
                "close": row.price_usd,
                "volume_usd": row.volume_24h_usd,
                "source": f"{row.source}_snapshot_proxy",
            }
        )
        previous_close = row.price_usd
    return candles


def _onchain_series(session: Session, asset_id: int, since: datetime | None) -> list[dict]:
    query = select(OnchainSnapshot).where(OnchainSnapshot.asset_id == asset_id).order_by(asc(OnchainSnapshot.observed_at))
    if since is not None:
        query = query.where(OnchainSnapshot.observed_at >= since)
    rows = session.scalars(query).all()
    points = []
    previous = None
    for row in rows:
        changes = [
            _pct_change(row.active_addresses, previous.active_addresses if previous else None),
            _pct_change(row.transaction_count, previous.transaction_count if previous else None),
            _pct_change(row.fees_usd, previous.fees_usd if previous else None),
            _pct_change(row.exchange_netflow_usd, previous.exchange_netflow_usd if previous else None),
        ]
        points.append(
            {
                "observed_at": row.observed_at.isoformat(),
                "active_addresses": row.active_addresses,
                "transaction_count": row.transaction_count,
                "fees_usd": row.fees_usd,
                "exchange_netflow_usd": row.exchange_netflow_usd,
                "availability": row.availability,
                "source": row.source,
                "impact_score": max(score_abs_change(change, medium=15, high=35) for change in changes),
            }
        )
        previous = row
    return points


def _supply_series(session: Session, asset_id: int, since: datetime | None) -> list[dict]:
    query = select(SupplySnapshot).where(SupplySnapshot.asset_id == asset_id).order_by(asc(SupplySnapshot.observed_at))
    if since is not None:
        query = query.where(SupplySnapshot.observed_at >= since)
    rows = session.scalars(query).all()
    points = []
    previous: dict | None = None
    for row in rows:
        current = {
            "circulating_supply": row.circulating_supply,
            "total_supply": row.total_supply,
            "burn_amount": row.burn_amount,
            "mint_amount": row.mint_amount,
        }
        delta = calculate_supply_delta(current, previous)
        points.append(
            {
                "observed_at": row.observed_at.isoformat(),
                "circulating_supply": row.circulating_supply,
                "total_supply": row.total_supply,
                "burn_amount": row.burn_amount,
                "mint_amount": row.mint_amount,
                "net_change": delta["net_change"],
                "net_change_pct": delta["net_change_pct"],
                "method": delta["method"],
                "availability": row.availability,
                "source": row.source,
                "impact_score": score_abs_change(delta["net_change_pct"], medium=0.5, high=1.5),
            }
        )
        previous = current
    return points


def _related_news(session: Session, symbol: str, since: datetime | None) -> list[NewsItem]:
    rows = session.scalars(select(NewsItem).order_by(desc(NewsItem.published_at)).limit(240)).all()
    related = []
    for item in rows:
        observed_at = _as_utc(item.published_at or item.created_at)
        if since is not None and observed_at and observed_at < since:
            continue
        if symbol in (item.related_symbols or []):
            related.append(item)
    return related


def _news_impacts(symbol: str, news_items: list[NewsItem], signals: list[SignalEvent], since: datetime | None) -> list[dict]:
    buckets: dict[datetime, list[NewsItem]] = {}
    for item in news_items:
        observed_at = _as_utc(item.published_at or item.created_at)
        if not observed_at:
            continue
        bucket = observed_at.replace(hour=0, minute=0, second=0, microsecond=0)
        buckets.setdefault(bucket, []).append(item)

    price_signals = [signal for signal in signals if signal.signal_type == "price_move"]
    points = []
    for observed_at, items in sorted(buckets.items()):
        nearest_signal = _nearest_signal(observed_at, price_signals)
        proximity_hours = None
        severity = None
        if nearest_signal:
            proximity_hours = abs((_as_utc(nearest_signal.occurred_at) - observed_at).total_seconds()) / 3600
            severity = nearest_signal.severity
        source_count = len({item.source for item in items})
        points.append(
            {
                "observed_at": observed_at.isoformat(),
                "score": score_news_impact(len(items), severity, proximity_hours, source_count),
                "item_count": len(items),
                "source_count": source_count,
                "summary": f"{symbol} 관련 뉴스 {len(items)}건이 가격 변동의 원인 후보로 묶였습니다.",
                "items": [_news_item_to_dict(item) for item in items[:8]],
            }
        )
    return points


def _factor_impacts(
    snapshots: list[MarketSnapshot],
    signals: list[SignalEvent],
    onchain_series: list[dict],
    supply_series: list[dict],
    news_impacts: list[dict],
    kimchi_premium_latest: dict | None,
) -> list[dict]:
    latest_snapshot = snapshots[-1] if snapshots else None
    market_signals = [signal for signal in signals if signal.signal_type in ("price_move", "volume_change")]
    market_score = max([_signal_score(signal.severity) for signal in market_signals] or [score_abs_change(latest_snapshot.price_change_24h_pct if latest_snapshot else None, 3, 6)])
    latest_onchain = onchain_series[-1] if onchain_series else None
    latest_supply = supply_series[-1] if supply_series else None
    latest_news = news_impacts[-1] if news_impacts else None
    kimchi_score = kimchi_premium_latest["score"] if kimchi_premium_latest else 0
    return [
        {
            "factor": "market",
            "label": "가격/거래량",
            "score": market_score,
            "direction": _direction(latest_snapshot.price_change_24h_pct if latest_snapshot else None),
            "summary": _latest_signal_summary(market_signals) or "가격과 거래량 변화가 아직 뚜렷한 신호로 묶이지 않았습니다.",
            "availability": "complete" if latest_snapshot else "unavailable",
            "confidence": _score_confidence(market_score),
        },
        {
            "factor": "onchain",
            "label": "온체인",
            "score": latest_onchain["impact_score"] if latest_onchain else 0,
            "direction": "neutral",
            "summary": "활성 주소, 거래 수, 수수료, 거래소 순유입 변화가 동반 신호 후보로 계산됩니다.",
            "availability": latest_onchain["availability"] if latest_onchain else "unavailable",
            "confidence": _score_confidence(latest_onchain["impact_score"] if latest_onchain else 0),
        },
        {
            "factor": "supply",
            "label": "순공급",
            "score": latest_supply["impact_score"] if latest_supply else 0,
            "direction": _direction(latest_supply["net_change"] if latest_supply else None),
            "summary": _supply_summary(latest_supply),
            "availability": latest_supply["availability"] if latest_supply else "unavailable",
            "confidence": _score_confidence(latest_supply["impact_score"] if latest_supply else 0),
        },
        {
            "factor": "news",
            "label": "뉴스",
            "score": latest_news["score"] if latest_news else 0,
            "direction": "neutral",
            "summary": latest_news["summary"] if latest_news else "최근 창에서 관련 뉴스 집중 신호가 낮습니다.",
            "availability": "complete" if latest_news else "partial",
            "confidence": _score_confidence(latest_news["score"] if latest_news else 0),
        },
        {
            "factor": "kimchi_premium",
            "label": "김치프리미엄",
            "score": kimchi_score,
            "direction": kimchi_premium_latest["direction"] if kimchi_premium_latest else "neutral",
            "summary": kimchi_premium_latest["summary"] if kimchi_premium_latest else "국내 KRW 거래소와 Binance USDT 기준 가격차 데이터가 아직 없습니다.",
            "availability": "partial" if kimchi_premium_latest else "unavailable",
            "confidence": _score_confidence(kimchi_score),
        },
    ]


def _timeline_events(signals: list[SignalEvent], news_impacts: list[dict]) -> list[dict]:
    events = [
        {
            "id": signal.id,
            "occurred_at": signal.occurred_at.isoformat(),
            "event_type": signal.signal_type,
            "severity": signal.severity,
            "title": signal.title,
            "description": signal.description,
            "score": _signal_score(signal.severity),
            "source": signal.source,
            "links": _evidence_links(signal.evidence),
        }
        for signal in signals
    ]
    events.extend(
        {
            "id": f"news-{item['observed_at']}",
            "occurred_at": item["observed_at"],
            "event_type": "news_candidate",
            "severity": _score_confidence(item["score"]),
            "title": f"뉴스 영향 후보 {item['score']}/100",
            "description": item["summary"],
            "score": item["score"],
            "source": "news_items",
            "links": [{"title": news["title"], "url": news["url"]} for news in item["items"] if news.get("url")],
        }
        for item in news_impacts
    )
    return sorted(events, key=lambda item: item["occurred_at"], reverse=True)[:80]


def _candle_to_dict(row: dict) -> dict:
    return {
        "opened_at": row["opened_at"].isoformat(),
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "close": row.get("close"),
        "volume_usd": row.get("volume_usd"),
        "ma7": row.get("ma7"),
        "ma20": row.get("ma20"),
        "source": row.get("source"),
    }


def _exchange_candle_to_dict(row: dict) -> dict:
    return {
        "opened_at": row["opened_at"].isoformat(),
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "close": row.get("close"),
        "volume_base": row.get("volume_base"),
        "volume_quote": row.get("volume_quote"),
        "quote_currency": row.get("quote_currency"),
        "exchange": row.get("exchange"),
        "market": row.get("market"),
        "ma7": row.get("ma7"),
        "ma20": row.get("ma20"),
        "source": row.get("source"),
    }


def _kimchi_snapshot_to_dict(row: KimchiPremiumSnapshot) -> dict:
    premium = row.premium_pct
    return {
        "observed_at": row.observed_at.isoformat(),
        "global_exchange": row.global_exchange,
        "global_market": row.global_market,
        "korean_exchange": row.korean_exchange,
        "korean_market": row.korean_market,
        "global_price_usd": row.global_price_usd,
        "korean_price_krw": row.korean_price_krw,
        "usd_krw": row.usd_krw,
        "korean_price_usd": row.korean_price_usd,
        "premium_pct": premium,
        "score": score_kimchi_premium(premium),
        "direction": _direction(premium),
        "source": row.source,
    }


def _news_item_to_dict(item: NewsItem) -> dict:
    return {
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }


def _nearest_signal(observed_at: datetime, signals: list[SignalEvent]) -> SignalEvent | None:
    if not signals:
        return None
    return min(signals, key=lambda signal: abs((_as_utc(signal.occurred_at) - observed_at).total_seconds()))


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / previous) * 100


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _signal_score(severity: str) -> int:
    if severity == "high":
        return 90
    if severity == "medium":
        return 60
    return 30


def _score_confidence(score: int | float) -> str:
    if score >= 75:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _direction(value: float | None) -> str:
    if value is None or value == 0:
        return "neutral"
    return "up" if value > 0 else "down"


def _latest_signal_summary(signals: list[SignalEvent]) -> str | None:
    if not signals:
        return None
    return signals[0].description


def _supply_summary(latest_supply: dict | None) -> str:
    if not latest_supply:
        return "순공급 데이터가 아직 없습니다."
    if latest_supply["method"] == "direct":
        return "발행량과 소각량의 순변화가 직접 계산되었습니다."
    if latest_supply["method"] == "circulating_proxy":
        return "직접 발행/소각 데이터가 없어 유통 공급량 변화로 순공급 후보를 계산했습니다."
    return "순공급 변화 계산에 필요한 데이터가 부족합니다."


def _kimchi_summary(premium_pct: float | None) -> str:
    if premium_pct is None:
        return "김치프리미엄 계산에 필요한 가격 또는 환율 데이터가 부족합니다."
    if premium_pct >= 5:
        return "국내 KRW 가격이 글로벌 기준보다 크게 높아 시장 과열/수요 집중의 동반 신호 후보입니다."
    if premium_pct >= 1:
        return "국내 KRW 가격이 글로벌 기준보다 높아 위험선호 또는 국내 수요 우위의 참고 신호입니다."
    if premium_pct <= -5:
        return "국내 KRW 가격이 글로벌 기준보다 크게 낮아 위험회피 또는 국내 매수세 약화의 동반 신호 후보입니다."
    if premium_pct <= -1:
        return "국내 KRW 가격이 글로벌 기준보다 낮아 국내 수요 약화 가능성을 참고할 수 있습니다."
    return "국내와 글로벌 가격차가 크지 않아 김치프리미엄 신호는 중립에 가깝습니다."


def _evidence_links(evidence: dict) -> list[dict]:
    items = evidence.get("items")
    if not isinstance(items, list):
        return []
    links = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        if isinstance(title, str) and isinstance(url, str):
            links.append({"title": title, "url": url})
    return links
