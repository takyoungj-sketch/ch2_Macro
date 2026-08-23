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
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { CandidateValidationList } from "./CandidateValidationList";
import { ModelComparisonCard } from "./ModelComparisonCard";
import { PoolingEvaluationCard } from "./PoolingEvaluationCard";
import { BUILT_MODEL_SELECTION_COMPARE_HELP } from "../utils/builtAnalysisHelp";

type RankTab = "aic" | "bic" | "mape" | "cv_mape";

const BLOCK_LABELS: Record<string, string> = {
  gross_area: "연면적",
  land_area: "대지면적",
  building_age: "연식",
  road_width: "도로조건",
  zone_type: "용도지역",
  building_use: "건축물용도",
  structure: "구조",
  asset_type: "유형",
  region_leaf: "지역(읍·면·동/법정리)",
};

function blockSummary(blocks: string[]) {
  if (!blocks.length) return "(절편만)";
  return blocks.map((b) => BLOCK_LABELS[b] ?? b).join(" · ");
}

function modelPurpose(metric: RankTab): string {
  if (metric === "cv_mape") return "예측모델";
  if (metric === "aic" || metric === "bic") return "설명모델";
  return "참고모델";
}

function jointTestSummary(tests: ModelCandidate["joint_f_tests"]) {
  if (!tests) return null;
  const tested = Object.entries(tests).filter(([, test]) => test.tested);
  if (!tested.length) return null;
  return tested.map(([block, test]) => {
    const p = test.p_value;
    const tone =
      p == null || p >= 0.1
        ? "text-red-600 dark:text-red-400"
        : p >= 0.05
          ? "text-amber-600 dark:text-amber-400"
          : "text-emerald-600 dark:text-emerald-400";
    const mark = p == null || p >= 0.1 ? "✕" : p >= 0.05 ? "△" : "✓";
    return (
      <span key={block} className={tone}>
        Joint F {BLOCK_LABELS[block] ?? block} {mark}
      </span>
    );
  });
}

function CandidateRow({
  c,
  expanded,
  onToggle,
  onAdopt,
  onPredict,
  adopting,
  predictActive,
  rankMetric,
}: {
  c: ModelCandidate;
  expanded: boolean;
  onToggle: () => void;
  onAdopt: () => void;
  onPredict?: () => void;
  adopting?: boolean;
  predictActive?: boolean;
  rankMetric: RankTab;
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
          {modelPurpose(rankMetric)} ·{" "}
          {c.response_scale} ·{" "}
          {rankMetric === "cv_mape"
            ? `CV-MAPE ${c.metrics.cv_mape != null ? `${c.metrics.cv_mape}%` : "—"}`
            : `MAPE ${c.metrics.mape != null ? `${c.metrics.mape}%` : "—"}`}
        </span>
      </button>
      {expanded && (
        <div className="px-2 pb-2 space-y-2 border-t border-slate-100 dark:border-slate-700">
          <div className="flex flex-wrap gap-x-3 pt-1 text-[11px] text-slate-600 dark:text-slate-400">
            <span>AIC {c.aic?.toFixed(1) ?? "—"}</span>
            <span>BIC {c.bic?.toFixed(1) ?? "—"}</span>
            <span>Adj R² {c.metrics.adj_r_squared?.toFixed(3) ?? "—"}</span>
            <span>
              CV-MAPE {c.metrics.cv_mape != null ? `${c.metrics.cv_mape}%` : "—"}
              {c.metrics.cv_folds ? ` (${c.metrics.cv_folds}개 fold)` : ""}
            </span>
            {jointTestSummary(c.joint_f_tests)}
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
  regionNameByCode,
}: {
  data: RegressionCompareResponse;
  onAdopt: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  adopting?: boolean;
  aiContext?: AiContextPayload | null;
  embedded?: boolean;
  onPredict?: (vars: RegressionVariableSpec, scale: ResponseScale, label: string) => void;
  predictActiveLabel?: string | null;
  regionNameByCode?: Record<string, string>;
}) {
  const [tab, setTab] = useState<RankTab>("aic");
  const [expandedRank, setExpandedRank] = useState<number | null>(1);

  const lists: Record<RankTab, ModelCandidate[]> = {
    aic: data.candidates_by_aic,
    bic: data.candidates_by_bic,
    mape: data.candidates_by_mape,
    cv_mape: data.candidates_by_cv_mape ?? [],
  };
  const candidates = lists[tab];
  const rankLabel =
    tab === "aic"
      ? "AIC (설명)"
      : tab === "bic"
        ? "BIC (설명)"
        : tab === "cv_mape"
          ? "CV-MAPE (예측)"
          : "MAPE (참고)";
  const topCandidate = candidates[0];
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
            {data.selection_n != null && ` · 공통 표본 n=${data.selection_n}`}
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
          순위 기준에 따라 1위 모형이 달라질 수 있습니다. AIC/BIC는 설명 목적,
          MAPE/CV-MAPE는 예측 목적의 지표입니다.
        </p>
      )}

      {data.warnings.length > 0 && (
        <ul className="text-amber-700 dark:text-amber-300 space-y-0.5">
          {data.warnings.map((w, i) => (
            <li key={i}>⚠ {w}</li>
          ))}
        </ul>
      )}

      <PoolingEvaluationCard
        evaluation={data.pooling_evaluation}
        regionNameByCode={regionNameByCode}
      />

      <div className="flex items-center gap-2">
        <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-300">
          순위 기준
        </span>
        {(
          [
            ["aic", "AIC"],
            ["bic", "BIC"],
            ["mape", "MAPE"],
            ["cv_mape", "CV-MAPE"],
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
        <span className="inline-flex items-center gap-0.5 ml-1">
          <StatsGlossaryHelp termId="aic" size="xs" />
          <StatsGlossaryHelp termId="bic" size="xs" />
          <StatsGlossaryHelp termId="mape" size="xs" />
          <StatsGlossaryHelp termId="cv_mape" size="xs" />
        </span>
      </div>
      <p className="text-[11px] text-slate-500 dark:text-slate-400">
        현재 순위 기준: <span className="font-semibold">{rankLabel}</span>
      </p>
      {topCandidate && (
        <p className="rounded bg-indigo-50 px-2 py-1 text-[11px] text-indigo-900 dark:bg-indigo-950/30 dark:text-indigo-200">
          추천 이유: {rankLabel} 기준 1위 후보이며, 공통 표본 n={data.selection_n ?? data.n}에서
          {tab === "cv_mape"
            ? ` CV-MAPE ${topCandidate.metrics.cv_mape ?? "—"}%가 가장 낮습니다.`
            : " 후보 간 동일한 표본과 기준으로 평가했습니다."}
        </p>
      )}

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
              rankMetric={tab}
            />
          );
        })}
        {!candidates.length && (
          <p className="text-slate-500">해당 지표로 랭킹할 후보가 없습니다.</p>
        )}
      </div>

      <CandidateValidationList
        validations={data.candidate_validations}
        poolingEvaluation={data.pooling_evaluation}
      />
    </div>
  );
}
