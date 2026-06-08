import { useEffect, useMemo, useState } from "react";
import { AlertCircle, BarChart3, Check, LineChart, RefreshCw } from "lucide-react";
import { getAssetOverview } from "../lib/api";
import { formatDateTime, formatNumber, formatPct, formatUsd, severityClass } from "../lib/format";
import type { Asset, AssetOverview, Interpretation, TimelineEvent } from "../types";
import { FactorTrendPanel } from "./intelligence/FactorTrendPanel";
import { FactorImpactPanel } from "./intelligence/FactorImpactPanel";
import { KimchiPremiumPanel } from "./intelligence/KimchiPremiumPanel";
import { NewsEvidenceList } from "./intelligence/NewsEvidenceList";
import { TradingChart } from "./intelligence/TradingChart";
import { MarketRegimeBar } from "./MarketRegimeBar";
import type { PriceCandle } from "../types";

type Props = {
  assets: Asset[];
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
};

type WindowOption = "7d" | "30d" | "90d" | "365d" | "max";
type ChartMode = "candles" | "line";
type ChartSourceOption = {
  id: string;
  label: string;
  detail: string;
  candles: PriceCandle[];
};

const windows: WindowOption[] = ["7d", "30d", "90d", "365d", "max"];
const windowLabels: Record<WindowOption, string> = {
  "7d": "7D",
  "30d": "30D",
  "90d": "90D",
  "365d": "1Y",
  max: "MAX"
};

export function CoinIntelligence({ assets, selectedSymbol, onSelectSymbol }: Props) {
  const [overview, setOverview] = useState<AssetOverview | null>(null);
  const [window, setWindow] = useState<WindowOption>("30d");
  const [chartMode, setChartMode] = useState<ChartMode>("candles");
  const [chartSourceId, setChartSourceId] = useState("binance");
  const [indicators, setIndicators] = useState({ ma7: true, ma20: true, volume: true, events: true });
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function load(symbol: string, selectedWindow: WindowOption) {
    if (!symbol) return;
    setIsLoading(true);
    setError(null);
    try {
      setOverview(await getAssetOverview(symbol, selectedWindow));
    } catch (err) {
      setError(err instanceof Error ? err.message : "코인 상세 로드 실패");
      setOverview(null);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load(selectedSymbol, window);
  }, [selectedSymbol, window]);

  const latest = useMemo(() => {
    const rows = overview?.market_snapshots?.length ? overview.market_snapshots : overview?.snapshots || [];
    return rows.length > 0 ? rows[rows.length - 1] : null;
  }, [overview]);

  const eventSummary = useMemo(() => {
    const events = overview?.timeline_events || [];
    return {
      high: events.filter((event) => event.severity === "high").length,
      medium: events.filter((event) => event.severity === "medium").length,
      top: events.filter((event) => event.score >= 60).slice(0, 3)
    };
  }, [overview]);

  const chartSources = useMemo<ChartSourceOption[]>(() => {
    if (!overview) return [];
    const exchangeRank: Record<string, number> = { binance: 0, upbit: 1, bithumb: 2 };
    const exchangeSources: ChartSourceOption[] = (overview.exchange_candles || [])
      .filter((series) => series.candles.length > 0)
      .sort((left, right) => (exchangeRank[left.exchange] ?? 99) - (exchangeRank[right.exchange] ?? 99))
      .map((series) => ({
        id: `${series.exchange}:${series.market}`,
        label: `${exchangeLabel(series.exchange)} ${series.market}${sourceBadge(series.candles)}`,
        detail: `${series.quote_currency}${sourceBadge(series.candles)}`,
        candles: series.candles as PriceCandle[]
      }));
    if (overview.price_candles.length > 0) {
      exchangeSources.push({
        id: "coingecko",
        label: `CoinGecko USD${sourceBadge(overview.price_candles)}`,
        detail: overview.price_candles.some((candle) => candle.source === "demo_fallback") ? "demo fallback" : "fallback",
        candles: overview.price_candles
      });
    }
    return exchangeSources;
  }, [overview]);

  useEffect(() => {
    if (chartSources.length === 0) return;
    if (!chartSources.some((source) => source.id === chartSourceId)) {
      setChartSourceId(chartSources[0].id);
    }
  }, [chartSourceId, chartSources]);

  const selectedChartSource = chartSources.find((source) => source.id === chartSourceId) || chartSources[0];
  const selectedCandles = selectedChartSource?.candles || [];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-normal text-ink">Coin Intelligence Workbench</h2>
          <p className="text-sm text-muted">가격, 온체인, 순공급, 뉴스 영향 후보를 같은 분석 화면에서 연결합니다.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-9 rounded border border-line bg-white px-3 text-sm text-ink outline-none focus:border-ink"
            value={selectedSymbol}
            onChange={(event) => onSelectSymbol(event.target.value)}
          >
            {assets.map((asset) => (
              <option key={asset.symbol} value={asset.symbol}>
                {asset.symbol} - {asset.name}
              </option>
            ))}
          </select>
          <SegmentedControl
            options={windows}
            value={window}
            onChange={(value) => setWindow(value as WindowOption)}
          />
          <button
            className="inline-flex h-9 items-center gap-2 rounded border border-line bg-white px-3 text-sm text-ink hover:bg-slate-50"
            onClick={() => load(selectedSymbol, window)}
            title="새로고침"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            새로고침
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-danger">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <MarketRegimeBar regime={overview?.market_regime} compact />

      <div className="grid metric-grid gap-3">
        <Metric label="Price" value={formatUsd(latest?.price_usd)} />
        <Metric label="24h Change" value={formatPct(latest?.price_change_24h_pct)} tone={(latest?.price_change_24h_pct ?? 0) >= 0 ? "up" : "down"} />
        <Metric label="Volume" value={formatUsd(latest?.volume_24h_usd)} />
        <Metric label="Latest Snapshot" value={formatDateTime(latest?.observed_at)} />
        <Metric label="Event Candidates" value={`${eventSummary.high} high / ${eventSummary.medium} medium`} />
        <Metric
          label="Kimchi Premium"
          value={formatPct(overview?.kimchi_premium_latest?.average_premium_pct)}
          tone={(overview?.kimchi_premium_latest?.average_premium_pct ?? 0) >= 0 ? "up" : "down"}
        />
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(360px,0.9fr)]">
        <div className="min-w-0 space-y-4">
          <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div>
                <h3 className="text-sm font-semibold tracking-normal text-ink">{selectedSymbol} Price Action</h3>
                <p className="text-xs text-muted">
                  {selectedCandles.length || 0} candles · {selectedChartSource?.label || "No source"} · {selectedChartSource?.detail || "-"} · {overview?.timeline_events.length || 0} events · {overview?.window || window}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  className="h-8 rounded border border-line bg-white px-2 text-xs text-ink outline-none focus:border-ink"
                  value={selectedChartSource?.id || ""}
                  onChange={(event) => setChartSourceId(event.target.value)}
                >
                  {chartSources.map((source) => (
                    <option key={source.id} value={source.id}>
                      {source.label}
                    </option>
                  ))}
                </select>
                <button
                  className={`inline-flex h-8 items-center gap-1 rounded border px-2 text-xs ${
                    chartMode === "candles" ? "border-ink bg-ink text-white" : "border-line bg-white text-ink hover:bg-slate-50"
                  }`}
                  onClick={() => setChartMode("candles")}
                >
                  <BarChart3 className="h-3.5 w-3.5" />
                  Candle
                </button>
                <button
                  className={`inline-flex h-8 items-center gap-1 rounded border px-2 text-xs ${
                    chartMode === "line" ? "border-ink bg-ink text-white" : "border-line bg-white text-ink hover:bg-slate-50"
                  }`}
                  onClick={() => setChartMode("line")}
                >
                  <LineChart className="h-3.5 w-3.5" />
                  Line
                </button>
                <IndicatorToggle label="MA7" checked={indicators.ma7} onChange={(checked) => setIndicators((current) => ({ ...current, ma7: checked }))} />
                <IndicatorToggle label="MA20" checked={indicators.ma20} onChange={(checked) => setIndicators((current) => ({ ...current, ma20: checked }))} />
                <IndicatorToggle label="Volume" checked={indicators.volume} onChange={(checked) => setIndicators((current) => ({ ...current, volume: checked }))} />
                <IndicatorToggle label="Events" checked={indicators.events} onChange={(checked) => setIndicators((current) => ({ ...current, events: checked }))} />
              </div>
            </div>
            <TradingChart
              candles={selectedCandles}
              events={overview?.timeline_events || []}
              indicators={indicators}
              isLoading={isLoading}
              mode={chartMode}
            />
          </div>
        </div>

        <aside className="min-w-0 space-y-4">
          <InsightSummaryPanel overview={overview} events={eventSummary.top} />
          <FactorImpactPanel factors={overview?.factor_impacts || []} latest={latest} />
          <KimchiPremiumPanel latest={overview?.kimchi_premium_latest || null} series={overview?.kimchi_premium_series || []} />
          <AIInterpretationPanel interpretation={overview?.interpretation || null} />
        </aside>
      </div>

      <FactorTrendPanel trends={overview?.factor_trends || []} />
      <NewsEvidenceList impacts={overview?.news_impacts || []} />
      <TimelinePanel events={overview?.timeline_events || []} isLoading={isLoading} />
    </section>
  );
}

function SegmentedControl({ options, value, onChange }: { options: string[]; value: string; onChange: (value: string) => void }) {
  return (
    <div className="inline-flex h-9 overflow-hidden rounded border border-line bg-white">
      {options.map((option) => (
        <button
          className={`min-w-[48px] px-3 text-sm ${value === option ? "bg-ink text-white" : "text-ink hover:bg-slate-50"}`}
          key={option}
          onClick={() => onChange(option)}
        >
          {windowLabels[option as WindowOption] || option.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

function IndicatorToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="inline-flex h-8 cursor-pointer items-center gap-1 rounded border border-line bg-white px-2 text-xs text-ink hover:bg-slate-50">
      <input className="sr-only" type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className={`flex h-4 w-4 items-center justify-center rounded border ${checked ? "border-accent bg-accent text-white" : "border-line bg-white"}`}>
        {checked && <Check className="h-3 w-3" />}
      </span>
      {label}
    </label>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string | number; tone?: "up" | "down" | "neutral" }) {
  return (
    <div className="rounded border border-line bg-white px-4 py-3">
      <p className="text-xs uppercase text-muted">{label}</p>
      <p className={`mt-1 text-lg font-semibold tracking-normal ${tone === "up" ? "text-accent" : tone === "down" ? "text-danger" : "text-ink"}`}>
        {value}
      </p>
    </div>
  );
}

function InsightSummaryPanel({ overview, events }: { overview: AssetOverview | null; events: TimelineEvent[] }) {
  const candidates = buildInsightCandidates(overview, events);
  return (
    <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
      <div className="border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold tracking-normal text-ink">원인 후보 요약</h3>
        <p className="mt-0.5 text-xs text-muted">가격·뉴스·온체인·순공급·김프의 상위 동반 신호</p>
      </div>
      <div className="divide-y divide-line">
        {candidates.length === 0 && <div className="p-4 text-sm text-muted">강한 원인 후보가 아직 없습니다.</div>}
        {candidates.map((candidate) => (
          <div className="px-4 py-3" key={candidate.title}>
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-semibold text-ink">{candidate.title}</p>
              <span className={`shrink-0 rounded px-2 py-1 text-xs font-medium ring-1 ${severityClass(candidate.confidence)}`}>{candidate.score}/100</span>
            </div>
            <p className="mt-1 text-sm leading-5 text-muted">{candidate.description}</p>
            <p className="mt-2 text-xs text-muted">{candidate.source}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildInsightCandidates(overview: AssetOverview | null, events: TimelineEvent[]) {
  if (!overview) return [];
  const items: Array<{ title: string; description: string; score: number; confidence: "low" | "medium" | "high"; source: string }> = [];
  const latestNews = overview.news_impacts[overview.news_impacts.length - 1];
  if (latestNews) {
    const counts = latestNews.stance_counts;
    const dominant = dominantNewsLabel(counts);
    items.push({
      title: `뉴스 ${dominant.label}`,
      description: `${latestNews.item_count}건의 관련 뉴스가 묶였고, ${dominant.label} 후보가 ${dominant.count}건입니다.`,
      score: latestNews.score,
      confidence: latestNews.score >= 75 ? "high" : latestNews.score >= 40 ? "medium" : "low",
      source: `출처 ${latestNews.source_count}곳 · ${formatDateTime(latestNews.observed_at)}`
    });
  }
  const trendCandidates = (overview.factor_trends || [])
    .map((trend) => ({ trend, latest: trend.points[trend.points.length - 1] }))
    .filter((item) => item.latest && item.latest.z_score_30d !== null)
    .sort((left, right) => Math.abs(right.latest.z_score_30d || 0) - Math.abs(left.latest.z_score_30d || 0))
    .slice(0, 2);
  trendCandidates.forEach(({ trend, latest }) => {
    const absoluteZ = Math.abs(latest.z_score_30d || 0);
    items.push({
      title: `${trend.label} ${latest.direction === "down" ? "감소" : latest.direction === "up" ? "증가" : "중립"} 후보`,
      description: `30D 평균 대비 ${formatPct(latest.vs_30d_avg_pct)}, z-score ${formatNumber(latest.z_score_30d)}입니다.`,
      score: Math.min(100, Math.round(absoluteZ * 35)),
      confidence: trend.data_quality === "investor_grade" && absoluteZ >= 2 ? "medium" : "low",
      source: `${trend.factor} · ${trend.data_quality}`
    });
  });
  const kimchi = overview.kimchi_premium_latest;
  if (kimchi?.average_premium_pct !== null && kimchi?.average_premium_pct !== undefined) {
    items.push({
      title: `김치프리미엄 ${kimchi.average_premium_pct >= 0 ? "양수" : "음수"} 구간`,
      description: `${formatPct(kimchi.average_premium_pct)}로 국내외 가격차가 가격 변동의 동반 신호 후보입니다.`,
      score: kimchi.score,
      confidence: kimchi.score >= 75 ? "high" : kimchi.score >= 40 ? "medium" : "low",
      source: `${kimchi.freshness_status} · ${kimchi.fx_source || "-"}`
    });
  }
  events.slice(0, 1).forEach((event) => {
    items.push({
      title: event.title,
      description: event.description,
      score: event.score,
      confidence: event.severity,
      source: `${event.event_type} · ${event.source}`
    });
  });
  return items.sort((left, right) => right.score - left.score).slice(0, 3);
}

function dominantNewsLabel(counts: AssetOverview["news_impacts"][number]["stance_counts"]) {
  const candidates = [
    { key: "positive_candidate", label: "잠재 호재", count: counts?.positive_candidate || 0 },
    { key: "negative_candidate", label: "잠재 악재", count: counts?.negative_candidate || 0 },
    { key: "mixed", label: "혼재", count: counts?.mixed || 0 },
    { key: "neutral", label: "중립", count: counts?.neutral || 0 }
  ];
  return candidates.sort((left, right) => right.count - left.count)[0] || { key: "unavailable", label: "판단 보류", count: 0 };
}

function CauseCandidatePanel({ events }: { events: TimelineEvent[] }) {
  return (
    <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
      <div className="border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold tracking-normal text-ink">Top Move Candidates</h3>
        <p className="mt-0.5 text-xs text-muted">가격 변동 근처의 상위 원인 후보입니다.</p>
      </div>
      <div className="divide-y divide-line">
        {events.length === 0 && <div className="p-4 text-sm text-muted">점수 60 이상의 후보 이벤트가 없습니다.</div>}
        {events.map((event) => (
          <div className="px-4 py-3" key={event.id}>
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-semibold text-ink">{event.title}</p>
              <span className={`shrink-0 rounded px-2 py-1 text-xs font-medium ring-1 ${severityClass(event.severity)}`}>{event.score}/100</span>
            </div>
            <p className="mt-1 text-sm leading-5 text-muted">{event.description}</p>
            <p className="mt-2 text-xs text-muted">
              {event.event_type} · {formatDateTime(event.occurred_at)} · {event.source}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function AIInterpretationPanel({ interpretation }: { interpretation: Interpretation | null }) {
  return (
    <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
      <div className="border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold tracking-normal text-ink">AI Cause Candidates</h3>
      </div>
      {!interpretation && <div className="p-4 text-sm text-muted">아직 AI 해석이 없습니다.</div>}
      {interpretation && (
        <div className="p-4">
          <p className="text-sm font-medium text-ink">{interpretation.summary}</p>
          <p className="mt-1 text-xs text-muted">
            {interpretation.model} · confidence {interpretation.confidence} · {formatDateTime(interpretation.generated_at)}
          </p>
          <div className="mt-4 divide-y divide-line">
            {interpretation.candidates.map((candidate, index) => (
              <div className="py-3 first:pt-0 last:pb-0" key={`${candidate.title}-${index}`}>
                <p className="text-sm font-semibold text-ink">{candidate.title}</p>
                <p className="mt-1 text-sm leading-5 text-muted">{candidate.rationale}</p>
              </div>
            ))}
          </div>
          {interpretation.caveats.length > 0 && (
            <div className="mt-4 border-t border-amber-200 pt-3 text-sm text-warn">
              {interpretation.caveats.join(" ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TimelinePanel({ events, isLoading }: { events: TimelineEvent[]; isLoading: boolean }) {
  return (
    <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold tracking-normal text-ink">Event Timeline</h3>
        <span className="text-xs text-muted">{events.length} events</span>
      </div>
      <div className="divide-y divide-line">
        {isLoading && <div className="p-4 text-sm text-muted">이벤트를 불러오는 중입니다.</div>}
        {!isLoading && events.length === 0 && <div className="p-4 text-sm text-muted">최근 이벤트가 없습니다.</div>}
        {!isLoading &&
          events.slice(0, 12).map((event) => (
            <div className="grid gap-3 px-4 py-3 md:grid-cols-[150px_minmax(0,1fr)_120px]" key={event.id}>
              <div>
                <span className={`inline-flex rounded px-2 py-1 text-xs font-medium ring-1 ${severityClass(event.severity)}`}>{event.severity}</span>
                <p className="mt-2 text-xs text-muted">{formatDateTime(event.occurred_at)}</p>
              </div>
              <div>
                <p className="text-sm font-semibold text-ink">{event.title}</p>
                <p className="mt-1 text-sm leading-5 text-muted">{event.description}</p>
                {event.links.length > 0 && (
                  <p className="mt-2 truncate text-xs text-accent">
                    근거 {event.links.length}건 · {event.links[0].title}
                  </p>
                )}
              </div>
              <div className="text-sm">
                <p className="text-xs uppercase text-muted">{event.event_type}</p>
                <p className="mt-1 font-semibold text-ink">{formatNumber(event.score)}/100</p>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}

function exchangeLabel(exchange: string): string {
  if (exchange === "binance") return "Binance";
  if (exchange === "upbit") return "Upbit";
  if (exchange === "bithumb") return "Bithumb";
  return exchange;
}

function sourceBadge(candles: PriceCandle[]): string {
  if (candles.length === 0) return "";
  return candles.some((candle) => candle.source === "demo_fallback") ? " (Demo)" : "";
}
