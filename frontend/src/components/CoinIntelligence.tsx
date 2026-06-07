import { useEffect, useMemo, useState } from "react";
import { AlertCircle, BarChart3, Check, LineChart, RefreshCw } from "lucide-react";
import { getAssetOverview } from "../lib/api";
import { formatDateTime, formatNumber, formatPct, formatUsd, severityClass } from "../lib/format";
import type { Asset, AssetOverview, Interpretation, TimelineEvent } from "../types";
import { FactorImpactPanel } from "./intelligence/FactorImpactPanel";
import { NewsEvidenceList } from "./intelligence/NewsEvidenceList";
import { SignalStrips } from "./intelligence/SignalStrips";
import { TradingChart } from "./intelligence/TradingChart";

type Props = {
  assets: Asset[];
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
};

type WindowOption = "7d" | "30d" | "90d";
type ChartMode = "candles" | "line";

const windows: WindowOption[] = ["7d", "30d", "90d"];

export function CoinIntelligence({ assets, selectedSymbol, onSelectSymbol }: Props) {
  const [overview, setOverview] = useState<AssetOverview | null>(null);
  const [window, setWindow] = useState<WindowOption>("30d");
  const [chartMode, setChartMode] = useState<ChartMode>("candles");
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

      <div className="grid metric-grid gap-3">
        <Metric label="Price" value={formatUsd(latest?.price_usd)} />
        <Metric label="24h Change" value={formatPct(latest?.price_change_24h_pct)} tone={(latest?.price_change_24h_pct ?? 0) >= 0 ? "up" : "down"} />
        <Metric label="Volume" value={formatUsd(latest?.volume_24h_usd)} />
        <Metric label="Latest Snapshot" value={formatDateTime(latest?.observed_at)} />
        <Metric label="Event Candidates" value={`${eventSummary.high} high / ${eventSummary.medium} medium`} />
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(360px,0.9fr)]">
        <div className="min-w-0 space-y-4">
          <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div>
                <h3 className="text-sm font-semibold tracking-normal text-ink">{selectedSymbol} Price Action</h3>
                <p className="text-xs text-muted">
                  {overview?.price_candles.length || 0} candles · {overview?.timeline_events.length || 0} events · {overview?.window || window}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
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
              candles={overview?.price_candles || []}
              events={overview?.timeline_events || []}
              indicators={indicators}
              isLoading={isLoading}
              mode={chartMode}
            />
          </div>

          <SignalStrips onchain={overview?.onchain_series || []} supply={overview?.supply_series || []} news={overview?.news_impacts || []} />
          <TimelinePanel events={overview?.timeline_events || []} isLoading={isLoading} />
        </div>

        <aside className="min-w-0 space-y-4">
          <FactorImpactPanel factors={overview?.factor_impacts || []} latest={latest} />
          <CauseCandidatePanel events={eventSummary.top} />
          <AIInterpretationPanel interpretation={overview?.interpretation || null} />
          <NewsEvidenceList impacts={overview?.news_impacts || []} />
        </aside>
      </div>
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
          {option.toUpperCase()}
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
