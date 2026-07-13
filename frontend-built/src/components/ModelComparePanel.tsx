import { useState } from "react";
import clsx from "clsx";
import type { AiContextPayload } from "@ch2/ai-assistant/aiClient";
import type {
  ModelCandidate,
  RegressionCompareResponse,
  RegressionVariableSpec,
  ResponseScale,
} from "../types";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import AiAssistantPanel from "./AiAssistantPanel";
import { ModelComparisonCard } from "./ModelComparisonCard";
import { BUILT_MODEL_SELECTION_COMPARE_HELP } from "../utils/builtAnalysisHelp";

type RankTab = "aic" | "bic" | "mape";

const BLOCK_LABELS: Record<string, string> = {
  gross_area: "연면적",
  land_area: "대지면적",
  building_age: "연식",
  road_width: "도로조건",
  zone_type: "용도지역",
  building_use: "건축물용도",
  asset_type: "유형",
  region_leaf: "지역(읍·면·동)",
};

function blockSummary(blocks: string[]) {
  if (!blocks.length) return "(절편만)";
  return blocks.map((b) => BLOCK_LABELS[b] ?? b).join(" · ");
}

function CandidateRow({
  c,
  expanded,
  onToggle,
  onAdopt,
  onPredict,
  adopting,
  predictActive,
}: {
  c: ModelCandidate;
  expanded: boolean;
  onToggle: () => void;
  onAdopt: () => void;
  onPredict?: () => void;
  adopting?: boolean;
  predictActive?: boolean;
}) {
  return (
    <div className="border border-slate-200 dark:border-slate-600 rounded-md overflow-hidden">
      <button
        type="button"
        className="w-full text-left px-2 py-1.5 flex items-center gap-2 hover:bg-slate-50 dark:hover:bg-slate-800/50 text-xs"
        onClick={onToggle}
      >
        <span className="font-semibold text-indigo-700 dark:text-indigo-300 w-6">#{c.rank}</span>
        <span className="flex-1 min-w-0 truncate">{blockSummary(c.blocks)}</span>
        <span className="text-slate-500 shrink-0 tabular-nums">
          {c.response_scale} · MAPE {c.metrics.mape != null ? `${c.metrics.mape}%` : "—"}
        </span>
      </button>
      {expanded && (
        <div className="px-2 pb-2 space-y-2 border-t border-slate-100 dark:border-slate-700">
          <div className="flex flex-wrap gap-x-3 pt-1 text-[11px] text-slate-600 dark:text-slate-400">
            <span>AIC {c.aic?.toFixed(1) ?? "—"}</span>
            <span>BIC {c.bic?.toFixed(1) ?? "—"}</span>
            <span>Adj R² {c.metrics.adj_r_squared?.toFixed(3) ?? "—"}</span>
          </div>
          {c.model_comparison && (
            <ModelComparisonCard cmp={c.model_comparison} selected={c.response_scale} />
          )}
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              className="btn btn-primary text-[11px]"
              disabled={adopting}
              onClick={onAdopt}
            >
              {adopting ? "분석 중…" : "이 모형으로 분석"}
            </button>
            {onPredict && (
              <button
                type="button"
                className={clsx(
                  "btn text-[11px]",
                  predictActive ? "btn-primary" : "btn-ghost",
                )}
                onClick={onPredict}
              >
                {predictActive ? "예측 대상" : "이 모형으로 예측"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function ModelComparePanel({
  data,
  onAdopt,
  adopting,
  aiContext,
  embedded = false,
  onPredict,
  predictActiveLabel,
}: {
  data: RegressionCompareResponse;
  onAdopt: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  adopting?: boolean;
  aiContext?: AiContextPayload | null;
  embedded?: boolean;
  onPredict?: (vars: RegressionVariableSpec, scale: ResponseScale, label: string) => void;
  predictActiveLabel?: string | null;
}) {
  const [tab, setTab] = useState<RankTab>("aic");
  const [expandedRank, setExpandedRank] = useState<number | null>(1);

  const lists: Record<RankTab, ModelCandidate[]> = {
    aic: data.candidates_by_aic,
    bic: data.candidates_by_bic,
    mape: data.candidates_by_mape,
  };
  const candidates = lists[tab];
  const aicTop = data.candidates_by_aic[0]?.blocks ?? [];
  const bicTop = data.candidates_by_bic[0]?.blocks ?? [];
  const rankMismatch =
    aicTop.length > 0 &&
    bicTop.length > 0 &&
    JSON.stringify(aicTop) !== JSON.stringify(bicTop);

  return (
    <div
      className={clsx(
        embedded
          ? "space-y-2 text-xs"
          : "rounded-md border border-indigo-200 bg-indigo-50/40 dark:bg-indigo-950/20 dark:border-indigo-800 p-3 space-y-2 text-xs",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-indigo-900 dark:text-indigo-100">모형 비교 (Group Best Subset)</h3>
          <p className="text-slate-600 dark:text-slate-400 mt-0.5">
            scope: {data.scope_label ?? "—"} · n={data.n}
            {data.total_subsets > 0 && ` · ${data.total_subsets}개 조합`}
            {data.truncated && " (일부만 평가)"}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <AnalysisHelpPanel explain={data.explain ?? BUILT_MODEL_SELECTION_COMPARE_HELP} />
          {aiContext && <AiAssistantPanel context={aiContext} />}
        </div>
      </div>

      {rankMismatch && (
        <p className="text-amber-800 dark:text-amber-200 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded px-2 py-1">
          AIC·BIC 1위 블록 집합이 다릅니다 — 기준(AIC/BIC/MAPE 탭)을 선택하세요.
        </p>
      )}

      {data.warnings.length > 0 && (
        <ul className="text-amber-700 dark:text-amber-300 space-y-0.5">
          {data.warnings.map((w, i) => (
            <li key={i}>⚠ {w}</li>
          ))}
        </ul>
      )}

      <div className="flex gap-1">
        {(
          [
            ["aic", "AIC"],
            ["bic", "BIC"],
            ["mape", "MAPE"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={clsx(
              "px-2 py-0.5 rounded text-[11px] border",
              tab === key
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-600 text-slate-600",
            )}
            onClick={() => {
              setTab(key);
              setExpandedRank(1);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="space-y-1.5">
        {candidates.map((c) => {
          const label = `비교 #${c.rank} (${tab.toUpperCase()})`;
          return (
            <CandidateRow
              key={`${tab}-${c.rank}`}
              c={c}
              expanded={expandedRank === c.rank}
              onToggle={() => setExpandedRank((r) => (r === c.rank ? null : c.rank))}
              onAdopt={() => onAdopt(c.variables, c.response_scale)}
              onPredict={
                onPredict
                  ? () => onPredict(c.variables, c.response_scale, label)
                  : undefined
              }
              adopting={adopting}
              predictActive={predictActiveLabel === label}
            />
          );
        })}
        {!candidates.length && (
          <p className="text-slate-500">해당 지표로 랭킹할 후보가 없습니다.</p>
        )}
      </div>
    </div>
  );
}
