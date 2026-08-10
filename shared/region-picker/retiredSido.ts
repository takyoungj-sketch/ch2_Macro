/** 2026-07-01 전남광주 통합 — UI·검색에서 제외할 구 시도 (sido 12 = 전남광주통합특별시). */

export const RETIRED_SIDO_CODES = new Set(["29", "46"]);
export const RETIRED_SIDO_NAMES = new Set(["광주광역시", "전라남도"]);

export function isRetiredSidoCode(code: string | null | undefined): boolean {
  return RETIRED_SIDO_CODES.has(String(code ?? "").trim());
}

export function isRetiredSidoName(name: string | null | undefined): boolean {
  return RETIRED_SIDO_NAMES.has(String(name ?? "").trim());
}
