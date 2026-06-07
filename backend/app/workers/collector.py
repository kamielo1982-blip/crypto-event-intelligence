from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.collectors.binance import demo_klines as demo_binance_klines
from app.collectors.binance import fetch_klines as fetch_binance_klines
from app.collectors.binance import fetch_ticker_price as fetch_binance_ticker_price
from app.collectors.binance import normalize_klines as normalize_binance_klines
from app.collectors.binance import normalize_ticker_price as normalize_binance_ticker_price
from app.collectors.bithumb import demo_candlesticks as demo_bithumb_candlesticks
from app.collectors.bithumb import fetch_candlesticks as fetch_bithumb_candlesticks
from app.collectors.bithumb import fetch_ticker as fetch_bithumb_ticker
from app.collectors.bithumb import normalize_candlesticks as normalize_bithumb_candlesticks
from app.collectors.bithumb import normalize_ticker as normalize_bithumb_ticker
from app.collectors.coingecko import (
    demo_market_chart_payload,
    demo_market_payload,
    demo_ohlc_payload,
    fetch_coin_market_chart,
    fetch_coin_markets,
    fetch_coin_ohlc,
)
from app.collectors.fx import fetch_usd_rates, normalize_open_er_rate
from app.collectors.news_rss import demo_news_payload, fetch_rss_news
from app.collectors.onchain_stub import demo_onchain_payload
from app.collectors.upbit import demo_day_candles as demo_upbit_day_candles
from app.collectors.upbit import fetch_day_candle_history as fetch_upbit_day_candle_history
from app.collectors.upbit import fetch_ticker as fetch_upbit_ticker
from app.collectors.upbit import normalize_day_candles as normalize_upbit_day_candles
from app.collectors.upbit import normalize_ticker as normalize_upbit_ticker
from app.config import Settings
from app.models import (
    AIInterpretation,
    Asset,
    CollectionRun,
    ExchangeCandle,
    ExchangeTickerSnapshot,
    FxRateSnapshot,
    KimchiPremiumSnapshot,
    LiveKimchiPremiumSnapshot,
    MarketSnapshot,
    NewsItem,
    OnchainSnapshot,
    PriceCandle,
    SignalEvent,
    SourceHealth,
    SupplySnapshot,
    utcnow,
)
from app.seed import seed_defaults
from app.services.ai_interpreter import LocalHeuristicInterpreter
from app.services.intelligence import calculate_kimchi_premium, calculate_live_kimchi_premium, normalize_market_chart_payload, normalize_ohlc_payload
from app.services.news import dedupe_news_items
from app.services.signal_engine import build_market_signals, build_news_signals, build_onchain_signals, build_supply_signals


def run_collection_once(session: Session, settings: Settings, trigger: str = "manual") -> CollectionRun:
    seed_defaults(session, settings)
    run = CollectionRun(status="running", trigger=trigger)
    session.add(run)
    session.commit()

    assets = session.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.group, Asset.rank)).all()
    summary = {
        "market": "pending",
        "news": "pending",
        "onchain": "pending",
        "exchange_candles": "pending",
        "kimchi_premium": "pending",
        "exchange_tickers": "pending",
        "fx_rate": "pending",
        "live_kimchi_premium": "pending",
    }
    try:
        market_payload, market_source, market_latency = _collect_market_data(assets, settings)
        _store_market_snapshots(session, run, assets, market_payload, market_source)
        _record_source_health(session, "coingecko_market", True, market_latency, f"{len(market_payload)} assets")
        summary["market"] = market_source
    except Exception as exc:
        _record_source_health(session, "coingecko_market", False, None, str(exc))
        summary["market"] = "failed"

    try:
        candle_count, candle_source, candle_latency = _collect_price_candles(session, run, assets, settings)
        _record_source_health(session, "coingecko_price_candles", True, candle_latency, f"{candle_count} candles")
        summary["price_candles"] = candle_source
    except Exception as exc:
        _record_source_health(session, "coingecko_price_candles", False, None, str(exc))
        summary["price_candles"] = "failed"

    try:
        exchange_counts, exchange_source, exchange_latency = _collect_exchange_candles(session, run, assets, settings)
        _record_source_health(session, "binance_candles", True, exchange_latency, f"{exchange_counts.get('binance', 0)} candles")
        _record_source_health(session, "upbit_candles", True, exchange_latency, f"{exchange_counts.get('upbit', 0)} candles")
        _record_source_health(session, "bithumb_candles", True, exchange_latency, f"{exchange_counts.get('bithumb', 0)} candles")
        _record_source_health(session, "kimchi_premium", True, exchange_latency, f"{exchange_counts.get('kimchi_premium', 0)} snapshots")
        summary["exchange_candles"] = exchange_source
        summary["kimchi_premium"] = "exchange_candles"
    except Exception as exc:
        _record_source_health(session, "exchange_candles", False, None, str(exc))
        summary["exchange_candles"] = "failed"
        summary["kimchi_premium"] = "failed"

    try:
        live_counts, live_source, live_latency = _collect_live_tickers_and_kimchi(session, run, assets, settings)
        _record_source_health(session, "binance_tickers", live_counts.get("binance", 0) > 0, live_latency, f"{live_counts.get('binance', 0)} tickers")
        _record_source_health(session, "upbit_tickers", live_counts.get("upbit", 0) > 0, live_latency, f"{live_counts.get('upbit', 0)} tickers")
        _record_source_health(session, "bithumb_tickers", live_counts.get("bithumb", 0) > 0, live_latency, f"{live_counts.get('bithumb', 0)} tickers")
        _record_source_health(session, "fx_rate_usd_krw", live_counts.get("fx_rate", 0) > 0, live_latency, f"{live_counts.get('fx_rate', 0)} rates")
        _record_source_health(
            session,
            "live_kimchi_premium",
            live_counts.get("live_kimchi_premium", 0) > 0,
            live_latency,
            f"{live_counts.get('live_kimchi_premium', 0)} snapshots, {live_counts.get('unavailable', 0)} unavailable",
        )
        summary["exchange_tickers"] = live_source
        summary["fx_rate"] = "open_er_api" if live_counts.get("fx_rate", 0) else "unavailable"
        summary["live_kimchi_premium"] = "live_ticker" if live_counts.get("live_kimchi_premium", 0) else "unavailable"
    except Exception as exc:
        _record_source_health(session, "live_kimchi_premium", False, None, str(exc))
        summary["exchange_tickers"] = "failed"
        summary["fx_rate"] = "failed"
        summary["live_kimchi_premium"] = "failed"

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

    run.status = "success" if not any(value in ("failed", "unavailable") for value in summary.values()) else "partial"
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
        payload, latency = fetch_coin_markets(
            ids,
            api_base_url=settings.coingecko_api_base_url,
            api_key=settings.coingecko_api_key,
            api_key_header=settings.coingecko_api_key_header,
        )
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


def _collect_price_candles(session: Session, run: CollectionRun, assets: list[Asset], settings: Settings) -> tuple[int, str, float]:
    started = time.perf_counter()
    created_or_updated = 0
    sources: set[str] = set()
    history_days = _history_days(settings.coingecko_history_days)
    for asset in assets:
        if asset.group != "investable" or not asset.coingecko_id:
            continue
        try:
            chart_payload, _ = fetch_coin_market_chart(
                asset.coingecko_id,
                days=history_days,
                interval="daily",
                api_base_url=settings.coingecko_api_base_url,
                api_key=settings.coingecko_api_key,
                api_key_header=settings.coingecko_api_key_header,
            )
            ohlc_payload = []
            if isinstance(history_days, int) and history_days <= 90:
                ohlc_payload, _ = fetch_coin_ohlc(
                    asset.coingecko_id,
                    days=history_days,
                    api_base_url=settings.coingecko_api_base_url,
                    api_key=settings.coingecko_api_key,
                    api_key_header=settings.coingecko_api_key_header,
                )
            source = "coingecko"
        except Exception:
            if not settings.enable_demo_data:
                raise
            demo_days = _demo_history_days(history_days)
            ohlc_payload = demo_ohlc_payload(asset.coingecko_id, days=demo_days if demo_days <= 90 else 90)
            chart_payload = demo_market_chart_payload(asset.coingecko_id, days=demo_days)
            source = "demo_fallback"

        volume_by_date = _volume_by_date(chart_payload)
        candles = normalize_ohlc_payload(ohlc_payload, source)
        market_chart_candles = normalize_market_chart_payload(chart_payload, source)
        if len(market_chart_candles) > len(candles):
            candles = market_chart_candles
        for candle in candles:
            candle["volume_usd"] = candle.get("volume_usd") or volume_by_date.get(candle["opened_at"].date())
            candle["raw_payload"] = {**(candle.get("raw_payload") or {}), "market_chart_volume": candle["volume_usd"]}
            _upsert_price_candle(session, run, asset, candle)
            created_or_updated += 1
        sources.add(source)
    session.commit()
    return created_or_updated, "+".join(sorted(sources)) if sources else "none", (time.perf_counter() - started) * 1000


def _collect_exchange_candles(session: Session, run: CollectionRun, assets: list[Asset], settings: Settings) -> tuple[dict[str, int], str, float]:
    started = time.perf_counter()
    history_days = _exchange_history_days(settings.exchange_candle_history_days)
    counts = {"binance": 0, "upbit": 0, "bithumb": 0, "kimchi_premium": 0}
    sources: set[str] = set()
    for asset in assets:
        if asset.group != "investable":
            continue

        binance_market = f"{asset.symbol}USDT"
        binance_rows = _load_binance_candles(binance_market, history_days, settings)
        counts["binance"] += _upsert_exchange_candles(session, run, asset, binance_rows)
        sources.update({row.get("source", "binance") for row in binance_rows})

        upbit_market = f"KRW-{asset.symbol}"
        upbit_rows = _load_upbit_candles(upbit_market, history_days, settings)
        counts["upbit"] += _upsert_exchange_candles(session, run, asset, upbit_rows)
        sources.update({row.get("source", "upbit") for row in upbit_rows})

        bithumb_market = f"{asset.symbol}_KRW"
        bithumb_rows = _load_bithumb_candles(bithumb_market, history_days, settings)
        counts["bithumb"] += _upsert_exchange_candles(session, run, asset, bithumb_rows)
        sources.update({row.get("source", "bithumb") for row in bithumb_rows})

        counts["kimchi_premium"] += _upsert_kimchi_history(session, run, asset, binance_rows, upbit_rows, settings.usd_krw_rate)
        counts["kimchi_premium"] += _upsert_kimchi_history(session, run, asset, binance_rows, bithumb_rows, settings.usd_krw_rate)

    session.commit()
    return counts, "+".join(sorted(sources)) if sources else "none", (time.perf_counter() - started) * 1000


def _collect_live_tickers_and_kimchi(session: Session, run: CollectionRun, assets: list[Asset], settings: Settings) -> tuple[dict[str, int], str, float]:
    started = time.perf_counter()
    counts = {"binance": 0, "upbit": 0, "bithumb": 0, "fx_rate": 0, "usdt_reference": 0, "live_kimchi_premium": 0, "unavailable": 0}
    sources: set[str] = set()

    fx_rate = _load_usd_krw_rate(settings)
    if fx_rate:
        _upsert_fx_rate_snapshot(session, run, fx_rate)
        counts["fx_rate"] += 1
        sources.add(fx_rate.get("source", "open_er_api"))

    usdt_asset = next((asset for asset in assets if asset.symbol == "USDT"), None)
    usdt_references = []
    for ticker in (_load_upbit_ticker("KRW-USDT", settings), _load_bithumb_ticker("USDT_KRW", settings)):
        if not ticker:
            continue
        _upsert_exchange_ticker(session, run, usdt_asset, ticker)
        counts[ticker["exchange"]] += 1
        counts["usdt_reference"] += 1
        sources.add(ticker.get("source", ticker["exchange"]))
        usdt_references.append(ticker)

    for asset in assets:
        if asset.group != "investable":
            continue

        binance_ticker = _load_binance_ticker(f"{asset.symbol}USDT", settings)
        if binance_ticker:
            _upsert_exchange_ticker(session, run, asset, binance_ticker)
            counts["binance"] += 1
            sources.add(binance_ticker.get("source", "binance"))

        korean_tickers = [
            _load_upbit_ticker(f"KRW-{asset.symbol}", settings),
            _load_bithumb_ticker(f"{asset.symbol}_KRW", settings),
        ]
        for ticker in [item for item in korean_tickers if item]:
            _upsert_exchange_ticker(session, run, asset, ticker)
            counts[ticker["exchange"]] += 1
            sources.add(ticker.get("source", ticker["exchange"]))
            availability = _upsert_live_kimchi_snapshot(session, run, asset, binance_ticker, ticker, fx_rate, usdt_references, settings)
            counts["live_kimchi_premium"] += 1
            if availability == "unavailable":
                counts["unavailable"] += 1

    session.commit()
    return counts, "+".join(sorted(sources)) if sources else "none", (time.perf_counter() - started) * 1000


def _load_binance_candles(market: str, history_days: int, settings: Settings) -> list[dict]:
    try:
        payload, _ = fetch_binance_klines(
            market,
            interval="1d",
            limit=history_days,
            api_base_url=settings.binance_api_base_url,
        )
        return normalize_binance_klines(payload, market, source="binance")
    except Exception:
        if not settings.enable_demo_data:
            raise
        return normalize_binance_klines(demo_binance_klines(market, history_days), market, source="demo_fallback")


def _load_upbit_candles(market: str, history_days: int, settings: Settings) -> list[dict]:
    try:
        payload, _ = fetch_upbit_day_candle_history(
            market,
            days=history_days,
            api_base_url=settings.upbit_api_base_url,
        )
        return normalize_upbit_day_candles(payload, market, source="upbit")
    except Exception:
        if not settings.enable_demo_data:
            raise
        payload = demo_upbit_day_candles(market, history_days, usd_krw=settings.usd_krw_rate)
        return normalize_upbit_day_candles(payload, market, source="demo_fallback")


def _load_bithumb_candles(market: str, history_days: int, settings: Settings) -> list[dict]:
    order_currency, payment_currency = market.split("_", 1)
    try:
        payload, _ = fetch_bithumb_candlesticks(
            order_currency,
            payment_currency=payment_currency,
            chart_interval="24h",
            api_base_url=settings.bithumb_api_base_url,
        )
        return normalize_bithumb_candlesticks(payload, market, source="bithumb", limit=history_days)
    except Exception:
        if not settings.enable_demo_data:
            raise
        payload = demo_bithumb_candlesticks(market, history_days, usd_krw=settings.usd_krw_rate)
        return normalize_bithumb_candlesticks(payload, market, source="demo_fallback", limit=history_days)


def _load_binance_ticker(market: str, settings: Settings) -> dict | None:
    try:
        payload, _ = fetch_binance_ticker_price(market, api_base_url=settings.binance_api_base_url)
        ticker = normalize_binance_ticker_price(payload, market, source="binance")
        return ticker if ticker.get("price") is not None else None
    except Exception:
        return None


def _load_upbit_ticker(market: str, settings: Settings) -> dict | None:
    try:
        payload, _ = fetch_upbit_ticker(market, api_base_url=settings.upbit_api_base_url)
        ticker = normalize_upbit_ticker(payload, market, source="upbit")
        return ticker if ticker.get("price") is not None else None
    except Exception:
        return None


def _load_bithumb_ticker(market: str, settings: Settings) -> dict | None:
    order_currency, payment_currency = market.split("_", 1)
    try:
        payload, _ = fetch_bithumb_ticker(order_currency, payment_currency=payment_currency, api_base_url=settings.bithumb_api_base_url)
        ticker = normalize_bithumb_ticker(payload, market, source="bithumb")
        return ticker if ticker.get("price") is not None else None
    except Exception:
        return None


def _load_usd_krw_rate(settings: Settings) -> dict | None:
    try:
        payload, _ = fetch_usd_rates(api_base_url=settings.fx_api_base_url)
        rate = normalize_open_er_rate(payload, quote_currency="KRW", source="open_er_api")
        return rate if rate.get("rate") is not None else None
    except Exception:
        return None


def _upsert_exchange_candles(session: Session, run: CollectionRun, asset: Asset, candles: list[dict]) -> int:
    count = 0
    for candle in candles:
        _upsert_exchange_candle(session, run, asset, candle)
        count += 1
    return count


def _upsert_exchange_candle(session: Session, run: CollectionRun, asset: Asset, candle: dict) -> None:
    existing = session.scalar(
        select(ExchangeCandle).where(
            ExchangeCandle.exchange == candle["exchange"],
            ExchangeCandle.market == candle["market"],
            ExchangeCandle.timeframe == candle.get("timeframe", "1d"),
            ExchangeCandle.opened_at == candle["opened_at"],
        )
    )
    if not existing:
        session.add(
            ExchangeCandle(
                asset_id=asset.id,
                collection_run_id=run.id,
                exchange=candle["exchange"],
                market=candle["market"],
                quote_currency=candle["quote_currency"],
                timeframe=candle.get("timeframe", "1d"),
                opened_at=candle["opened_at"],
                open=candle.get("open"),
                high=candle.get("high"),
                low=candle.get("low"),
                close=candle.get("close"),
                volume_base=candle.get("volume_base"),
                volume_quote=candle.get("volume_quote"),
                source=candle.get("source") or "unknown",
                raw_payload=candle.get("raw_payload"),
            )
        )
        return

    existing.asset_id = asset.id
    existing.collection_run_id = run.id
    existing.quote_currency = candle["quote_currency"]
    existing.open = candle.get("open")
    existing.high = candle.get("high")
    existing.low = candle.get("low")
    existing.close = candle.get("close")
    existing.volume_base = candle.get("volume_base")
    existing.volume_quote = candle.get("volume_quote")
    existing.source = candle.get("source") or existing.source
    existing.raw_payload = candle.get("raw_payload")


def _upsert_exchange_ticker(session: Session, run: CollectionRun, asset: Asset | None, ticker: dict) -> None:
    existing = session.scalar(
        select(ExchangeTickerSnapshot).where(
            ExchangeTickerSnapshot.collection_run_id == run.id,
            ExchangeTickerSnapshot.exchange == ticker["exchange"],
            ExchangeTickerSnapshot.market == ticker["market"],
        )
    )
    payload = {
        "asset_id": asset.id if asset else None,
        "collection_run_id": run.id,
        "exchange": ticker["exchange"],
        "market": ticker["market"],
        "base_currency": ticker["base_currency"],
        "quote_currency": ticker["quote_currency"],
        "price": ticker.get("price"),
        "observed_at": ticker.get("observed_at") or utcnow(),
        "source": ticker.get("source") or "unknown",
        "raw_payload": ticker.get("raw_payload"),
    }
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        return
    session.add(ExchangeTickerSnapshot(**payload))


def _upsert_fx_rate_snapshot(session: Session, run: CollectionRun, rate: dict) -> None:
    existing = session.scalar(
        select(FxRateSnapshot).where(
            FxRateSnapshot.collection_run_id == run.id,
            FxRateSnapshot.base_currency == rate["base_currency"],
            FxRateSnapshot.quote_currency == rate["quote_currency"],
            FxRateSnapshot.source == rate["source"],
        )
    )
    payload = {
        "collection_run_id": run.id,
        "base_currency": rate["base_currency"],
        "quote_currency": rate["quote_currency"],
        "rate": rate.get("rate"),
        "observed_at": rate.get("observed_at") or utcnow(),
        "source_updated_at": rate.get("source_updated_at"),
        "source": rate.get("source") or "unknown",
        "raw_payload": rate.get("raw_payload"),
    }
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        return
    session.add(FxRateSnapshot(**payload))


def _upsert_live_kimchi_snapshot(
    session: Session,
    run: CollectionRun,
    asset: Asset,
    global_ticker: dict | None,
    korean_ticker: dict,
    fx_rate: dict | None,
    usdt_references: list[dict],
    settings: Settings,
) -> str:
    now = utcnow()
    observed_at = _as_utc(run.started_at) or now
    usdt_krw_reference = _average_ticker_price(usdt_references)
    global_price = global_ticker.get("price") if global_ticker else None
    korean_price = korean_ticker.get("price")
    usd_krw = fx_rate.get("rate") if fx_rate else None
    premium = calculate_live_kimchi_premium(global_price, korean_price, usd_krw, usdt_krw_reference)
    data_age_seconds = _max_data_age_seconds(
        now,
        [
            global_ticker.get("observed_at") if global_ticker else None,
            korean_ticker.get("observed_at"),
            fx_rate.get("observed_at") if fx_rate else None,
        ],
    )
    availability = _live_kimchi_availability(global_price, korean_price, usd_krw, data_age_seconds, settings.live_data_stale_after_seconds)
    existing = session.scalar(
        select(LiveKimchiPremiumSnapshot).where(
            LiveKimchiPremiumSnapshot.collection_run_id == run.id,
            LiveKimchiPremiumSnapshot.asset_id == asset.id,
            LiveKimchiPremiumSnapshot.korean_exchange == korean_ticker["exchange"],
        )
    )
    payload = {
        "collection_run_id": run.id,
        "observed_at": observed_at,
        "global_exchange": global_ticker["exchange"] if global_ticker else "binance",
        "global_market": global_ticker["market"] if global_ticker else f"{asset.symbol}USDT",
        "korean_exchange": korean_ticker["exchange"],
        "korean_market": korean_ticker["market"],
        "global_price_usd": global_price,
        "korean_price_krw": korean_price,
        "usd_krw": usd_krw,
        "fx_source": fx_rate.get("source") if fx_rate else None,
        "usdt_krw_reference": usdt_krw_reference,
        "korean_price_usd": premium["korean_price_usd"],
        "premium_pct": premium["premium_pct"],
        "usdt_basis_premium_pct": premium["usdt_basis_premium_pct"],
        "basis": "usd_krw_live_fx",
        "data_age_seconds": data_age_seconds,
        "availability": availability,
        "source": "live_ticker",
        "raw_payload": {
            "method": "korean_live_ticker_krw_div_live_usd_krw_vs_binance_usdt_ticker",
            "global_source": global_ticker.get("source") if global_ticker else None,
            "korean_source": korean_ticker.get("source"),
            "fx_source": fx_rate.get("source") if fx_rate else None,
            "usdt_reference_sources": [
                {"exchange": item["exchange"], "market": item["market"], "price": item.get("price"), "observed_at": _isoformat(item.get("observed_at"))}
                for item in usdt_references
            ],
        },
    }
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
    else:
        session.add(LiveKimchiPremiumSnapshot(asset_id=asset.id, **payload))
    return availability


def _upsert_kimchi_history(
    session: Session,
    run: CollectionRun,
    asset: Asset,
    global_candles: list[dict],
    korean_candles: list[dict],
    usd_krw: float,
) -> int:
    global_by_date = {candle["opened_at"].date(): candle for candle in global_candles if candle.get("close") is not None}
    count = 0
    for korean in korean_candles:
        global_candle = global_by_date.get(korean["opened_at"].date())
        if not global_candle:
            continue
        premium = calculate_kimchi_premium(global_candle.get("close"), korean.get("close"), usd_krw)
        observed_at = korean["opened_at"]
        existing = session.scalar(
            select(KimchiPremiumSnapshot).where(
                KimchiPremiumSnapshot.asset_id == asset.id,
                KimchiPremiumSnapshot.observed_at == observed_at,
                KimchiPremiumSnapshot.korean_exchange == korean["exchange"],
            )
        )
        payload = {
            "global_exchange": global_candle["exchange"],
            "global_market": global_candle["market"],
            "korean_exchange": korean["exchange"],
            "korean_market": korean["market"],
            "global_price_usd": global_candle.get("close"),
            "korean_price_krw": korean.get("close"),
            "usd_krw": usd_krw,
            "korean_price_usd": premium["korean_price_usd"],
            "premium_pct": premium["premium_pct"],
            "source": "exchange_candles",
            "raw_payload": {
                "global_source": global_candle.get("source"),
                "korean_source": korean.get("source"),
                "method": "korean_krw_close_div_usd_krw_vs_binance_usdt_close",
            },
        }
        if existing:
            existing.collection_run_id = run.id
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            session.add(KimchiPremiumSnapshot(asset_id=asset.id, collection_run_id=run.id, observed_at=observed_at, **payload))
        count += 1
    return count


def _average_ticker_price(tickers: list[dict]) -> float | None:
    prices = [float(ticker["price"]) for ticker in tickers if ticker.get("price") is not None]
    if not prices:
        return None
    return sum(prices) / len(prices)


def _max_data_age_seconds(now: datetime, observed_values: list[datetime | None]) -> float | None:
    ages = []
    for value in observed_values:
        observed_at = _as_utc(value)
        if observed_at is None:
            continue
        ages.append(max(0.0, (now - observed_at).total_seconds()))
    if not ages:
        return None
    return max(ages)


def _live_kimchi_availability(
    global_price_usd: float | None,
    korean_price_krw: float | None,
    usd_krw: float | None,
    data_age_seconds: float | None,
    stale_after_seconds: int,
) -> str:
    if global_price_usd in (None, 0) or korean_price_krw in (None, 0) or usd_krw in (None, 0):
        return "unavailable"
    if data_age_seconds is not None and data_age_seconds > stale_after_seconds:
        return "stale"
    return "complete"


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat(value: datetime | None) -> str | None:
    observed_at = _as_utc(value)
    return observed_at.isoformat() if observed_at else None


def _history_days(value: str) -> int | str:
    normalized = value.strip().lower()
    if normalized == "max":
        return "max"
    parsed = int(normalized)
    return max(parsed, 1)


def _demo_history_days(value: int | str) -> int:
    if value == "max":
        return 365
    return int(value)


def _exchange_history_days(value: str) -> int:
    normalized = value.strip().lower()
    if normalized == "max":
        return 1000
    return min(max(int(normalized), 1), 1000)


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


def _upsert_price_candle(session: Session, run: CollectionRun, asset: Asset, candle: dict) -> None:
    existing = session.scalar(
        select(PriceCandle).where(
            PriceCandle.asset_id == asset.id,
            PriceCandle.timeframe == "1d",
            PriceCandle.opened_at == candle["opened_at"],
        )
    )
    if not existing:
        session.add(
            PriceCandle(
                asset_id=asset.id,
                collection_run_id=run.id,
                timeframe="1d",
                opened_at=candle["opened_at"],
                open=candle.get("open"),
                high=candle.get("high"),
                low=candle.get("low"),
                close=candle.get("close"),
                volume_usd=candle.get("volume_usd"),
                source=candle.get("source") or "unknown",
                raw_payload=candle.get("raw_payload"),
            )
        )
        return

    existing.collection_run_id = run.id
    existing.open = candle.get("open")
    existing.high = candle.get("high")
    existing.low = candle.get("low")
    existing.close = candle.get("close")
    existing.volume_usd = candle.get("volume_usd")
    existing.source = candle.get("source") or existing.source
    existing.raw_payload = candle.get("raw_payload")


def _volume_by_date(payload: dict) -> dict:
    values = {}
    for row in payload.get("total_volumes", []):
        if len(row) < 2:
            continue
        observed_at = datetime.fromtimestamp(float(row[0]) / 1000, tz=timezone.utc)
        values[observed_at.date()] = row[1]
    return values


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
