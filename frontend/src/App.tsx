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

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-base font-bold text-slate-800">토지 실거래 통계</h1>
          <p className="text-xs text-slate-400">감정평가사용 토지 가격 분석</p>
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
      </header>

      <main className="flex flex-1 overflow-hidden">
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
