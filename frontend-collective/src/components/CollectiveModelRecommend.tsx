import { useState } from "react";
import { ModelRecommendSection } from "@ch2/model-recommend";
import type { ModelRecommendPurposeTab } from "@ch2/model-recommend";
import type { RegressionModelType } from "../types";
import type { RegressionValidationContext } from "../../../shared/regression-ui/types";
import { validationCaption } from "../../../shared/regression-ui/validation";
import ValidationStatus from "../../../shared/regression-ui/ValidationStatus";

const SCALE_LABEL: Record<string, string> = {
  linear: "선형",
  log: "로그",
};

const BLOCK_LABEL: Record<string, string> = {
  exclusive_area: "전용면적",
  building_age: "연식",
  floor: "층",
  dong: "동",
  housing_subtype: "권리",
  contract_period: "거래시점",
  households: "총 세대수",
  parking: "세대당 주차",
  assessed_land_price: "개별공시지가",
  structure: "구조",
  asset_type_dummy: "유형",
  gross_area: "연면적",
  zone_type: "용도지역",
  building_use: "건축물용도",
  road_width: "도로폭",
  road_code: "도로폭(m)",
};

export type ScaleSearchCandidate = {
  cv_diagnostics?: RegressionValidationContext | null;
  validation?: RegressionValidationContext | null;
  comparison?: import("../../../shared/regression-ui/types").RegressionComparisonContext | null;
  rank: number;
  purpose?: "predictive" | "explanatory";
  blocks: string[];
  model_type: RegressionModelType;
  n: number;
  adj_r_squared?: number | null;
  mape?: number | null;
  cv_mape?: number | null;
  hold_mape?: number | null;
};

export type ScaleSearchPick = {
  modelType: RegressionModelType;
  blocks: string[];
};

function fmtPct(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(1)}%`;
}

function fmtAdj(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(3);
}

function blockLine(blocks: string[], labels: Record<string, string>) {
  if (!blocks.length) return "변수 없음";
  return blocks.map((name) => labels[name] ?? name).join(" · ");
}

function errorOf(row: ScaleSearchCandidate) {
  if (row.hold_mape != null) return { label: "분리 검증 MAPE", value: row.hold_mape };
  if (row.cv_mape != null) return { label: "5겹 교차검증 MAPE", value: row.cv_mape };
  return { label: "표본 안 MAPE", value: row.mape };
}

function tabsFor(
  candidates: ScaleSearchCandidate[],
  labels: Record<string, string>,
  samplePhrase: string,
  outcomeNoun: string,
): ModelRecommendPurposeTab[] {
  const predictive = candidates
    .filter((row) => (row.purpose ?? "predictive") === "predictive")
    .sort((a, b) => a.rank - b.rank);
  const explanatory = candidates
    .filter((row) => row.purpose === "explanatory")
    .sort((a, b) => a.rank - b.rank);
  const basis = errorOf(predictive[0] ?? { mape: null, blocks: [], model_type: "linear", n: 0, rank: 0 }).label;

  const toRows = (rows: ScaleSearchCandidate[], purpose: "predictive" | "explanatory") =>
    rows.map((row) => {
      const err = errorOf(row);
      const scale = SCALE_LABEL[row.model_type] ?? row.model_type;
      const lead = row.rank === 1
        ? `${scale} · ${blockLine(row.blocks, labels)} · 이 목적의 후보`
        : `${scale} · ${blockLine(row.blocks, labels)}`;
      const metrics =
        purpose === "explanatory"
          ? `원척도 Adj R² ${fmtAdj(row.adj_r_squared)} · ${err.label} ${fmtPct(err.value)} · n=${row.n}`
          : `${err.label} ${fmtPct(err.value)} · 원척도 Adj R² ${fmtAdj(row.adj_r_squared)} · n=${row.n}`;
      const unit = row.comparison?.observation_unit === "complex" ? "곳" : "건";
      const coverage = row.comparison ? ` · 적합 ${row.comparison.fit_n}${unit}${row.comparison.evaluation_n != null ? ` · 검증 ${row.comparison.evaluation_n}${unit}` : " · 검증 미제공"}` : "";
      const validation = validationCaption(row.cv_diagnostics ?? row.validation);
      return { key: `${purpose}-${row.rank}-${row.model_type}`, primary: lead, metrics: metrics + coverage + (validation ? ` · ${validation}` : "") };
    });

  return [
    {
      id: "predictive",
      label: "예측형",
      optimizeSentence: `${samplePhrase} 변수와 선형·로그를 탐색했습니다. ${outcomeNoun} 원척도 ${basis}가 낮은 후보입니다.`,
      rows: toRows(predictive, "predictive"),
      emptyText: "예측형 후보가 없습니다.",
    },
    {
      id: "explanatory",
      label: "설명형",
      optimizeSentence: `${samplePhrase} 변수와 선형·로그를 탐색했습니다. ${outcomeNoun} 원척도 Adj R²가 높은 후보입니다.`,
      rows: toRows(explanatory, "explanatory"),
      emptyText: "설명형 후보가 없습니다.",
    },
  ];
}

export function blocksMatch(a: string[], b: string[]) {
  if (a.length !== b.length) return false;
  const left = [...a].sort();
  const right = [...b].sort();
  return left.every((name, i) => name === right[i]);
}

export default function CollectiveModelRecommend({
  candidates,
  selectedType,
  selectedBlocks,
  selectionN,
  datasetNote,
  onAdopt,
  blockLabels,
  samplePhrase = "선택한 거래에서",
  outcomeNoun = "금액",
  applyNote = "후보를 적용하면 변수와 척도 설정이 바뀝니다. 회귀를 다시 실행해야 결과와 추정에 반영됩니다.",
}: {
  candidates?: ScaleSearchCandidate[] | null;
  selectedType: RegressionModelType;
  selectedBlocks: string[];
  selectionN?: number | null;
  datasetNote: string;
  onAdopt: (pick: ScaleSearchPick) => void;
  blockLabels?: Record<string, string>;
  samplePhrase?: string;
  outcomeNoun?: string;
  applyNote?: string;
}) {
  const rows = candidates ?? [];
  const labels = { ...BLOCK_LABEL, ...blockLabels };
  const tabs = rows.length ? tabsFor(rows, labels, samplePhrase, outcomeNoun) : [];
  const [tabId, setTabId] = useState("predictive");
  const purpose = tabId === "explanatory" ? "explanatory" : "predictive";
  const chosen = rows
    .filter((row) => (row.purpose ?? "predictive") === purpose)
    .sort((a, b) => a.rank - b.rank)[0];
  const already = Boolean(
    chosen && chosen.model_type === selectedType && blocksMatch(chosen.blocks, selectedBlocks),
  );

  if (!tabs.length || !chosen) {
    return (
      <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-3 text-xs dark:border-indigo-800 dark:bg-indigo-950/20">
        <p className="font-semibold text-indigo-900 dark:text-indigo-100">모형 추천</p>
        <p className="mt-1 text-[11px] text-slate-500">공통 유효 표본에서 비교 가능한 후보를 제공하지 못했습니다. 자료의 범위와 결측 상태를 확인하세요.</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <ModelRecommendSection
        depth="standard_plus"
        selectionN={chosen.comparison?.sample_n ?? selectionN}
        limitations={`${datasetNote} 탐색 변수 풀에서 후보를 찾습니다. 다른 지역은 넣지 않습니다. 후보는 통계적 비교용이며 감정평가액을 제시하지 않습니다.`}
        tabs={tabs}
        defaultTabId="predictive"
        onTabChange={setTabId}
        headerExtra={
          <button
            type="button"
            className="btn btn-primary text-[11px] ml-auto"
            disabled={already}
            onClick={() => onAdopt({ modelType: chosen.model_type, blocks: chosen.blocks })}
          >
            {already ? "설정에 반영됨 · 다시 분석해야 적용됩니다" : "이 후보 적용"}
          </button>
        }
      />
      {chosen.comparison && <p className="text-[11px] text-slate-600 dark:text-slate-300">
        후보 비교는 공통 완전 관측 {chosen.comparison.sample_n.toLocaleString("ko-KR")}{chosen.comparison.observation_unit === "complex" ? "곳" : "건"}을 사용합니다.
        {chosen.comparison.role === "selection_validation"
          ? ` 선정용 검증 ${chosen.comparison.evaluation_n?.toLocaleString("ko-KR") ?? "—"}${chosen.comparison.observation_unit === "complex" ? "곳" : "건"} · ${chosen.comparison.method.startsWith("random_holdout") ? "무작위 분리 검증" : "5겹 교차검증"}입니다. 독립 확인 결과는 아닙니다.`
          : " 이 후보의 선정 지표는 학습 오차입니다. 교차검증 실행 상태와 미제공 이유를 확인하세요. 새로운 관측에 대한 정확도를 검증한 결과가 아닙니다."}
        {" 후보 적용 후 재실행은 해당 변수의 유효 표본으로 다시 적합하므로 표본 수와 지표가 달라질 수 있습니다."}
      </p>}
      <ValidationStatus report={chosen.cv_diagnostics ?? chosen.validation} />
      <p className="text-[10px] text-slate-500 dark:text-slate-400">{applyNote}</p>
    </div>
  );
}
