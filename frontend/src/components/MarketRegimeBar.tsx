import { Activity, AlertTriangle, BarChart3, Gauge, Scale, ShieldCheck, TrendingUp } from "lucide-react";
import { formatAge, formatNumber, formatPct, formatUsd } from "../lib/format";
import type { MarketRegime } from "../types";

type Props = {
  regime: MarketRegime | null | undefined;
  compact?: boolean;
};

export function MarketRegimeBar({ regime, compact = false }: Props) {
  const stale = regime?.freshness_status === "stale" || regime?.freshness_status === "outdated";
  const unavailable = !regime || regime.freshness_status === "unavailable";
  const statusClass = unavailable
    ? "bg-slate-50 text-muted ring-slate-200"
    : stale
      ? "bg-amber-50 text-warn ring-amber-200"
      : "bg-emerald-50 text-accent ring-emerald-200";

  return (
    <div className="overflow-hidden rounded border border-line bg-white">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <Activity className="h-4 w-4 shrink-0 text-muted" />
          <p className="truncate text-sm font-semibold text-ink">Market Regime</p>
        </div>
        <span className={`shrink-0 rounded px-2 py-1 text-xs font-medium ring-1 ${statusClass}`}>
          {freshnessLabel(regime?.freshness_status)} · age {formatAge(regime?.snapshot_age_seconds)}
        </span>
      </div>
      <div className={`grid gap-0 divide-y divide-line sm:divide-y-0 ${compact ? "sm:grid-cols-4 xl:grid-cols-7" : "sm:grid-cols-4 lg:grid-cols-7"}`}>
        <RegimeMetric icon={BarChart3} label="BTC.D" value={formatPct(regime?.btc_dominance_pct)} />
        <RegimeMetric icon={TrendingUp} label="총 시총 24h" value={formatPct(regime?.total_market_cap_change_24h_pct)} />
        <RegimeMetric icon={Gauge} label="공포탐욕" value={fearGreedValue(regime)} detail={regime?.fear_greed_label || "-"} />
        <RegimeMetric icon={Scale} label="BTC funding" value={formatPct((regime?.btc_funding_rate ?? null) === null ? null : (regime!.btc_funding_rate as number) * 100)} />
        <RegimeMetric icon={ShieldCheck} label="OI" value={formatUsd(regime?.btc_open_interest_usd)} />
        <RegimeMetric icon={Activity} label="L/S" value={formatNumber(regime?.btc_long_short_ratio)} />
        <RegimeMetric
          icon={AlertTriangle}
          label="BTC 김프"
          value={formatPct(regime?.btc_kimchi_premium_pct)}
          detail={freshnessLabel(regime?.btc_kimchi_freshness_status)}
        />
      </div>
    </div>
  );
}

function RegimeMetric({
  icon: Icon,
  label,
  value,
  detail
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="min-w-0 px-4 py-3">
      <div className="flex items-center gap-1.5 text-xs uppercase text-muted">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{label}</span>
      </div>
      <p className="mt-1 truncate text-sm font-semibold text-ink" title={value}>
        {value}
      </p>
      {detail && <p className="mt-0.5 truncate text-xs text-muted">{detail}</p>}
    </div>
  );
}

function fearGreedValue(regime: MarketRegime | null | undefined): string {
  if (regime?.fear_greed_value === null || regime?.fear_greed_value === undefined) return "-";
  return `${Math.round(regime.fear_greed_value)}/100`;
}

function freshnessLabel(value: string | null | undefined): string {
  if (value === "fresh") return "fresh";
  if (value === "stale") return "stale";
  if (value === "outdated") return "outdated";
  return "unavailable";
}
