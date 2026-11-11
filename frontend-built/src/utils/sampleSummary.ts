import type { SampleBreakdown } from "../types";

/**
 * B-04: 「조회 → 제외(사유별) → 최종」 한 줄. 표본 구성(funnel)과 같은 숫자를 쓴다.
 * 예: 조회 376건 → 제외 84건(연식 결측 84) → 최종 292건 · 대장 보강 연식 36건
 */
export function sampleSummaryLine(sample?: SampleBreakdown | null, extra: string[] = []): string | null {
  if (!sample) return null;
  const fmt = (n: number) => n.toLocaleString("ko-KR");
  const steps = sample.funnel ?? [];
  const drops = steps.filter(s => s.kind === "drop" && s.n > 0);
  const reasons = drops.flatMap(s => (s.reasons?.length ? s.reasons.map(r => `${r.label} ${fmt(r.n)}`) : [`${s.label} ${fmt(s.n)}`]));
  const dropped = drops.reduce((acc, s) => acc + s.n, 0);
  const parts = [`조회 ${fmt(sample.n_pool)}건`];
  parts.push(dropped ? `제외 ${fmt(dropped)}건(${reasons.join(", ")})` : "제외 없음");
  parts.push(`최종 ${fmt(sample.n_fit)}건`);
  const infos = steps.filter(s => s.kind === "info" && s.n > 0).map(s => `${s.label} ${fmt(s.n)}건`);
  return [parts.join(" → "), ...infos, ...extra].join(" · ");
}
