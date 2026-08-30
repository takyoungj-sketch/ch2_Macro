// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐

export const CH2_AI_SELECTOR = "[data-ch2-ai]";
export const CH2_AI_OPEN_ATTR = "data-ch2-ai-open";

export function eventHitsCh2Ai(e: {
  target: EventTarget | null;
  nativeEvent?: { composedPath?: () => EventTarget[] };
}): boolean {
  const nev = e.nativeEvent;
  const path = typeof nev?.composedPath === "function" ? nev.composedPath() : [];
  for (const n of path) {
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
