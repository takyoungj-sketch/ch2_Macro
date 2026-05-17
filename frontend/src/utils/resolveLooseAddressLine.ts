import type { RegionItem } from "../types";

function compact(s: string): string {
  return String(s ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
}

function includesLoose(haystack: string, needle: string): boolean {
  const n = needle.trim();
  if (!n) return true;
  const h = compact(haystack);
  const q = compact(n);
  if (!q) return true;
  return h.includes(q);
}

/** 공백·쉼표·슬래시 등으로 토큰 분할 */
export function tokenizeLooseAddressLine(raw: string): string[] {
  return raw
    .split(/[\s,，/|]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** 공백 등으로 여러 지명이 나뉘었거나 10자리 법정코드 1개인 경우 — 전역 카탈로그에서만 좁힘 */
export function isLooseMultiSegmentQuery(raw: string): boolean {
  const tokens = tokenizeLooseAddressLine(raw);
  if (tokens.length >= 2) return true;
  if (tokens.length === 1 && /^\d{10}$/.test(tokens[0]!)) return true;
  return false;
}

/**
 * 한 줄에 여러 지명(예: `흥덕구 가경동`)을 넣었을 때 후보 법정단위를 찾는다.
 * 각 토큰은 시·군구·읍면동·리 이름 중 어딘가와 느슨하게 매칭되어야 한다(동명이인 축소용).
 */
export function resolveBeopjungriFromLooseAddressLine(
  regions: readonly RegionItem[],
  raw: string
): { rows: RegionItem[]; codes: string[] } {
  const tokens = tokenizeLooseAddressLine(raw);
  if (tokens.length === 0) {
    return { rows: [], codes: [] };
  }

  if (tokens.length === 1 && /^\d{10}$/.test(tokens[0]!)) {
    const code = tokens[0]!;
    const rows = regions.filter((r) => String(r.beopjungri_code ?? "").trim() === code);
    const codes = [...new Set(rows.map((r) => String(r.beopjungri_code).trim()))].sort((a, b) =>
      a.localeCompare(b, "ko-KR")
    );
    return { rows, codes };
  }

  const rowMatchesAllTokens = (r: RegionItem): boolean => {
    const fields = [r.sido_name, r.sigungu_name, r.eupmyeondong_name, r.beopjungri_name];
    return tokens.every((t) => fields.some((f) => includesLoose(f ?? "", t)));
  };

  const rows = regions.filter(rowMatchesAllTokens);
  const codes = [...new Set(rows.map((r) => String(r.beopjungri_code).trim()))].sort((a, b) =>
    a.localeCompare(b, "ko-KR")
  );
  return { rows, codes };
}

/**
 * 느슨 매칭으로 모인 행이 전부 같은 읍·면·동 또는 같은 시·군·구에만 속하면
 * Enter로 [읍·면 포함] / [시군구 포함] 칩을 고를 수 있다.
 * 읍·면이 하나로 좁혀지면 시군구보다 읍·면을 우선한다.
 */
export function commonTierCodesFromLooseRows(rows: readonly RegionItem[]): {
  eupmyeondongCode: string | null;
  sigunguCode: string | null;
} {
  if (rows.length === 0) {
    return { eupmyeondongCode: null, sigunguCode: null };
  }
  const eup = new Set(
    rows.map((r) => String(r.eupmyeondong_code ?? "").trim()).filter(Boolean)
  );
  const sig = new Set(
    rows.map((r) => String(r.sigungu_code ?? "").trim()).filter(Boolean)
  );
  return {
    eupmyeondongCode: eup.size === 1 ? [...eup][0]! : null,
    sigunguCode: sig.size === 1 ? [...sig][0]! : null,
  };
}
