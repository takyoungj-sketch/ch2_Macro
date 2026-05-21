/**
 * 유료 지역 칩 선택 규칙 (복수는 법정 최종 단위 동·리·읍 칩만, 최대 합계 아래 상수).
 * 시·도·[시]·시군구·읍면동 행정코드 칩은 각각 최대 1개.
 */

/** 동·리·읍 등 법정단위(beopjungri_code) 칩 복수 허용 상한 — 동·리 혼합 시 합산 개수 */
export const MAX_PAID_LEAF_BEOPJUNGRI_PICK = 10;

/** 시·도(sido_codes) 칩 상한 */
export const MAX_SIDO_TIER_CHIP = 1;
/** 자치구 묶음 시(city_codes) 칩 상한 */
export const MAX_CITY_TIER_CHIP = 1;
/** 시군구(sigungu_codes) 칩 상한 */
export const MAX_SIGUNGU_TIER_CHIP = 1;
/** 읍·면·동 행정코드(eupmyeondong_codes) 칩 상한 */
export const MAX_EUPMYEONDONG_TIER_CHIP = 1;
