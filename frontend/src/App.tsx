import { useAppStore } from "./store";
import RegionSelector from "./components/RegionSelector";
import FreeStatsPanel from "./components/FreeStatsPanel";
import PaidAnalysisPanel from "./components/PaidAnalysisPanel";

export default function App() {
  const { viewMode, setViewMode } = useAppStore();

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* 헤더 */}
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-base font-bold text-slate-800">토지 실거래 통계</h1>
          <p className="text-xs text-slate-400">감정평가사용 토지 가격 분석</p>
        </div>
        <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
          <button
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

      {/* 본문: 2열 레이아웃 */}
      <main className="flex flex-1 overflow-hidden">
        {/* 왼쪽: 지역 선택 */}
        <aside className="w-72 border-r border-slate-200 bg-white overflow-y-auto p-4 space-y-4 flex-shrink-0">
          <RegionSelector />
        </aside>

        {/* 오른쪽: 결과 */}
        <section className="flex-1 overflow-y-auto p-6">
          {viewMode === "free" ? <FreeStatsPanel /> : <PaidAnalysisPanel />}
        </section>
      </main>
    </div>
  );
}
