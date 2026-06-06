import { useEffect, useMemo, useRef, useState } from "react";
import { createChart, ColorType, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import { AlertCircle, ExternalLink, RefreshCw } from "lucide-react";
import { getAssetOverview } from "../lib/api";
import { formatDateTime, formatNumber, formatPct, formatUsd, severityClass } from "../lib/format";
import type { Asset, AssetOverview, SignalEvent } from "../types";

type Props = {
  assets: Asset[];
  selectedSymbol: string;
  onSelectSymbol: (symbol: string) => void;
};

export function CoinIntelligence({ assets, selectedSymbol, onSelectSymbol }: Props) {
  const [overview, setOverview] = useState<AssetOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function load(symbol: string) {
    if (!symbol) return;
    setIsLoading(true);
    setError(null);
    try {
      setOverview(await getAssetOverview(symbol));
    } catch (err) {
      setError(err instanceof Error ? err.message : "코인 상세 로드 실패");
      setOverview(null);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load(selectedSymbol);
  }, [selectedSymbol]);

  const latest = overview && overview.snapshots.length > 0 ? overview.snapshots[overview.snapshots.length - 1] : null;
  const signalCounts = useMemo(() => {
    const counts = { high: 0, medium: 0, low: 0 };
    overview?.signals.forEach((signal) => {
      counts[signal.severity] += 1;
    });
    return counts;
  }, [overview]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-normal text-ink">Coin Intelligence</h2>
          <p className="text-sm text-muted">가격, 이벤트, 구조화 신호, AI 원인 후보를 한 화면에서 연결합니다.</p>
        </div>
        <div className="flex items-center gap-2">
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
          <button
            className="inline-flex h-9 items-center gap-2 rounded border border-line bg-white px-3 text-sm text-ink hover:bg-slate-50"
            onClick={() => load(selectedSymbol)}
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
        <Metric label="24h Change" value={formatPct(latest?.price_change_24h_pct)} />
        <Metric label="24h Volume" value={formatUsd(latest?.volume_24h_usd)} />
        <Metric label="Latest Snapshot" value={formatDateTime(latest?.observed_at)} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(360px,0.85fr)]">
        <div className="rounded border border-line bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
            <div>
              <h3 className="text-sm font-semibold tracking-normal text-ink">{selectedSymbol} Price & Signals</h3>
              <p className="text-xs text-muted">{overview?.snapshots.length || 0} snapshots</p>
            </div>
            <div className="flex gap-2 text-xs">
              <Badge label={`High ${signalCounts.high}`} tone="high" />
              <Badge label={`Medium ${signalCounts.medium}`} tone="medium" />
              <Badge label={`Low ${signalCounts.low}`} tone="low" />
            </div>
          </div>
          <PriceChart overview={overview} isLoading={isLoading} />
        </div>

        <div className="space-y-4">
          <AIInterpretationPanel overview={overview} />
          <SupplyPanel overview={overview} />
        </div>
      </div>

      <div className="rounded border border-line bg-white">
        <div className="border-b border-line px-4 py-3">
          <h3 className="text-sm font-semibold tracking-normal text-ink">Recent Signals</h3>
        </div>
        <div className="divide-y divide-line">
          {isLoading && <div className="p-4 text-sm text-muted">신호를 불러오는 중입니다.</div>}
          {!isLoading && (!overview || overview.signals.length === 0) && (
            <div className="p-4 text-sm text-muted">최근 구조화 신호가 없습니다.</div>
          )}
          {!isLoading && overview?.signals.map((signal) => <SignalRow key={signal.id} signal={signal} />)}
        </div>
      </div>
    </section>
  );
}

function PriceChart({ overview, isLoading }: { overview: AssetOverview | null; isLoading: boolean }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || !overview || overview.snapshots.length === 0) return;

    let lineSeries: ISeriesApi<"Line"> | null = null;
    const chart: IChartApi = createChart(containerRef.current, {
      height: 360,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#637083"
      },
      grid: {
        vertLines: { color: "#edf0f4" },
        horzLines: { color: "#edf0f4" }
      },
      rightPriceScale: { borderColor: "#d8dee8" },
      timeScale: { borderColor: "#d8dee8", timeVisible: true }
    });

    lineSeries = chart.addLineSeries({
      color: "#0f7b6c",
      lineWidth: 2,
      priceLineVisible: false
    });
    const priceData = overview.snapshots
      .filter((snapshot) => snapshot.price_usd !== null)
      .map((snapshot) => ({
        time: Math.floor(new Date(snapshot.observed_at).getTime() / 1000) as UTCTimestamp,
        value: snapshot.price_usd as number
      }))
      .sort((a, b) => a.time - b.time);

    const markers = overview.signals
      .slice(0, 30)
      .map((signal) => ({
        time: Math.floor(new Date(signal.occurred_at).getTime() / 1000) as UTCTimestamp,
        position: signal.severity === "high" ? ("aboveBar" as const) : ("belowBar" as const),
        color: signal.severity === "high" ? "#b42318" : signal.severity === "medium" ? "#b06a00" : "#0f7b6c",
        shape: signal.severity === "high" ? ("arrowDown" as const) : ("circle" as const),
        text: signal.signal_type
      }))
      .sort((a, b) => a.time - b.time);

    lineSeries.setData(priceData);
    lineSeries.setMarkers(markers);

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) chart.applyOptions({ width });
    });
    observer.observe(containerRef.current);
    chart.timeScale().fitContent();

    return () => {
      observer.disconnect();
      chart.remove();
      lineSeries = null;
    };
  }, [overview]);

  if (isLoading) {
    return <div className="flex h-[360px] items-center justify-center text-sm text-muted">차트 로드 중</div>;
  }

  if (!overview || overview.snapshots.length === 0) {
    return <div className="flex h-[360px] items-center justify-center text-sm text-muted">가격 스냅샷이 없습니다.</div>;
  }

  return <div className="h-[360px] w-full" ref={containerRef} />;
}

function AIInterpretationPanel({ overview }: { overview: AssetOverview | null }) {
  const interpretation = overview?.interpretation;
  return (
    <div className="rounded border border-line bg-white">
      <div className="border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold tracking-normal text-ink">AI Cause Candidates</h3>
      </div>
      {!interpretation && <div className="p-4 text-sm text-muted">아직 AI 해석이 없습니다.</div>}
      {interpretation && (
        <div className="space-y-4 p-4">
          <div>
            <p className="text-sm font-medium text-ink">{interpretation.summary}</p>
            <p className="mt-1 text-xs text-muted">
              {interpretation.model} · confidence {interpretation.confidence} · {formatDateTime(interpretation.generated_at)}
            </p>
          </div>
          <div className="space-y-3">
            {interpretation.candidates.map((candidate, index) => (
              <div className="rounded border border-line p-3" key={`${candidate.title}-${index}`}>
                <p className="text-sm font-semibold text-ink">{candidate.title}</p>
                <p className="mt-1 text-sm text-muted">{candidate.rationale}</p>
              </div>
            ))}
          </div>
          {interpretation.caveats.length > 0 && (
            <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-warn">
              {interpretation.caveats.join(" ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SupplyPanel({ overview }: { overview: AssetOverview | null }) {
  const latest = overview && overview.snapshots.length > 0 ? overview.snapshots[overview.snapshots.length - 1] : undefined;
  return (
    <div className="rounded border border-line bg-white">
      <div className="border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold tracking-normal text-ink">Supply Context</h3>
      </div>
      <div className="grid grid-cols-2 gap-3 p-4 text-sm">
        <div>
          <p className="text-xs uppercase text-muted">Circulating</p>
          <p className="font-semibold text-ink">{formatNumber(latest?.circulating_supply)}</p>
        </div>
        <div>
          <p className="text-xs uppercase text-muted">Total</p>
          <p className="font-semibold text-ink">{formatNumber(latest?.total_supply)}</p>
        </div>
      </div>
    </div>
  );
}

function SignalRow({ signal }: { signal: SignalEvent }) {
  const evidenceItems = readEvidenceItems(signal.evidence);
  return (
    <div className="grid gap-3 px-4 py-3 md:grid-cols-[160px_minmax(0,1fr)_220px]">
      <div>
        <span className={`inline-flex rounded px-2 py-1 text-xs font-medium ring-1 ${severityClass(signal.severity)}`}>
          {signal.severity}
        </span>
        <p className="mt-2 text-xs text-muted">{formatDateTime(signal.occurred_at)}</p>
      </div>
      <div>
        <p className="text-sm font-semibold text-ink">{signal.title}</p>
        <p className="mt-1 text-sm text-muted">{signal.description}</p>
      </div>
      <div className="space-y-1 text-sm">
        <p className="text-xs uppercase text-muted">{signal.signal_type}</p>
        {evidenceItems.map((item) => (
          <a
            className="flex min-w-0 items-center gap-1 truncate text-accent hover:underline"
            href={item.url}
            key={item.url}
            rel="noreferrer"
            target="_blank"
          >
            <ExternalLink className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{item.title}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

function Badge({ label, tone }: { label: string; tone: "high" | "medium" | "low" }) {
  return <span className={`rounded px-2 py-1 ring-1 ${severityClass(tone)}`}>{label}</span>;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-line bg-white px-4 py-3">
      <p className="text-xs uppercase text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold tracking-normal text-ink">{value}</p>
    </div>
  );
}

function readEvidenceItems(evidence: Record<string, unknown>): Array<{ title: string; url: string }> {
  const items = evidence.items;
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const row = item as Record<string, unknown>;
      if (typeof row.url !== "string" || typeof row.title !== "string") return null;
      return { title: row.title, url: row.url };
    })
    .filter((item): item is { title: string; url: string } => Boolean(item));
}
