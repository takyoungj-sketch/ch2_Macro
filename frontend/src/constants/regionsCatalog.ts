/** react-query: 전체 법정동·리 카탈로그 (한 번 로드 후 장시간 stale) */
export const REGIONS_CATALOG_QUERY_KEY = ["regions", "catalog"] as const;

/** 유료: 칩이 이 개수 이상이면 부하 안내 */
export const REGION_PICK_MANY_WARN_AT = 8;
