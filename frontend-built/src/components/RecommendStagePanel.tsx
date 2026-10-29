import { useState, type ReactNode } from "react";
import clsx from "clsx";
import type { AssetType, RegressionLevelResult, RegressionRecommendResponse, RegressionVariableSpec, ResponseScale, PredictOptions } from "../types";
import MacroLocalResults from "./MacroLocalResults";
import MacroTwinResults from "./MacroTwinResults";

export type AdoptPoolPayload = {
  vars: RegressionVariableSpec;
  scale: ResponseScale;
  regionCodes: string[];
  label: string;
};

export type RecommendStagePanelProps = {
  data: RegressionRecommendResponse;
  onAdopt?: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  onAdoptPool?: (payload: AdoptPoolPayload) => void;
  adopting?: boolean;
  onPredict?: (
    vars: RegressionVariableSpec,
    scale: ResponseScale,
    label: string,
    opts?: { regionCodes?: string[]; fitN?: number; slot?: "twin1" | "twin2" },
  ) => void;
  predictActiveLabel?: string | null;
  twin1PredictActiveLabel?: string | null;
  twin1PredictIdentity?: string | null;
  researchPredictIdentity?: string | null;
  researchPredictActiveLabel?: string | null;
  regionNameByCode?: Record<string, string>;
  onRunTwin?: () => void;
  twinChoices?: { code: string; rank: number; label: string }[];
  checkedTwinCodes?: string[];
  resultTwinCodes?: string[];
  twinSelectionChanged?: boolean;
  twinStatus?: string;
  researchStatus?: string;
  onToggleTwinCode?: (code: string) => void;
  twinRunning?: boolean;
  onRunTwinResearch?: () => void;
  twinResearchRunning?: boolean;
  /** Profile Twin 이웃 조회 상태. ready 일 때만 실험 요청을 보낸다. */
  twinCandidateStatus?: "loading" | "ready" | "none";
  busy?: boolean;
  /** @deprecated 4단계 스토리로 통합. 호출부 호환만 유지 */
  mode?: "full" | "predictive" | "explanatory";
  predictPanel?: ReactNode;
  predictOptions?: PredictOptions | null;
  twin1PredictPanel?: ReactNode;
  researchPredictPanel?: ReactNode;
  assetType?: AssetType;
  minePrimary?: RegressionLevelResult | null;
  mineScale?: ResponseScale | null;
};

type WorkspaceTab = "predict" | "explain" | "twin";

const WORKSPACE_TABS: { id: WorkspaceTab; label: string }[] = [
  { id: "predict", label: "예측형" },
  { id: "explain", label: "설명형" },
  { id: "twin", label: "쌍둥이 확장" },
];

function WorkspaceTabs({
  value,
  onChange,
}: {
  value: WorkspaceTab;
  onChange: (next: WorkspaceTab) => void;
}) {
  return (
    <div
      className="inline-flex flex-wrap rounded-md border border-slate-200 bg-slate-50 p-0.5 text-sm dark:border-slate-600 dark:bg-slate-900/70"
      role="tablist"
      aria-label="모형 탐색 작업"
    >
      {WORKSPACE_TABS.map((tab) => {
        const selected = value === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            className={clsx(
              "px-3 py-1.5 rounded whitespace-nowrap transition-colors",
              selected && tab.id === "predict" && "bg-white shadow-sm font-medium text-indigo-800 dark:bg-slate-700 dark:text-indigo-200",
              selected && tab.id === "explain" && "bg-white shadow-sm font-medium text-teal-800 dark:bg-slate-700 dark:text-teal-200",
              selected && tab.id === "twin" && "bg-white shadow-sm font-medium text-violet-800 dark:bg-slate-700 dark:text-violet-200",
              !selected && "text-slate-500 dark:text-slate-400",
            )}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

export default function RecommendStagePanel(props: RecommendStagePanelProps) {
  const [workspace, setWorkspace] = useState<WorkspaceTab>("predict");
  const { data, assetType, busy = false, onPredict, predictPanel, predictActiveLabel, predictOptions } = props;
  const resolvedAssetType = assetType ?? (data.analysis_scope.asset_slice === "unified" ? "commercial" : data.analysis_scope.asset_slice as AssetType);
  return <div className="space-y-3 text-base">
    <WorkspaceTabs value={workspace} onChange={setWorkspace} />
    {workspace === "twin" ? <MacroTwinResults {...props} assetType={resolvedAssetType} onOpenLocal={() => setWorkspace("predict")} />
      : <MacroLocalResults key={workspace} mode={workspace} data={data} assetType={resolvedAssetType} busy={busy}
          onPredict={onPredict} predictPanel={predictPanel} predictActiveLabel={predictActiveLabel} predictOptions={predictOptions} />}
  </div>;
}
