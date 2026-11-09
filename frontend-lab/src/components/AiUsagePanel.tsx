import { useQuery } from "@tanstack/react-query";
import { fetchAiUsage, fetchAiAccountUsage } from "../api/aiUsageClient";

function fmtKrw(n: number) {
  return `${Math.round(n).toLocaleString("ko-KR")}원`;
}

export default function AiUsagePanel() {
  const account = useQuery({ queryKey: ["ai-account-usage"], queryFn: fetchAiAccountUsage, refetchInterval: 15000, retry: false });
  const q = useQuery({
    queryKey: ["ai-usage"],
    queryFn: () => fetchAiUsage(),
    refetchInterval: 15_000,
    // 401/403 을 재시도하면 15초 가까이 "불러오는 중"으로 보인다.
    retry: false,
  });

  if (q.isLoading) {
    return <p className="max-w-3xl mx-auto px-4 py-8 text-sm text-slate-500">불러오는 중…</p>;
  }
  if (q.error) {
    const status = (q.error as { response?: { status?: number } }).response?.status;
    return (
      <p className="max-w-3xl mx-auto px-4 py-8 text-sm text-red-600">
        {status === 401 || status === 403
          ? "관리자 인증이 필요합니다. QA 점검 패널에서 QA 토큰을 저장한 뒤 다시 열어 주세요."
          : "사용량 API를 읽지 못했습니다. 백엔드가 켜져 있는지 확인하세요."}
      </p>
    );
  }
  const d = q.data;
  if (!d) return null;
  const callPct = d.call_limit > 0 ? Math.min(100, (d.calls / d.call_limit) * 100) : 0;
  const costPct = d.budget_krw > 0 ? Math.min(100, (d.krw / d.budget_krw) * 100) : 0;

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
      {account.data?.enabled ? <section className="card p-4 space-y-2">
        <h2 className="font-semibold">계정별 AI 제공량 · 모델 원가</h2>
        <p className="text-sm text-slate-500">사용자 차감과 내부 생성·검증 호출은 별도입니다. 아래 기존 실험 장부의 서버 전체 200회 한도는 계정별 유료 요청에 적용되지 않습니다.</p>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th>계정</th><th>기능</th><th>사용 / 한도</th><th>예약</th><th>다음 초기화</th></tr></thead><tbody>
          {account.data.balances.map((b, i) => <tr key={`${b.user_id}-${b.feature}-${i}`}><td>{b.user_id}</td><td>{b.feature}</td><td>{b.used} / {b.limit_units}</td><td>{b.reserved}</td><td>{new Date(b.period_end).toLocaleDateString("ko-KR")}</td></tr>)}
        </tbody></table></div>
        {account.data.costs.map(c => <p className="text-sm" key={`${c.stage}-${c.status}`}>{c.stage} · {c.status} · {c.calls}호출 · {c.estimated_usd == null ? "비용 미확정" : `$${c.estimated_usd.toFixed(6)} (토큰 추정)`}</p>)}
        {account.data.pending?.length ? <p className="text-sm">정산 대기 {account.data.pending.length}건. 오래된 예약은 작업 종료 여부를 확인한 뒤 복구 도구로 처리해 주세요.</p> : null}
      </section> : null}
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
        {(d.limit_warnings ?? []).map((w, i) => (
          <p key={i} className="text-sm text-amber-800 dark:text-amber-200">{w}</p>
        ))}
      </div>

      {d.questions ? (
        <div className="card p-4 space-y-1">
          <p className="text-xs text-slate-500">질문 단위 (질문 문장은 저장하지 않음)</p>
          <p className="text-sm">
            질문 {d.questions.questions}건 · LLM 사용 {d.questions.answered_with_llm}건 · 질문당 호출{" "}
            {d.questions.avg_llm_calls ?? "—"}회 · 질문당 원가 {d.questions.avg_krw == null ? "—" : fmtKrw(d.questions.avg_krw)}
          </p>
          <p className="text-sm">
            지연 p50 {d.questions.latency_p50_ms == null ? "—" : `${(d.questions.latency_p50_ms / 1000).toFixed(1)}초`} · p90{" "}
            {d.questions.latency_p90_ms == null ? "—" : `${(d.questions.latency_p90_ms / 1000).toFixed(1)}초`}
          </p>
          <p className="text-xs text-slate-500">
            검증 결과:{" "}
            {Object.entries(d.questions.validation).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"}
          </p>
        </div>
      ) : null}

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
