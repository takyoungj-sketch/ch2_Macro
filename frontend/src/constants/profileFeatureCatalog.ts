/**
 * Regional Profile UI feature catalog.
 * SSOT mirror: pipeline/config/profile_feature_catalog.yaml
 */

export type ProfileFeatureCategoryId =
  | "population"
  | "land_market"
  | "apartment_market"
  | "rowhouse_market"
  | "officetel_market"
  | "composition"
  | "other";

export type ProfileValueKind =
  | "count"
  | "money_sqm"
  | "population"
  | "density"
  | "ratio"
  | "percent"
  | "number";

export interface ProfileFeatureSpec {
  key: string;
  category: ProfileFeatureCategoryId;
  labelKo: string;
  valueKind: ProfileValueKind;
  unit?: string;
  sourceTable?: string;
  sourceDomain?: string;
  countKey?: string;
  sortOrder: number;
}

export interface ProfileCategorySpec {
  id: ProfileFeatureCategoryId;
  labelKo: string;
  order: number;
}

export const MIN_RELIABLE_PROFILE_COUNT = 15;

export const PROFILE_CATEGORIES: ProfileCategorySpec[] = [
  { id: "population", labelKo: "인구", order: 1 },
  { id: "land_market", labelKo: "토지 시장", order: 2 },
  { id: "apartment_market", labelKo: "아파트 시장", order: 3 },
  { id: "rowhouse_market", labelKo: "연립·다세대 시장", order: 4 },
  { id: "officetel_market", labelKo: "오피스텔 시장", order: 5 },
  { id: "composition", labelKo: "거래 구성", order: 6 },
  { id: "other", labelKo: "기타", order: 99 },
];

/** count_key 등은 YAML 과 동일 키 */
export const PROFILE_FEATURE_SPECS: ProfileFeatureSpec[] = [
  {
    key: "population",
    category: "population",
    labelKo: "인구",
    valueKind: "population",
    sourceTable: "population_stats",
    sortOrder: 1,
  },
  {
    key: "population_density",
    category: "population",
    labelKo: "인구밀도",
    valueKind: "density",
    unit: "명/km²",
    sourceTable: "population_stats",
    sortOrder: 2,
  },
  {
    key: "land_residential_count",
    category: "land_market",
    labelKo: "거래수 (주거용지)",
    valueKind: "count",
    sourceTable: "market_stats",
    sourceDomain: "land_residential",
    sortOrder: 10,
  },
  {
    key: "land_residential_mean",
    category: "land_market",
    labelKo: "평균단가 (주거용지)",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "land_residential",
    countKey: "land_residential_count",
    sortOrder: 11,
  },
  {
    key: "land_residential_median",
    category: "land_market",
    labelKo: "중앙단가 (주거용지)",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "land_residential",
    countKey: "land_residential_count",
    sortOrder: 12,
  },
  {
    key: "land_residential_std",
    category: "land_market",
    labelKo: "표준편차 (주거용지)",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "land_residential",
    countKey: "land_residential_count",
    sortOrder: 13,
  },
  {
    key: "land_commercial_count",
    category: "land_market",
    labelKo: "거래수 (상업용지)",
    valueKind: "count",
    sourceTable: "market_stats",
    sourceDomain: "land_commercial",
    sortOrder: 20,
  },
  {
    key: "land_commercial_mean",
    category: "land_market",
    labelKo: "평균단가 (상업용지)",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "land_commercial",
    countKey: "land_commercial_count",
    sortOrder: 21,
  },
  {
    key: "land_commercial_median",
    category: "land_market",
    labelKo: "중앙단가 (상업용지)",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "land_commercial",
    countKey: "land_commercial_count",
    sortOrder: 22,
  },
  {
    key: "land_commercial_std",
    category: "land_market",
    labelKo: "표준편차 (상업용지)",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "land_commercial",
    countKey: "land_commercial_count",
    sortOrder: 23,
  },
  {
    key: "land_industrial_count",
    category: "land_market",
    labelKo: "거래수 (공업용지)",
    valueKind: "count",
    sourceTable: "market_stats",
    sourceDomain: "land_industrial",
    sortOrder: 30,
  },
  {
    key: "land_industrial_mean",
    category: "land_market",
    labelKo: "평균단가 (공업용지)",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "land_industrial",
    countKey: "land_industrial_count",
    sortOrder: 31,
  },
  {
    key: "land_industrial_median",
    category: "land_market",
    labelKo: "중앙단가 (공업용지)",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "land_industrial",
    countKey: "land_industrial_count",
    sortOrder: 32,
  },
  {
    key: "land_industrial_std",
    category: "land_market",
    labelKo: "표준편차 (공업용지)",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "land_industrial",
    countKey: "land_industrial_count",
    sortOrder: 33,
  },
  {
    key: "apartment_count",
    category: "apartment_market",
    labelKo: "거래수",
    valueKind: "count",
    sourceTable: "market_stats",
    sourceDomain: "apartment_market",
    sortOrder: 1,
  },
  {
    key: "apartment_mean",
    category: "apartment_market",
    labelKo: "평균단가",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "apartment_market",
    countKey: "apartment_count",
    sortOrder: 2,
  },
  {
    key: "apartment_median",
    category: "apartment_market",
    labelKo: "중앙단가",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "apartment_market",
    countKey: "apartment_count",
    sortOrder: 3,
  },
  {
    key: "apartment_std",
    category: "apartment_market",
    labelKo: "표준편차",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "apartment_market",
    countKey: "apartment_count",
    sortOrder: 4,
  },
  {
    key: "apartment_volatility",
    category: "apartment_market",
    labelKo: "변동성",
    valueKind: "ratio",
    sourceTable: "market_stats",
    sourceDomain: "apartment_market",
    countKey: "apartment_count",
    sortOrder: 5,
  },
  {
    key: "apartment_yoy",
    category: "apartment_market",
    labelKo: "전년 대비",
    valueKind: "percent",
    sourceTable: "market_stats",
    sourceDomain: "apartment_market",
    countKey: "apartment_count",
    sortOrder: 6,
  },
  {
    key: "rowhouse_count",
    category: "rowhouse_market",
    labelKo: "거래수",
    valueKind: "count",
    sourceTable: "market_stats",
    sourceDomain: "rowhouse_market",
    sortOrder: 1,
  },
  {
    key: "rowhouse_mean",
    category: "rowhouse_market",
    labelKo: "평균단가",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "rowhouse_market",
    countKey: "rowhouse_count",
    sortOrder: 2,
  },
  {
    key: "rowhouse_median",
    category: "rowhouse_market",
    labelKo: "중앙단가",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "rowhouse_market",
    countKey: "rowhouse_count",
    sortOrder: 3,
  },
  {
    key: "rowhouse_std",
    category: "rowhouse_market",
    labelKo: "표준편차",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "rowhouse_market",
    countKey: "rowhouse_count",
    sortOrder: 4,
  },
  {
    key: "rowhouse_volatility",
    category: "rowhouse_market",
    labelKo: "변동성",
    valueKind: "ratio",
    sourceTable: "market_stats",
    sourceDomain: "rowhouse_market",
    countKey: "rowhouse_count",
    sortOrder: 5,
  },
  {
    key: "officetel_count",
    category: "officetel_market",
    labelKo: "거래수",
    valueKind: "count",
    sourceTable: "market_stats",
    sourceDomain: "officetel_market",
    sortOrder: 1,
  },
  {
    key: "officetel_mean",
    category: "officetel_market",
    labelKo: "평균단가",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "officetel_market",
    countKey: "officetel_count",
    sortOrder: 2,
  },
  {
    key: "officetel_median",
    category: "officetel_market",
    labelKo: "중앙단가",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "officetel_market",
    countKey: "officetel_count",
    sortOrder: 3,
  },
  {
    key: "officetel_std",
    category: "officetel_market",
    labelKo: "표준편차",
    valueKind: "money_sqm",
    sourceTable: "market_stats",
    sourceDomain: "officetel_market",
    countKey: "officetel_count",
    sortOrder: 4,
  },
  {
    key: "officetel_volatility",
    category: "officetel_market",
    labelKo: "변동성",
    valueKind: "ratio",
    sourceTable: "market_stats",
    sourceDomain: "officetel_market",
    countKey: "officetel_count",
    sortOrder: 5,
  },
  {
    key: "ratio_residential_zone",
    category: "composition",
    labelKo: "주거 용도지역 거래비중",
    valueKind: "ratio",
    sourceTable: "land_upper_stats_v2",
    sortOrder: 1,
  },
  {
    key: "ratio_commercial_zone",
    category: "composition",
    labelKo: "상업 용도지역 거래비중",
    valueKind: "ratio",
    sourceTable: "land_upper_stats_v2",
    sortOrder: 2,
  },
  {
    key: "ratio_agri_zone",
    category: "composition",
    labelKo: "농림·녹지 거래비중",
    valueKind: "ratio",
    sourceTable: "land_upper_stats_v2",
    sortOrder: 3,
  },
  {
    key: "ratio_land_danji",
    category: "composition",
    labelKo: "대지 거래비중",
    valueKind: "ratio",
    sourceTable: "land_upper_stats_v2",
    sortOrder: 4,
  },
  {
    key: "ratio_land_rice",
    category: "composition",
    labelKo: "전·답 거래비중",
    valueKind: "ratio",
    sourceTable: "land_upper_stats_v2",
    sortOrder: 5,
  },
  {
    key: "ratio_land_forest",
    category: "composition",
    labelKo: "임야 거래비중",
    valueKind: "ratio",
    sourceTable: "land_upper_stats_v2",
    sortOrder: 6,
  },
];

const SPEC_BY_KEY = new Map(PROFILE_FEATURE_SPECS.map((s) => [s.key, s]));

export function getProfileFeatureSpec(key: string): ProfileFeatureSpec | undefined {
  return SPEC_BY_KEY.get(key);
}

export function getCategoryLabel(id: ProfileFeatureCategoryId): string {
  return PROFILE_CATEGORIES.find((c) => c.id === id)?.labelKo ?? id;
}
