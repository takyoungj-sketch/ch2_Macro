import { useState } from "react";
import { ModelRecommendSection } from "@ch2/model-recommend";
import type { LandModelCandidate, LandRegressionSuggestResponse } from "../types";

const LABELS: Record<string, string> = { area_sqm: "면적", road_condition: "도로조건", deal_type: "거래유형", partial_ownership: "지분여부", year_trend: "연도추세", beopjungri_fe: "법정동 효과", assessed_land_price: "개별공시지가" };
const number = (v?: number | null, digits = 2) => v != null && Number.isFinite(v) ? v.toFixed(digits) : "—";
const keyOf = (c: LandModelCandidate, purpose: string) => `${purpose}-${c.rank}-${c.model_type}-${c.blocks.join(",")}`;
export default function LandModelRecommend({ data, pending, differentSample, onAdopt }: {
  data: LandRegressionSuggestResponse; pending: boolean; differentSample: boolean;
  onAdopt: (candidate: LandModelCandidate) => void;
}) {
  const [purpose, setPurpose] = useState("explanatory");
  const [selected, setSelected] = useState<Record<string, string>>({});
  const candidates = purpose === "explanatory" ? data.candidates_by_aic : data.candidates_by_mape;
  const chosen = candidates.find(c => keyOf(c, purpose) === selected[purpose]) ?? candidates[0];
  const toRows = (rows: LandModelCandidate[], id: string) => rows.map(c => ({ key: keyOf(c, id),
    primary: `${c.rank}위 · ${c.model_type === "log" ? "로그" : "선형"} · ${c.blocks.map(b => LABELS[b] ?? b).join(" · ")}`,
    metrics: `AIC ${number(c.aic, 1)} · 학습 MAPE ${c.mape == null ? "—" : `${number(c.mape)}%`} · 조정 R² ${number(c.adj_r_squared, 3)} · 적합 ${c.n}건`,
  }));
  return <div className="space-y-2">
    <ModelRecommendSection className="!bg-indigo-50/40 dark:!bg-slate-900/60" depth="standard" selectionN={data.selection_n}
      limitations="후보의 오차는 학습 자료에서 계산했습니다. 새 거래의 예측 정확도를 검증한 결과는 아닙니다. 후보 적용 후 유효 표본과 결과 수치가 달라질 수 있습니다."
      tabs={[
        {id:"predictive",label:"예측형",optimizeSentence:"같은 표본에서 학습 MAPE가 낮은 후보입니다. 교차검증 오차 기준은 아닙니다.",rows:toRows(data.candidates_by_mape,"predictive"),emptyText:"비교 가능한 예측형 후보가 없습니다."},
        {id:"explanatory",label:"설명형",optimizeSentence:"같은 표본에서 AIC가 낮은 후보입니다. 기존 토지 모형 추천 기준을 유지합니다.",rows:toRows(data.candidates_by_aic,"explanatory"),emptyText:"비교 가능한 설명형 후보가 없습니다."},
      ]} defaultTabId="explanatory" onTabChange={setPurpose}
      selectedRowKey={chosen ? keyOf(chosen,purpose) : undefined}
      onRowSelect={key => setSelected(prev => ({...prev,[purpose]:key}))} selectionDisabled={pending}
      headerExtra={<button type="button" disabled={pending || !chosen} className="ml-auto rounded bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50" onClick={() => chosen && onAdopt(chosen)}>{pending ? "회귀 실행 중…" : "후보 설정 반영"}</button>}
    />
    {differentSample && <p className="text-xs text-amber-800 dark:text-amber-200">현재 적합 모형과 표본 또는 조건이 다릅니다. 지표를 직접 비교하지 마세요.</p>}
    {[...new Set(data.warnings)].map(w => <p key={w} className="text-xs leading-relaxed text-amber-800 dark:text-amber-200">{w}</p>)}
    <p className="text-xs text-slate-500 dark:text-slate-400">후보를 선택한 뒤 ‘후보 설정 반영’을 누르면 변수 설정을 바꾸고 회귀를 실행합니다.</p>
  </div>;
}
