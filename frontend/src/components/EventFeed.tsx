import { useEffect, useMemo, useState } from "react";
import { AlertCircle, ExternalLink, Filter, RefreshCw } from "lucide-react";
import { getEvents } from "../lib/api";
import { formatDateTime, severityClass } from "../lib/format";
import type { Asset, SignalEvent } from "../types";

type Props = {
  assets: Asset[];
};

const signalTypes = ["price_move", "volume_change", "news_cluster", "onchain_change", "supply_change"];
const severities = ["high", "medium", "low"];

export function EventFeed({ assets }: Props) {
  const [symbol, setSymbol] = useState("");
  const [signalType, setSignalType] = useState("");
  const [severity, setSeverity] = useState("");
  const [events, setEvents] = useState<SignalEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      setEvents(await getEvents({ symbol, signal_type: signalType, severity }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "이벤트 로드 실패");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [symbol, signalType, severity]);

  const counts = useMemo(() => {
    return events.reduce(
      (acc, event) => {
        acc[event.severity] += 1;
        return acc;
      },
      { high: 0, medium: 0, low: 0 }
    );
  }, [events]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-normal text-ink">Event & Signal Feed</h2>
          <p className="text-sm text-muted">코인, 신호 타입, 중요도 기준으로 가격 변동 원인 후보를 좁힙니다.</p>
        </div>
        <button
          className="inline-flex h-9 items-center gap-2 rounded border border-line bg-white px-3 text-sm text-ink hover:bg-slate-50"
          onClick={load}
          title="새로고침"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          새로고침
        </button>
      </div>

      <div className="rounded border border-line bg-white p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-muted" />
          <select className="h-9 rounded border border-line px-3 text-sm" value={symbol} onChange={(event) => setSymbol(event.target.value)}>
            <option value="">All coins</option>
            {assets.map((asset) => (
              <option key={asset.symbol} value={asset.symbol}>
                {asset.symbol}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded border border-line px-3 text-sm"
            value={signalType}
            onChange={(event) => setSignalType(event.target.value)}
          >
            <option value="">All signal types</option>
            {signalTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded border border-line px-3 text-sm"
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
          >
            <option value="">All severities</option>
            {severities.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <div className="ml-auto flex gap-2 text-xs">
            <span className="rounded bg-red-50 px-2 py-1 text-danger ring-1 ring-red-200">High {counts.high}</span>
            <span className="rounded bg-amber-50 px-2 py-1 text-warn ring-1 ring-amber-200">Medium {counts.medium}</span>
            <span className="rounded bg-emerald-50 px-2 py-1 text-accent ring-1 ring-emerald-200">Low {counts.low}</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-danger">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded border border-line bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-[980px] w-full border-collapse text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Asset</th>
                <th className="px-4 py-2 font-medium">Severity</th>
                <th className="px-4 py-2 font-medium">Signal</th>
                <th className="px-4 py-2 font-medium">Evidence</th>
                <th className="px-4 py-2 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td className="px-4 py-8 text-center text-muted" colSpan={6}>
                    이벤트 로드 중
                  </td>
                </tr>
              )}
              {!isLoading && events.length === 0 && (
                <tr>
                  <td className="px-4 py-8 text-center text-muted" colSpan={6}>
                    필터 조건에 맞는 이벤트가 없습니다.
                  </td>
                </tr>
              )}
              {!isLoading &&
                events.map((event) => (
                  <tr className="border-t border-line align-top hover:bg-slate-50" key={event.id}>
                    <td className="px-4 py-3 text-muted">{formatDateTime(event.occurred_at)}</td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-ink">{event.asset?.symbol || "-"}</div>
                      <div className="text-xs text-muted">{event.asset?.name || ""}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded px-2 py-1 text-xs font-medium ring-1 ${severityClass(event.severity)}`}>
                        {event.severity}
                      </span>
                    </td>
                    <td className="max-w-[360px] px-4 py-3">
                      <div className="font-medium text-ink">{event.title}</div>
                      <div className="mt-1 text-muted">{event.description}</div>
                      <div className="mt-2 text-xs uppercase text-muted">{event.signal_type}</div>
                    </td>
                    <td className="max-w-[260px] px-4 py-3">
                      <EvidenceLinks evidence={event.evidence} />
                    </td>
                    <td className="px-4 py-3 text-xs text-muted">{event.source}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function EvidenceLinks({ evidence }: { evidence: Record<string, unknown> }) {
  const items = Array.isArray(evidence.items) ? evidence.items : [];
  const links = items
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const row = item as Record<string, unknown>;
      if (typeof row.title !== "string" || typeof row.url !== "string") return null;
      return { title: row.title, url: row.url };
    })
    .filter((item): item is { title: string; url: string } => Boolean(item));

  if (links.length === 0) {
    return <span className="text-muted">-</span>;
  }

  return (
    <div className="space-y-1">
      {links.map((link) => (
        <a
          className="flex min-w-0 items-center gap-1 truncate text-accent hover:underline"
          href={link.url}
          key={link.url}
          rel="noreferrer"
          target="_blank"
        >
          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{link.title}</span>
        </a>
      ))}
    </div>
  );
}
