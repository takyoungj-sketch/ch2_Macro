import type { CollectiveMapResolveCodesResponse } from "../api/mapClient";
import type { CollectiveAnalysisUnit } from "./collectiveAnalysisUnits";

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

/** 분석 단위(analysisUnits) 기준 — 복합 resolveBuiltProfileTarget 과 동일. */
export function resolveCollectiveProfileTargetFromUnits(
  units: CollectiveAnalysisUnit[],
): ProfileLinkTarget | null {
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

export function profileHref(target: ProfileLinkTarget): string {
  return `/profile/?region_level=${target.level}&region_code=${target.code}`;
}
