/** 집합 2단계 P4 — 화면에 쓰는 단지 이름.
 * C-2 로 나뉜 아파트 조각은 API 가 `display_label`(「단지명 (YYYY년 준공)」)을 준다. 없으면 `display_name`.
 * 검색·정렬 기준·키는 `display_name` 그대로다(표시만 바꾼다). */
export function buildingDisplayName(row: { display_name?: string | null; display_label?: string | null }): string {
  return (row.display_label || row.display_name || "").trim();
}
