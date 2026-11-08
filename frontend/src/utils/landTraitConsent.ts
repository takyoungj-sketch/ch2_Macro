/** backend/app/land_trait_link.py NOTICE · MATCH_NOTE 와 같아야 한다. */

export const LAND_TRAIT_NOTICE = [
  "CH2 Macro는 실거래자료의 소재지와 필지정보 등을 토지특성 및 개별공시지가 자료와 연결하여 공시지가를 표시합니다.",
  "공시지가는 거래연도 자료를 우선 사용하며, 없는 경우 전년도 자료를 사용할 수 있습니다. 표시된 기준연도를 함께 확인해 주세요. 자료의 관측일과 공시지가 기준시점은 다를 수 있습니다.",
] as const;

export const LAND_TRAIT_MISSING_REASONS = [
  "지분거래 등 거래대상 필지를 명확하게 확인하기 어려운 경우",
  "소재지·필지정보가 부족하거나 대장자료와 연결되지 않는 경우",
  "여러 후보가 있거나 공시지가 자료 사이에 확인되지 않은 차이가 있는 경우",
  "해당 기준시점의 공시지가 자료가 없거나 아직 연결하지 않은 경우",
] as const;

export const LAND_TRAIT_MATCH_NOTE =
  "공시지가는 실거래가격과 별개의 공적 자료이며, 개별 부동산의 적정가격을 의미하지 않습니다.";
