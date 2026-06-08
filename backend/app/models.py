from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    coingecko_id: Mapped[str | None] = mapped_column(String(120), index=True)
    group: Mapped[str] = mapped_column(String(32), index=True)
    rank: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    market_snapshots: Mapped[list["MarketSnapshot"]] = relationship(back_populates="asset")
    signal_events: Mapped[list["SignalEvent"]] = relationship(back_populates="asset")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), index=True, default="running")
    trigger: Mapped[str] = mapped_column(String(32), default="scheduled")
    message: Mapped[str | None] = mapped_column(Text)
    raw_summary: Mapped[dict | None] = mapped_column(JSON)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    price_usd: Mapped[float | None] = mapped_column(Float)
    market_cap_usd: Mapped[float | None] = mapped_column(Float)
    volume_24h_usd: Mapped[float | None] = mapped_column(Float)
    price_change_24h_pct: Mapped[float | None] = mapped_column(Float)
    circulating_supply: Mapped[float | None] = mapped_column(Float)
    total_supply: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    asset: Mapped["Asset"] = relationship(back_populates="market_snapshots")

    __table_args__ = (Index("ix_market_asset_observed", "asset_id", "observed_at"),)


class PriceCandle(Base):
    __tablename__ = "price_candles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), default="1d", index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume_usd: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("asset_id", "timeframe", "opened_at", name="uq_price_candle_asset_timeframe_opened"),
        Index("ix_price_candle_asset_timeframe_opened", "asset_id", "timeframe", "opened_at"),
    )


class ExchangeCandle(Base):
    __tablename__ = "exchange_candles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(40), index=True)
    quote_currency: Mapped[str] = mapped_column(String(12), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), default="1d", index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume_base: Mapped[float | None] = mapped_column(Float)
    volume_quote: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("exchange", "market", "timeframe", "opened_at", name="uq_exchange_candle_market_timeframe_opened"),
        Index("ix_exchange_candle_asset_exchange_opened", "asset_id", "exchange", "opened_at"),
    )


class ExchangeTickerSnapshot(Base):
    __tablename__ = "exchange_ticker_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str] = mapped_column(String(40), index=True)
    base_currency: Mapped[str] = mapped_column(String(16), index=True)
    quote_currency: Mapped[str] = mapped_column(String(16), index=True)
    price: Mapped[float | None] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("collection_run_id", "exchange", "market", name="uq_exchange_ticker_run_exchange_market"),
        Index("ix_exchange_ticker_asset_exchange_observed", "asset_id", "exchange", "observed_at"),
    )


class FxRateSnapshot(Base):
    __tablename__ = "fx_rate_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    base_currency: Mapped[str] = mapped_column(String(16), index=True)
    quote_currency: Mapped[str] = mapped_column(String(16), index=True)
    rate: Mapped[float | None] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("collection_run_id", "base_currency", "quote_currency", "source", name="uq_fx_rate_run_pair_source"),
        Index("ix_fx_rate_pair_observed", "base_currency", "quote_currency", "observed_at"),
    )


class LiveKimchiPremiumSnapshot(Base):
    __tablename__ = "live_kimchi_premium_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    global_exchange: Mapped[str] = mapped_column(String(32), default="binance", index=True)
    global_market: Mapped[str] = mapped_column(String(40))
    korean_exchange: Mapped[str] = mapped_column(String(32), index=True)
    korean_market: Mapped[str] = mapped_column(String(40))
    global_price_usd: Mapped[float | None] = mapped_column(Float)
    korean_price_krw: Mapped[float | None] = mapped_column(Float)
    usd_krw: Mapped[float | None] = mapped_column(Float)
    fx_source: Mapped[str | None] = mapped_column(String(64))
    usdt_krw_reference: Mapped[float | None] = mapped_column(Float)
    korean_price_usd: Mapped[float | None] = mapped_column(Float)
    premium_pct: Mapped[float | None] = mapped_column(Float)
    usdt_basis_premium_pct: Mapped[float | None] = mapped_column(Float)
    basis: Mapped[str] = mapped_column(String(64), default="usd_krw_live_fx")
    data_age_seconds: Mapped[float | None] = mapped_column(Float)
    availability: Mapped[str] = mapped_column(String(32), default="unavailable", index=True)
    source: Mapped[str] = mapped_column(String(64), default="live_ticker")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("collection_run_id", "asset_id", "korean_exchange", name="uq_live_kimchi_run_asset_exchange"),
        Index("ix_live_kimchi_asset_observed", "asset_id", "observed_at"),
    )


class MarketRegimeSnapshot(Base):
    __tablename__ = "market_regime_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    btc_dominance_pct: Mapped[float | None] = mapped_column(Float)
    total_market_cap_usd: Mapped[float | None] = mapped_column(Float)
    total_volume_usd: Mapped[float | None] = mapped_column(Float)
    total_market_cap_change_24h_pct: Mapped[float | None] = mapped_column(Float)
    fear_greed_value: Mapped[float | None] = mapped_column(Float)
    fear_greed_label: Mapped[str | None] = mapped_column(String(64))
    btc_funding_rate: Mapped[float | None] = mapped_column(Float)
    btc_open_interest_usd: Mapped[float | None] = mapped_column(Float)
    btc_open_interest_contracts: Mapped[float | None] = mapped_column(Float)
    btc_long_short_ratio: Mapped[float | None] = mapped_column(Float)
    availability: Mapped[str] = mapped_column(String(32), default="unavailable", index=True)
    source: Mapped[str] = mapped_column(String(64), default="market_regime")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (Index("ix_market_regime_observed", "observed_at"),)


class KimchiPremiumSnapshot(Base):
    __tablename__ = "kimchi_premium_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    global_exchange: Mapped[str] = mapped_column(String(32), default="binance", index=True)
    global_market: Mapped[str] = mapped_column(String(40))
    korean_exchange: Mapped[str] = mapped_column(String(32), index=True)
    korean_market: Mapped[str] = mapped_column(String(40))
    global_price_usd: Mapped[float | None] = mapped_column(Float)
    korean_price_krw: Mapped[float | None] = mapped_column(Float)
    usd_krw: Mapped[float | None] = mapped_column(Float)
    korean_price_usd: Mapped[float | None] = mapped_column(Float)
    premium_pct: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="exchange_candles")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("asset_id", "observed_at", "korean_exchange", name="uq_kimchi_asset_observed_exchange"),
        Index("ix_kimchi_asset_observed", "asset_id", "observed_at"),
    )


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    related_symbols: Mapped[list[str]] = mapped_column(JSON, default=list)
    duplicate_key: Mapped[str] = mapped_column(String(128), index=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("duplicate_key", "source", name="uq_news_duplicate_source"),)


class NewsAnalysis(Base):
    __tablename__ = "news_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    news_item_id: Mapped[int] = mapped_column(ForeignKey("news_items.id"), index=True)
    language: Mapped[str] = mapped_column(String(8), default="ko", index=True)
    summary_ko: Mapped[str] = mapped_column(Text)
    stance: Mapped[str] = mapped_column(String(32), index=True)
    stance_label_ko: Mapped[str] = mapped_column(String(32))
    stance_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason_ko: Mapped[str] = mapped_column(Text)
    risk_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    model: Mapped[str] = mapped_column(String(80), default="local-fallback")
    prompt_version: Mapped[str] = mapped_column(String(32), default="news-ko-v1", index=True)
    analysis_source: Mapped[str] = mapped_column(String(32), default="local_fallback", index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    raw_output: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (UniqueConstraint("news_item_id", "language", "prompt_version", name="uq_news_analysis_item_language_prompt"),)


class OnchainSnapshot(Base):
    __tablename__ = "onchain_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    active_addresses: Mapped[float | None] = mapped_column(Float)
    transaction_count: Mapped[float | None] = mapped_column(Float)
    fees_usd: Mapped[float | None] = mapped_column(Float)
    exchange_netflow_usd: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="unavailable")
    availability: Mapped[str] = mapped_column(String(32), default="unavailable")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)


class SupplySnapshot(Base):
    __tablename__ = "supply_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    circulating_supply: Mapped[float | None] = mapped_column(Float)
    total_supply: Mapped[float | None] = mapped_column(Float)
    max_supply: Mapped[float | None] = mapped_column(Float)
    burn_amount: Mapped[float | None] = mapped_column(Float)
    mint_amount: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="market_api")
    availability: Mapped[str] = mapped_column(String(32), default="partial")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)


class SignalEvent(Base):
    __tablename__ = "signal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    signal_type: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)

    asset: Mapped["Asset"] = relationship(back_populates="signal_events")


class AIInterpretation(Base):
    __tablename__ = "ai_interpretations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1")
    model: Mapped[str] = mapped_column(String(80), default="local-heuristic")
    summary: Mapped[str] = mapped_column(Text)
    candidates: Mapped[list[dict]] = mapped_column(JSON, default=list)
    caveats: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[str] = mapped_column(String(24), default="low")
    evidence_signal_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    raw_output: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (UniqueConstraint("asset_id", "collection_run_id", "prompt_version", name="uq_ai_asset_run_prompt"),)


class SourceHealth(Base):
    __tablename__ = "source_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    success_rate_24h: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
