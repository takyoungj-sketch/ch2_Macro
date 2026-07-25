import type { CollectiveMapResolveCodesResponse } from "../api/mapClient";

export type ProfileLinkTarget = { level: "sigungu" | "eupmyeondong"; code: string };

/**
 * 지도 resolve-codes 응답을 신규 독립 지역 프로필 앱(/profile/) 대상으로 해석 — D-027 §12.
 * 단일 시군구/읍면동, 또는 동일 읍면동으로 묶이는 법정동 묶음일 때만 해석.
 */
export function resolveCollectiveProfileTarget(
  resolved: CollectiveMapResolveCodesResponse | undefined,
): ProfileLinkTarget | null {
  if (!resolved || !resolved.has_selection || !resolved.level) return null;
  const codes = resolved.selected_codes.filter(Boolean);
  if (codes.length === 0) return null;

  if (resolved.level === "sigungu") {
    if (codes.length !== 1) return null;
    return { level: "sigungu", code: codes[0]! };
  }

  if (resolved.level === "eupmyeondong") {
    if (codes.length !== 1) return null;
    return { level: "eupmyeondong", code: codes[0]! };
  }

  if (resolved.level === "beopjungri") {
    const eupCodes = new Set(codes.map((c) => c.slice(0, 8)));
    if (eupCodes.size !== 1) return null;
    const eup = [...eupCodes][0]!;
    if (!/^\d{8}$/.test(eup)) return null;
    return { level: "eupmyeondong", code: eup };
  }

  return null;
}

export function profileHref(target: ProfileLinkTarget): string {
  return `/profile/?region_level=${target.level}&region_code=${target.code}`;
}
