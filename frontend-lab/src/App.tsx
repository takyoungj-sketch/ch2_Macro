import { useCallback, useEffect, useState, type ReactNode } from "react";
import TwinExperimentLab from "../../frontend-built/src/components/TwinExperimentLab";
import LabHome from "./components/LabHome";
import PlanLog from "./components/PlanLog";
import QaAuditPanel from "./components/QaAuditPanel";
import RentConversionLab from "./components/RentConversionLab";
import TwinEngineV2Lab from "./components/TwinEngineV2Lab";
import AiUsagePanel from "./components/AiUsagePanel";
import WhyDecision, { WhyLinks } from "./components/WhyDecision";
import { TOOL_WHY } from "./labContent";

export type LabTool = "plan" | "qa" | "twin" | "rent" | "ai";
export type TwinPane = "v2" | "mape";

type LabParams = {
  tool: LabTool | null;
  why: string | null;
  twinPane: TwinPane;
};

function readParams(): LabParams {
  const q = new URLSearchParams(window.location.search);
  const t = q.get("tool");
  const tool =
    t === "plan" || t === "qa" || t === "twin" || t === "rent" || t === "ai" ? t : null;
  const pane = q.get("pane");
  return {
    tool,
    why: q.get("why") || q.get("decision"),
    twinPane: pane === "mape" ? "mape" : "v2",
  };
}

function writeParams(p: LabParams) {
  const url = new URL(window.location.href);
  if (p.tool) url.searchParams.set("tool", p.tool);
  else url.searchParams.delete("tool");
  if (p.why) url.searchParams.set("why", p.why);
  else url.searchParams.delete("why");
  if (p.tool === "twin" && p.twinPane === "mape") url.searchParams.set("pane", "mape");
  else url.searchParams.delete("pane");
  url.searchParams.delete("decision");
  url.searchParams.delete("journal");
  window.history.replaceState({}, "", url.pathname + url.search);
}

export default function App() {
  const [params, setParams] = useState<LabParams>(() => readParams());

  useEffect(() => {
    writeParams(params);
  }, [params]);

  const setTool = useCallback((tool: LabTool | null) => {
    setParams((p) => ({ ...p, tool, why: null, twinPane: tool === "twin" ? p.twinPane : "v2" }));
  }, []);
  const setTwinPane = useCallback((twinPane: TwinPane) => {
    setParams((p) => ({ ...p, twinPane }));
  }, []);
  const setWhy = useCallback((why: string | null) => {
    setParams((p) => ({ ...p, why }));
  }, []);
  const back = useCallback(() => setTool(null), [setTool]);

  const whyModal = params.why ? (
    <WhyDecision id={params.why} onClose={() => setWhy(null)} />
  ) : null;

  if (params.tool === "plan") {
    return (
      <LabChrome title="계획일지" whyIds={TOOL_WHY.plan} onWhy={setWhy} onBack={back}>
        <PlanLog onWhy={setWhy} />
        {whyModal}
      </LabChrome>
    );
  }
  if (params.tool === "twin") {
    return (
      <>
        <div className="border-b border-amber-200 bg-amber-50/80 dark:bg-amber-950/30 dark:border-amber-900 px-4 py-1.5">
          <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <WhyLinks ids={TOOL_WHY.twin} onWhy={setWhy} />
              <div className="inline-flex rounded border border-amber-300/80 dark:border-amber-800 p-0.5">
                <button
                  type="button"
                  className={`px-2 py-0.5 text-[11px] rounded ${
                    params.twinPane === "v2"
                      ? "bg-amber-800 text-white dark:bg-amber-200 dark:text-amber-950"
                      : "text-amber-900 dark:text-amber-100"
                  }`}
                  onClick={() => setTwinPane("v2")}
                >
                  V2 거리
                </button>
                <button
                  type="button"
                  className={`px-2 py-0.5 text-[11px] rounded ${
                    params.twinPane === "mape"
                      ? "bg-amber-800 text-white dark:bg-amber-200 dark:text-amber-950"
                      : "text-amber-900 dark:text-amber-100"
                  }`}
                  onClick={() => setTwinPane("mape")}
                >
                  V1 풀 실험
                </button>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-slate-500">제품 프로필 카드는 아직 V1</span>
              <button type="button" className="btn btn-ghost text-xs" onClick={back}>
                관리자로
              </button>
            </div>
          </div>
        </div>
        {params.twinPane === "v2" ? (
          <TwinEngineV2Lab />
        ) : (
          <TwinExperimentLab onClose={back} closeLabel="관리자로" />
        )}
        {whyModal}
      </>
    );
  }
  if (params.tool === "rent") {
    return (
      <LabChrome title="전월세 전환율" whyIds={TOOL_WHY.rent} onWhy={setWhy} onBack={back}>
        <RentConversionLab onBack={back} />
        {whyModal}
      </LabChrome>
    );
  }
  if (params.tool === "qa") {
    return (
      <LabChrome title="검증로봇" whyIds={TOOL_WHY.qa} onWhy={setWhy} onBack={back}>
        <QaAuditPanel onWhy={() => setWhy(TOOL_WHY.qa[0])} />
        {whyModal}
      </LabChrome>
    );
  }
  if (params.tool === "ai") {
    return (
      <LabChrome title="AI 사용량" whyIds={TOOL_WHY.ai} onWhy={setWhy} onBack={back}>
        <AiUsagePanel />
        {whyModal}
      </LabChrome>
    );
  }

  return (
    <>
      <LabHome onOpenTool={setTool} />
      {whyModal}
    </>
  );
}

function LabChrome({
  title,
  whyIds,
  onWhy,
  onBack,
  children,
}: {
  title: string;
  whyIds: string[];
  onWhy: (id: string) => void;
  onBack: () => void;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-800/80">
        <div className="max-w-[96rem] mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">관리자</p>
            <h1 className="text-lg font-bold">{title}</h1>
            <WhyLinks ids={whyIds} onWhy={onWhy} className="mt-1" />
          </div>
          <button type="button" className="btn btn-ghost text-xs" onClick={onBack}>
            관리자로
          </button>
        </div>
      </header>
      {children}
    </div>
  );
}
