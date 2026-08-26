/** 세종 등 시군구(addr2) 없이 시도 → 읍·면·동만 있는 계층 — 백엔드 `FLAT_SIDO_ADDR2_TOKEN` 과 동일 */
export const FLAT_SIDO_ADDR2_TOKEN = "__FLAT_SIDO__";

export function isFlatSidoAddr2(addr2: string | undefined | null): boolean {
  return String(addr2 ?? "").trim() === FLAT_SIDO_ADDR2_TOKEN;
}

export function formatAddr2OptionLabel(value: string): string {
  if (isFlatSidoAddr2(value)) return "읍·면·동 (시군구 없음)";
  return value;
}

export function formatScopeAddr2(addr2: string, _addr1?: string): string {
  if (isFlatSidoAddr2(addr2)) return "";
  return addr2;
}

function sameSidoName(a: string, b: string): boolean {
  const x = a.trim();
  const y = b.trim();
  if (!x || !y) return false;
  return x === y || x.startsWith(y) || y.startsWith(x);
}

/** flat sido 앵커일 때 동일 시도 단위만 __FLAT_SIDO__ — cross-sido 단위 addr2 유지 */
export function resolveUnitAddr2(
  scopeAddr1: string,
  scopeAddr2: string,
  unitAddr1: string,
  unitAddr2: string,
  crossParent: boolean,
): string {
  if (isFlatSidoAddr2(scopeAddr2) && sameSidoName(unitAddr1 || scopeAddr1, scopeAddr1)) {
    return scopeAddr2;
  }
  return unitAddr2 || (crossParent ? "" : scopeAddr2);
}
