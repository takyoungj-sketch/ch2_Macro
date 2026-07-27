import type { CollectiveMapResolveCodesResponse } from "../api/mapClient";

export type ProfileLinkTarget = { level: "sigungu" | "eupmyeondong" | "beopjungri"; code: string };

/**
 * 지도 resolve-codes 응답을 Profile 앱 대상으로 해석 — D-027/D-030.
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
    if (codes.length !== 1) return null;
    const code = codes[0]!.replace(/\D/g, "");
    if (!/^\d{10}$/.test(code)) return null;
    return { level: "beopjungri", code };
  }

  return null;
}

export function profileHref(target: ProfileLinkTarget): string {
  return `/profile/?region_level=${target.level}&region_code=${target.code}`;
}
