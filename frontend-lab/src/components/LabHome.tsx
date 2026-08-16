import type { LabTool } from "../App";

const DOORS: { id: LabTool; title: string; desc: string }[] = [
  {
    id: "plan",
    title: "계획일지",
    desc: "토지 · 복합 · 집합 · 임대 · 지역프로필 · 관리 — 한 표로 오늘과 다음.",
  },
  {
    id: "qa",
    title: "검증로봇",
    desc: "지정·랜덤 지역에서 원장 → 정제 → 마트를 다시 계산해 대조합니다.",
  },
  {
    id: "twin",
    title: "쌍둥이 지역 실험",
    desc: "V2 거리(비교/풀)를 눈으로 보고, V1 풀 CV-MAPE는 옆 탭.",
  },
  {
    id: "rent",
    title: "전월세 전환율",
    desc: "4방법 r · 서울 검증. 연구는 종료, 적용은 단순평균.",
  },
];

export default function LabHome({ onOpenTool }: { onOpenTool: (id: LabTool) => void }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-amber-300/70 bg-amber-50 dark:bg-amber-950/40 dark:border-amber-800">
        <div className="max-w-3xl mx-auto px-4 py-6">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200">
            관리자 · 공개 게이트웨이에 없음
          </p>
          <h1 className="text-xl font-bold mt-0.5">CH2 Macro 관리자</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">들어갈 문을 고르면 됩니다.</p>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-8 grid gap-3 sm:grid-cols-2">
        {DOORS.map((d) => (
          <button
            key={d.id}
            type="button"
            className="card p-5 text-left hover:border-amber-400 transition-colors"
            onClick={() => onOpenTool(d.id)}
          >
            <h2 className="text-lg font-semibold">{d.title}</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 leading-relaxed">{d.desc}</p>
          </button>
        ))}
      </main>
    </div>
  );
}
