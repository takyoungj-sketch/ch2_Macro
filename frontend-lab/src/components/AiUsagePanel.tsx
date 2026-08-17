import { useQuery } from "@tanstack/react-query";
import { fetchAiUsage } from "../api/aiUsageClient";

function fmtKrw(n: number) {
  return `${Math.round(n).toLocaleString("ko-KR")}원`;
}

export default function AiUsagePanel() {
  const q = useQuery({
    queryKey: ["ai-usage"],
    queryFn: () => fetchAiUsage(),
    refetchInterval: 15_000,
  });

  if (q.isLoading) {
    return <p className="max-w-3xl mx-auto px-4 py-8 text-sm text-slate-500">불러오는 중…</p>;
  }
  if (q.error) {
    return (
      <p className="max-w-3xl mx-auto px-4 py-8 text-sm text-red-600">
        사용량 API를 읽지 못했습니다. 백엔드가 켜져 있는지 확인하세요.
      </p>
    );
  }
  const d = q.data;
  if (!d) return null;
  const callPct = d.call_limit > 0 ? Math.min(100, (d.calls / d.call_limit) * 100) : 0;
  const costPct = d.budget_krw > 0 ? Math.min(100, (d.krw / d.budget_krw) * 100) : 0;

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
      <div className="card p-4 space-y-2">
        <p className="text-xs text-slate-500 leading-relaxed">
          질문 내용이 아니라 <strong>토큰·원화 장부</strong>입니다. 이번 달 실험: 서버 전체 {d.call_limit}회 ·{" "}
          {fmtKrw(d.budget_krw)}. 80% 경고, 100% 중지. 환율 가정 1달러={d.usd_krw.toLocaleString("ko-KR")}원.
        </p>
        <p className="text-sm">
          <span className="font-semibold">{d.month}</span>
          {d.requested_model ? ` · 요청 모델 ${d.requested_model}` : ""}
          {d.stopped ? (
            <span className="ml-2 text-red-600 font-semibold">중지</span>
          ) : d.warn ? (
            <span className="ml-2 text-amber-700 font-semibold">80% 경고</span>
          ) : (
            <span className="ml-2 text-emerald-700">여유</span>
          )}
        </p>
        {d.warning ? <p className="text-sm text-amber-800 dark:text-amber-200">{d.warning}</p> : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="card p-4">
          <p className="text-xs text-slate-500">월 호출</p>
          <p className="text-2xl font-semibold mt-1">
            {d.calls} <span className="text-base font-normal text-slate-500">/ {d.call_limit || "∞"}</span>
          </p>
          <div className="h-2 mt-3 rounded bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div className="h-full bg-amber-700" style={{ width: `${callPct}%` }} />
          </div>
        </div>
        <div className="card p-4">
          <p className="text-xs text-slate-500">월 추정 비용</p>
          <p className="text-2xl font-semibold mt-1">
            {fmtKrw(d.krw)}{" "}
            <span className="text-base font-normal text-slate-500">/ {fmtKrw(d.budget_krw)}</span>
          </p>
          <p className="text-[11px] text-slate-400 mt-1">${d.usd.toFixed(4)}</p>
          <div className="h-2 mt-3 rounded bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div className="h-full bg-amber-700" style={{ width: `${costPct}%` }} />
          </div>
        </div>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500 border-b border-slate-200 dark:border-slate-700">
            <tr>
              <th className="px-3 py-2">시각(UTC)</th>
              <th className="px-3 py-2">모델</th>
              <th className="px-3 py-2">토큰 in/out</th>
              <th className="px-3 py-2">원</th>
              <th className="px-3 py-2">화면</th>
            </tr>
          </thead>
          <tbody>
            {d.recent.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-slate-500" colSpan={5}>
                  이번 달 LLM 호출이 아직 없습니다. 복합·집합 어시스턴트에 질문하면 여기 쌓입니다.
                </td>
              </tr>
            ) : (
              d.recent.map((e, i) => (
                <tr key={`${e.ts}-${i}`} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="px-3 py-2 whitespace-nowrap">{e.ts.replace("T", " ")}</td>
                  <td className="px-3 py-2">{e.served_model || e.requested_model || "—"}</td>
                  <td className="px-3 py-2">
                    {e.prompt_tokens ?? 0} / {e.completion_tokens ?? 0}
                  </td>
                  <td className="px-3 py-2">{fmtKrw(e.krw || 0)}</td>
                  <td className="px-3 py-2 text-slate-500">
                    {[e.app, e.panel, e.scope_label].filter(Boolean).join(" · ") || "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
