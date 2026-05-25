import type { MatrixYearlyStat } from "../types";

export function yyDotMm(year: number, month: number): string {
  return `${String(year).slice(-2)}.${String(month).padStart(2, "0")}`;
}

function parseLeadingYmd(isoOrDate: string): { y: number; m: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoOrDate.trim());
  if (!m) return null;
  return { y: Number(m[1]), m: Number(m[2]) };
}

/** 롤링·기간 버킷: YY.MM~YY.MM. 레거시 계약연도 모드는 해당 연도 01~12월. */
export function formatMatrixBucketAxisLabel(r: MatrixYearlyStat): string {
  const ps = r.period_start;
  const pe = r.period_end;
  if (
    typeof ps === "string" &&
    typeof pe === "string" &&
    ps.length > 0 &&
    pe.length > 0
  ) {
    const a = parseLeadingYmd(ps);
    const b = parseLeadingYmd(pe);
    if (a && b) return `${yyDotMm(a.y, a.m)}~${yyDotMm(b.y, b.m)}`;
  }
  if (r.year != null && Number.isFinite(Number(r.year))) {
    const y = Number(r.year);
    return `${yyDotMm(y, 1)}~${yyDotMm(y, 12)}`;
  }
  const c = (r.chart_label ?? "").trim();
  if (c) return c;
  if (r.bucket_index != null) return `구간 ${r.bucket_index}`;
  return "—";
}
