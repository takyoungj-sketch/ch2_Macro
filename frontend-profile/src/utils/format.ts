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
 * ㎡당 단가(만원/㎡) 표시.
 * 토지·집합 mart UI와 동일하게 만원/㎡ 단위를 사용한다.
 * (거래액 `formatAmountManwon`의 억원 변환과 혼동하지 않음)
 */
export function formatUnitPrice(manwonPerSqm: number | null | undefined): string {
  if (manwonPerSqm === null || manwonPerSqm === undefined || Number.isNaN(manwonPerSqm)) return "-";
  const rounded = Math.round(manwonPerSqm * 10) / 10;
  const str = Number.isInteger(rounded)
    ? rounded.toLocaleString("ko-KR")
    : rounded.toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${str}만원/㎡`;
}

export function formatYoy(pct: number | null | undefined): string {
  if (pct === null || pct === undefined || Number.isNaN(pct)) return "-";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

/** 순위표 인구 — 1만 이상이면 N만 */
export function formatPopMan(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n) || n <= 0) return "—";
  if (n >= 10_000) {
    const man = n / 10_000;
    const digits = man >= 100 ? 0 : 1;
    const s = man.toFixed(digits).replace(/\.0$/, "");
    return `${s}만`;
  }
  return Math.round(n).toLocaleString("ko-KR");
}

/** 만원 → 1조 이상이면 N조, 아니면 억원 */
export function formatAmountCompact(manwon: number | null | undefined): string {
  if (manwon === null || manwon === undefined || Number.isNaN(manwon)) return "—";
  const jo = manwon / 100_000_000;
  if (Math.abs(jo) >= 1) {
    const digits = Math.abs(jo) >= 100 ? 0 : 1;
    return `${jo.toFixed(digits).replace(/\.0$/, "")}조`;
  }
  return formatAmountManwon(manwon);
}

/** 3년 총액(만원) ÷ 인구 → 인당 */
export function formatAmountPerCapita(manwon: number, population: number | null | undefined): string {
  if (population === null || population === undefined || population <= 0) return "—";
  const per = manwon / population;
  if (per >= 10_000) {
    const eok = per / 10_000;
    const digits = eok >= 100 ? 0 : 1;
    return `${eok.toFixed(digits).replace(/\.0$/, "")}억원/인`;
  }
  const digits = per >= 100 ? 0 : 1;
  return `${per.toFixed(digits).replace(/\.0$/, "")}만원/인`;
}

/** '서울 역삼동 역삼동' → '서울 역삼동' */
export function dedupeRegionLabel(name: string): string {
  const out: string[] = [];
  for (const p of name.split(/\s+/).filter(Boolean)) {
    if (out[out.length - 1] !== p) out.push(p);
  }
  return out.join(" ");
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
