import type { AiContextPayload, AiPurpose } from "@ch2/ai-assistant/aiClient";
import type {
  AssetType,
  CollectiveRegressionResponse,
  CommercialFloorIndexResponse,
  CommercialHistogramResponse,
  CommercialRegressionResponse,
  CohortRegressionResponse,
  FloorIndexResponse,
  HistogramResponse,
  CohortFloorIndexResponse,
  CohortHistogramResponse,
  RollingStatPoint,
  RollingStatsResponse,
  YearlyStatPoint,
  YearlyStatsResponse,
} from "../types";

function rollingPointsToRows(points: RollingStatPoint[]) {
  return points.map((p) => ({
    chart_label: p.label,
    bucket_index: p.bucket_index,
    count: p.count,
    mean: p.mean,
    mean_unit_price_per_sqm: p.mean,
  }));
}

function yearlyPointsToRows(points: YearlyStatPoint[]) {
  return points.map((p) => ({
    year: p.year,
    count: p.count,
    mean: p.mean,
    mean_unit_price_per_sqm: p.mean,
  }));
}

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

export function buildCollectiveFloorIndexContext(
  data: FloorIndexResponse | CohortFloorIndexResponse,
  opts: {
    regionLabel: string;
    assetType: AssetType;
    cohort?: boolean;
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "FloorIndexPanel",
    purpose: opts.purpose ?? "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      ...data,
      n: data.n_regression ?? data.n_total,
      cohort: opts.cohort ?? false,
    },
  };
}

export function buildCollectiveRollingTrendContext(
  data: RollingStatsResponse,
  opts: {
    regionLabel: string;
    assetType: AssetType;
    cohort?: boolean;
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "TrendCard",
    purpose: opts.purpose ?? "market_analysis",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      rows: rollingPointsToRows(data.points),
      window_years: data.window_years,
      trend_kind: "rolling",
      cohort: opts.cohort ?? false,
    },
  };
}

export function buildCollectiveCohortRollingTrendContext(
  items: RollingStatsResponse[],
  opts: {
    regionLabel: string;
    assetType: AssetType;
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "TrendCard",
    purpose: opts.purpose ?? "market_analysis",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      series: items.map((item) => ({
        label: item.display_name,
        points: item.points.map((p) => ({
          year: p.label,
          count: p.count,
          mean: p.mean,
          median: p.mean,
        })),
      })),
      trend_kind: "rolling",
      cohort: true,
    },
  };
}

export function buildCollectiveYearlyTrendContext(
  data: YearlyStatsResponse | YearlyStatPoint[],
  opts: {
    regionLabel: string;
    assetType: AssetType;
    cohort?: boolean;
    purpose?: AiPurpose;
  },
): AiContextPayload {
  const points = Array.isArray(data) ? data : data.points;
  return {
    app: "collective",
    panel: "LongTermTrendPanel",
    purpose: opts.purpose ?? "market_analysis",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      series: [
        {
          points: points.map((p) => ({
            year: p.year,
            count: p.count,
            mean: p.mean,
            median: p.mean,
          })),
        },
      ],
      trend_kind: "long_term",
      cohort: opts.cohort ?? false,
    },
  };
}

export function buildCollectiveHistogramContext(
  data: HistogramResponse | CohortHistogramResponse,
  opts: {
    regionLabel: string;
    assetType: AssetType;
    cohort?: boolean;
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "HistogramPanel",
    purpose: opts.purpose ?? "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      ...data,
      cohort: opts.cohort ?? false,
    },
  };
}

export function buildCommercialRegressionContext(
  regData: CommercialRegressionResponse,
  opts: {
    regionLabel: string;
    assetType: "collective_shop" | "collective_factory";
    purpose?: AiPurpose;
    cohort?: boolean;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "CommercialRegressionPanel",
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

export function buildCommercialFloorIndexContext(
  data: CommercialFloorIndexResponse,
  opts: {
    regionLabel: string;
    assetType: "collective_shop" | "collective_factory";
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "CommercialFloorIndexPanel",
    purpose: opts.purpose ?? "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      ...data,
      n: data.n_regression ?? data.n_total,
    },
  };
}

export function buildCommercialYearlyTrendContext(
  points: YearlyStatPoint[],
  opts: {
    regionLabel: string;
    assetType: "collective_shop" | "collective_factory";
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "TrendCard",
    purpose: opts.purpose ?? "market_analysis",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      rows: yearlyPointsToRows(points),
      trend_kind: "yearly",
    },
  };
}

export function buildCommercialHistogramContext(
  data: CommercialHistogramResponse,
  opts: {
    regionLabel: string;
    assetType: "collective_shop" | "collective_factory";
    purpose?: AiPurpose;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "HistogramPanel",
    purpose: opts.purpose ?? "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      ...data,
    },
  };
}
