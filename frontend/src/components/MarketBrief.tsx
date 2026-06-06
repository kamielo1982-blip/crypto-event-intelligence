import { useEffect, useMemo, useState } from "react";
import { AlertCircle, ArrowDownRight, ArrowUpRight, RefreshCw } from "lucide-react";
import { getMarketBrief, runCollection } from "../lib/api";
import { formatDateTime, formatPct, formatUsd } from "../lib/format";
import type { BriefRow, MarketBrief as MarketBriefType } from "../types";

type Props = {
  onSelectAsset: (symbol: string) => void;
};

export function MarketBrief({ onSelectAsset }: Props) {
  const [data, setData] = useState<MarketBriefType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCollecting, setIsCollecting] = useState(false);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      setData(await getMarketBrief());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Market Brief 로드 실패");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCollect() {
    setIsCollecting(true);
    setError(null);
    try {
      await runCollection();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "수집 실행 실패");
    } finally {
      setIsCollecting(false);
    }
  }

  const summary = useMemo(() => {
    const rows = data?.investable || [];
    const moving = rows.filter((row) => Math.abs(row.latest_snapshot?.price_change_24h_pct || 0) >= 3).length;
    const highSignalRows = rows.filter((row) => row.signal_count_24h > 0).length;
    const observedTimes = rows
      .map((row) => row.latest_snapshot?.observed_at)
      .filter(Boolean)
      .sort();
    const latest = observedTimes.length > 0 ? observedTimes[observedTimes.length - 1] : undefined;
    return { moving, highSignalRows, latest };
  }, [data]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-normal text-ink">Market Brief</h2>
          <p className="text-sm text-muted">상위 변동성 코인과 스테이블코인 그룹을 분리해서 봅니다.</p>
        </div>
        <button
          className="inline-flex h-9 items-center gap-2 rounded border border-line bg-white px-3 text-sm text-ink hover:bg-slate-50 disabled:opacity-60"
          onClick={handleCollect}
          disabled={isCollecting}
          title="수동 수집 실행"
        >
          <RefreshCw className={`h-4 w-4 ${isCollecting ? "animate-spin" : ""}`} />
          수동 갱신
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-danger">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="grid metric-grid gap-3">
        <Metric label="Investable Assets" value={data?.investable.length ?? 0} />
        <Metric label="3%+ 24h Movers" value={summary.moving} />
        <Metric label="Signal Assets" value={summary.highSignalRows} />
        <Metric label="Latest Snapshot" value={formatDateTime(summary.latest)} />
      </div>

      <BriefTable title="Investable Watchlist" rows={data?.investable || []} isLoading={isLoading} onSelectAsset={onSelectAsset} />
      <BriefTable title="Stablecoin Liquidity Group" rows={data?.stablecoins || []} isLoading={isLoading} onSelectAsset={onSelectAsset} muted />
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-line bg-white px-4 py-3">
      <p className="text-xs uppercase text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold tracking-normal text-ink">{value}</p>
    </div>
  );
}

function BriefTable({
  title,
  rows,
  isLoading,
  onSelectAsset,
  muted = false
}: {
  title: string;
  rows: BriefRow[];
  isLoading: boolean;
  onSelectAsset: (symbol: string) => void;
  muted?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded border border-line bg-white">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h3 className="text-sm font-semibold tracking-normal text-ink">{title}</h3>
        <span className="text-xs text-muted">{rows.length} assets</span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[920px] w-full border-collapse text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">Asset</th>
              <th className="px-4 py-2 font-medium">Price</th>
              <th className="px-4 py-2 font-medium">24h</th>
              <th className="px-4 py-2 font-medium">Volume</th>
              <th className="px-4 py-2 font-medium">Signals</th>
              <th className="px-4 py-2 font-medium">AI Summary</th>
              <th className="px-4 py-2 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <SkeletonRows />}
            {!isLoading && rows.length === 0 && (
              <tr>
                <td className="px-4 py-8 text-center text-muted" colSpan={7}>
                  아직 수집된 스냅샷이 없습니다.
                </td>
              </tr>
            )}
            {!isLoading &&
              rows.map((row) => {
                const pct = row.latest_snapshot?.price_change_24h_pct;
                const positive = (pct || 0) >= 0;
                const TrendIcon = positive ? ArrowUpRight : ArrowDownRight;
                return (
                  <tr
                    key={row.asset.symbol}
                    className="border-t border-line hover:bg-slate-50"
                    role="button"
                    onClick={() => !muted && onSelectAsset(row.asset.symbol)}
                  >
                    <td className="px-4 py-3">
                      <div className="font-semibold text-ink">{row.asset.symbol}</div>
                      <div className="text-xs text-muted">{row.asset.name}</div>
                    </td>
                    <td className="px-4 py-3 tabular-nums">{formatUsd(row.latest_snapshot?.price_usd)}</td>
                    <td className={`px-4 py-3 tabular-nums ${positive ? "text-accent" : "text-danger"}`}>
                      <span className="inline-flex items-center gap-1">
                        <TrendIcon className="h-4 w-4" />
                        {formatPct(pct)}
                      </span>
                    </td>
                    <td className="px-4 py-3 tabular-nums">{formatUsd(row.latest_snapshot?.volume_24h_usd)}</td>
                    <td className="px-4 py-3 tabular-nums">{row.signal_count_24h}</td>
                    <td className="max-w-[360px] px-4 py-3 text-muted">{row.interpretation?.summary || "-"}</td>
                    <td className="px-4 py-3 text-xs text-muted">{row.latest_snapshot?.source || "-"}</td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SkeletonRows() {
  return (
    <>
      {[0, 1, 2].map((item) => (
        <tr className="border-t border-line" key={item}>
          <td className="px-4 py-4" colSpan={7}>
            <div className="h-4 w-full animate-pulse rounded bg-slate-200" />
          </td>
        </tr>
      ))}
    </>
  );
}
