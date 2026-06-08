import { Activity, BarChart3, CircleDollarSign, Newspaper, Scale } from "lucide-react";
import type { FactorImpact, MarketSnapshot } from "../../types";
import { formatDateTime, formatPct, formatUsd, severityClass } from "../../lib/format";

type Props = {
  factors: FactorImpact[];
  latest: MarketSnapshot | null;
};

const icons = {
  market: BarChart3,
  onchain: Activity,
  supply: CircleDollarSign,
  news: Newspaper,
  kimchi_premium: Scale
};

export function FactorImpactPanel({ factors, latest }: Props) {
  return (
    <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
      <div className="border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold tracking-normal text-ink">Impact Candidates</h3>
        <p className="mt-0.5 text-xs text-muted">요소별 원인 후보 점수입니다. 확정 원인이나 매매 신호가 아닙니다.</p>
      </div>
      <div className="space-y-4 p-4">
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <Metric label="Price" value={formatUsd(latest?.price_usd)} />
          <Metric label="24h" value={formatPct(latest?.price_change_24h_pct)} tone={(latest?.price_change_24h_pct ?? 0) >= 0 ? "up" : "down"} />
          <Metric label="Volume" value={formatUsd(latest?.volume_24h_usd)} />
          <Metric label="Snapshot" value={formatDateTime(latest?.observed_at)} />
        </div>

        <div className="space-y-3">
          {factors.map((factor) => {
            const Icon = icons[factor.factor as keyof typeof icons] || Activity;
            return (
          <div className="border-t border-line pt-3 first:border-t-0 first:pt-0" key={factor.factor}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <Icon className="h-4 w-4 shrink-0 text-muted" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink">{factor.label}</p>
                      <p className="mt-0.5 text-xs text-muted">{factor.availability}</p>
                    </div>
                  </div>
                  <div className="shrink-0 space-y-1 text-right">
                    <span className={`inline-flex rounded px-2 py-1 text-xs font-medium ring-1 ${severityClass(factor.confidence)}`}>
                      {factor.score}/100
                    </span>
                    {factor.data_quality && (
                      <span className={`block rounded px-2 py-1 text-xs font-medium ring-1 ${qualityClass(factor.data_quality)}`}>
                        {qualityLabel(factor.data_quality)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded bg-slate-100">
                  <div className={`h-full rounded ${barColor(factor.confidence)}`} style={{ width: `${Math.max(4, Math.min(100, factor.score))}%` }} />
                </div>
                <p className="mt-2 text-sm leading-5 text-muted">{factor.summary}</p>
                {factor.quality_reason && <p className="mt-1 text-xs leading-4 text-muted">{factor.quality_reason}</p>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "up" | "down" | "neutral" }) {
  return (
    <div>
      <p className="text-xs uppercase text-muted">{label}</p>
      <p className={`mt-1 truncate font-semibold ${tone === "up" ? "text-accent" : tone === "down" ? "text-danger" : "text-ink"}`}>{value}</p>
    </div>
  );
}

function barColor(confidence: string): string {
  if (confidence === "high") return "bg-danger";
  if (confidence === "medium") return "bg-warn";
  return "bg-accent";
}

function qualityLabel(value: string): string {
  if (value === "investor_grade") return "Investor-grade";
  if (value === "research_only") return "Research-only";
  return "Unavailable";
}

function qualityClass(value: string): string {
  if (value === "investor_grade") return "bg-emerald-50 text-accent ring-emerald-200";
  if (value === "research_only") return "bg-amber-50 text-warn ring-amber-200";
  return "bg-slate-50 text-muted ring-slate-200";
}
