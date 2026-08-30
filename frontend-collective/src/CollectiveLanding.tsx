import MacroStatsHeader from "@ch2/macro-shell/MacroStatsHeader";
import { useUiColorScheme } from "@ch2/macro-shell/useUiColorScheme";
import { useUiFontScale } from "@ch2/macro-shell/useUiFontScale";
import AiAssistantPanel from "@ch2/ai-assistant/AiAssistantPanel";
import { ActiveAiViewProvider, emptyAiContext } from "@ch2/ai-assistant/ActiveAiView";

export default function CollectiveLanding() {
  const { fontPct, fontStepMin, fontStepMax, bumpUiFontScale } = useUiFontScale();
  const { isDark, toggleUiColorScheme } = useUiColorScheme();

  return (
    <ActiveAiViewProvider fallback={emptyAiContext("collective", "CollectiveLanding")}>
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
        <MacroStatsHeader
          currentApp="collective"
          title="집합부동산"
          fontPct={fontPct}
          fontStepMin={fontStepMin}
          fontStepMax={fontStepMax}
          onBumpFont={bumpUiFontScale}
          isDark={isDark}
          onToggleTheme={toggleUiColorScheme}
          rightSlot={<AiAssistantPanel />}
        />
        <div className="max-w-3xl mx-auto px-5 py-12">
          <header className="text-center mb-10">
            <p className="text-xs font-semibold tracking-widest uppercase text-slate-500 dark:text-slate-400 mb-2">
              집합부동산
            </p>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
              분석 유형 선택
            </h1>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-3 max-w-md mx-auto leading-relaxed">
              주거형과 상업·업무형은 통계 단위·회귀 방식이 다릅니다. 먼저 갈래를 선택하세요.
            </p>
          </header>

          <main className="grid sm:grid-cols-2 gap-4" aria-label="집합부동산 유형">
            <a
              href="/collective/residential/"
              className="group flex flex-col min-h-[11rem] p-5 rounded-xl border border-slate-200 bg-white shadow-sm hover:border-blue-300 hover:shadow-md hover:-translate-y-0.5 transition-all no-underline text-inherit dark:border-slate-600 dark:bg-slate-800"
            >
              <span className="self-start mb-3 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800">
                주거형
              </span>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-1">
                아파트 · 연립 · 오피스텔 · 분양권
              </h2>
              <p className="text-sm text-slate-600 dark:text-slate-300 flex-1 leading-relaxed">
                단지·건물별 ㎡당 단가, 신뢰구간, 층·동 효용지수, 건물 회귀
              </p>
              <span className="mt-4 text-sm font-semibold text-blue-600 group-hover:text-blue-700">주거형 통계 →</span>
            </a>

            <a
              href="/collective/commercial/"
              className="group flex flex-col min-h-[11rem] p-5 rounded-xl border border-slate-200 bg-white shadow-sm hover:border-blue-300 hover:shadow-md hover:-translate-y-0.5 transition-all no-underline text-inherit dark:border-slate-600 dark:bg-slate-800"
            >
              <span className="self-start mb-3 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-900">
                상업·업무
              </span>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-1">집합상가 · 집합공장</h2>
              <p className="text-sm text-slate-600 dark:text-slate-300 flex-1 leading-relaxed">
                도로(상권) cluster별 단가, 층·면적 효용지수, 도로 회귀 —{" "}
                <span className="text-slate-500">복합부동산(개별 건물)과 다릅니다</span>
              </p>
              <span className="mt-4 text-sm font-semibold text-blue-600 group-hover:text-blue-700">상업·업무 통계 →</span>
            </a>
          </main>

          <footer className="mt-10 text-center text-xs text-slate-400">© CH2 Macro</footer>
        </div>
      </div>
    </ActiveAiViewProvider>
  );
}
