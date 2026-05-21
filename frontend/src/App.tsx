import { useLayoutEffect } from "react";
import { UI_FONT_SCALE_STEPS, clampFontStep } from "./constants/displayUi";
import { useAppStore } from "./store";
import RegionSelector from "./components/RegionSelector";
import FreeStatsPanel from "./components/FreeStatsPanel";
import PaidAnalysisPanel from "./components/PaidAnalysisPanel";
import PaidFilterTable from "./components/PaidFilterTable";

function PaidIntro() {
  return (
    <div className="bg-white rounded-xl shadow-sm p-8 text-center text-slate-600 text-sm space-y-3 max-w-xl mx-auto">
      <p className="font-semibold text-slate-800">유료 분석 시작</p>
      <ol className="text-xs text-left space-y-2 leading-relaxed list-decimal list-inside">
        <li>
          지역 입력 후 <strong className="text-slate-700">기본 통계 보기</strong> — 무료 통계와 같은
          동·리 요약
        </li>
        <li>
          아래 연도·도로 등을 조정한 뒤 <strong className="text-slate-700">필터 분석 실행</strong>{" "}
          — 조건별 매트릭스
        </li>
      </ol>
    </div>
  );
}

export default function App() {
  const { viewMode, setViewMode, paidResultView } = useAppStore();
  const uiFontScaleStep = useAppStore((s) => s.uiFontScaleStep);
  const bumpUiFontScale = useAppStore((s) => s.bumpUiFontScale);

  useLayoutEffect(() => {
    document.documentElement.style.removeProperty("font-size");
  }, []);

  const fontIdx = clampFontStep(uiFontScaleStep);
  const contentZoom = UI_FONT_SCALE_STEPS[fontIdx];
  const fontPct = Math.round(UI_FONT_SCALE_STEPS[fontIdx] * 100);
  const fontStepMin = fontIdx <= 0;
  const fontStepMax = fontIdx >= UI_FONT_SCALE_STEPS.length - 1;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex flex-wrap items-center justify-between gap-3 shadow-sm">
        <div>
          <h1 className="text-base font-bold text-slate-800">토지 실거래 통계</h1>
          <p className="text-xs text-slate-400">감정평가사용 토지 가격 분석</p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-3 shrink-0">
          <div
            className="flex flex-wrap items-center gap-2 text-xs text-slate-600"
            aria-label="화면 표시 설정"
          >
            <span className="text-[11px] text-slate-500 hidden sm:inline">글자</span>
            <div className="flex items-center gap-0.5 border border-slate-200 rounded-md bg-slate-50/90 p-0.5">
              <button
                type="button"
                className="w-8 h-7 rounded text-sm font-semibold leading-none text-slate-700 hover:bg-white disabled:opacity-40 disabled:hover:bg-transparent"
                aria-label="글자 크기 줄이기"
                disabled={fontStepMin}
                onClick={() => bumpUiFontScale(-1)}
              >
                −
              </button>
              <span
                className="min-w-[2.85rem] text-center tabular-nums font-medium text-[11px] text-slate-600"
                aria-live="polite"
              >
                {fontPct}%
              </span>
              <button
                type="button"
                className="w-8 h-7 rounded text-sm font-semibold leading-none text-slate-700 hover:bg-white disabled:opacity-40 disabled:hover:bg-transparent"
                aria-label="글자 크기 키우기"
                disabled={fontStepMax}
                onClick={() => bumpUiFontScale(1)}
              >
                +
              </button>
            </div>
          </div>
          <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
          <button
            type="button"
            onClick={() => setViewMode("free")}
            className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-colors ${
              viewMode === "free"
                ? "bg-white text-blue-700 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            무료 통계
          </button>
          <button
            type="button"
            onClick={() => setViewMode("paid")}
            className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-colors ${
              viewMode === "paid"
                ? "bg-white text-blue-700 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            유료 분석
          </button>
        </div>
        </div>
      </header>

      <main className="flex flex-1 overflow-hidden min-h-0" style={{ zoom: contentZoom }}>
        <aside className="w-[22rem] min-w-[20rem] border-r border-slate-200 bg-white overflow-y-auto p-4 space-y-3 flex-shrink-0">
          <RegionSelector />
          {viewMode === "paid" && <PaidFilterTable />}
        </aside>

        <section className="flex-1 overflow-y-auto p-6">
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
