import type { BuiltAnalysisUnit } from "./builtAnalysisUnits";

export type ProfileLinkTarget = { level: "eupmyeondong" | "sigungu"; code: string };

/**
 * 선택된 분석 단위(analysisUnits)를 신규 독립 지역 프로필 앱(/profile/) 대상으로 해석 — D-027 §12.
 * 단일 읍면동(또는 동일 읍면동으로 묶이는 법정동·리 묶음)일 때만 해석, 그 외(교차 시군구·복수 읍면동)는 null.
 */
export function resolveBuiltProfileTarget(units: BuiltAnalysisUnit[]): ProfileLinkTarget | null {
  const withCode = units.filter((u) => u.code && !u.crossParent);
  if (withCode.length === 0) return null;

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
