import type { MatrixYearlyStat } from "../types";

export function yyDotMm(year: number, month: number): string {
  return `${String(year).slice(-2)}.${String(month).padStart(2, "0")}`;
}

function parseLeadingYmd(isoOrDate: string): { y: number; m: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoOrDate.trim());
  if (!m) return null;
  return { y: Number(m[1]), m: Number(m[2]) };
}

/** 롤링·기간 버킷: YY.MM~YY.MM. 계약연도만 있는 레거시 집계는 두 자리 연도 라벨(예 25·26). */
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
    return String(y).slice(-2);
  }
  const c = (r.chart_label ?? "").trim();
  if (c) return c;
  if (r.bucket_index != null) return `구간 ${r.bucket_index}`;
  return "—";
}
