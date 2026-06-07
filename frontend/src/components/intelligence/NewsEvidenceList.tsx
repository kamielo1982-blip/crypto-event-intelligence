import { ExternalLink } from "lucide-react";
import { formatDateTime } from "../../lib/format";
import type { NewsImpactPoint } from "../../types";

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
        <h3 className="text-sm font-semibold tracking-normal text-ink">News Evidence</h3>
        <p className="mt-0.5 text-xs text-muted">가격 변동 근처에 묶인 관련 뉴스 후보입니다.</p>
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
              <p className="line-clamp-2 text-sm font-medium text-ink">{item.title}</p>
              <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
            </div>
            <p className="mt-1 text-xs text-muted">
              {item.source} · {formatDateTime(item.published_at || item.impactTime)} · 후보 점수 {item.score}/100
            </p>
          </a>
        ))}
      </div>
    </div>
  );
}
