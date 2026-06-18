import { useLayoutEffect } from "react";
import {
  UI_FONT_SCALE_STEPS,
  applyColorScheme,
  clampFontStep,
} from "./constants/displayUi";
import { useAppStore } from "./store";
import RegionSelector from "./components/RegionSelector";
import FreeStatsPanel from "./components/FreeStatsPanel";
import PaidAnalysisPanel from "./components/PaidAnalysisPanel";
import PaidFilterTable from "./components/PaidFilterTable";

function PaidIntro() {
  return <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm min-h-[12rem]" />;
}

export default function App() {
  const { viewMode, setViewMode, paidResultView } = useAppStore();
  const uiFontScaleStep = useAppStore((s) => s.uiFontScaleStep);
  const bumpUiFontScale = useAppStore((s) => s.bumpUiFontScale);
  const uiColorScheme = useAppStore((s) => s.uiColorScheme);
  const toggleUiColorScheme = useAppStore((s) => s.toggleUiColorScheme);

  useLayoutEffect(() => {
    document.documentElement.style.removeProperty("font-size");
  }, []);

  useLayoutEffect(() => {
    applyColorScheme(uiColorScheme);
  }, [uiColorScheme]);

  const fontIdx = clampFontStep(uiFontScaleStep);
  const contentZoom = UI_FONT_SCALE_STEPS[fontIdx];
  const fontPct = Math.round(UI_FONT_SCALE_STEPS[fontIdx] * 100);
  const fontStepMin = fontIdx <= 0;
  const fontStepMax = fontIdx >= UI_FONT_SCALE_STEPS.length - 1;
  const isDark = uiColorScheme === "dark";

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex flex-col">
      <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-3 flex flex-wrap items-center justify-between gap-3 shadow-sm">
        <div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-0.5">
            <a href="/" className="hover:text-slate-700 dark:hover:text-slate-200">
              CH2 Macro
            </a>
            {" · 토지"}
          </p>
          <h1 className="text-base font-bold text-slate-800 dark:text-slate-100">
            토지 실거래 통계
          </h1>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-3 shrink-0">
          <a
            href="/built/"
            className="text-xs text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-600 rounded-md px-2 py-1 hover:bg-slate-50 dark:hover:bg-slate-700"
          >
            복합부동산 →
          </a>
          <div
            className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300"
            aria-label="화면 표시 설정"
          >
            <button
              type="button"
              role="switch"
              aria-checked={isDark}
              aria-label={isDark ? "밝은 테마로 전환" : "어두운 테마로 전환"}
              title={isDark ? "밝은 테마" : "어두운 테마"}
              className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors ${
                isDark
                  ? "border-slate-600 bg-slate-700 text-slate-100 hover:bg-slate-600"
                  : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-white"
              }`}
              onClick={() => toggleUiColorScheme()}
            >
              <span aria-hidden>{isDark ? "☀" : "☾"}</span>
              <span className="hidden sm:inline">{isDark ? "밝게" : "어둡게"}</span>
            </button>
            <span className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:inline">
              글자
            </span>
            <div className="flex items-center gap-0.5 border border-slate-200 dark:border-slate-600 rounded-md bg-slate-50/90 dark:bg-slate-700/90 p-0.5">
              <button
                type="button"
                className="w-8 h-7 rounded text-sm font-semibold leading-none text-slate-700 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-600 disabled:opacity-40 disabled:hover:bg-transparent"
                aria-label="글자 크기 줄이기"
                disabled={fontStepMin}
                onClick={() => bumpUiFontScale(-1)}
              >
                −
              </button>
              <span
                className="min-w-[2.85rem] text-center tabular-nums font-medium text-[11px] text-slate-600 dark:text-slate-300"
                aria-live="polite"
              >
                {fontPct}%
              </span>
              <button
                type="button"
                className="w-8 h-7 rounded text-sm font-semibold leading-none text-slate-700 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-600 disabled:opacity-40 disabled:hover:bg-transparent"
                aria-label="글자 크기 키우기"
                disabled={fontStepMax}
                onClick={() => bumpUiFontScale(1)}
              >
                +
              </button>
            </div>
          </div>
          <div className="flex gap-1 bg-slate-100 dark:bg-slate-700 rounded-lg p-1">
            <button
              type="button"
              onClick={() => setViewMode("free")}
              className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                viewMode === "free"
                  ? "bg-white dark:bg-slate-600 text-blue-700 dark:text-blue-300 shadow-sm"
                  : "text-slate-500 dark:text-slate-300 hover:text-slate-700 dark:hover:text-slate-100"
              }`}
            >
              무료 통계
            </button>
            <button
              type="button"
              onClick={() => setViewMode("paid")}
              className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                viewMode === "paid"
                  ? "bg-white dark:bg-slate-600 text-blue-700 dark:text-blue-300 shadow-sm"
                  : "text-slate-500 dark:text-slate-300 hover:text-slate-700 dark:hover:text-slate-100"
              }`}
            >
              유료 분석
            </button>
          </div>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden min-h-0" style={{ zoom: contentZoom }}>
        <aside className="w-[22rem] min-w-[20rem] border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-y-auto p-4 space-y-3 flex-shrink-0">
          <RegionSelector />
          {viewMode === "paid" && <PaidFilterTable />}
        </aside>

        <section className="flex-1 overflow-y-auto p-6 bg-slate-50 dark:bg-slate-900">
          {viewMode === "free" ? (
            <FreeStatsPanel />
          ) : paidResultView === "idle" ? (
            <PaidIntro />
          ) : paidResultView === "basic" ? (
            <FreeStatsPanel />
          ) : (
            <PaidAnalysisPanel />
          )}
        </section>
      </main>
    </div>
  );
}
