export type Severity = "low" | "medium" | "high";
export type DataQuality = "investor_grade" | "research_only" | "unavailable";
export type FreshnessStatus = "fresh" | "stale" | "outdated" | "unavailable";
export type NewsStance = "positive_candidate" | "neutral" | "negative_candidate" | "mixed" | "unavailable";

export type Asset = {
  symbol: string;
  name: string;
  group: "investable" | "stablecoin" | string;
  rank: number | null;
};

export type MarketSnapshot = {
  observed_at: string;
  price_usd: number | null;
  market_cap_usd: number | null;
  volume_24h_usd: number | null;
  price_change_24h_pct: number | null;
  circulating_supply: number | null;
  total_supply: number | null;
  source: string;
};

export type PriceCandle = {
  opened_at: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume_usd?: number | null;
  volume_quote?: number | null;
  volume_base?: number | null;
  quote_currency?: string | null;
  ma7: number | null;
  ma20: number | null;
  source: string;
};

export type ExchangeCandle = PriceCandle & {
  volume_base: number | null;
  volume_quote: number | null;
  quote_currency: string;
  exchange: string;
  market: string;
};

export type ExchangeCandleSeries = {
  exchange: string;
  market: string;
  quote_currency: string;
  timeframe: string;
  candles: ExchangeCandle[];
};

export type KimchiPremiumPoint = {
  observed_at: string;
  global_exchange: string;
  global_market: string;
  korean_exchange: string;
  korean_market: string;
  global_price_usd: number | null;
  korean_price_krw: number | null;
  usd_krw: number | null;
  fx_source: string | null;
  usdt_krw_reference: number | null;
  korean_price_usd: number | null;
  premium_pct: number | null;
  usdt_basis_premium_pct: number | null;
  basis: string | null;
  data_age_seconds: number | null;
  snapshot_age_seconds: number | null;
  source_skew_seconds: number | null;
  freshness_status: FreshnessStatus;
  availability: string;
  score: number;
  direction: "up" | "down" | "neutral" | string;
  source: string;
};

export type KimchiPremiumLatest = {
  observed_at: string;
  average_premium_pct: number | null;
  max_abs_premium_pct: number | null;
  score: number;
  direction: "up" | "down" | "neutral" | string;
  summary: string;
  basis: string | null;
  fx_source: string | null;
  usd_krw: number | null;
  usdt_krw_reference: number | null;
  data_age_seconds: number | null;
  snapshot_age_seconds: number | null;
  source_skew_seconds: number | null;
  freshness_status: FreshnessStatus;
  availability: string;
  exchanges: KimchiPremiumPoint[];
};

export type OnchainPoint = {
  observed_at: string;
  active_addresses: number | null;
  transaction_count: number | null;
  fees_usd: number | null;
  exchange_netflow_usd: number | null;
  availability: string;
  source: string;
  impact_score: number;
  data_quality?: DataQuality;
  quality_reason?: string;
};

export type SupplyPoint = {
  observed_at: string;
  circulating_supply: number | null;
  total_supply: number | null;
  burn_amount: number | null;
  mint_amount: number | null;
  net_change: number | null;
  net_change_pct: number | null;
  method: "direct" | "circulating_proxy" | "unavailable" | string;
  availability: string;
  source: string;
  impact_score: number;
  data_quality?: DataQuality;
  quality_reason?: string;
};

export type NewsEvidenceItem = {
  title: string;
  url: string;
  source: string;
  published_at: string | null;
  summary_ko: string | null;
  stance: NewsStance;
  stance_label_ko: string;
  stance_confidence: number;
  reason_ko: string;
  risk_notes: string[];
  analysis_source: string;
};

export type NewsImpactPoint = {
  observed_at: string;
  score: number;
  item_count: number;
  source_count: number;
  stance_counts: Record<NewsStance, number>;
  summary: string;
  items: NewsEvidenceItem[];
};

export type FactorImpact = {
  factor: "market" | "onchain" | "supply" | "news" | string;
  label: string;
  score: number;
  direction: "up" | "down" | "neutral" | string;
  summary: string;
  availability: string;
  confidence: Severity;
  data_quality?: DataQuality;
  quality_reason?: string;
};

export type FactorTrendPoint = {
  observed_at: string;
  value: number | null;
  delta_pct: number | null;
  vs_7d_avg_pct: number | null;
  vs_30d_avg_pct: number | null;
  z_score_30d: number | null;
  direction: "up" | "down" | "neutral" | string;
  availability: string;
  source: string;
};

export type FactorTrendSeries = {
  factor: "onchain" | "supply" | string;
  metric: string;
  label: string;
  unit: "count" | "usd" | "token" | "pct" | string;
  data_quality: DataQuality;
  points: FactorTrendPoint[];
};

export type TimelineEvent = {
  id: number | string;
  occurred_at: string;
  event_type: string;
  severity: Severity;
  title: string;
  description: string;
  score: number;
  source: string;
  links: Array<{ title: string; url: string }>;
};

export type SignalEvent = {
  id: number;
  occurred_at: string;
  signal_type: string;
  severity: Severity;
  title: string;
  description: string;
  value: number | null;
  source: string;
  evidence: Record<string, unknown>;
  data_quality: DataQuality;
  quality_reason: string;
  is_investor_grade: boolean;
  asset?: Pick<Asset, "symbol" | "name">;
};

export type Interpretation = {
  generated_at: string;
  summary: string;
  candidates: Array<{
    title: string;
    rationale: string;
    evidence?: Record<string, unknown>;
    signal_type?: string;
  }>;
  caveats: string[];
  confidence: Severity;
  model: string;
  prompt_version: string;
};

export type BriefRow = {
  asset: Asset;
  latest_snapshot: MarketSnapshot | null;
  previous_snapshot: MarketSnapshot | null;
  signal_count_24h: number;
  interpretation: Interpretation | null;
};

export type MarketRegime = {
  observed_at: string | null;
  snapshot_age_seconds: number | null;
  btc_dominance_pct: number | null;
  total_market_cap_usd: number | null;
  total_market_cap_change_24h_pct: number | null;
  fear_greed_value: number | null;
  fear_greed_label: string | null;
  btc_funding_rate: number | null;
  btc_open_interest_usd: number | null;
  btc_long_short_ratio: number | null;
  btc_kimchi_premium_pct: number | null;
  btc_kimchi_freshness_status: FreshnessStatus;
  freshness_status: FreshnessStatus;
  availability: string;
  sources: string[];
};

export type MarketBrief = {
  investable: BriefRow[];
  stablecoins: BriefRow[];
  market_regime: MarketRegime;
  generated_at: string;
};

export type AssetOverview = {
  asset: Asset;
  window: string;
  market_regime: MarketRegime;
  snapshots: MarketSnapshot[];
  market_snapshots: MarketSnapshot[];
  price_candles: PriceCandle[];
  exchange_candles: ExchangeCandleSeries[];
  kimchi_premium_series: KimchiPremiumPoint[];
  kimchi_premium_latest: KimchiPremiumLatest | null;
  onchain_series: OnchainPoint[];
  supply_series: SupplyPoint[];
  news_impacts: NewsImpactPoint[];
  factor_impacts: FactorImpact[];
  factor_trends: FactorTrendSeries[];
  timeline_events: TimelineEvent[];
  signals: SignalEvent[];
  interpretation: Interpretation | null;
};

export type SourceHealth = {
  source: string;
  status: string;
  success_rate_24h: number | null;
  latency_ms: number | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  message: string | null;
  updated_at: string | null;
};
