import { useCallback, useEffect, useState, type ReactNode } from "react";
import TwinExperimentLab from "../../frontend-built/src/components/TwinExperimentLab";
import LabHome from "./components/LabHome";
import PlanLog from "./components/PlanLog";
import QaAuditPanel from "./components/QaAuditPanel";
import RentConversionLab from "./components/RentConversionLab";
import WhyDecision, { WhyLinks } from "./components/WhyDecision";
import { TOOL_WHY } from "./labContent";

export type LabTool = "plan" | "qa" | "twin" | "rent";

type LabParams = {
  tool: LabTool | null;
  why: string | null;
};

function readParams(): LabParams {
  const q = new URLSearchParams(window.location.search);
  const t = q.get("tool");
  const tool = t === "plan" || t === "qa" || t === "twin" || t === "rent" ? t : null;
  return {
    tool,
    why: q.get("why") || q.get("decision"),
  };
}

function writeParams(p: LabParams) {
  const url = new URL(window.location.href);
  if (p.tool) url.searchParams.set("tool", p.tool);
  else url.searchParams.delete("tool");
  if (p.why) url.searchParams.set("why", p.why);
  else url.searchParams.delete("why");
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
    setParams((p) => ({ ...p, tool, why: null }));
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
            <WhyLinks ids={TOOL_WHY.twin} onWhy={setWhy} />
            <span className="text-[11px] text-slate-500">숫자는 실험 API · 가중치는 실험적</span>
          </div>
        </div>
        <TwinExperimentLab onClose={back} closeLabel="관리자로" />
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
