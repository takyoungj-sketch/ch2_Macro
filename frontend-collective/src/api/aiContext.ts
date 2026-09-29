import type { AiContextPayload, AiPurpose } from "@ch2/ai-assistant/aiClient";
import type {
  AssetType,
  BuildingStatsRow,
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
import { assetTypeLabel, commercialAssetTypeLabel } from "../types";
import type {
  RegionalRegressionPredictResponse,
  RegionalRegressionRunResponse,
} from "./regionalRegressionClient";

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

export function buildCollectiveListContext(opts: {
  regionLabel: string;
  assetType: string;
  windowYears: number;
  total: number;
  first?: BuildingStatsRow | null;
  items?: BuildingStatsRow[] | null;
  sort?: string;
}): AiContextPayload {
  const first = opts.first;
  return {
    app: "collective",
    panel: "BuildingList",
    purpose: "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
      filters: { window_years: opts.windowYears },
    },
    facts: {
      screen: "building_list",
      list_n: opts.total,
      window_years: opts.windowYears,
      region_label: opts.regionLabel,
      list_sort: opts.sort ?? "count",
      visible_rows: (opts.items ?? []).slice(0, 40).map((row) => ({
        name: row.display_name,
        asset_label: assetTypeLabel(row.asset_type),
        count: row.count,
        median: row.median,
        mean: row.mean,
        building_year: row.building_year,
        households: row.households,
      })),
      first_row: first
        ? {
            name: first.display_name,
            asset_label: assetTypeLabel(first.asset_type),
            count: first.count,
            median: first.median,
            mean: first.mean,
            ci_lower: first.ci_lower,
            ci_upper: first.ci_upper,
            is_reliable: first.is_reliable,
            building_year: first.building_year,
            households: first.households,
            extra: first.builder_label ? `시공사 ${first.builder_label}` : undefined,
          }
        : null,
    },
  };
}

export function buildCommercialListContext(opts: {
  regionLabel: string;
  assetType: string;
  windowYears: number;
  total: number;
  first?: {
    display_label?: string | null;
    road_name?: string | null;
    asset_type?: string | null;
    count?: number | null;
    median?: number | null;
    mean?: number | null;
    ci_lower?: number | null;
    ci_upper?: number | null;
    is_reliable?: boolean;
  } | null;
  items?: Array<{
    display_label?: string | null;
    road_name?: string | null;
    asset_type?: string | null;
    count?: number | null;
    median?: number | null;
    mean?: number | null;
  }> | null;
  sort?: string;
}): AiContextPayload {
  const first = opts.first;
  return {
    app: "collective",
    panel: "CommercialList",
    purpose: "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
      filters: { window_years: opts.windowYears },
    },
    facts: {
      screen: "commercial_list",
      list_n: opts.total,
      window_years: opts.windowYears,
      region_label: opts.regionLabel,
      list_sort: opts.sort ?? "count",
      visible_rows: (opts.items ?? []).slice(0, 40).map((row) => ({
        name: row.road_name || row.display_label,
        asset_label: row.asset_type ? commercialAssetTypeLabel(row.asset_type) : undefined,
        count: row.count,
        median: row.median,
        mean: row.mean,
      })),
      first_row: first
        ? {
            name: first.road_name || first.display_label,
            asset_label: first.asset_type
              ? commercialAssetTypeLabel(first.asset_type)
              : undefined,
            count: first.count,
            median: first.median,
            mean: first.mean,
            ci_lower: first.ci_lower,
            ci_upper: first.ci_upper,
            is_reliable: first.is_reliable !== false,
            extra: first.is_reliable === false ? "n<15 (표본 얇음)" : undefined,
          }
        : null,
    },
  };
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

export function buildRegionalRegressionContext(
  data: RegionalRegressionRunResponse,
  opts: {
    regionLabel: string;
    assetType: string;
    tab: "local" | "twin";
    prediction?: RegionalRegressionPredictResponse | null;
  },
): AiContextPayload {
  return {
    app: "collective",
    panel: "RegionalRegressionModal",
    purpose: "statistics",
    scope: {
      region_label: opts.regionLabel,
      asset_type: opts.assetType,
    },
    facts: {
      screen: "regional_regression",
      ran: true,
      tab: opts.tab,
      n: data.n,
      model_type: data.model_type,
      weight_mode: data.weight_mode,
      n_effective: data.n_effective,
      r_squared: data.r_squared,
      adj_r_squared: data.adj_r_squared,
      mape: data.mape,
      hold_mape: data.hold_mape,
      equation: data.equation,
      scope_label: data.scope_label,
      as_of_month: data.as_of_month,
      warnings: data.warnings,
      coefficients: data.coefficients,
      sample: data.sample,
      blocks: data.blocks,
      model_candidates: data.model_candidates ?? [],
      reference_categories: data.reference_categories,
      fitted: data.fitted.slice(0, 40).map((row) => ({
        display_name: row.display_name,
        asset_type: row.asset_type,
        y: row.y,
        y_hat: row.y_hat,
        ape: row.ape,
        households: row.households,
        max_floor: row.max_floor,
        building_age: row.building_age,
        parking_per_household: row.parking_per_household,
        structure_group: row.structure_group,
        builder_group: row.builder_group,
      })),
      prediction: opts.prediction
        ? {
            y_hat: opts.prediction.y_hat,
            unit: opts.prediction.unit,
            ci_lower: opts.prediction.ci_lower,
            ci_upper: opts.prediction.ci_upper,
            pi_lower: opts.prediction.pi_lower,
            pi_upper: opts.prediction.pi_upper,
            model_type: opts.prediction.model_type,
            warnings: opts.prediction.warnings,
          }
        : null,
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
            median: p.median ?? p.mean,
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
