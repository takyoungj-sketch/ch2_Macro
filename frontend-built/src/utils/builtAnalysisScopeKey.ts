import type { RegressionRunRequest } from "../types";

/** 변수·스케일 제외 — 채택으로 식이 바뀌어도 Macro 탐색을 유지하기 위한 키 */
export function builtAnalysisScopeKey(body: RegressionRunRequest): string {
  return JSON.stringify({
    asset_type: body.asset_type,
    addr1: body.addr1 ?? "",
    addr2: body.addr2 ?? "",
    addr3: body.addr3 ?? "",
    addr3_list: body.addr3_list ?? [],
    addr4_list: body.addr4_list ?? [],
    ri_list: body.ri_list ?? [],
    region_codes: body.region_codes ?? [],
    region_code_level: body.region_code_level ?? "",
    region_addrs: body.region_addrs ?? [],
    contract_year_from: body.contract_year_from ?? null,
    contract_year_to: body.contract_year_to ?? null,
    as_of_month: body.as_of_month ?? "",
    window_years: body.window_years ?? null,
    zone_types: body.zone_types ?? [],
    building_uses: body.building_uses ?? [],
    road_width_labels: body.road_width_labels ?? [],
    gross_area_min: body.gross_area_min ?? null,
    gross_area_max: body.gross_area_max ?? null,
    land_area_min: body.land_area_min ?? null,
    land_area_max: body.land_area_max ?? null,
    building_age_min: body.building_age_min ?? null,
    building_age_max: body.building_age_max ?? null,
    exclude_outliers_iqr: body.exclude_outliers_iqr,
    outlier_iqr_multiplier: body.outlier_iqr_multiplier ?? null,
    include_partial: body.include_partial ?? false,
    anchor_region_code: body.anchor_region_code ?? "",
    leaf_level: body.leaf_level ?? "",
  });
}
