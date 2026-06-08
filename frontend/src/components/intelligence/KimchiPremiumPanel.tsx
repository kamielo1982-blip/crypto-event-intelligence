import { AlertTriangle, Gauge } from "lucide-react";
import { formatAge, formatDateTime, formatKrw, formatNumber, formatPct, formatUsd, severityClass } from "../../lib/format";
import type { KimchiPremiumLatest, KimchiPremiumPoint } from "../../types";

type Props = {
  latest: KimchiPremiumLatest | null;
  series: KimchiPremiumPoint[];
};

export function KimchiPremiumPanel({ latest, series }: Props) {
  const recent = series.slice(-24);
  const isWarning =
    latest?.freshness_status === "stale" ||
    latest?.freshness_status === "outdated" ||
    latest?.freshness_status === "unavailable" ||
    latest?.availability === "stale" ||
    latest?.availability === "unavailable";

  return (
    <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
      <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold tracking-normal text-ink">Kimchi Premium</h3>
          <p className="mt-0.5 text-xs text-muted">USD/KRW live FX 기준, USDT/KRW는 참고값</p>
        </div>
        {isWarning ? <AlertTriangle className="h-4 w-4 shrink-0 text-warn" /> : <Gauge className="h-4 w-4 shrink-0 text-muted" />}
      </div>
      {!latest && <div className="p-4 text-sm text-muted">김치프리미엄 데이터가 아직 없습니다.</div>}
      {latest && (
        <div className="space-y-4 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className={`text-2xl font-semibold tracking-normal ${Number(latest.average_premium_pct ?? 0) >= 0 ? "text-accent" : "text-danger"}`}>
                {formatPct(latest.average_premium_pct)}
              </p>
              <p className="mt-1 text-xs text-muted">
                {formatDateTime(latest.observed_at)} · {availabilityLabel(latest.availability)} · {freshnessLabel(latest.freshness_status)}
              </p>
            </div>
            <span className={`shrink-0 rounded px-2 py-1 text-xs font-medium ring-1 ${severityClass(latest.score >= 75 ? "high" : latest.score >= 40 ? "medium" : "low")}`}>
              {latest.score}/100
            </span>
          </div>

          <p className="text-sm leading-5 text-muted">{latest.summary}</p>

          {isWarning && (
            <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-warn">
              {latest.freshness_status === "outdated"
                ? `Snapshot age가 ${formatAge(latest.snapshot_age_seconds)}라 outdated 상태입니다. 최신 수집 후 해석하세요.`
                : latest.freshness_status === "stale"
                  ? `Snapshot age가 ${formatAge(latest.snapshot_age_seconds)}라 stale 상태입니다. 최신 수집 후 해석하세요.`
                  : latest.availability === "stale"
                    ? `Source skew가 ${formatAge(latest.source_skew_seconds ?? latest.data_age_seconds)}입니다. ticker/FX 관측 시점 차이를 확인하세요.`
                  : "필수 live ticker 또는 USD/KRW 환율이 없어 현재 김프를 계산하지 않았습니다."}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 text-xs text-muted">
            <Meta label="기준" value={basisLabel(latest.basis)} />
            <Meta label="FX 출처" value={latest.fx_source || "-"} />
            <Meta label="USD/KRW" value={formatNumber(latest.usd_krw)} />
            <Meta label="USDT/KRW 참고" value={formatNumber(latest.usdt_krw_reference)} />
            <Meta label="Snapshot age" value={formatAge(latest.snapshot_age_seconds)} />
            <Meta label="Source skew" value={formatAge(latest.source_skew_seconds ?? latest.data_age_seconds)} />
            <Meta label="Freshness" value={freshnessLabel(latest.freshness_status)} />
            <Meta label="상태" value={availabilityLabel(latest.availability)} />
          </div>

          <div className="space-y-2">
            {latest.exchanges.map((point) => (
              <div className="rounded border border-line px-3 py-2" key={`${point.korean_exchange}-${point.observed_at}`}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-ink">
                    {exchangeLabel(point.korean_exchange)} · {availabilityLabel(point.availability)} · {freshnessLabel(point.freshness_status)}
                  </p>
                  <p className={`text-sm font-semibold ${Number(point.premium_pct ?? 0) >= 0 ? "text-accent" : "text-danger"}`}>
                    {formatPct(point.premium_pct)}
                  </p>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted">
                  <p title={formatKrw(point.korean_price_krw)}>{point.korean_market} {formatKrw(point.korean_price_krw)}</p>
                  <p title={formatUsd(point.global_price_usd)}>{point.global_market} {formatUsd(point.global_price_usd)}</p>
                  <p>USD/KRW {formatNumber(point.usd_krw)}</p>
                  <p>환산 {formatUsd(point.korean_price_usd)}</p>
                  <p>USDT/KRW {formatNumber(point.usdt_krw_reference)}</p>
                  <p>USDT 기준 {formatPct(point.usdt_basis_premium_pct)}</p>
                  <p>Snapshot age {formatAge(point.snapshot_age_seconds)}</p>
                  <p>Source skew {formatAge(point.source_skew_seconds ?? point.data_age_seconds)}</p>
                </div>
              </div>
            ))}
          </div>

          {recent.length > 0 && (
            <div>
              <div className="flex h-16 items-end gap-1 overflow-hidden">
                {recent.map((point) => {
                  const value = point.premium_pct ?? 0;
                  const height = Math.max(6, Math.min(60, Math.abs(value) * 8));
                  const color = value >= 0 ? "bg-accent" : "bg-danger";
                  return (
                    <div className="group flex min-w-[5px] flex-1 items-end" key={`${point.korean_exchange}-${point.observed_at}`} title={`${exchangeLabel(point.korean_exchange)} ${formatDateTime(point.observed_at)} · ${formatPct(point.premium_pct)}`}>
                      <div className={`w-full rounded-t ${color} opacity-70 transition group-hover:opacity-100`} style={{ height }} />
                    </div>
                  );
                })}
              </div>
              <p className="mt-2 text-xs text-muted">최근 {recent.length}개 거래소별 관측값</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded border border-line px-2 py-1.5">
      <p className="uppercase text-muted">{label}</p>
      <p className="truncate font-medium text-ink" title={value}>{value}</p>
    </div>
  );
}

function exchangeLabel(exchange: string): string {
  if (exchange === "upbit") return "Upbit";
  if (exchange === "bithumb") return "Bithumb";
  return exchange;
}

function availabilityLabel(value: string | null | undefined): string {
  if (value === "complete") return "live";
  if (value === "stale") return "stale";
  if (value === "partial") return "partial";
  return "unavailable";
}

function freshnessLabel(value: string | null | undefined): string {
  if (value === "fresh") return "fresh";
  if (value === "stale") return "stale";
  if (value === "outdated") return "outdated";
  return "unavailable";
}

function basisLabel(value: string | null | undefined): string {
  if (value === "usd_krw_live_fx") return "USD/KRW live FX";
  return value || "-";
}
