import { formatDateTime, formatNumber, formatPct } from "../../lib/format";
import type { NewsImpactPoint, OnchainPoint, SupplyPoint } from "../../types";

type Props = {
  onchain: OnchainPoint[];
  supply: SupplyPoint[];
  news: NewsImpactPoint[];
};

type StripPoint = {
  time: string;
  value: number | null;
  label: string;
  score?: number;
};

export function SignalStrips({ onchain, supply, news }: Props) {
  const onchainPoints = onchain.map((item) => ({
    time: item.observed_at,
    value: item.active_addresses,
    label: `활성 주소 ${formatNumber(item.active_addresses)} · 거래 ${formatNumber(item.transaction_count)}`,
    score: item.impact_score
  }));
  const supplyPoints = supply.map((item) => ({
    time: item.observed_at,
    value: item.net_change,
    label: `순공급 ${formatNumber(item.net_change)} · ${formatPct(item.net_change_pct)} · ${methodLabel(item.method)}`,
    score: item.impact_score
  }));
  const newsPoints = news.map((item) => ({
    time: item.observed_at,
    value: item.score,
    label: `뉴스 ${item.item_count}건 · 출처 ${item.source_count}곳 · 후보 점수 ${item.score}`,
    score: item.score
  }));

  return (
    <div className="grid min-w-0 gap-3 lg:grid-cols-3">
      <Strip title="On-chain Trend" subtitle="활성 주소, 거래 수, 수수료 변화" points={onchainPoints} tone="teal" emptyText="온체인 시계열 없음" />
      <Strip title="Net Supply" subtitle="직접값 우선, 없으면 유통 공급 proxy" points={supplyPoints} tone="amber" emptyText="순공급 시계열 없음" />
      <Strip title="News Impact" subtitle="뉴스 집중도와 가격 변동 근접도 점수" points={newsPoints} tone="blue" emptyText="뉴스 영향 후보 없음" />
    </div>
  );
}

function Strip({
  title,
  subtitle,
  points,
  tone,
  emptyText
}: {
  title: string;
  subtitle: string;
  points: StripPoint[];
  tone: "teal" | "amber" | "blue";
  emptyText: string;
}) {
  const max = Math.max(...points.map((point) => Math.abs(point.value ?? 0)), 0);
  const latest = points[points.length - 1];
  const color = tone === "teal" ? "bg-accent" : tone === "amber" ? "bg-warn" : "bg-blue-600";

  return (
    <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold tracking-normal text-ink">{title}</h3>
            <p className="mt-0.5 text-xs text-muted">{subtitle}</p>
          </div>
          {latest && <span className="shrink-0 text-xs text-muted">{formatDateTime(latest.time)}</span>}
        </div>
      </div>
      <div className="p-4">
        {points.length === 0 && <div className="flex h-24 items-center justify-center text-sm text-muted">{emptyText}</div>}
        {points.length > 0 && (
          <>
            <div className="flex h-24 items-end gap-1 overflow-hidden">
              {points.map((point) => {
                const height = max > 0 && point.value !== null ? Math.max(8, (Math.abs(point.value) / max) * 88) : 8;
                return (
                  <div
                    className="group flex min-w-[5px] flex-1 items-end"
                    key={`${point.time}-${point.label}`}
                    title={`${formatDateTime(point.time)} · ${point.label}`}
                  >
                    <div className={`w-full rounded-t ${color} opacity-75 transition group-hover:opacity-100`} style={{ height }} />
                  </div>
                );
              })}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div>
                <p className="uppercase text-muted">Latest</p>
                <p className="mt-1 truncate font-medium text-ink" title={latest?.label}>
                  {latest?.label}
                </p>
              </div>
              <div>
                <p className="uppercase text-muted">Impact</p>
                <p className="mt-1 font-medium text-ink">{latest?.score ?? 0}/100</p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function methodLabel(method: string): string {
  if (method === "direct") return "직접 계산";
  if (method === "circulating_proxy") return "공급량 proxy";
  return "데이터 부족";
}
