/** B-01: 추정값 경고에서 「Macro 모형 탐색」 창을 연다. 패널이 이 이벤트를 듣는다. */
export const OPEN_MACRO_EXPLORE_EVENT = "ch2:built-open-macro";

export function requestOpenMacroExplore() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(OPEN_MACRO_EXPLORE_EVENT));
  document.getElementById("built-step-macro")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** 서버가 붙인 부호 경고(B-01) — 결과 카드가 따로 그리므로 일반 경고 목록에서 뺀다. */
export function isSignWarning(text: string) {
  return text.startsWith("추정값이 0 이하입니다.") || text.startsWith("구간 하한이 0 미만입니다.");
}
