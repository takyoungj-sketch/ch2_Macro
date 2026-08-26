/** D-051 집합 목록 조인 배지. 상세의 TIER_META 와 같은 축. */

export function collectiveMatchBadge(tier?: string | null): { label: string; tone: "slate" | "amber" } {
  const t = (tier ?? "").trim();
  if (!t || t === "Z") return { label: "미연결", tone: "amber" };
  if (t === "T") return { label: "표제부", tone: "slate" };
  if (t === "A" || t === "B" || t === "C") return { label: "K-apt", tone: "slate" };
  return { label: "조인주의", tone: "amber" };
}
