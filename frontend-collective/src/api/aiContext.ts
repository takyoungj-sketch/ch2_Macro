import type { AiContextPayload, AiPurpose } from "@ch2/ai-assistant/aiClient";
import type { AssetType, CollectiveRegressionResponse, CohortRegressionResponse } from "../types";

export function buildCollectiveRegressionContext(
  regData: CollectiveRegressionResponse | CohortRegressionResponse,
  opts: {
    regionLabel: string;
    assetType: AssetType;
    cohort?: boolean;
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "BuildingRegressionPanel",
    purpose: opts.purpose ?? "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      ...regData,
      cohort: opts.cohort ?? false,
    },
  };
}
