// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
/** AI2 입구. 화면 어시스턴트의 세션·프롬프트를 쓰지 않는다. */

import { useState, type ReactNode } from "react";

export type Ai2Domain = "land" | "built" | "collective" | "commercial" | "rent" | "profile";

type LiveSpec = {
  fixture: string;
  property_type: string;
  analysis_type: string;
  measure?: string;
  needsBuilding: boolean;
  placeholder: string;
};

const LIVE: Partial<Record<Ai2Domain, LiveSpec>> = {
  land: {
    fixture: "live_twin",
    property_type: "land",
    analysis_type: "twin_region",
    needsBuilding: false,
    placeholder: "흥덕구 토지 쌍둥이",
  },
  built: {
    fixture: "live_built",
    property_type: "built",
    analysis_type: "built_predict",
    measure: "total",
    needsBuilding: true,
    placeholder: "가경동 복합 예측",
  },
  collective: {
    fixture: "live",
    property_type: "apartment",
    analysis_type: "floor_utility",
    needsBuilding: false,
    placeholder: "가경동 아파트 층별효용",
  },
  commercial: {
    fixture: "live_shop",
    property_type: "collective_shop",
    analysis_type: "shop_floor",
    needsBuilding: false,
    placeholder: "가경동 상가 면적형, 공장 또는 면적대",
  },
  rent: {
    fixture: "live_rent",
    property_type: "rent",
    analysis_type: "rent_conversion",
    needsBuilding: false,
    placeholder: "흥덕구 전월세 전환율",
  },
  profile: {
    fixture: "live_profile",
    property_type: "profile",
    analysis_type: "profile_twin",
    needsBuilding: false,
    placeholder: "흥덕구 지역 쌍둥이",
  },
};

type Alternative = {
  id: string;
  change: string;
  needs_confirm: boolean;
};

type Action = {
  kind: string;
  message: string;
  alternatives?: Alternative[];
};

/** 잎이 하나면 그 이름, 아니면 구가 하나, 아니면 시군구 하나. 여러 곳이면 빈 문자열. */
export function singleScreenRegion(input: {
  leaf?: readonly string[];
  gu?: readonly string[];
  sigungu?: string;
}): string {
  const leaf = (input.leaf ?? []).map((name) => name.trim()).filter(Boolean);
  const gu = (input.gu ?? []).map((name) => name.trim()).filter(Boolean);
  const sigungu = (input.sigungu ?? "").trim();
  if (leaf.length === 1) return leaf[0];
  if (leaf.length === 0 && gu.length === 1) return gu[0];
  if (leaf.length === 0 && gu.length === 0 && sigungu) return sigungu;
  return "";
}

export function Ai2HeaderSlot({
  domain,
  screenRegion = "",
  screenTarget = "",
  children,
}: {
  domain: Ai2Domain;
  screenRegion?: string;
  screenTarget?: string;
  children: ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <Ai2Entry domain={domain} screenRegion={screenRegion} screenTarget={screenTarget} />
      {children}
    </span>
  );
}

export default function Ai2Entry({
  domain,
  screenRegion = "",
  screenTarget = "",
}: {
  domain: Ai2Domain;
  screenRegion?: string;
  screenTarget?: string;
}) {
  const spec = LIVE[domain];
  const [open, setOpen] = useState(false);
  const [sessionId] = useState(() => `ai2-${domain}-${Date.now()}`);
  const [sentence, setSentence] = useState("");
  const [grossArea, setGrossArea] = useState("");
  const [landArea, setLandArea] = useState("");
  const [buildingAge, setBuildingAge] = useState("");
  const [trace, setTrace] = useState<Action[]>([]);
  const [started, setStarted] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const last = trace[trace.length - 1];
  const waiting = last?.kind === "ask" || last?.kind === "offer";
  const offers = last?.kind === "offer" ? last.alternatives ?? [] : [];

  async function post(reset: boolean, extra: Record<string, unknown>) {
    if (!spec) return;
    setError("");
    setBusy(true);
    const body: Record<string, unknown> = {
      session_id: sessionId,
      fixture: spec.fixture,
      reset,
      use_llm: true,
      ...extra,
    };
    if (reset) {
      body.property_type = spec.property_type;
      body.analysis_type = spec.analysis_type;
      if (spec.measure) body.measure = spec.measure;
      if (screenRegion.trim()) body.screen_region = screenRegion.trim();
      if (screenTarget.trim()) body.screen_target = screenTarget.trim();
    }
    if (spec.needsBuilding) {
      if (grossArea.trim()) body.gross_area = Number(grossArea);
      if (landArea.trim()) body.land_area = Number(landArea);
      if (buildingAge.trim()) body.building_age = Number(buildingAge);
    }
    try {
      const res = await fetch("/api/lab/ai2/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        setError(await res.text());
        setTrace([]);
        return;
      }
      const data = await res.json();
      setTrace(Array.isArray(data.actions) ? data.actions : []);
      setStarted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "요청에 실패했습니다.");
      setTrace([]);
    } finally {
      setBusy(false);
    }
  }

  function send() {
    const reset = !started || !waiting;
    const extra: Record<string, unknown> = { sentence: sentence.trim() };
    if (!reset) extra.continue_session = true;
    void post(reset, extra);
  }

  function accept(index: number) {
    void post(false, { accept_offer: true, offer_index: index, continue_session: true });
  }

  return (
    <>
      <span className="inline-flex shrink-0">
        <button
          type="button"
          className="btn btn-ghost shrink-0"
          title="화면 어시스턴트와 세션이 분리된 AI2"
          onClick={() => setOpen(true)}
        >
          AI2
        </button>
      </span>
      {open ? (
        <div
          role="dialog"
          aria-label="AI2"
          className="fixed right-4 top-20 z-[80] w-[min(24rem,calc(100vw-2rem))] rounded border border-slate-200 bg-white p-3 text-sm shadow dark:border-slate-600 dark:bg-slate-800"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <strong>AI2</strong>
            <button type="button" className="btn btn-ghost text-xs" onClick={() => setOpen(false)}>
              닫기
            </button>
          </div>
          <p className="mb-2 text-xs text-slate-500">
            화면 어시스턴트와 세션이 분리됩니다. 숫자는 도구 결과입니다.
            {screenRegion.trim() ? ` 화면 지역은 ${screenRegion.trim()}입니다. 문장에 지역이 있으면 문장을 씁니다.` : ""}
            {screenTarget.trim() ? ` 화면 대상은 ${screenTarget.trim()}입니다. 문장에 대상이 있으면 문장을 씁니다.` : ""}
          </p>
          {spec ? (
            <>
              <textarea
                className="input mb-2 w-full"
                rows={3}
                value={sentence}
                placeholder={spec.placeholder}
                onChange={(event) => setSentence(event.target.value)}
              />
              {spec.needsBuilding ? (
                <div className="mb-2 grid grid-cols-3 gap-2">
                  <input className="input" value={grossArea} placeholder="연면적" onChange={(event) => setGrossArea(event.target.value)} />
                  <input className="input" value={landArea} placeholder="대지면적" onChange={(event) => setLandArea(event.target.value)} />
                  <input className="input" value={buildingAge} placeholder="연식" onChange={(event) => setBuildingAge(event.target.value)} />
                </div>
              ) : null}
              <button type="button" className="btn btn-primary text-xs" disabled={busy || !sentence.trim()} onClick={send}>
                {busy ? "계산 중" : "묻기"}
              </button>
              {offers.length > 0 ? (
                <div className="mt-2 flex flex-col gap-1">
                  {offers.map((alt, index) => (
                    <button
                      key={`${alt.id}-${index}`}
                      type="button"
                      className="btn btn-ghost text-xs"
                      disabled={busy}
                      onClick={() => accept(index)}
                    >
                      {alt.change}
                    </button>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <p>이 화면의 실데이터 도구는 아직 없습니다. 픽스처 숫자로 대신하지 않습니다.</p>
          )}
          {error ? <pre className="mt-2 whitespace-pre-wrap text-red-600">{error}</pre> : null}
          <ol className="mt-2 space-y-2">
            {trace.filter((action) => action.message).map((action, index) => (
              <li key={index} className="border border-slate-200 p-2 dark:border-slate-600">
                {action.message ? <p>{action.message}</p> : null}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </>
  );
}
