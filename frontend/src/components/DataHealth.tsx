import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Brain, Database, Newspaper, Play, RefreshCw, ShieldCheck } from "lucide-react";
import { getSourceHealth, regenerateInterpretations, regenerateNewsAnalyses, runCollection } from "../lib/api";
import { formatAge, formatDateTime, parseApiDate } from "../lib/format";
import type { SourceHealth } from "../types";

export function DataHealth() {
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCollecting, setIsCollecting] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRegeneratingNews, setIsRegeneratingNews] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      setSources(await getSourceHealth());
    } catch (err) {
      setError(err instanceof Error ? err.message : "데이터 상태 로드 실패");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCollection() {
    setIsCollecting(true);
    setMessage(null);
    setError(null);
    try {
      const result = await runCollection();
      setMessage(`collection run #${result.id}: ${result.status}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "수집 실행 실패");
    } finally {
      setIsCollecting(false);
    }
  }

  async function handleRegenerate() {
    setIsRegenerating(true);
    setMessage(null);
    setError(null);
    try {
      const result = await regenerateInterpretations();
      setMessage(`AI interpretation: ${result.status}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 해석 재생성 실패");
    } finally {
      setIsRegenerating(false);
    }
  }

  async function handleNewsRegenerate() {
    setIsRegeneratingNews(true);
    setMessage(null);
    setError(null);
    try {
      const result = await regenerateNewsAnalyses();
      setMessage(`news analysis: ${result.status}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "뉴스 분석 재생성 실패");
    } finally {
      setIsRegeneratingNews(false);
    }
  }

  const summary = useMemo(() => {
    const ok = sources.filter((source) => source.status === "ok").length;
    const failed = sources.filter((source) => source.status === "failed").length;
    const updatedTimes = sources
      .map((source) => source.updated_at)
      .filter(Boolean)
      .sort();
    const latest = updatedTimes.length > 0 ? updatedTimes[updatedTimes.length - 1] : undefined;
    return { ok, failed, latest };
  }, [sources]);

  const reliability = useMemo(() => {
    const researchOnly = sources.filter((source) => isResearchOnlySource(source));
    const stale = sources.filter((source) => source.updated_at && sourceAgeSeconds(source.updated_at) > 6 * 60 * 60);
    const failed = sources.filter((source) => source.status === "failed");
    const investorGrade = sources.filter(
      (source) => source.status === "ok" && !isResearchOnlySource(source) && !(source.updated_at && sourceAgeSeconds(source.updated_at) > 6 * 60 * 60)
    );
    return { investorGrade, researchOnly, stale, failed };
  }, [sources]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-normal text-ink">Data Health</h2>
          <p className="text-sm text-muted">수집 소스와 AI 해석 생성 상태를 운영 기준으로 확인합니다.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="inline-flex h-9 items-center gap-2 rounded border border-line bg-white px-3 text-sm text-ink hover:bg-slate-50 disabled:opacity-60"
            onClick={load}
            disabled={isLoading}
            title="새로고침"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            새로고침
          </button>
          <button
            className="inline-flex h-9 items-center gap-2 rounded border border-line bg-white px-3 text-sm text-ink hover:bg-slate-50 disabled:opacity-60"
            onClick={handleCollection}
            disabled={isCollecting}
            title="수집 실행"
          >
            <Play className="h-4 w-4" />
            수집 실행
          </button>
          <button
            className="inline-flex h-9 items-center gap-2 rounded bg-ink px-3 text-sm text-white disabled:opacity-60"
            onClick={handleRegenerate}
            disabled={isRegenerating}
            title="AI 해석 재생성"
          >
            <Brain className="h-4 w-4" />
            AI 재생성
          </button>
          <button
            className="inline-flex h-9 items-center gap-2 rounded bg-accent px-3 text-sm text-white disabled:opacity-60"
            onClick={handleNewsRegenerate}
            disabled={isRegeneratingNews}
            title="뉴스 분석 재생성"
          >
            <Newspaper className="h-4 w-4" />
            뉴스 분석
          </button>
        </div>
      </div>

      {message && <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-accent">{message}</div>}
      {error && (
        <div className="flex items-center gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-danger">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="grid metric-grid gap-3">
        <Metric label="OK Sources" value={summary.ok} />
        <Metric label="Failed Sources" value={summary.failed} />
        <Metric label="Tracked Sources" value={sources.length} />
        <Metric label="Latest Update" value={formatDateTime(summary.latest)} />
      </div>

      <div className="overflow-hidden rounded border border-line bg-white">
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <ShieldCheck className="h-4 w-4 text-muted" />
          <h3 className="text-sm font-semibold tracking-normal text-ink">Investor Reliability</h3>
        </div>
        <div className="grid gap-0 divide-y divide-line sm:grid-cols-4 sm:divide-y-0">
          <ReliabilityMetric label="Investor-grade sources" value={reliability.investorGrade.length} tone="good" />
          <ReliabilityMetric label="Research-only sources" value={reliability.researchOnly.length} tone="warn" />
          <ReliabilityMetric label="Stale sources" value={reliability.stale.length} tone="warn" />
          <ReliabilityMetric label="Failed sources" value={reliability.failed.length} tone="bad" />
        </div>
      </div>

      <div className="overflow-hidden rounded border border-line bg-white">
        <div className="border-b border-line px-4 py-3">
          <h3 className="text-sm font-semibold tracking-normal text-ink">Source Status</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-[920px] w-full border-collapse text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Source</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">24h Success</th>
                <th className="px-4 py-2 font-medium">Latency</th>
                <th className="px-4 py-2 font-medium">Last Success</th>
                <th className="px-4 py-2 font-medium">Last Failure</th>
                <th className="px-4 py-2 font-medium">Message</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td className="px-4 py-8 text-center text-muted" colSpan={7}>
                    상태 로드 중
                  </td>
                </tr>
              )}
              {!isLoading && sources.length === 0 && (
                <tr>
                  <td className="px-4 py-8 text-center text-muted" colSpan={7}>
                    아직 기록된 source health가 없습니다.
                  </td>
                </tr>
              )}
              {!isLoading &&
                sources.map((source) => (
                  <tr className="border-t border-line align-top hover:bg-slate-50" key={source.source}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 font-semibold text-ink">
                        <Database className="h-4 w-4 text-muted" />
                        {source.source}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="space-y-1">
                        <span
                          className={`rounded px-2 py-1 text-xs font-medium ring-1 ${
                            source.status === "ok"
                              ? "bg-emerald-50 text-accent ring-emerald-200"
                              : "bg-red-50 text-danger ring-red-200"
                          }`}
                        >
                          {source.status}
                        </span>
                        <span className={`block w-fit rounded px-2 py-1 text-xs font-medium ring-1 ${qualityClass(source)}`}>
                          {qualityLabel(source)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 tabular-nums">
                      {source.success_rate_24h === null ? "-" : `${Math.round(source.success_rate_24h * 100)}%`}
                    </td>
                    <td className="px-4 py-3 tabular-nums">{source.latency_ms === null ? "-" : `${Math.round(source.latency_ms)}ms`}</td>
                    <td className="px-4 py-3 text-muted">{formatDateTime(source.last_success_at)}</td>
                    <td className="px-4 py-3 text-muted">{formatDateTime(source.last_failure_at)}</td>
                    <td className="max-w-[360px] px-4 py-3 text-muted">
                      {source.message || "-"}
                      {source.updated_at && <div className="mt-1 text-xs">age {formatAge(sourceAgeSeconds(source.updated_at))}</div>}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
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

function ReliabilityMetric({ label, value, tone }: { label: string; value: number; tone: "good" | "warn" | "bad" }) {
  const className = tone === "good" ? "text-accent" : tone === "warn" ? "text-warn" : "text-danger";
  return (
    <div className="px-4 py-3">
      <p className="text-xs uppercase text-muted">{label}</p>
      <p className={`mt-1 text-xl font-semibold tracking-normal ${className}`}>{value}</p>
    </div>
  );
}

function isResearchOnlySource(source: SourceHealth): boolean {
  const haystack = `${source.source} ${source.message || ""}`.toLowerCase();
  return haystack.includes("demo") || haystack.includes("partial") || haystack.includes("local_fallback") || source.source === "onchain_supply_demo";
}

function sourceAgeSeconds(value: string): number {
  return Math.max(0, (Date.now() - parseApiDate(value).getTime()) / 1000);
}

function qualityLabel(source: SourceHealth): string {
  if (source.status === "failed") return "Unavailable";
  if (isResearchOnlySource(source)) return "Research-only";
  return "Investor-grade";
}

function qualityClass(source: SourceHealth): string {
  if (source.status === "failed") return "bg-slate-50 text-muted ring-slate-200";
  if (isResearchOnlySource(source)) return "bg-amber-50 text-warn ring-amber-200";
  return "bg-emerald-50 text-accent ring-emerald-200";
}
