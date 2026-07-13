import type { AiContextPayload } from "@ch2/ai-assistant/aiClient";
import type {
  LandRegressionPredictResponse,
  LandRegressionResponse,
  LongTermTrendResponse,
  MatrixYearlyStat,
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
    panel: "PaidMatrixCell",
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
