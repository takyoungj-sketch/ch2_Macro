import type { AiContextPayload } from "@ch2/ai-assistant/aiClient";
import type {
  LandRegressionPredictResponse,
  LandRegressionResponse,
  LongTermTrendResponse,
  MatrixCell,
  MatrixYearlyStat,
  StatsResult,
} from "../types";

export function buildLandRegressionContext(
  regData: LandRegressionResponse,
  opts: {
    regionLabel: string;
    zoneType: string;
    landCategory: string;
    modelType: "log" | "linear";
  },
): AiContextPayload {
  return {
    app: "land",
    panel: "LandRegressionTab",
    purpose: "statistics",
    scope: { region_label: opts.regionLabel },
    facts: {
      ...regData,
      zone_type: opts.zoneType,
      land_category: opts.landCategory,
      model_type: opts.modelType,
    },
  };
}

export function buildLandScatterContext(
  regData: LandRegressionResponse,
  opts: {
    regionLabel: string;
    zoneType: string;
    landCategory: string;
    activeTab?: "raw" | "partial";
  },
): AiContextPayload {
  return {
    app: "land",
    panel: "LandRegressionTab",
    purpose: "statistics",
    scope: { region_label: opts.regionLabel },
    facts: {
      ...(regData as unknown as Record<string, unknown>),
      zone_type: opts.zoneType,
      land_category: opts.landCategory,
      scatter_tab: opts.activeTab ?? "raw",
      unit: "만원/㎡",
    },
  };
}

export function buildLandPredictionContext(
  predict: LandRegressionPredictResponse,
  opts: {
    regionLabel: string;
    regressionN: number;
    adjR2: number;
  },
): AiContextPayload {
  return {
    app: "land",
    panel: "LandPredict",
    purpose: "statistics",
    scope: { region_label: opts.regionLabel },
    facts: {
      ...predict,
      unit: "만원/㎡",
      regression_n: opts.regressionN,
      adj_r_squared: opts.adjR2,
    },
  };
}

export function buildLandMatrixTrendContext(
  rows: MatrixYearlyStat[],
  opts: {
    regionLabel: string;
    zoneType: string;
    landCategory: string;
  },
): AiContextPayload {
  return {
    app: "land",
    panel: "TrendCard",
    purpose: "market_analysis",
    scope: { region_label: opts.regionLabel },
    facts: {
      rows,
      zone_type: opts.zoneType,
      land_category: opts.landCategory,
    },
  };
}

export function buildLandLongTermContext(
  data: LongTermTrendResponse,
  opts: { regionLabel: string },
): AiContextPayload {
  return {
    app: "land",
    panel: "TrendCard",
    purpose: "market_analysis",
    scope: { region_label: opts.regionLabel },
    facts: data as unknown as Record<string, unknown>,
  };
}

function sortLabelsByCount(
  labels: string[],
  totals: Record<string, StatsResult>,
  fallbackCount: (label: string) => number,
): string[] {
  return [...labels].sort((a, b) => {
    const countDiff =
      (totals[b]?.count ?? fallbackCount(b)) -
      (totals[a]?.count ?? fallbackCount(a));
    return countDiff || a.localeCompare(b, "ko-KR");
  });
}

/** 표와 같이 거래수 순 행·열의 (1,1)칸. 비어 있으면 거래수 최대 칸. */
export function pickLandMatrixTopCell(
  matrix: MatrixCell[],
  byZone: Record<string, StatsResult> = {},
  byLandCategory: Record<string, StatsResult> = {},
): {
  zone_type: string;
  land_category: string;
  stats: StatsResult;
  is_top_left: boolean;
} | null {
  const cells = matrix.filter((cell) => cell.stats != null);
  if (cells.length === 0) return null;
  const zones = sortLabelsByCount(
    Array.from(new Set(cells.map((cell) => cell.zone_type))),
    byZone,
    (label) =>
      cells
        .filter((cell) => cell.zone_type === label)
        .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0),
  );
  const cats = sortLabelsByCount(
    Array.from(new Set(cells.map((cell) => cell.land_category))),
    byLandCategory,
    (label) =>
      cells
        .filter((cell) => cell.land_category === label)
        .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0),
  );
  const zone = zones[0];
  const cat = cats[0];
  const topLeft = cells.find(
    (cell) => cell.zone_type === zone && cell.land_category === cat,
  );
  if (topLeft?.stats && topLeft.stats.count > 0) {
    return {
      zone_type: topLeft.zone_type,
      land_category: topLeft.land_category,
      stats: topLeft.stats,
      is_top_left: true,
    };
  }
  const richest = [...cells].sort(
    (a, b) => (b.stats?.count ?? 0) - (a.stats?.count ?? 0),
  )[0];
  if (!richest?.stats || richest.stats.count <= 0) return null;
  return {
    zone_type: richest.zone_type,
    land_category: richest.land_category,
    stats: richest.stats,
    is_top_left: false,
  };
}

export function buildLandMatrixOverviewContext(opts: {
  regionLabel: string;
  windowYears: number;
  txCount: number;
  matrixMode?: "category" | "group";
  matrix?: MatrixCell[];
  byZone?: Record<string, StatsResult>;
  byLandCategory?: Record<string, StatsResult>;
}): AiContextPayload {
  const picked = pickLandMatrixTopCell(
    opts.matrix ?? [],
    opts.byZone,
    opts.byLandCategory,
  );
  const topCell = picked
    ? {
        zone_type: picked.zone_type,
        land_category: picked.land_category,
        is_top_left: picked.is_top_left,
        count: picked.stats.count,
        mean: picked.stats.mean,
        std: picked.stats.std ?? null,
        median: picked.stats.median,
        min: picked.stats.min,
        p25: picked.stats.p25,
        p75: picked.stats.p75,
        max: picked.stats.max,
        ci_lower: picked.stats.ci_lower,
        ci_upper: picked.stats.ci_upper,
        is_reliable: picked.stats.is_reliable,
      }
    : null;
  return {
    app: "land",
    panel: "PaidMatrixCell",
    purpose: "statistics",
    scope: { region_label: opts.regionLabel },
    facts: {
      screen: "land_matrix",
      region_label: opts.regionLabel,
      window_years: opts.windowYears,
      tx_count: opts.txCount,
      matrix_mode: opts.matrixMode ?? "category",
      top_cell: topCell,
    },
  };
}
