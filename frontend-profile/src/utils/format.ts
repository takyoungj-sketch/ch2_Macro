export function formatInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return Math.round(n).toLocaleString("ko-KR");
}

export function formatPercent(ratio: number | null | undefined, digits = 1): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return "-";
  return `${(ratio * 100).toFixed(digits)}%`;
}

/**
 * 만원 → 억원 표시.
 * 천만(0.1억) 단위로 반올림한 뒤 "N억원" / "N.N억원".
 */
export function formatAmountManwon(manwon: number | null | undefined): string {
  if (manwon === null || manwon === undefined || Number.isNaN(manwon)) return "-";
  return `${formatEokNumber(manwonToEokTenths(manwon))}억원`;
}

/**
 * 만원/㎡ 단가 → 억원/㎡ 표시.
 * 거래액과 동일하게 천만 단위 반올림.
 */
export function formatUnitPrice(manwonPerSqm: number | null | undefined): string {
  if (manwonPerSqm === null || manwonPerSqm === undefined || Number.isNaN(manwonPerSqm)) return "-";
  return `${formatEokNumber(manwonToEokTenths(manwonPerSqm))}억원/㎡`;
}

export function formatYoy(pct: number | null | undefined): string {
  if (pct === null || pct === undefined || Number.isNaN(pct)) return "-";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

/** 만원 → 0.1억(천만) 단위 정수. 예: 12,550만원 → 13 (1.3억) */
function manwonToEokTenths(manwon: number): number {
  return Math.round(manwon / 1000);
}

/** 0.1억 단위 정수 → "1,234" 또는 "1,234.5" */
function formatEokNumber(eokTenths: number): string {
  const sign = eokTenths < 0 ? "-" : "";
  const abs = Math.abs(eokTenths);
  const whole = Math.floor(abs / 10);
  const frac = abs % 10;
  const wholeStr = whole.toLocaleString("ko-KR");
  if (frac === 0) return `${sign}${wholeStr}`;
  return `${sign}${wholeStr}.${frac}`;
}
