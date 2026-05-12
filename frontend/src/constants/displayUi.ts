/** 글자 크기 단계별 배율(사이드바·우측 본문 레이아웃 `zoom`만 적용, 최상단 헤더는 제외). */
export const UI_FONT_SCALE_STEPS = [
  0.8125, 0.875, 0.9375, 1, 1.0625, 1.125, 1.1875, 1.25,
] as const;

export const UI_FONT_LS_KEY = "ch2_macro_ui_font_step";

export type UiTableTone = "neutral" | "blueHeaders";

export function clampFontStep(step: number): number {
  const max = UI_FONT_SCALE_STEPS.length - 1;
  if (!Number.isFinite(step)) return 3;
  return Math.max(0, Math.min(max, Math.round(step)));
}

export function readStoredFontStep(): number {
  try {
    return clampFontStep(Number(localStorage.getItem(UI_FONT_LS_KEY)));
  } catch {
    return 3;
  }
}

export function persistFontStep(step: number): void {
  try {
    localStorage.setItem(UI_FONT_LS_KEY, String(clampFontStep(step)));
  } catch {
    /* ignore */
  }
}

/** 매트릭스(용도·지목 헤더·좌측 용도지역 열)는 항상 연블루 톤 고정 */
export const MATRIX_TABLE_TONE: UiTableTone = "blueHeaders";

/** 간단 표(StatsTable, Yearly 등) thead 한 줄 스타일 */
export function simpleTableHeadClass(tone: UiTableTone): string {
  return tone === "blueHeaders"
    ? "bg-sky-100 text-sky-900"
    : "bg-slate-100 text-slate-600";
}

/** Sticky 헤더 셀 배경만 (연도별 표 등) */
export function simpleTableHeadStickyBgClass(tone: UiTableTone): string {
  return tone === "blueHeaders" ? "bg-sky-100" : "bg-slate-100";
}

export function matrixTheadPrimaryClass(tone: UiTableTone): string {
  return tone === "blueHeaders"
    ? "bg-sky-100 text-sky-900 shadow-[inset_0_-1px_0_0_rgb(186_230_253)]"
    : "bg-slate-100 text-slate-600 shadow-[inset_0_-1px_0_0_rgb(226_232_240)]";
}
