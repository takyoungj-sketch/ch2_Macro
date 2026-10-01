import { useState } from "react";

type Action = {
  kind: string;
  message: string;
  tool_id: string | null;
  envelope: { reason_code?: string | null; valid_n?: number | null; required_n?: number | null } | null;
};

const PRESETS: { id: string; fixture: string; label: string; body: Record<string, unknown> }[] = [
  {
    id: "ask",
    fixture: "one_eligible",
    label: "대상 없음 → 질문",
    body: { region: "가경동", property_type: "apartment", analysis_type: "floor_utility" },
  },
  {
    id: "region",
    fixture: "one_eligible",
    label: "지역 전체 → 후보 제안",
    body: { region: "가경동", property_type: "apartment", analysis_type: "floor_utility", target: "region" },
  },
  {
    id: "live",
    fixture: "live",
    label: "실데이터 가경동",
    body: { region: "가경동", property_type: "apartment", analysis_type: "floor_utility", target: "region" },
  },
  {
    id: "live-twin",
    fixture: "live_twin",
    label: "실데이터 쌍둥이",
    body: { region: "흥덕구", property_type: "land", analysis_type: "twin_region" },
  },
  {
    id: "live-built",
    fixture: "live_built",
    label: "실데이터 복합 예측",
    body: {
      region: "가경동",
      property_type: "built",
      analysis_type: "built_predict",
      measure: "total",
      gross_area: 200,
      land_area: 150,
      building_age: 20,
    },
  },
  {
    id: "below",
    fixture: "below_gate",
    label: "최소 건수 미달 → 확대만",
    body: { region: "가경동", property_type: "apartment", analysis_type: "floor_utility", target: "region" },
  },
  {
    id: "named",
    fixture: "named_ok",
    label: "단지 지정 → 지수와 Insight",
    body: { region: "가경동", property_type: "apartment", analysis_type: "floor_utility", target: "세원가경골" },
  },
  {
    id: "method",
    fixture: "named_ok",
    label: "산식만 → 회귀 없음",
    body: { region: "가경동", property_type: "apartment", analysis_type: "floor_utility_method" },
  },
  {
    id: "period-snap",
    fixture: "period_snap",
    label: "기간 밖 → 보유 기간",
    body: {
      region: "가경동",
      property_type: "apartment",
      analysis_type: "floor_utility",
      target: "세원가경골",
      period: "2010-01~2010-12",
    },
  },
  {
    id: "period",
    fixture: "named_ok",
    label: "2010년 기간 → 거절",
    body: {
      region: "가경동",
      property_type: "apartment",
      analysis_type: "floor_utility",
      target: "세원가경골",
      period: "2010-01~2010-12",
    },
  },
  {
    id: "land-reg",
    fixture: "twin_worse",
    label: "토지 회귀 → 거절",
    body: { region: "흥덕구", property_type: "land", analysis_type: "land_regression" },
  },
  {
    id: "twin-no",
    fixture: "twin_worse",
    label: "쌍둥이 검증 실패",
    body: { region: "흥덕구", property_type: "land", analysis_type: "twin_region" },
  },
  {
    id: "built",
    fixture: "built_ok",
    label: "복합 예측 구간",
    body: { region: "가경동", property_type: "built", analysis_type: "built_predict" },
  },
  {
    id: "built-hide",
    fixture: "built_extrap",
    label: "외삽 → 중심값 숨김",
    body: { region: "가경동", property_type: "built", analysis_type: "built_predict" },
  },
  {
    id: "value",
    fixture: "built_ok",
    label: "총액·㎡당 질문",
    body: { region: "가경동", property_type: "built", analysis_type: "built_value" },
  },
  {
    id: "claim-n",
    fixture: "named_short",
    label: "건수 충분 주장",
    body: {
      region: "가경동",
      property_type: "apartment",
      analysis_type: "floor_utility",
      target: "짧은단지",
      claimed_n: 200,
    },
  },
  {
    id: "appraisal",
    fixture: "built_ok",
    label: "적정가 요청",
    body: { region: "가경동", property_type: "built", analysis_type: "built_predict", claim: "appraisal" },
  },
  {
    id: "ineligible",
    fixture: "one_eligible",
    label: "부적격 단지",
    body: { region: "가경동", property_type: "apartment", analysis_type: "floor_utility", target: "C아파트" },
  },
  {
    id: "two-alts",
    fixture: "two_alts",
    label: "기간·지역 대안",
    body: {
      region: "가경동",
      property_type: "apartment",
      analysis_type: "floor_utility",
      target: "세원가경골",
      period: "2010-01~2010-12",
    },
  },
  {
    id: "expand-hits",
    fixture: "expand_hits",
    label: "확대하면 후보",
    body: { region: "가경동", property_type: "apartment", analysis_type: "floor_utility", target: "region" },
  },
  {
    id: "mixed",
    fixture: "twin_worse",
    label: "토지와 아파트",
    body: {
      region: "흥덕구",
      property_type: "land",
      analysis_type: "twin_region",
      also_fixture: "named_ok",
      also_region: "가경동",
      also_property_type: "apartment",
      also_analysis_type: "floor_utility_method",
    },
  },
];

export default function Ai2ProtocolLab() {
  const [sessionId] = useState(() => `ai2-${Date.now()}`);
  const [fixture, setFixture] = useState("one_eligible");
  const [region, setRegion] = useState("가경동");
  const [propertyType, setPropertyType] = useState("apartment");
  const [analysisType, setAnalysisType] = useState("floor_utility");
  const [target, setTarget] = useState("");
  const [sentence, setSentence] = useState("가경동 아파트 층별효용");
  const [trace, setTrace] = useState<Action[]>([]);
  const [llmMode, setLlmMode] = useState("");
  const [error, setError] = useState("");

  async function send(reset: boolean, extra: Record<string, unknown>, keepContext = false) {
    setError("");
    const body: Record<string, unknown> = {
      session_id: sessionId,
      fixture,
      reset,
    };
    if (!keepContext) {
      body.region = region;
      body.property_type = propertyType;
      body.analysis_type = analysisType;
      body.target = target || null;
    }
    Object.assign(body, extra);
    const res = await fetch("/api/lab/ai2/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      setError(await res.text());
      return;
    }
    const data = await res.json();
    setLlmMode(typeof data.llm === "string" ? data.llm : "");
    setTrace(data.actions ?? []);
  }

  function sendSentence(fixtureName: string, text: string) {
    setFixture(fixtureName);
    send(true, { fixture: fixtureName, sentence: text, use_llm: true }, true);
  }

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-3 text-sm">
      <p className="text-slate-600">
        같은 OpenAI 연결을 쓴다. 화면 어시스턴트와 세션은 분리된다. 숫자는 도구 봉투에서만 온다.
        {llmMode === "used" ? " 이번 턴은 모델이 맥락만 골랐다." : ""}
        {llmMode === "fallback" ? " 모델 호출이 없어 규칙 해석을 썼다." : ""}
        {llmMode === "off" ? " 이번 턴은 규칙 해석이다." : ""}
      </p>
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            className="btn btn-ghost text-xs"
            onClick={() => {
              setFixture(p.fixture);
              send(true, { fixture: p.fixture, ...p.body });
            }}
          >
            {p.label}
          </button>
        ))}
        <button type="button" className="btn btn-ghost text-xs" onClick={() => send(false, { accept_offer: true }, true)}>
          제안 수락
        </button>
        <button type="button" className="btn btn-ghost text-xs" onClick={() => send(false, { accept_offer: true, offer_index: 1 }, true)}>
          둘째 제안
        </button>
        <button type="button" className="btn btn-ghost text-xs" onClick={() => send(false, { target: "A아파트" }, true)}>
          적격 단지로
        </button>
        <button type="button" className="btn btn-ghost text-xs" onClick={() => send(false, { measure: "unit_price" }, true)}>
          ㎡당으로
        </button>
        <button type="button" className="btn btn-ghost text-xs" onClick={() => send(false, { drop_property_type: "land" }, true)}>
          토지 빼기
        </button>
        <button type="button" className="btn btn-ghost text-xs" onClick={() => send(false, { explain: true }, true)}>
          결과 설명
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input className="input input-sm" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="region" />
        <input className="input input-sm" value={propertyType} onChange={(e) => setPropertyType(e.target.value)} placeholder="property_type" />
        <input className="input input-sm" value={analysisType} onChange={(e) => setAnalysisType(e.target.value)} placeholder="analysis_type" />
        <input className="input input-sm" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="target" />
      </div>
      <div className="flex gap-2">
        <input
          className="input input-sm flex-1"
          value={sentence}
          onChange={(e) => setSentence(e.target.value)}
          placeholder="문장"
        />
        <button type="button" className="btn btn-ghost text-xs" onClick={() => sendSentence(fixture, sentence)}>
          문장으로
        </button>
        <button type="button" className="btn btn-ghost text-xs" onClick={() => send(false, { sentence, continue_session: true, use_llm: true }, true)}>
          이어서
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn btn-ghost text-xs" onClick={() => sendSentence("one_eligible", "가경동 아파트 층별효용")}>
          문장 → 질문
        </button>
        <button type="button" className="btn btn-ghost text-xs" onClick={() => sendSentence("named_ok", "가경동 세원가경골 아파트 층별효용")}>
          문장 → 단지
        </button>
        <button type="button" className="btn btn-ghost text-xs" onClick={() => sendSentence("named_ok", "가경동 공실률")}>
          문장 → 없는 분석
        </button>
        <button type="button" className="btn btn-ghost text-xs" onClick={() => sendSentence("twin_worse", "흥덕구 토지 회귀")}>
          문장 → 토지 회귀
        </button>
      </div>
      <button type="button" className="btn btn-primary text-xs" onClick={() => send(true, {})}>
        이 맥락으로 턴
      </button>
      {error ? <pre className="text-red-600 whitespace-pre-wrap">{error}</pre> : null}
      <ol className="space-y-2">
        {trace.map((a, i) => (
          <li key={i} className="border border-slate-200 p-2">
            <div className="font-mono text-xs">{a.kind}{a.tool_id ? ` · ${a.tool_id}` : ""}</div>
            {a.message ? <p className="mt-1">{a.message}</p> : null}
            {a.envelope ? (
              <p className="mt-1 text-xs text-slate-500">
                {a.envelope.reason_code ?? ""} {a.envelope.valid_n ?? ""}/{a.envelope.required_n ?? ""}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
