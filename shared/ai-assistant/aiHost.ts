// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐

export const CH2_AI_SELECTOR = "[data-ch2-ai]";
export const CH2_AI_OPEN_ATTR = "data-ch2-ai-open";

function eventPath(e: {
  target: EventTarget | null;
  composedPath?: () => EventTarget[];
  nativeEvent?: { composedPath?: () => EventTarget[] };
}): EventTarget[] {
  if (typeof e.composedPath === "function") return e.composedPath();
  const nev = e.nativeEvent;
  if (typeof nev?.composedPath === "function") return nev.composedPath();
  return [];
}

export function eventHitsCh2Ai(e: {
  target: EventTarget | null;
  composedPath?: () => EventTarget[];
  nativeEvent?: { composedPath?: () => EventTarget[] };
}): boolean {
  for (const n of eventPath(e)) {
    if (n instanceof Element && n.closest(CH2_AI_SELECTOR)) return true;
  }
  const t = e.target;
  if (t instanceof Element && t.closest(CH2_AI_SELECTOR)) return true;
  return false;
}

export function setAiChatOpen(open: boolean) {
  if (typeof document === "undefined") return;
  if (open) document.documentElement.setAttribute(CH2_AI_OPEN_ATTR, "1");
  else document.documentElement.removeAttribute(CH2_AI_OPEN_ATTR);
}

export function isAiChatOpen(): boolean {
  if (typeof document === "undefined") return false;
  return document.documentElement.getAttribute(CH2_AI_OPEN_ATTR) === "1";
}

/** 분석 모달이 AI·헤더 클릭 때문에 닫히지 않게 */
export function shouldIgnoreModalDismiss(e: {
  target: EventTarget | null;
  clientY?: number;
  composedPath?: () => EventTarget[];
  nativeEvent?: { composedPath?: () => EventTarget[]; clientY?: number };
}): boolean {
  if (isAiChatOpen()) return true;
  if (eventHitsCh2Ai(e)) return true;
  const t = e.target;
  if (t instanceof Element && t.closest(".ch2-macro-stats-header")) return true;
  const y = e.clientY ?? e.nativeEvent?.clientY;
  const header =
    typeof document === "undefined" ? null : document.querySelector(".ch2-macro-stats-header");
  if (header && typeof y === "number" && y <= header.getBoundingClientRect().bottom) return true;
  return false;
}
