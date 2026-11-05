// @ts-nocheck — 기존 공유 AI 컴포넌트와 같은 프런트별 React 해석 경로 사용
import { useEffect, useRef, useState } from "react";
import "./ai3Assistant.css";

type Fact = { id: string; label: string; value: string; source: string };
type Plan = { id: string; tool_id: string; label: string; arguments: Record<string, unknown> };
type Reply = {
  session_id: string; kind: string; answer: string; llm_used: boolean;
  evidence: { id: string; label: string; source: string }[];
  facts: Fact[]; limitations: string[]; plan: Plan | null; history_ids: string[];
};
type Execution = {
  id: string; session_id: string; plan_id: string; status: string; error: string | null;
  result: Record<string, unknown> | null; facts: Fact[]; limitations: string[];
  applied_arguments: Record<string, unknown>;
};
type Tool = { id: string; label: string; app: string; schema: Record<string, unknown> };
type Health = { llm_configured: boolean; model: string; tools: Tool[]; monthly_call_limit: number };

const SAMPLES: Record<string, Record<string, unknown>> = {
  "regions.search": { name: "가경동" },
  "targets.search": { addr1: "충청북도", addr2: "청주시", addr4: "가경동", name: "세원", domain: "residential" },
  "land.basic_stats": { beopjungri_code: "", window_years: 5, as_of_month: "", matrix_mode: "category" },
  "built.predict": { admin_level: "eupmyeondong", asset_type: "detached", addr1: "", addr2: "", addr4_list: [],
    contract_year_from: 2021, contract_year_to: 2025, gross_area: 200, land_area: 150, building_age: 20 },
  "collective.residential.index": { target_key: "", year_from: 2021, year_to: 2025, dimension: "floor", floor_mode: "relative" },
  "collective.commercial.index": { target_key: "", year_from: 2021, year_to: 2025, dimension: "floor", floor_mode: "shop" },
  "rent.conversion": { addr1: "", addr2: "", asset_type: "apartment", window_years: 5, as_of_month: "" },
  "profile.twins": { sigungu_code: "", window_years: 3, scope: "national", twin_profile: "general", profile_version: "v2.1-national", top_k: 3 },
};

function Facts({ facts }: { facts: Fact[] }) {
  if (!facts.length) return null;
  return <details className="mt-3"><summary className="cursor-pointer text-xs">근거 값 {facts.length}개</summary>
    <div className="max-h-72 overflow-auto mt-2"><table className="w-full text-xs"><thead><tr><th className="text-left">항목</th><th className="text-left">값</th></tr></thead>
      <tbody>{facts.map(f => <tr key={`${f.source}-${f.id}`} className="border-t border-slate-200 dark:border-slate-700"><td className="p-1 break-all">{f.label}</td><td className="p-1 break-all">{f.value}</td></tr>)}</tbody>
    </table></div></details>;
}

type Ai3AssistantProps = {
  initialApp?: string;
  screenRegion?: string;
  embedded?: boolean;
};

export default function Ai3Assistant({ initialApp, screenRegion, embedded = false }: Ai3AssistantProps) {
  const [health, setHealth] = useState<Health | null>(null);
  const [token, setToken] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [app, setApp] = useState(() => {
    const value = initialApp || new URLSearchParams(window.location.search).get("app") || "land";
    return ["land", "built", "collective", "commercial", "rent", "profile", "insight"].includes(value) ? value : "land";
  });
  const [region, setRegion] = useState(() => (screenRegion ?? new URLSearchParams(window.location.search).get("region") ?? "").slice(0, 120));
  const [metrics, setMetrics] = useState("{}");
  const [message, setMessage] = useState("");
  const [entries, setEntries] = useState<{ question: string; reply: Reply }[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [runs, setRuns] = useState<Execution[]>([]);
  const [toolId, setToolId] = useState("regions.search");
  const [argumentsText, setArgumentsText] = useState(JSON.stringify(SAMPLES["regions.search"], null, 2));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(true);
  const activeRequests = useRef(new Set<AbortController>());
  const scope = useRef(0);
  const connectionAttempt = useRef(0);

  useEffect(() => {
    if (initialApp) setApp(initialApp);
  }, [initialApp]);
  useEffect(() => {
    if (screenRegion !== undefined) setRegion(screenRegion.slice(0, 120));
  }, [screenRegion]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; activeRequests.current.forEach(c => c.abort()); };
  }, []);

  async function api<T,>(path: string, body?: unknown): Promise<T> {
    const controller = new AbortController();
    activeRequests.current.add(controller);
    try {
      const res = await fetch(`/api/ai3${path}`, {
        method: body === undefined ? "GET" : "POST", credentials: "same-origin", signal: controller.signal,
        headers: { "Content-Type": "application/json", ...(token ? { "X-Ai3-Token": token } : {}),
          ...(import.meta.env.VITE_API_TOKEN ? { "X-Api-Token": import.meta.env.VITE_API_TOKEN } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
      return data;
    } finally { activeRequests.current.delete(controller); }
  }

  async function connect() {
    const attempt = ++connectionAttempt.current;
    setBusy(true); setError("");
    try {
      const result = await api<Health>("/health");
      if (mounted.current && attempt === connectionAttempt.current) setHealth(result);
    } catch (e) {
      if (mounted.current && attempt === connectionAttempt.current && !(e instanceof DOMException && e.name === "AbortError")) {
        setError(e instanceof Error ? e.message : String(e)); setHealth(null);
      }
    } finally { if (mounted.current && attempt === connectionAttempt.current) setBusy(false); }
  }

  useEffect(() => { void connect(); }, []);

  const running = runs.some(r => ["running", "cancel_requested"].includes(r.status));
  useEffect(() => {
    if (!running || !sessionId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const currentScope = scope.current;
    async function poll() {
      try {
        const active = runs.filter(r => ["running", "cancel_requested"].includes(r.status));
        const updates = await Promise.all(active.map(r => api<Execution>(`/executions/${r.id}?session_id=${encodeURIComponent(sessionId!)}`)));
        if (!stopped && currentScope === scope.current) setRuns(old => old.map(r => updates.find(u => u.id === r.id) ?? r));
      } catch (e) { if (!stopped) setError(e instanceof Error ? e.message : String(e)); }
      if (!stopped) timer = setTimeout(poll, 2000);
    }
    timer = setTimeout(poll, 1000);
    return () => { stopped = true; clearTimeout(timer); };
  }, [running, sessionId, runs]);

  async function ask(manual = false) {
    if (busy || !health) return;
    setBusy(true); setError(""); setPlan(null);
    const currentScope = scope.current;
    const question = message.trim() || (manual ? "아래 조건으로 분석 계획을 만들어줘" : "");
    try {
      const metricValues = JSON.parse(metrics);
      const body = { session_id: sessionId, message: question, context: { app, region_label: region, metrics: metricValues },
        ...(manual ? { tool_id: toolId, arguments: JSON.parse(argumentsText) } : {}) };
      const reply = await api<Reply>("/chat", body);
      if (!mounted.current || currentScope !== scope.current) return;
      setSessionId(reply.session_id); setPlan(reply.plan); setMessage("");
      setEntries(old => [...old, { question, reply }]);
    } catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : String(e)); }
    finally { if (mounted.current) setBusy(false); }
  }

  async function execute() {
    if (!plan || !sessionId) return;
    setBusy(true); setError("");
    try {
      const result = await api<Execution>("/executions", { session_id: sessionId, plan_id: plan.id });
      setRuns(old => old.some(r => r.id === result.id) ? old : [...old, result]);
      setPlan(null);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { if (mounted.current) setBusy(false); }
  }

  async function cancel(run: Execution) {
    try {
      const result = await api<Execution>(`/executions/${run.id}/cancel`, { session_id: sessionId, plan_id: run.plan_id });
      setRuns(old => old.map(r => r.id === result.id ? result : r));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  function reset() {
    scope.current += 1;
    setSessionId(null); setEntries([]); setRuns([]); setPlan(null); setError(""); setMessage("");
  }

  return <main className={`ai3-trial max-w-5xl mx-auto p-4 space-y-4 ${embedded ? "ai3-trial-embedded" : ""}`}>
    <div className="flex flex-wrap justify-between gap-3">
      <div><h2 className="text-lg font-semibold">{embedded ? "무엇을 도와드릴까요?" : "AI3 통합 어시스턴트 시험"}</h2>
        <p className="text-sm text-slate-500">제품 전반 질문 · 통계 설명 · 승인 후 분석 · 결과 비교. AI·AI2와 별도 대화입니다.</p></div>
      <button className="btn btn-ghost text-xs" onClick={reset} disabled={busy || running}>새 대화</button>
    </div>
    <details open={!embedded} className="border border-slate-200 dark:border-slate-700 rounded p-3 space-y-2">
      <summary className="text-xs cursor-pointer">화면 및 연결 설정{embedded ? (health ? " · 연결됨" : " · 연결 확인 중") : ""}</summary>
      <div className="flex flex-wrap gap-2 items-center"><input type="password" autoComplete="off" className="input" placeholder="접근 토큰 (설정한 서버만)" value={token} onChange={e => setToken(e.target.value)} />
        <button className="btn btn-ghost text-xs" onClick={() => void connect()} disabled={busy}>연결 확인</button>
        <span className="text-xs">{health ? `연결됨 · ${health.llm_configured ? health.model : "LLM 미설정"} · AI3 월 ${health.monthly_call_limit}회 상한` : "연결 대기"}</span>
      </div>
      <p className="text-xs text-slate-500">질문·제품 지식·집계 결과를 기존 OpenAI API로 전달할 수 있습니다. 원시 거래·주소·비밀키를 질문에 넣지 마세요. 세션은 이 서버의 메모리에 보관되며 재시작하면 초기화됩니다.</p>
      <div className="flex flex-wrap gap-2"><label className="text-sm">현재 앱 <select aria-label="현재 앱" className="input" disabled={embedded} value={app} onChange={e => setApp(e.target.value)}>
        {[['land','토지'],['built','복합'],['collective','집합 주거'],['commercial','집합 비주거'],['rent','임대'],['profile','지역프로필'],['insight','Insight']].map(([v,l]) => <option key={v} value={v}>{l}</option>)}
      </select></label><input aria-label="화면 지역" className="input" readOnly={embedded} placeholder="화면 지역 (선택)" value={region} onChange={e => setRegion(e.target.value)} /></div>
      <details><summary className="text-xs cursor-pointer">화면 지표 요약 입력 (시험용)</summary><textarea aria-label="화면 지표" className="input w-full font-mono text-xs mt-2" rows={3} value={metrics} onChange={e => setMetrics(e.target.value)} /><p className="text-xs">숫자 지표만 입력합니다. 이 스냅샷은 검증된 엔진 실행 결과와 구별됩니다.</p></details>
    </details>
    {error && <p role="alert" className="text-sm text-red-600 whitespace-pre-wrap">{error}</p>}
    <section aria-label="대화 기록" className="space-y-3">{entries.map(({question, reply}, i) => <article key={i} className="border-b border-slate-200 dark:border-slate-700 py-3">
      <p className="text-sm font-semibold mb-2">{question}</p>
      {reply.limitations.length > 0 && <ul className="text-xs text-amber-800 dark:text-amber-200 mb-2">{reply.limitations.map((l,j) => <li key={j}>{l}</li>)}</ul>}
      <p className="text-sm whitespace-pre-wrap">{reply.answer}</p>
      <p className="text-xs text-slate-500 mt-2">{reply.llm_used ? "LLM 응답" : "서버 응답"} · {reply.evidence.map(e => e.label).join(" · ")}</p>
      <Facts facts={reply.facts} />
    </article>)}</section>
    {runs.map(run => <section key={run.id} aria-label="분석 실행" className="border border-slate-200 dark:border-slate-700 rounded p-3">
      <div className="flex justify-between"><strong className="text-sm">분석 상태: {({running:'실행 중',succeeded:'완료',failed:'실패',cancel_requested:'취소 요청됨',cancelled:'취소 완료'} as Record<string,string>)[run.status]}</strong>
        {run.status === "running" && <button className="btn btn-ghost text-xs" onClick={() => void cancel(run)}>취소 요청</button>}</div>
      <p className="text-xs text-slate-500 break-all">실행 ID: {run.id}</p>
      {run.limitations.map((l,i) => <p key={i} className="text-xs text-amber-800 dark:text-amber-200 mt-1">{l}</p>)}
      {run.error && <p className="text-sm text-red-600 mt-2">{run.error}</p>}
      <Facts facts={run.facts} />
      {run.result && <details className="mt-2"><summary className="text-xs cursor-pointer">전체 구조화 결과</summary><pre className="text-xs max-h-80 overflow-auto whitespace-pre-wrap">{JSON.stringify(run.result, null, 2)}</pre></details>}
      {run.status === "succeeded" && <button className="btn btn-ghost text-xs mt-2" onClick={() => setMessage("방금 완료한 분석의 결과와 한계를 설명해줘")}>이 결과 설명 질문 작성</button>}
    </section>)}
    <form onSubmit={e => { e.preventDefault(); void ask(); }} className="space-y-2">
      <textarea aria-label="AI3 질문" className="input w-full" rows={3} placeholder="어느 앱의 기능이든 질문하거나 분석을 요청하세요." value={message} onChange={e => setMessage(e.target.value)} />
      <button className="btn btn-primary text-sm" disabled={busy || !health || !message.trim()} type="submit">{busy ? "처리 중" : "질문하기"}</button>
    </form>
    {plan && <section aria-label="실행 승인" className="border border-amber-300 dark:border-amber-700 rounded p-3 space-y-2">
      <h3 className="font-semibold">{plan.label} · 실행 조건 확인</h3>
      <pre className="text-xs max-h-64 overflow-auto whitespace-pre-wrap">{JSON.stringify(plan.arguments, null, 2)}</pre>
      <button className="btn btn-primary text-sm" disabled={busy || running} onClick={() => void execute()}>승인하고 실행</button>
      <button className="btn btn-ghost text-sm ml-2" onClick={() => setPlan(null)}>실행하지 않기</button>
    </section>}
    <details className="border-t border-slate-200 dark:border-slate-700 pt-3"><summary className="cursor-pointer text-sm">도구와 조건을 직접 선택해 시험</summary>
      <p className="text-xs text-slate-500 my-2">빈 코드·기준월은 실제 값으로 채워야 합니다. 검색 도구로 지역·대상을 확인할 수 있습니다. 계획을 만든 뒤 별도로 승인합니다.</p>
      <select aria-label="분석 도구" className="input w-full" value={toolId} onChange={e => { setToolId(e.target.value); setArgumentsText(JSON.stringify(SAMPLES[e.target.value] ?? {},null,2)); }}>
        {(health?.tools ?? []).map(t => <option key={t.id} value={t.id}>{t.label}</option>)}</select>
      <textarea aria-label="도구 입력 조건" className="input w-full font-mono text-xs my-2" rows={9} value={argumentsText} onChange={e => setArgumentsText(e.target.value)} />
      <button className="btn btn-ghost text-sm" disabled={busy || !health} onClick={() => void ask(true)}>이 조건으로 계획 만들기</button>
      <details className="mt-2"><summary className="text-xs cursor-pointer">도구 입력 명세</summary><pre className="text-xs max-h-60 overflow-auto whitespace-pre-wrap">{JSON.stringify(health?.tools.find(t => t.id === toolId)?.schema, null, 2)}</pre></details>
    </details>
  </main>;
}
