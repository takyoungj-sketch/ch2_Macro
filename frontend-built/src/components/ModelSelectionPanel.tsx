import clsx from "clsx";
import type { AiContextPayload } from "@ch2/ai-assistant/aiClient";
import type { RegressionSuggestResponse, RegressionVariableSpec, ResponseScale } from "../types";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import AiAssistantPanel from "./AiAssistantPanel";
import { ModelComparisonCard } from "./ModelComparisonCard";
import { BUILT_MODEL_SELECTION_SUGGEST_HELP } from "../utils/builtAnalysisHelp";

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

function fmtMetric(v: number | null | undefined, digits = 3) {
  if (v == null) return "—";
  return v.toFixed(digits);
}

export function ModelSelectionPanel({
  data,
  onAdopt,
  adopting,
  aiContext,
  embedded = false,
  onPredict,
  predictActive,
}: {
  data: RegressionSuggestResponse;
  onAdopt: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  adopting?: boolean;
  aiContext?: AiContextPayload | null;
  embedded?: boolean;
  onPredict?: (vars: RegressionVariableSpec, scale: ResponseScale, label: string) => void;
  predictActive?: boolean;
}) {
  const included = data.recommended_blocks.map((id) => BLOCK_LABELS[id] ?? id);
  return (
    <div
      className={clsx(
        embedded
          ? "space-y-2 text-xs"
          : "rounded-md border border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/20 dark:border-emerald-800 p-3 space-y-2 text-xs",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-emerald-900 dark:text-emerald-100">추천 모형 (Group Forward)</h3>
          <p className="text-slate-600 dark:text-slate-400 mt-0.5">
            scope: {data.scope_label ?? "—"} · n={data.n} · scale={data.response_scale}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <AnalysisHelpPanel explain={data.explain ?? BUILT_MODEL_SELECTION_SUGGEST_HELP} />
          {aiContext && <AiAssistantPanel context={aiContext} />}
          <button
          type="button"
          className="btn btn-primary text-xs shrink-0"
          disabled={adopting}
          onClick={() => onAdopt(data.recommended_variables, data.response_scale)}
        >
          {adopting ? "분석 중…" : "이 모형으로 분석"}
          </button>
          {onPredict && (
            <button
              type="button"
              className={clsx("btn text-xs shrink-0", predictActive ? "btn-primary" : "btn-ghost")}
              onClick={() =>
                onPredict(
                  data.recommended_variables,
                  data.response_scale,
                  "추천 모형 (Group Forward)",
                )
              }
            >
              {predictActive ? "예측 대상" : "이 모형으로 예측"}
            </button>
          )}
        </div>
      </div>

      {data.warnings.length > 0 && (
        <ul className="text-amber-700 dark:text-amber-300 space-y-0.5">
          {data.warnings.map((w, i) => (
            <li key={i}>⚠ {w}</li>
          ))}
        </ul>
      )}

      <div>
        <span className="font-medium text-slate-700 dark:text-slate-200">포함 블록: </span>
        {included.length ? included.join(", ") : "(절편만)"}
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-600 dark:text-slate-400">
        <span>Adj R² {fmtMetric(data.metrics.adj_r_squared)}</span>
        <span>MAPE {data.metrics.mape != null ? `${data.metrics.mape}%` : "—"}</span>
        <span>AIC {fmtMetric(data.forward_steps.length ? data.forward_steps[data.forward_steps.length - 1]!.aic_after : undefined, 1)}</span>
      </div>

      {data.model_comparison && (
        <ModelComparisonCard cmp={data.model_comparison} selected={data.response_scale} />
      )}

      {data.excluded.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer font-medium text-slate-700 dark:text-slate-200">
            제외 블록 {data.excluded.length}개
          </summary>
          <ul className="mt-1 space-y-1.5 pl-2 border-l-2 border-slate-200 dark:border-slate-600">
            {data.excluded.map((ex) => (
              <li key={ex.block_id}>
                <span className="font-medium">{ex.label}</span>
                <ul className="text-slate-500 dark:text-slate-400 mt-0.5 space-y-0.5">
                  {ex.reasons.map((r, i) => (
                    <li key={i} className={clsx(r.code === "forward_stop" && "italic")}>
                      · {r.message}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </details>
      )}

      {data.forward_steps.length > 0 && (
        <details>
          <summary className="cursor-pointer text-slate-500">Forward 단계 ({data.forward_steps.length})</summary>
          <ol className="mt-1 list-decimal pl-4 space-y-0.5 text-slate-500">
            {data.forward_steps.map((s, i) => (
              <li key={i}>
                +{s.block_label}: AIC {s.aic_before.toFixed(1)} → {s.aic_after.toFixed(1)}
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
