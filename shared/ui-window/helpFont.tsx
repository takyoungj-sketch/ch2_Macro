// @ts-nocheck — shared: 각 frontend node_modules 기준 경로가 달라짐
import type { ReactNode } from "react";

export const HELP_FONT_PX_MIN = 13;
export const HELP_FONT_PX_MAX = 22;
export const HELP_FONT_PX_DEFAULT = 15;
export const HELP_FONT_STORAGE_KEY = "ch2-help-font-px";
const LEGACY_GLOSSARY_KEY = "ch2-glossary-font-px";

function clampFontPx(n: number): number {
  return Math.min(HELP_FONT_PX_MAX, Math.max(HELP_FONT_PX_MIN, n));
}

export function readStoredHelpFontPx(): number {
  try {
    const stored = localStorage.getItem(HELP_FONT_STORAGE_KEY);
    if (stored != null) {
      const n = Number(stored);
      if (Number.isFinite(n)) return clampFontPx(n);
    }
    const legacy = localStorage.getItem(LEGACY_GLOSSARY_KEY);
    if (legacy != null) {
      const n = Number(legacy);
      // 예전 glossary 기본값 13은 새 기본 15로 올린다. 이용자가 ±로 고른 다른 값은 유지.
      if (Number.isFinite(n) && n !== 13) return clampFontPx(n);
    }
  } catch {
    /* ignore */
  }
  return HELP_FONT_PX_DEFAULT;
}

export function persistHelpFontPx(n: number): void {
  try {
    localStorage.setItem(HELP_FONT_STORAGE_KEY, String(clampFontPx(n)));
  } catch {
    /* ignore */
  }
}

export function nextHelpFontPx(current: number, delta: number): number {
  return clampFontPx(current + delta);
}

const BTN =
  "inline-flex items-center justify-center w-6 h-6 rounded border border-slate-200 bg-transparent text-slate-600 text-base leading-none disabled:opacity-40 disabled:cursor-default disabled:pointer-events-none hover:bg-slate-50 dark:border-slate-500 dark:text-slate-200 dark:hover:bg-slate-700";

export function HelpFontStepper({
  value,
  onChange,
}: {
  value: number;
  onChange: (next: number) => void;
}): ReactNode {
  return (
    <div
      className="flex items-center gap-1 shrink-0"
      title="본문 글자 크기"
      onPointerDown={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        className={BTN}
        aria-label="글자 작게"
        disabled={value <= HELP_FONT_PX_MIN}
        onClick={() => onChange(nextHelpFontPx(value, -1))}
      >
        −
      </button>
      <span
        className="tabular-nums text-slate-500 dark:text-slate-300 w-6 text-center"
        style={{ fontSize: 11 }}
      >
        {value}
      </span>
      <button
        type="button"
        className={BTN}
        aria-label="글자 크게"
        disabled={value >= HELP_FONT_PX_MAX}
        onClick={() => onChange(nextHelpFontPx(value, 1))}
      >
        +
      </button>
    </div>
  );
}
