import type { AiContextPayload, AiPurpose } from "@ch2/ai-assistant/aiClient";
import type {
  RegressionCompareResponse,
  RegressionPredictResponse,
  RegressionRunResponse,
  RegressionSuggestResponse,
} from "../types";

export function buildBuiltModelSelectionContext(
  data: RegressionSuggestResponse | RegressionCompareResponse,
  opts: {
    regionLabel: string;
    assetType: string;
    mode: "suggest" | "compare";
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "built",
    panel: "ModelSelectionCard",
    purpose: opts.purpose ?? "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      ...(data as unknown as Record<string, unknown>),
      selection_mode: opts.mode,
    },
  };
}

export function buildBuiltScatterContext(
  regData: RegressionRunResponse,
  opts: {
    regionLabel: string;
    assetType: string;
    responseScale?: "log" | "linear";
    activeTab?: "raw" | "partial";
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "built",
    panel: "RegressionScatterCard",
    purpose: opts.purpose ?? "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      ...(regData as unknown as Record<string, unknown>),
      response_scale: opts.responseScale ?? "linear",
      scatter_tab: opts.activeTab ?? "raw",
    },
  };
}

export function buildBuiltRegressionContext(
  regData: RegressionRunResponse,
  opts: {
    regionLabel: string;
    assetType: string;
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "built",
    panel: "RegressionCard",
    purpose: opts.purpose ?? "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: regData as unknown as Record<string, unknown>,
  };
}

export function buildBuiltPredictionContext(
  predict: RegressionPredictResponse,
  opts: {
    regionLabel: string;
    assetType: string;
    regressionN?: number;
    adjR2?: number | null;
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "built",
    panel: "PredictionCard",
    purpose: opts.purpose ?? "prediction",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      ...predict,
      regression_n: opts.regressionN,
      adj_r_squared: opts.adjR2 ?? undefined,
    },
  };
}
