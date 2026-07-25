/** 글자 크기 단계별 배율(앱 셸 전체 `zoom`). 토지 앱과 동일 localStorage 키 공유. */
export const UI_FONT_SCALE_STEPS = [
  1, 1.0625, 1.125, 1.1875, 1.25, 1.375, 1.5, 1.625, 1.75, 2,
] as const;

export const UI_FONT_LS_KEY = "ch2_macro_ui_font_step";
/** 스키마 버전 — 배포 가독성 상향 시 기존 저장 단계를 1회 보정. */
export const UI_FONT_LS_SCHEMA_KEY = "ch2_macro_ui_font_step_schema";
export const UI_FONT_LS_SCHEMA = 4;

/** 모달 전용 — 전체화면에서도 글자·버튼·옵션을 더 키울 수 있게 상한을 높임. */
export const MODAL_FONT_SCALE_STEPS = [
  0.875, 1, 1.0625, 1.125, 1.1875, 1.25, 1.375, 1.5, 1.625, 1.75,
] as const;

export const MODAL_FONT_LS_KEY = "ch2_macro_modal_font_step";

/** MODAL_FONT_SCALE_STEPS에서 100% 위치. */
export const DEFAULT_MODAL_FONT_SCALE_STEP = 1;

export type UiColorScheme = "light" | "dark";

export const UI_COLOR_SCHEME_LS_KEY = "ch2_macro_ui_color_scheme";

export const DEFAULT_UI_COLOR_SCHEME: UiColorScheme = "dark";

/** 기본 100% (UI_FONT_SCALE_STEPS[0]). */
export const DEFAULT_UI_FONT_SCALE_STEP = 0;

export function clampFontStep(step: number): number {
  const max = UI_FONT_SCALE_STEPS.length - 1;
  if (!Number.isFinite(step)) return DEFAULT_UI_FONT_SCALE_STEP;
  return Math.max(0, Math.min(max, Math.round(step)));
}

export function readStoredFontStep(): number {
  try {
    const raw = localStorage.getItem(UI_FONT_LS_KEY);
    const schemaRaw = localStorage.getItem(UI_FONT_LS_SCHEMA_KEY);
    const schema = schemaRaw == null || schemaRaw.trim() === "" ? 0 : Number(schemaRaw);
    if (raw == null || raw.trim() === "") {
      localStorage.setItem(UI_FONT_LS_SCHEMA_KEY, String(UI_FONT_LS_SCHEMA));
      return DEFAULT_UI_FONT_SCALE_STEP;
    }
    const step = clampFontStep(Number(raw));
    if (!Number.isFinite(schema) || schema < UI_FONT_LS_SCHEMA) {
      localStorage.setItem(UI_FONT_LS_SCHEMA_KEY, String(UI_FONT_LS_SCHEMA));
    }
    return step;
  } catch {
    return DEFAULT_UI_FONT_SCALE_STEP;
  }
}

export function persistFontStep(step: number): void {
  try {
    localStorage.setItem(UI_FONT_LS_KEY, String(clampFontStep(step)));
  } catch {
    /* ignore */
  }
}

export function clampModalFontStep(step: number): number {
  const max = MODAL_FONT_SCALE_STEPS.length - 1;
  if (!Number.isFinite(step)) return DEFAULT_MODAL_FONT_SCALE_STEP;
  return Math.max(0, Math.min(max, Math.round(step)));
}

export function readStoredModalFontStep(): number {
  try {
    const raw = localStorage.getItem(MODAL_FONT_LS_KEY);
    if (raw == null || raw.trim() === "") return DEFAULT_MODAL_FONT_SCALE_STEP;
    return clampModalFontStep(Number(raw));
  } catch {
    return DEFAULT_MODAL_FONT_SCALE_STEP;
  }
}

export function persistModalFontStep(step: number): void {
  try {
    localStorage.setItem(MODAL_FONT_LS_KEY, String(clampModalFontStep(step)));
  } catch {
    /* ignore */
  }
}

export function readStoredColorScheme(): UiColorScheme {
  try {
    const raw = localStorage.getItem(UI_COLOR_SCHEME_LS_KEY);
    if (raw == null || raw.trim() === "") return DEFAULT_UI_COLOR_SCHEME;
    return raw === "dark" ? "dark" : "light";
  } catch {
    return DEFAULT_UI_COLOR_SCHEME;
  }
}

export function persistColorScheme(scheme: UiColorScheme): void {
  try {
    localStorage.setItem(UI_COLOR_SCHEME_LS_KEY, scheme);
  } catch {
    /* ignore */
  }
}

/** SSR·첫 페인트 전 html 클래스 동기화(FOUC 방지). */
export function applyColorScheme(scheme: UiColorScheme): void {
  const root = document.documentElement;
  if (scheme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  root.style.colorScheme = scheme;
}
