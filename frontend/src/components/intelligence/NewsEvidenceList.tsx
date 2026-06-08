import { ExternalLink } from "lucide-react";
import { formatDateTime } from "../../lib/format";
import type { NewsEvidenceItem, NewsImpactPoint, NewsStance } from "../../types";

type Props = {
  impacts: NewsImpactPoint[];
};

export function NewsEvidenceList({ impacts }: Props) {
  const items = impacts.flatMap((impact) =>
    impact.items.map((item) => ({
      ...item,
      score: impact.score,
      impactTime: impact.observed_at
    }))
  );

  return (
    <div className="min-w-0 overflow-hidden rounded border border-line bg-white">
      <div className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold tracking-normal text-ink">Korean News Intelligence</h3>
            <p className="mt-0.5 text-xs text-muted">한국어 요약과 방향성 후보 라벨</p>
          </div>
          <StanceSummary impacts={impacts} />
        </div>
      </div>
      <div className="divide-y divide-line">
        {items.length === 0 && <div className="p-4 text-sm text-muted">관련 뉴스 근거가 없습니다.</div>}
        {items.slice(0, 8).map((item) => (
          <a
            className="block px-4 py-3 hover:bg-slate-50"
            href={item.url}
            key={`${item.url}-${item.impactTime}`}
            rel="noreferrer"
            target="_blank"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded px-2 py-1 text-xs font-medium ring-1 ${stanceClass(item.stance)}`}>{item.stance_label_ko}</span>
                  <span className="text-xs text-muted">confidence {Math.round((item.stance_confidence || 0) * 100)}%</span>
                  <span className="text-xs text-muted">{item.analysis_source}</span>
                </div>
                <p className="mt-2 line-clamp-3 text-sm font-semibold leading-5 text-ink">{item.summary_ko || fallbackSummary(item)}</p>
              </div>
              <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
            </div>
            <p className="mt-2 line-clamp-2 text-sm leading-5 text-muted">{item.reason_ko}</p>
            <p className="mt-2 line-clamp-1 text-xs text-muted">{item.title}</p>
            <p className="mt-1 text-xs text-muted">
              {item.source} · {formatDateTime(item.published_at || item.impactTime)} · 후보 점수 {item.score}/100
            </p>
          </a>
        ))}
      </div>
    </div>
  );
}

function StanceSummary({ impacts }: { impacts: NewsImpactPoint[] }) {
  const counts = impacts.reduce(
    (acc, impact) => {
      Object.entries(impact.stance_counts || {}).forEach(([key, value]) => {
        acc[key as NewsStance] = (acc[key as NewsStance] || 0) + value;
      });
      return acc;
    },
    {
      positive_candidate: 0,
      neutral: 0,
      negative_candidate: 0,
      mixed: 0,
      unavailable: 0
    } as Record<NewsStance, number>
  );
  const summary = [
    ["잠재 호재", counts.positive_candidate],
    ["중립", counts.neutral],
    ["잠재 악재", counts.negative_candidate],
    ["혼재", counts.mixed]
  ];
  return (
    <div className="flex flex-wrap gap-1 text-xs">
      {summary.map(([label, value]) => (
        <span className="rounded bg-slate-50 px-2 py-1 text-muted ring-1 ring-slate-200" key={label}>
          {label} {value}
        </span>
      ))}
    </div>
  );
}

function fallbackSummary(item: NewsEvidenceItem): string {
  return `${item.source}에서 수집된 관련 뉴스 후보입니다. 한국어 분석 캐시가 아직 생성되지 않았습니다.`;
}

function stanceClass(stance: NewsStance): string {
  if (stance === "positive_candidate") return "bg-emerald-50 text-accent ring-emerald-200";
  if (stance === "negative_candidate") return "bg-red-50 text-danger ring-red-200";
  if (stance === "mixed") return "bg-amber-50 text-warn ring-amber-200";
  if (stance === "neutral") return "bg-slate-50 text-muted ring-slate-200";
  return "bg-slate-100 text-muted ring-slate-200";
}
