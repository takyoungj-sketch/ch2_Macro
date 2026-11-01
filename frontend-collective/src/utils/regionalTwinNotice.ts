type TwinNoticeInput = {
  loading: boolean;
  error: string | null;
  scopeEmpty: boolean;
  hasAnchor: boolean;
  hasTwins: boolean;
};

export function regionalTwinNotice(state: TwinNoticeInput) {
  if (state.loading) return null;
  if (state.error) {
    if (state.error.includes("이 읍면동의 아파트 재고로 쌍둥이 순위를 만들지 못했습니다")) {
      return {
        kind: "insufficient" as const,
        title: "쌍둥이 지역을 선정할 기준 자료가 부족합니다.",
        reason: "기준 지역에서 최근 3년의 거래 수와 필수 단지 정보 조건을 충족하는 아파트 자료를 확보하지 못했습니다.",
      };
    }
    return { kind: "error" as const, title: "쌍둥이 지역 목록을 불러오지 못했습니다.", reason: state.error };
  }
  if (state.scopeEmpty) {
    return {
      kind: "insufficient" as const,
      title: "선택한 범위에서 쌍둥이 기준 지역을 찾지 못했습니다.",
      reason: "쌍둥이 비교에 필요한 아파트 자료가 갖춰진 읍면동이 없습니다.",
    };
  }
  if (state.hasAnchor && !state.hasTwins) {
    return {
      kind: "insufficient" as const,
      title: "선정 기준에 맞는 쌍둥이 후보가 없습니다.",
      reason: "기준 지역 자료는 있지만, 아파트 재고와 가격분포를 비교할 후보를 확보하지 못했습니다.",
    };
  }
  return null;
}
