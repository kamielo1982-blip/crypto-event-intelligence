export function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  if (Math.abs(value) >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (Math.abs(value) >= 1) return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  return `$${value.toPrecision(3)}`;
}

export function formatKrw(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  if (Math.abs(value) >= 1_000_000_000_000) return `₩${(value / 1_000_000_000_000).toFixed(2)}T`;
  if (Math.abs(value) >= 1_000_000_000) return `₩${(value / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(value) >= 1_000_000) return `₩${(value / 1_000_000).toFixed(2)}M`;
  return `₩${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function severityClass(severity: string): string {
  if (severity === "high") return "bg-red-50 text-danger ring-red-200";
  if (severity === "medium") return "bg-amber-50 text-warn ring-amber-200";
  return "bg-emerald-50 text-accent ring-emerald-200";
}
