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
  snapshots: MarketSnapshot[];
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
