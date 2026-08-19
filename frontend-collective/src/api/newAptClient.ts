/** 신규아파트 트랙 A 실험 — 기존 건물 회귀와 분리. */

import { api } from "./client";

export type NewAptCoef = {
  name: string;
  coef: number;
  se: number | null;
  t: number | null;
  p: number | null;
  plain: string | null;
};

export type NewAptSpecRow = {
  track: string;
  product: string;
  location: string;
  sample: string;
  n_train: number;
  n_train_buildings?: number;
  adj_r_squared: number | null;
  holdout_mae: number | null;
  holdout_mape: number | null;
  n_holdout: number;
  land_coef: number | null;
  equation?: string;
  coefficients?: NewAptCoef[];
  warnings?: string[];
  is_baseline?: boolean;
};

export type NewAptCell = {
  building_key: string;
  display_name?: string | null;
  calendar_year: number | null;
  sigungu_code: string | null;
  sigungu_name?: string | null;
  y: number | null;
  yhat: number | null;
  residual: number | null;
  ape: number | null;
  land_p50: number | null;
  land_n: number | null;
  zone_compact: string | null;
  zone_resolution: string;
  uqa_label: string | null;
  households: number | null;
  max_floor: number | null;
  parking_per_household: number | null;
  vintage: string | null;
  age: number | null;
  n_tx: number | null;
  builder_group: string | null;
  attr_quality_flags: string | null;
  in_holdout: boolean;
  in_m2: boolean;
  outlier_y: boolean;
  outlier_ape: boolean;
};

export type NewAptValRow = {
  group: string;
  label?: string;
  n_train: number;
  n_hold: number;
  n_hold_buildings?: number;
  mae: number | null;
  mape: number | null;
  land_coef: number | null;
  skipped?: boolean;
  reason?: string | null;
};

export type NewAptExperiment = {
  sido_code: string | null;
  sido_name: string | null;
  baseline: string;
  baseline_role: string;
  land_join: {
    n_cells: number;
    n_buildings?: number;
    n_land: number;
    land_join_pct: number;
    n_missing_land: number;
    n_thin_land: number;
    zone_resolution?: Record<string, number>;
    note?: string;
  };
  land_dispersion: {
    land_cv_daejeon?: number | null;
    land_cv_mean_within_eup?: number | null;
    land_cv_mean_within_sigungu?: number | null;
    n_eup_with_3plus?: number;
    note?: string;
  };
  comparison: { table: NewAptSpecRow[] };
  m2: NewAptSpecRow;
  cells: NewAptCell[];
  cell_summary: {
    n_cells: number;
    n_m2: number;
    n_holdout_cells: number;
    n_outlier_y: number;
    n_outlier_ape: number;
    ape_outlier_threshold: number;
  };
  validation: {
    random_new_buildings: {
      label: string;
      mae: number | null;
      mape: number | null;
      n_hold: number | null;
      n_hold_buildings?: number;
    };
    leave_one_gu: NewAptValRow[];
    leave_one_gu_pooled_mape: number | null;
    leave_one_year: NewAptValRow[];
    latest_year: NewAptValRow | null;
    year_holdout_note?: string;
  };
  notes: string[];
  error_audit?: {
    n_m2_buildings: number;
    n_review_buildings: number;
    repeat_min: number;
    buildings: {
      building_key: string;
      display_name?: string | null;
      sigungu_name?: string | null;
      n_years: number;
      median_ape: number;
      max_ape: number;
      direction: string;
      households?: number | null;
      vintage?: string | null;
      age_min?: number | null;
      zone_compact?: string | null;
      land_n_min?: number | null;
      in_holdout: boolean;
      is_new: boolean;
      tags: string[];
    }[];
    patterns: {
      tag: string;
      label: string;
      bucket: string;
      n_buildings: number;
      n_holdout: number;
      n_new_train: number;
      n_old: number;
      repeat: boolean;
      action: string;
      examples: { display_name?: string; median_ape: number; sigungu_name?: string; in_holdout: boolean }[];
    }[];
    next_variable_candidates: string[];
    data_fix_candidates: string[];
    notes: string[];
    decision?: {
      baseline_locked: boolean;
      baseline: string;
      open_next_variable: boolean;
      verdict: string;
      data_fixes: string[];
      next_step: string;
      builder_vs_brand: string;
    };
    large_new_watch?: {
      pattern: string;
      n_buildings: number;
      n_builders: number;
      n_brands: number;
      n_sigungu: number;
      mean_ape: number | null;
      direction_underpred_pct: number | null;
      builders: string[];
      brands: string[];
      ready_for_builder_layer: boolean;
      gate: { repeat_min: number; min_sigungu: number; min_builders: number; note: string };
      members: {
        building_key: string;
        display_name?: string | null;
        sigungu_name?: string | null;
        median_ape?: number;
        households?: number | null;
        builder_group?: string | null;
        brand?: string | null;
        in_holdout?: boolean;
      }[];
      history: {
        as_of: string;
        n_buildings: number;
        n_builders: number;
        n_brands: number;
        n_sigungu: number;
        mean_ape: number | null;
        ready_for_builder_layer?: boolean;
      }[];
    };
    data_fix_sensitivity?: {
      label: string;
      n_train: number | null;
      n_dropped: number;
      adj_r_squared: number | null;
      holdout_mape: number | null;
      baseline_holdout_mape: number | null;
      delta_mape: number | null;
      replaces_baseline: boolean;
      note: string;
    };
  };
};

export async function fetchNewAptExperiment(sidoCode = "30"): Promise<NewAptExperiment> {
  const { data } = await api.get<NewAptExperiment>("/analysis/new-apt/experiment", {
    params: { sido_code: sidoCode },
  });
  return data;
}

export type NewAptFocusCoef = {
  coef: number | null;
  t: number | null;
  p: number | null;
  sign: string | null;
};

export type NewAptRegionModel = {
  id: string;
  region: string;
  purpose: string;
  location: string;
  product?: string;
  n_train: number;
  n_train_buildings?: number;
  n_hold_buildings?: number;
  hold_scope?: string;
  adj_r_squared: number | null;
  holdout_mae: number | null;
  holdout_mape: number | null;
  n_holdout: number;
  land_coef: number | null;
  households_coef?: number | null;
  floor_coef?: number | null;
  parking_coef?: number | null;
  focus?: Record<string, NewAptFocusCoef>;
  warnings?: string[];
  is_baseline?: boolean;
  primary_pool?: boolean;
};

export type NewAptRegionCompare = {
  baseline: string;
  baseline_status: string;
  baseline_role: string;
  adopt_pooled: boolean;
  samples: {
    daejeon?: { n_cells: number; n_buildings: number; n_land: number; land_join_pct: number; n_sigungu?: number };
    chungbuk?: { n_cells: number; n_buildings: number; n_land: number; land_join_pct: number; n_sigungu?: number };
  };
  models: NewAptRegionModel[];
  transfer: {
    n_hold_buildings: number;
    n_hold_cells: number;
    rows: { model_id: string; train: string; test: string; mape: number | null; mae?: number | null; n_hold?: number }[];
    verdict: {
      code: string;
      delta_mape: number | null;
      improves_daejeon: boolean;
      adopt_pooled: boolean;
      summary: string;
    };
    misleading_overall?: {
      label: string;
      mape: number | null;
      n_hold?: number;
      n_hold_buildings?: number;
      note?: string;
    };
  };
  next_steps: string[];
  notes: string[];
};

export async function fetchNewAptRegionCompare(): Promise<NewAptRegionCompare> {
  const { data } = await api.get<NewAptRegionCompare>("/analysis/new-apt/region-compare");
  return data;
}
