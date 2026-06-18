/** 글자 크기 단계별 배율(사이드바·우측 본문 레이아웃 `zoom`만 적용, 최상단 헤더는 제외). */
export const UI_FONT_SCALE_STEPS = [
  0.8125, 0.875, 0.9375, 1, 1.0625, 1.125, 1.1875, 1.25,
] as const;

export const UI_FONT_LS_KEY = "ch2_macro_ui_font_step";

export type UiColorScheme = "light" | "dark";

export const UI_COLOR_SCHEME_LS_KEY = "ch2_macro_ui_color_scheme";

export const DEFAULT_UI_COLOR_SCHEME: UiColorScheme = "light";

export type UiTableTone = "neutral" | "blueHeaders";

/** 글자 크기 100%에 해당하는 단계 인덱스 (UI_FONT_SCALE_STEPS[3] === 1). */
export const DEFAULT_UI_FONT_SCALE_STEP = 3;

export function clampFontStep(step: number): number {
  const max = UI_FONT_SCALE_STEPS.length - 1;
  if (!Number.isFinite(step)) return DEFAULT_UI_FONT_SCALE_STEP;
  return Math.max(0, Math.min(max, Math.round(step)));
}

export function readStoredFontStep(): number {
  try {
    const raw = localStorage.getItem(UI_FONT_LS_KEY);
    if (raw == null || raw.trim() === "") return DEFAULT_UI_FONT_SCALE_STEP;
    return clampFontStep(Number(raw));
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

export function readStoredColorScheme(): UiColorScheme {
  try {
    const raw = localStorage.getItem(UI_COLOR_SCHEME_LS_KEY);
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
  root.classList.toggle("dark", scheme === "dark");
  root.style.colorScheme = scheme;
}

/** 매트릭스(용도·지목 헤더·좌측 용도지역 열)는 항상 연블루 톤 고정 */
export const MATRIX_TABLE_TONE: UiTableTone = "blueHeaders";

/** 간단 표(StatsTable, Yearly 등) thead 한 줄 스타일 */
export function simpleTableHeadClass(tone: UiTableTone): string {
  return tone === "blueHeaders"
    ? "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-100"
    : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300";
}

/** Sticky 헤더 셀 배경만 (연도별 표 등) */
export function simpleTableHeadStickyBgClass(tone: UiTableTone): string {
  return tone === "blueHeaders" ? "bg-sky-100 dark:bg-sky-950" : "bg-slate-100 dark:bg-slate-800";
}

export function matrixTheadPrimaryClass(tone: UiTableTone): string {
  return tone === "blueHeaders"
    ? "bg-sky-100 text-sky-900 shadow-[inset_0_-1px_0_0_rgb(186_230_253)] dark:bg-sky-950 dark:text-sky-100 dark:shadow-[inset_0_-1px_0_0_rgb(12_74_110)]"
    : "bg-slate-100 text-slate-600 shadow-[inset_0_-1px_0_0_rgb(226_232_240)] dark:bg-slate-800 dark:text-slate-300 dark:shadow-[inset_0_-1px_0_0_rgb(51_65_85)]";
}
