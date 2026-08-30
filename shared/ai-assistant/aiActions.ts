// @ts-nocheck — shared 패키지

export const CH2_AI_ACTION_EVENT = "ch2-ai-screen-action";
export const CH2_AI_ENGINE_DONE_EVENT = "ch2-ai-engine-done";

export type AiScreenAction = {
  id: string;
  kind: "navigate" | "open_ui" | "run_engine";
  label: string;
  href?: string | null;
  ui?: string | null;
  path_id?: string | null;
  confirm_message?: string | null;
};

export function dispatchAiScreenAction(action: AiScreenAction) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(CH2_AI_ACTION_EVENT, { detail: action }));
}

export function dispatchAiEngineDone() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(CH2_AI_ENGINE_DONE_EVENT));
}

/** History 기록 뒤 한 틱 쉬고 알림 — Active Context가 갱신된 다음 해석 질문이 나가게. */
export function notifyAiEngineReady(after?: Promise<unknown> | null) {
  if (typeof window === "undefined") return;
  const fire = () => {
    window.setTimeout(() => dispatchAiEngineDone(), 0);
  };
  if (after) {
    void Promise.resolve(after).finally(fire);
  } else {
    fire();
  }
}

function pathOnly(url: string) {
  try {
    const u = url.startsWith("http") ? new URL(url) : new URL(url, window.location.origin);
    return u.pathname.replace(/\/$/, "") || "/";
  } catch {
    return url.replace(/\/$/, "");
  }
}

export function applyAiScreenAction(action: AiScreenAction) {
  if (action.kind === "navigate" && action.href) {
    const here = pathOnly(window.location.pathname);
    const there = pathOnly(action.href);
    if (here !== there && !here.startsWith(`${there}/`)) {
      window.location.assign(action.href);
      return;
    }
  }
  dispatchAiScreenAction(action);
}
