/**
 * 유료 지역 칩 선택 규칙.
 * 시·도·[시]·시군구 행정 칩은 각각 최대 1개.
 * 시군구 미만은 읍·면·동 행정 단위(칩 1개 = 1곳) + 법정동·리 줄(1줄 = 1곳)을 합쳐 아래 한도까지 복수 가능(혼합 허용).
 */

/** 시군구 미만 선택 단위 합계 상한 — 읍·면·동 행정 칩 수 + 법정동·리 줄 수 */
export const MAX_PAID_SUBSIGUNGU_SELECTIONS = 10;

/** @deprecated 이름 호환용 — MAX_PAID_SUBSIGUNGU_SELECTIONS 와 동일 */
export const MAX_PAID_LEAF_BEOPJUNGRI_PICK = MAX_PAID_SUBSIGUNGU_SELECTIONS;

/** 시·도(sido_codes) 칩 상한 */
export const MAX_SIDO_TIER_CHIP = 1;
/** 자치구 묶음 시(city_codes) 칩 상한 */
export const MAX_CITY_TIER_CHIP = 1;
/** 시군구(sigungu_codes) 칩 상한 */
export const MAX_SIGUNGU_TIER_CHIP = 1;
/** 읍·면·동(eupmyeondong_codes) 행정 칩: 시군구 미만 슬롯 합산 한도 안에서만 복수 허용 */
export const MAX_EUPMYEONDONG_TIER_CHIP = MAX_PAID_SUBSIGUNGU_SELECTIONS;
