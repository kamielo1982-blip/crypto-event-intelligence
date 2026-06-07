export type Severity = "low" | "medium" | "high";

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
  volume_usd: number | null;
  ma7: number | null;
  ma20: number | null;
  source: string;
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
};

export type NewsEvidenceItem = {
  title: string;
  url: string;
  source: string;
  published_at: string | null;
};

export type NewsImpactPoint = {
  observed_at: string;
  score: number;
  item_count: number;
  source_count: number;
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

export type MarketBrief = {
  investable: BriefRow[];
  stablecoins: BriefRow[];
  generated_at: string;
};

export type AssetOverview = {
  asset: Asset;
  window: string;
  snapshots: MarketSnapshot[];
  market_snapshots: MarketSnapshot[];
  price_candles: PriceCandle[];
  onchain_series: OnchainPoint[];
  supply_series: SupplyPoint[];
  news_impacts: NewsImpactPoint[];
  factor_impacts: FactorImpact[];
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
