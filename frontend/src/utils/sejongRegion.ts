import type { RegionItem } from "../types";

/** 세종특별자치시: region_codes 에 시군구 코드가 36110 하나뿐이고 동·면명은 sigungu_name 에 둠. */
export const SEJONG_SIDO_CODE = "36";
export const SEJONG_PSEUDO_SIGUNGU_CODE = "36110";

export function isSejongPseudoSigunguCode(sigunguCode: string): boolean {
  return String(sigunguCode ?? "").trim() === SEJONG_PSEUDO_SIGUNGU_CODE;
}

export function isSejongRegionRow(row: RegionItem): boolean {
  return String(row.sido_code ?? "").trim() === SEJONG_SIDO_CODE;
}

/**
 * 세종 행정동·읍·면: sigungu_name 이 행정 단위명(집현동, 전의면 등)일 때
 * eupmyeondong_code(8자) 하나로 좁힐 수 있으면 반환.
 */
export function uniqueSejongEupCodeForAdminName(
  regions: readonly RegionItem[],
  adminNameNorm: string
): string | null {
  if (!adminNameNorm) return null;
  const eups = new Set<string>();
  for (const row of regions) {
    if (!isSejongRegionRow(row)) continue;
    const sg = String(row.sigungu_name ?? "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "");
    if (sg !== adminNameNorm) continue;
    const ec = String(row.eupmyeondong_code ?? "").trim();
    if (ec) eups.add(ec);
  }
  if (eups.size !== 1) return null;
  return [...eups][0]!;
}

export function normRegionLabel(s: string): string {
  return String(s ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
}
