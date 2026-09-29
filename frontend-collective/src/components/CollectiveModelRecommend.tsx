import { useState } from "react";
import { ModelRecommendSection } from "@ch2/model-recommend";
import type { ModelRecommendPurposeTab } from "@ch2/model-recommend";
import type { RegressionModelType } from "../types";

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
  if (row.hold_mape != null) return { label: "홀드아웃 MAPE", value: row.hold_mape };
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
      return { key: `${purpose}-${row.rank}-${row.model_type}`, primary: lead, metrics };
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
  applyNote = "적용은 위의 변수 체크와 로그 체크를 바꿉니다. 식과 시나리오 금액은 회귀를 다시 실행해야 바뀝니다.",
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
        <p className="mt-1 text-[11px] text-slate-500">이 표본에서는 변수와 척도를 견주지 못했습니다.</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <ModelRecommendSection
        depth="standard_plus"
        selectionN={selectionN}
        limitations={`${datasetNote} 변수는 위의 체크와 무관하게 찾습니다. 다른 지역은 넣지 않습니다. 후보는 정답 식이 아니고, 금액 예측·감정이 아닙니다.`}
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
            {already ? "이 후보를 쓰는 중" : "이 후보 적용"}
          </button>
        }
      />
      <p className="text-[10px] text-slate-500 dark:text-slate-400">{applyNote}</p>
    </div>
  );
}
