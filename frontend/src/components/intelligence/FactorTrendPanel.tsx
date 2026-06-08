import { Activity, ArrowDown, ArrowRight, ArrowUp, Scale } from "lucide-react";
import { formatDateTime, formatNumber, formatPct, formatUsd } from "../../lib/format";
import type { DataQuality, FactorTrendSeries } from "../../types";

type Props = {
  trends: FactorTrendSeries[];
};

export function FactorTrendPanel({ trends }: Props) {
  const visible = trends.filter((trend) => trend.points.length > 0);

  return (
    <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold tracking-normal text-ink">Factor Trend</h3>
          <p className="mt-0.5 text-xs text-muted">7D/30D 평균 대비 변화 · 30D z-score</p>
        </div>
        <span className="rounded bg-slate-50 px-2 py-1 text-xs font-medium text-muted ring-1 ring-slate-200">{visible.length} metrics</span>
      </div>
      {visible.length === 0 && <div className="p-4 text-sm text-muted">온체인·순공급 trend 데이터가 없습니다.</div>}
      {visible.length > 0 && (
        <div className="grid gap-3 p-4 lg:grid-cols-3">
          {visible.map((trend) => (
            <TrendCard key={`${trend.factor}-${trend.metric}`} trend={trend} />
          ))}
        </div>
      )}
    </div>
  );
}

function TrendCard({ trend }: { trend: FactorTrendSeries }) {
  const latest = trend.points[trend.points.length - 1];
  const maxAbsZ = Math.max(...trend.points.map((point) => Math.abs(point.z_score_30d ?? 0)), 1);
  const Icon = trend.factor === "supply" ? Scale : Activity;

  return (
    <div className="min-w-0 rounded border border-line bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 shrink-0 text-muted" />
            <p className="truncate text-sm font-semibold text-ink">{trend.label}</p>
          </div>
          <p className="mt-1 text-xs text-muted">{formatDateTime(latest.observed_at)} · {latest.source}</p>
        </div>
        <span className={`shrink-0 rounded px-2 py-1 text-xs font-medium ring-1 ${qualityClass(trend.data_quality)}`}>{qualityLabel(trend.data_quality)}</span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <Metric label="Latest" value={formatByUnit(latest.value, trend.unit)} />
        <Metric label="Prev" value={formatPct(latest.delta_pct)} tone={latest.delta_pct} />
        <Metric label="vs 7D avg" value={formatPct(latest.vs_7d_avg_pct)} tone={latest.vs_7d_avg_pct} />
        <Metric label="vs 30D avg" value={formatPct(latest.vs_30d_avg_pct)} tone={latest.vs_30d_avg_pct} />
      </div>

      <div className="mt-4 flex h-16 items-end gap-1 overflow-hidden rounded bg-slate-50 px-2 pb-2 pt-2">
        {trend.points.slice(-30).map((point) => {
          const height = Math.max(6, (Math.abs(point.z_score_30d ?? 0) / maxAbsZ) * 48);
          return (
            <div className="group flex min-w-[5px] flex-1 items-end justify-center" key={point.observed_at} title={`${formatDateTime(point.observed_at)} · z ${formatNumber(point.z_score_30d)}`}>
              <div className={`w-full rounded-t ${barClass(point.z_score_30d)}`} style={{ height }} />
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex items-center justify-between gap-2 text-xs">
        <span className="text-muted">z-score 30D {formatNumber(latest.z_score_30d)}</span>
        <span className={`inline-flex items-center gap-1 font-medium ${directionClass(latest.direction)}`}>
          {directionIcon(latest.direction)}
          {directionLabel(latest.direction)}
        </span>
      </div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: number | null }) {
  return (
    <div className="min-w-0">
      <p className="text-xs uppercase text-muted">{label}</p>
      <p className={`mt-1 truncate font-semibold ${toneClass(tone)}`}>{value}</p>
    </div>
  );
}

function formatByUnit(value: number | null, unit: string): string {
  if (unit === "pct") return formatPct(value);
  if (unit === "usd") return formatUsd(value);
  return formatNumber(value);
}

function toneClass(value?: number | null): string {
  if (value === null || value === undefined || value === 0) return "text-ink";
  return value > 0 ? "text-accent" : "text-danger";
}

function barClass(value: number | null): string {
  if (value === null || value === 0) return "bg-slate-300";
  return value > 0 ? "bg-accent" : "bg-danger";
}

function qualityLabel(value: DataQuality): string {
  if (value === "investor_grade") return "Investor-grade";
  if (value === "research_only") return "Research-only";
  return "Unavailable";
}

function qualityClass(value: DataQuality): string {
  if (value === "investor_grade") return "bg-emerald-50 text-accent ring-emerald-200";
  if (value === "research_only") return "bg-amber-50 text-warn ring-amber-200";
  return "bg-slate-50 text-muted ring-slate-200";
}

function directionClass(direction: string): string {
  if (direction === "up") return "text-accent";
  if (direction === "down") return "text-danger";
  return "text-muted";
}

function directionIcon(direction: string) {
  if (direction === "up") return <ArrowUp className="h-3.5 w-3.5" />;
  if (direction === "down") return <ArrowDown className="h-3.5 w-3.5" />;
  return <ArrowRight className="h-3.5 w-3.5" />;
}

function directionLabel(direction: string): string {
  if (direction === "up") return "증가";
  if (direction === "down") return "감소";
  return "중립";
}
