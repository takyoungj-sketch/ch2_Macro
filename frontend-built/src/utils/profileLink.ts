import type { ProfileTwinCandidateNeighbor, ProfileTwinNeighborItem } from "../types";
import type { BuiltAnalysisUnit } from "./builtAnalysisUnits";

export type ProfileLinkTarget = { level: "eupmyeondong" | "sigungu" | "beopjungri"; code: string };

/**
 * 선택된 분석 단위(analysisUnits)를 Profile 앱 대상으로 해석 — D-027/D-030.
 * 단일 beop · 단일 eup(동일 8자) · 그 외 null.
 */
export function resolveBuiltProfileTarget(units: BuiltAnalysisUnit[]): ProfileLinkTarget | null {
  const withCode = units.filter((u) => u.code && !u.crossParent);
  if (withCode.length === 0) return null;

  if (withCode.length === 1) {
    const u = withCode[0]!;
    const digits = u.code.replace(/\D/g, "");
    if (u.level === "beopjungri" && /^\d{10}$/.test(digits)) {
      return { level: "beopjungri", code: digits };
    }
  }

  const eupCodes = new Set(
    withCode.map((u) => {
      const digits = u.code.replace(/\D/g, "");
      return digits.length >= 8 ? digits.slice(0, 8) : digits.padEnd(8, "0").slice(0, 8);
    }),
  );
  if (eupCodes.size !== 1) return null;

  const eup = [...eupCodes][0]!;
  if (!/^\d{8}$/.test(eup)) return null;
  return { level: "eupmyeondong", code: eup };
}

/** Twin 이웃 조회용 앵커 — Profile 링크와 달리 복수 읍면동이면 첫 단위를 쓴다. */
export function resolveTwinAnchor(units: BuiltAnalysisUnit[]): ProfileLinkTarget | null {
  const single = resolveBuiltProfileTarget(units);
  if (single && (single.level === "eupmyeondong" || single.level === "beopjungri")) {
    return single;
  }
  const withCode = units.filter((u) => u.code && !u.crossParent);
  const first = withCode[0];
  if (!first) return null;
  const digits = first.code.replace(/\D/g, "");
  if (first.level === "beopjungri" && digits.length >= 10) {
    return { level: "beopjungri", code: digits.slice(0, 10) };
  }
  if (digits.length >= 8) {
    return { level: "eupmyeondong", code: digits.slice(0, 8) };
  }
  return null;
}

/** Twin 이웃 조회 — Profile 링크가 없어도 region_codes 첫 단위로 앵커를 잡는다. */
export function resolveTwinAnchorFromRequest(opts: {
  profileTarget?: ProfileLinkTarget | null;
  regionCodes?: string[] | null;
  regionCodeLevel?: string | null;
}): ProfileLinkTarget | null {
  const t = opts.profileTarget;
  if (t?.level === "eupmyeondong" || t?.level === "beopjungri") return t;
  const level = (opts.regionCodeLevel || "eupmyeondong").toLowerCase();
  if (level === "sigungu") return null;
  const raw = String(opts.regionCodes?.[0] ?? "").replace(/\D/g, "");
  if (!raw) return null;
  if (level === "beopjungri" && raw.length >= 10) {
    return { level: "beopjungri", code: raw.slice(0, 10) };
  }
  if (raw.length >= 8) {
    return { level: "eupmyeondong", code: raw.slice(0, 8) };
  }
  return null;
}

export function profileHref(target: ProfileLinkTarget): string {
  return `/profile/?region_level=${target.level}&region_code=${target.code}`;
}

/** Profile Twin API 이웃 → 모형 탐색 요청에 실을 후보. 코드 없는 행은 버린다. */
export function mapProfileTwinNeighbors(
  neighbors: ProfileTwinNeighborItem[] | null | undefined,
): ProfileTwinCandidateNeighbor[] {
  if (!neighbors?.length) return [];
  return neighbors
    .map((n) => ({
      region_code: (n.twin_beopjungri_code || n.twin_eupmyeondong_code || "").trim(),
      similarity_score: n.similarity_score,
      detail_scores: n.detail_scores ?? null,
    }))
    .filter((n) => n.region_code);
}
