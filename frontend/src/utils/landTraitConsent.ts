/** backend/app/land_trait_link.py NOTICE · MATCH_NOTE 와 같아야 한다. */

export const LAND_TRAIT_NOTICE = [
  "이 버튼은 거래 목록에 토지특성 대장의 공시지가와 특성 기준일을 붙입니다. 실거래 원장의 값은 바꾸지 않습니다.",
  "필지가 하나로 정해진 거래만 공시지가를 채웁니다. 후보가 여러 개이거나, 계약일 이전 관측이 없거나, 같은 해 공시지가가 서로 다르면 금액을 채우지 않고 상태만 보여 줍니다.",
] as const;

export const LAND_TRAIT_MATCH_NOTE =
  "전국 연결 시험(2019년 이후, 비교 가능 거래)에서 필지가 하나로 정해진 비율은 71.4%입니다. 연결은 검증 전입니다.";
