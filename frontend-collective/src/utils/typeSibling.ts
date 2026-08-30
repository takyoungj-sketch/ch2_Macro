import type { BuildingStatsRow, TypeSibling } from "../types";

export function rowFromTypeSibling(parent: BuildingStatsRow, sib: TypeSibling): BuildingStatsRow {
  const back: TypeSibling = {
    asset_type: parent.asset_type,
    building_key: parent.building_key,
    display_name: parent.display_name,
    count: parent.count,
    median: parent.median ?? null,
    mean: parent.mean ?? null,
  };
  return {
    building_key: sib.building_key,
    display_name: sib.display_name,
    address: parent.address,
    jibun_address: parent.jibun_address,
    road_address: parent.road_address,
    building_year: parent.building_year,
    households: parent.households,
    households_flagged: parent.households_flagged,
    builder_label: parent.builder_label,
    builder_is_joint: parent.builder_is_joint,
    match_tier: null,
    match_rule: null,
    assessed_land_price: parent.assessed_land_price,
    assessed_land_price_year: parent.assessed_land_price_year,
    asset_type: sib.asset_type,
    count: sib.count,
    mean: sib.mean ?? null,
    median: sib.median ?? null,
    ci_lower: null,
    ci_upper: null,
    is_reliable: sib.count >= 15,
    analysis: parent.analysis,
    type_siblings: [back],
    scale_scope: "complex",
  };
}
