import type { RegionNameInfo } from "./types";

/** 세종특별자치시: region_codes 에 시군구 코드가 36110 하나뿐이고 동·면명은 sigungu_name 에 둠. */
export const SEJONG_SIDO_CODE = "36";
export const SEJONG_PSEUDO_SIGUNGU_CODE = "36110";

export function isSejongPseudoSigunguCode(sigunguCode: string): boolean {
  return String(sigunguCode ?? "").trim() === SEJONG_PSEUDO_SIGUNGU_CODE;
}

export function isSejongRegionRow(row: RegionNameInfo): boolean {
  return String(row.sido_code ?? "").trim() === SEJONG_SIDO_CODE;
}

/**
 * 세종 행정동·읍·면명은 sigungu_name 에 있다.
 * `연동면` 뿐 아니라 `세종특별자치시 연동면` 처럼 시도가 붙은 검색어도 매칭.
 */
export function sejongAdminNameMatchesQuery(
  adminName: string,
  rawQuery: string,
  opts?: { allowContains?: boolean },
): boolean {
  const adminNn = normRegionLabel(adminName);
  const qN = normRegionLabel(rawQuery);
  if (!adminNn || !qN) return false;
  if (adminNn === qN) return true;
  if (adminNn.length >= 2 && qN.endsWith(adminNn)) return true;
  const last = lastTokenNorm(rawQuery);
  if (last && adminNn === last) return true;
  if (opts?.allowContains && adminNn.includes(qN)) return true;
  return false;
}

function lastTokenNorm(rawQuery: string): string {
  const tokens = String(rawQuery ?? "")
    .trim()
    .split(/[\s,，/|]+/)
    .filter(Boolean);
  return normRegionLabel(tokens[tokens.length - 1] ?? "");
}

/**
 * 세종 행정동·읍·면: sigungu_name 이 행정 단위명(집현동, 전의면 등)일 때
 * eupmyeondong_code(8자) 하나로 좁힐 수 있으면 반환.
 */
export function uniqueSejongEupCodeForAdminName(
  regions: readonly RegionNameInfo[],
  adminNameNorm: string,
): string | null {
  if (!adminNameNorm) return null;
  const eups = new Set<string>();
  for (const row of regions) {
    if (!isSejongRegionRow(row)) continue;
    if (
      !sejongAdminNameMatchesQuery(String(row.sigungu_name ?? ""), adminNameNorm, {
        allowContains: false,
      })
    ) {
      continue;
    }
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
