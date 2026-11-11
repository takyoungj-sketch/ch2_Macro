import type { BuiltTransactionRow } from "../types";
import { ALLOCATION_DEFAULTS } from "./allocationDefaults";

export const DEFAULT_MIN_RESIDUAL = 0.1;

export type CostBand = {
  low: number;
  high: number;
  life: number;
  minResidual: number;
};

export type RowOverride = {
  low?: number;
  high?: number;
  life?: number;
  minResidual?: number;
  /** 직접 넣은 잔존연수(년). 있으면 경과년수 대신 잔가율에 쓴다. */
  remainingYears?: number;
};

export type BandMap = Record<string, CostBand>;

export function bandKey(use: string, structure: string): string {
  return `${use}\t${structure}`;
}

export function defaultBands(): BandMap {
  const out: BandMap = {};
  for (const row of ALLOCATION_DEFAULTS) {
    out[bandKey(row.use, row.structure)] = {
      low: row.low,
      high: row.high,
      life: row.life,
      minResidual: DEFAULT_MIN_RESIDUAL,
    };
  }
  return out;
}

export function defaultBand(use: string, structure: string): CostBand | null {
  const row = ALLOCATION_DEFAULTS.find((item) => item.use === use && item.structure === structure);
  if (!row) return null;
  return { low: row.low, high: row.high, life: row.life, minResidual: DEFAULT_MIN_RESIDUAL };
}

type AgeRow = {
  contract_year?: number | null;
  approve_year?: number | null;
  building_age?: number | null;
  building_year?: number | null;
};

/** 실거래 건축연도가 있는지. 대장 사용승인연도는 여기 포함하지 않는다. */
export function hasBuiltYear(row: AgeRow): boolean {
  if (row.building_year != null) return true;
  return row.contract_year != null && row.building_age != null && Number.isFinite(row.building_age);
}

/** 실거래 건축연도를 먼저 쓰고, 없을 때만 대장 사용승인연도로 경과년수를 구한다. */
export function allocationAge(row: AgeRow): { years: number; source: "실거래" | "대장 사용승인" } | null {
  const contract = row.contract_year;
  if (hasBuiltYear(row)) {
    if (row.building_year != null && contract != null) {
      return { years: Math.max(0, contract - row.building_year), source: "실거래" };
    }
    if (row.building_age != null && Number.isFinite(row.building_age)) {
      return { years: Math.max(0, row.building_age), source: "실거래" };
    }
  }
  // 사용승인연도가 계약연도보다 뒤면 그 건물은 계약 당시 없었다 — 0으로 자르지 않고 쓰지 않는다 (F-1).
  if (
    row.approve_year != null &&
    contract != null &&
    row.approve_year >= 1900 &&
    row.approve_year <= 2100 &&
    row.approve_year <= contract
  ) {
    return { years: contract - row.approve_year, source: "대장 사용승인" };
  }
  return null;
}

export function residualRatio(elapsed: number, life: number, minResidual: number): number | null {
  if (!(life > 0) || !Number.isFinite(elapsed) || !Number.isFinite(minResidual)) return null;
  const floor = Math.min(1, Math.max(0, minResidual));
  return Math.max(floor, 1 - elapsed / life);
}

/** 만원, ㎡, 만원/㎡. 토지가액이 음수여도 단가를 그대로 돌려준다. */
export function landUnit(
  price: number,
  grossArea: number,
  landArea: number,
  cost: number,
  residual: number,
): number | null {
  if (!(grossArea > 0) || !(landArea > 0) || !(cost >= 0) || !(residual >= 0) || !Number.isFinite(price)) {
    return null;
  }
  return (price - grossArea * cost * residual) / landArea;
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

/** 구조가 없을 때 그 용도의 구조별 하한·상한을 모아 넓은 범위를 만든다. 내용연수와 최소잔가는 중앙값. */
function envelopeBand(use: string, bands: BandMap): CostBand | null {
  const list = Object.entries(bands)
    .filter(([key]) => key.startsWith(`${use}\t`))
    .map(([, band]) => band);
  if (list.length === 0) return null;
  const lifeMid = median(list.map((band) => band.life));
  const life = Number.isInteger(lifeMid) ? lifeMid : Math.round(lifeMid / 5) * 5;
  return {
    low: Math.min(...list.map((band) => band.low)),
    high: Math.max(...list.map((band) => band.high)),
    life,
    minResidual: median(list.map((band) => band.minResidual)),
  };
}

export function referenceBand(use: string, structure: string, bands: BandMap): CostBand | null {
  if (!use) return null;
  if (structure) return bands[bandKey(use, structure)] ?? null;
  return envelopeBand(use, bands);
}

export type ResolvedBand = {
  band: CostBand | null;
  customized: boolean;
  reason: string | null;
};

export function resolveBand(
  row: Pick<BuiltTransactionRow, "building_use" | "structure_group">,
  bands: BandMap,
  override?: RowOverride | null,
): ResolvedBand {
  const use = row.building_use?.trim() || "";
  const structure = row.structure_group?.trim() || "";
  const base = referenceBand(use, structure, bands);
  const ov = override ?? {};
  const customized =
    ov.low != null || ov.high != null || ov.life != null || ov.minResidual != null || ov.remainingYears != null;
  const low = ov.low ?? base?.low;
  const high = ov.high ?? base?.high;
  const life = ov.life ?? base?.life;
  const minResidual = ov.minResidual ?? base?.minResidual ?? DEFAULT_MIN_RESIDUAL;
  if (low == null || high == null || life == null || life <= 0) {
    if (!use) return { band: null, customized, reason: "용도 없음" };
    if (!base && !structure) return { band: null, customized, reason: "구조 없음" };
    if (!base) return { band: null, customized, reason: "기준 없음" };
    return { band: null, customized, reason: "직접 입력" };
  }
  return {
    band: {
      low: Math.min(low, high),
      high: Math.max(low, high),
      life,
      minResidual,
    },
    customized,
    reason: null,
  };
}

export function formatYearInput(years: number): string {
  const rounded = Math.round(years * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

/** 잔존연수를 직접 넣지 않았을 때의 기본값. 최소잔가율보다 짧아지지 않는다. */
export function defaultRemainingYears(elapsed: number, life: number, minResidual: number): number | null {
  const ratio = residualRatio(elapsed, life, minResidual);
  if (ratio == null) return null;
  return ratio * life;
}

export type AllocationView = {
  elapsed: number | null;
  ageSource: string | null;
  remaining: number | null;
  residual: number;
  landLow: number | null;
  landMid: number | null;
  landHigh: number | null;
  unfitAll: boolean;
};

export type AllocationOutcome =
  | { ok: false; reason: string; customized: boolean }
  | { ok: true; band: CostBand; view: AllocationView; customized: boolean };

export function allocateRow(
  row: BuiltTransactionRow,
  bands: BandMap,
  override?: RowOverride | null,
): AllocationOutcome {
  const resolved = resolveBand(row, bands, override);
  if (!resolved.band) {
    return { ok: false, reason: resolved.reason ?? "직접 입력", customized: resolved.customized };
  }
  const gross = row.gross_area;
  const land = row.land_area;
  if (row.price == null || !(gross != null && gross > 0) || !(land != null && land > 0)) {
    return { ok: false, reason: "금액·면적 없음", customized: resolved.customized };
  }
  const age = allocationAge(row);
  const explicitRemaining = override?.remainingYears;
  let residual: number | null;
  let remaining: number | null;
  if (explicitRemaining != null && Number.isFinite(explicitRemaining)) {
    // 직접 넣은 잔존연수. 최소잔가율은 기본값일 뿐이라 여기서는 쓰지 않는다.
    remaining = Math.min(resolved.band.life, Math.max(0, explicitRemaining));
    residual = remaining / resolved.band.life;
  } else if (!age) {
    residual = Math.min(1, Math.max(0, resolved.band.minResidual));
    remaining = null;
  } else {
    residual = residualRatio(age.years, resolved.band.life, resolved.band.minResidual);
    if (residual == null) return { ok: false, reason: "내용연수 없음", customized: resolved.customized };
    remaining = residual * resolved.band.life;
  }
  const midCost = (resolved.band.low + resolved.band.high) / 2;
  const landHigh = landUnit(row.price, gross, land, resolved.band.low, residual);
  const landMid = landUnit(row.price, gross, land, midCost, residual);
  const landLow = landUnit(row.price, gross, land, resolved.band.high, residual);
  return {
    ok: true,
    band: resolved.band,
    customized: resolved.customized,
    view: {
      elapsed: age?.years ?? null,
      ageSource: age?.source ?? null,
      remaining,
      residual,
      landLow,
      landMid,
      landHigh,
      unfitAll: landHigh != null && landHigh <= 0,
    },
  };
}

export function formatMan(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "부적합";
  return Math.round(value).toLocaleString("ko-KR");
}

export function formatLandRange(view: AllocationView): string {
  const low = formatMan(view.landLow);
  const high = formatMan(view.landHigh);
  return low === high ? high : `${low}~${high}`;
}

export function allocationTitle(outcome: AllocationOutcome): string | undefined {
  if (!outcome.ok) return undefined;
  const { view } = outcome;
  const mid = view.landMid == null ? "부적합" : `${formatMan(view.landMid)}만원/㎡`;
  const residual = `${Math.round(view.residual * 100)}%`;
  if (view.remaining == null) return `기준 ${mid} · 건축연도 없음 · 최종잔가 ${residual}`;
  const elapsed =
    view.elapsed == null
      ? ""
      : `경과 ${Number.isInteger(view.elapsed) ? String(view.elapsed) : view.elapsed.toFixed(1)}년${view.ageSource ? `(${view.ageSource})` : ""} · `;
  return `기준 ${mid} · ${elapsed}잔존 ${formatYearInput(view.remaining)}년 · 잔가 ${residual}`;
}

export function allocationSortValue(
  row: BuiltTransactionRow,
  bands: BandMap,
  override: RowOverride | undefined,
  key: "alloc_cost" | "alloc_life" | "alloc_land",
): number | null {
  const outcome = allocateRow(row, bands, override);
  if (!outcome.ok) return null;
  if (key === "alloc_life") return outcome.band.life;
  if (key === "alloc_cost") return (outcome.band.low + outcome.band.high) / 2;
  return outcome.view.landMid ?? outcome.view.landHigh;
}
