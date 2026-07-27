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

export function profileHref(target: ProfileLinkTarget): string {
  return `/profile/?region_level=${target.level}&region_code=${target.code}`;
}
