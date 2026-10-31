import { useEffect, useState, type ReactNode } from "react";
import type { AssetType, CvCoverage, ModelCandidate, PredictOptions, RegressionRecommendResponse, RegressionVariableSpec, ResponseScale } from "../types";
import { dummyReferenceRows } from "../utils/regressionFormat";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { BasicRegressionCoefficients, BasicRegressionEquation } from "./BasicRegressionDetails";
import { formatResponseScale } from "../utils/recommendationLabels";

const LABELS: Record<string, string> = { gross_area: "연면적", land_area: "대지면적", building_age: "연식", zone_type: "용도지역", road_width: "도로조건", asset_type: "유형", structure: "구조", building_use: "건축물용도", assessed_land_price: "개별공시지가", region_leaf: "지역" };
const variables = (c: ModelCandidate) => c.blocks.map(b => LABELS[b] ?? "추가 변수").join(" · ") || "절편만";
const number = (v?: number | null, digits = 2, unit = "") => v != null && Number.isFinite(v) ? `${v.toFixed(digits)}${unit}` : "—";
const same = (a: ModelCandidate, b: ModelCandidate) => a.response_scale === b.response_scale && a.blocks.join(",") === b.blocks.join(",");
function coverage(s?: CvCoverage | null) {
  if (!s) return "평가 정보가 제공되지 않았습니다.";
  return [s.years?.length ? `${s.years.join("·")}년` : "평가 연도 없음", s.n_trades != null ? `${s.n_trades}건` : "", `완료 ${s.folds ?? 0}/${s.requested_years?.length ?? s.folds ?? 0}개`, ...Object.entries(s.failure_reasons ?? {}).map(([year, reason]) => `${year}년: ${reason}`)].filter(Boolean).join(" · ");
}
function Help({ candidate }: { candidate: ModelCandidate }) {
  return <AnalysisHelpPanel title="후보 비교와 검증 기준 설명" explain={{
    spec_id: "macro_local_comparison", spec_version: "1", title: "후보 비교와 검증 기준",
    summary: "탐색 오차는 후보 선정에, 확인 오차는 선정에 쓰지 않은 마지막 연도의 확인에 사용합니다. 두 오차는 평가 기간과 거래가 다를 수 있습니다.",
    interpretation: ["예측형 순위는 제공된 탐색 CV 기준입니다. 설명형 추천은 기존 로그·로그-로그 후보의 AIC 기준을 유지합니다.", "같은 평가 거래·분할·계산 기준이 확인된 후보만 성능 유사로 표시합니다. 표본 수가 같다는 이유만으로 직접 비교하지 않습니다.", "회귀식은 기본회귀와 같이 유의한 변수만 표시합니다. 실제 적합된 전체 변수는 계수 표에서 확인할 수 있습니다.", "탐색 후보 자료에는 기준 범주가 제공되지 않습니다. 조건별 추정을 열면 재적합한 모형의 실제 기준 범주를 확인할 수 있습니다."],
    controls: [`탐색 CV: ${coverage(candidate.cv_report?.search)}`, `확인 CV: ${coverage(candidate.cv_report?.confirm)}`, "성능 유사는 탐색 최저 오차와 1.0%p 이내이며 평가 기준의 일치가 확인된 경우입니다. 통계적 동률을 뜻하지 않습니다."],
    limitations: ["학습 MAPE는 모형을 적합한 자료 안의 오차입니다. 새로운 거래의 예측 성능을 직접 뜻하지 않습니다.", "AIC는 같은 표본과 종속변수 척도에서 비교해야 합니다. 서로 다른 척도의 수치만으로 성능 우열을 판단하지 마세요.", "조건별 추정은 선택한 변수로 다시 적합합니다. 숫자 변수의 결측에 따라 탐색 표본과 추정용 적합 표본 수가 다를 수 있습니다.", "용도지역이 여러 개인 필지는 원자료의 제1용도지역으로 분석합니다. 면적이나 가격 영향이 가장 큰 용도지역이라는 뜻은 아닙니다.", "로그모형의 금액 환산과 보정은 기존 추정 계산을 따릅니다. 회귀계수와 금액을 직접 같은 단위로 비교하지 마세요."], presets: [], interpretation_hints: [],
  }} />;
}
function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-slate-200 bg-white/70 p-3 dark:border-slate-600 dark:bg-slate-900/50"><p className="text-sm text-slate-500 dark:text-slate-400">{label}</p><p className="mt-1 text-xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">{value}</p></div>;
}

export default function MacroLocalResults({ mode, data, assetType, onPredict, predictPanel, predictActiveLabel, predictOptions, busy }: {
  mode: "predict" | "explain"; data: RegressionRecommendResponse; assetType: AssetType; busy: boolean;
  onPredict?: (vars: RegressionVariableSpec, scale: ResponseScale, label: string) => void;
  predictPanel?: ReactNode; predictActiveLabel?: string | null; predictOptions?: PredictOptions | null;
}) {
  const { stage1 } = data;
  const predictive = mode === "predict";
  const recommended = predictive ? stage1.primary : stage1.alternate;
  const candidates = predictive ? stage1.candidates_predictive : stage1.candidates_explanatory;
  const [selectedIndex, setSelectedIndex] = useState(0);
  const key = candidates.map(c => `${c.rank}:${c.response_scale}:${c.blocks.join(",")}`).join("|");
  useEffect(() => { setSelectedIndex(Math.max(0, candidates.findIndex(c => recommended && same(c, recommended)))); }, [key, recommended]);
  const selected = candidates[selectedIndex] ?? recommended;
  const [estimateOpen, setEstimateOpen] = useState(false);
  const selectedKey = selected ? `${mode}:${selected.rank}:${selected.response_scale}:${selected.blocks.join(",")}` : mode;
  useEffect(() => { setEstimateOpen(false); }, [selectedKey]);
  if (!recommended || !selected) return <p className="py-4 text-sm text-slate-500">이 분석에서 {predictive ? "예측형" : "설명형"} 추천 모형을 제공하지 않습니다.</p>;
  const selectedLabel = `${predictive ? "예측형" : "설명형"} 후보 ${selected.rank} · ${formatResponseScale(selected.response_scale)} · ${variables(selected)}`;
  const confirmed = stage1.representative_confirmed !== false;
  const warning = predictive ? data.warnings[0] : null;
  return <div role="tabpanel" aria-label={predictive ? "예측형 결과" : "설명형 결과"} className="space-y-4 pt-3">
    <section className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 dark:border-indigo-800 dark:bg-indigo-950/20 space-y-3">
      <div className="flex items-center gap-2"><h3 className="text-base font-semibold">추천 모형 요약 · {predictive ? "예측 오차 기준" : "설명력·복잡도 기준"}</h3><Help candidate={recommended} /></div>
      <p className="text-sm">{formatResponseScale(recommended.response_scale)} · {variables(recommended)}</p>
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {predictive ? <><Metric label="탐색 CV-MAPE" value={number(recommended.metrics.cv_mape, 2, "%")} /><Metric label="확인 CV-MAPE" value={number(recommended.cv_report?.confirm?.mape, 2, "%")} /></> : <><Metric label="AIC" value={number(recommended.aic, 1)} /><Metric label="조정 R²" value={number(recommended.metrics.adj_r_squared, 3)} /></>}
        <Metric label="학습 MAPE" value={number(recommended.metrics.mape, 2, "%")} />
        <Metric label={predictive ? "조정 R²" : "탐색 CV-MAPE"} value={predictive ? number(recommended.metrics.adj_r_squared, 3) : number(recommended.metrics.cv_mape, 2, "%")} />
      </div>
      {predictive && !confirmed && <p role="status" className="text-sm text-amber-800 dark:text-amber-300">탐색 1위 후보이며 대표 예측모형은 미확정입니다. {stage1.representative_note || "검증 표본과 확인 오차를 확인해 주세요."}</p>}
      {predictive && recommended.cv_report?.confirm?.mape == null && <p className="text-sm text-amber-800 dark:text-amber-300">확인 CV-MAPE가 제공되지 않았습니다.</p>}
      {(recommended.cv_report?.search?.requested_years?.length ?? 0) > (recommended.cv_report?.search?.folds ?? 0) && <p className="text-sm text-amber-800 dark:text-amber-300">탐색 검증을 일부 연도에서만 완료했습니다. 평가 범위는 도움말에서 확인해 주세요.</p>}
      {!predictive && <p className="text-sm text-slate-600 dark:text-slate-300">기존 AIC 기준으로 추천한 모형입니다. 예측형의 추천 순위와는 구분해서 읽어 주세요.</p>}
      {warning && <p className="text-sm text-amber-800 dark:text-amber-300">{warning}</p>}
      {predictive && (stage1.primary_cv_extreme_rate ?? 0) > 0.05 && <p className="text-sm text-amber-800 dark:text-amber-300">검증 예측의 {number((stage1.primary_cv_extreme_rate ?? 0) * 100, 1, "%")}가 학습 금액 범위를 크게 벗어났습니다. 개별 추정에 주의해 주세요.</p>}
    </section>
    {candidates.length > 0 && <section className="space-y-2">
      <div className="flex items-center gap-2"><h3 className="text-base font-semibold">후보 비교</h3><Help candidate={selected} /></div>
      <p className="text-sm text-slate-500 dark:text-slate-400">후보를 선택하면 아래 모형 상세가 바뀝니다. 평가 표본·기간·척도가 다른 수치는 직접 비교하지 마세요.</p>
      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700"><table className="w-full min-w-[660px] text-sm">
        <thead className="bg-slate-100 dark:bg-slate-900"><tr>{["순위·선택", "척도", "주요 변수", ...(predictive ? ["탐색 CV-MAPE", "확인 CV-MAPE", "탐색 1위와 차이(%p)"] : ["AIC", "조정 R²"]), "표시"].map(t => <th key={t} className="px-3 py-2 text-left font-medium">{t}</th>)}</tr></thead>
        <tbody>{candidates.map((c, index) => <tr key={`${c.rank}-${index}`} className={`${index === selectedIndex ? "bg-indigo-50 dark:bg-indigo-950/40" : ""} border-t border-slate-200 dark:border-slate-700`}>
          <td className="px-3 py-2"><button type="button" disabled={busy} aria-pressed={index === selectedIndex} onClick={() => setSelectedIndex(index)} className="rounded border border-slate-300 px-2 py-1 font-medium dark:border-slate-600 disabled:opacity-50">{index === selectedIndex ? "선택됨" : "선택"} · {c.rank}위</button></td>
          <td className="px-3 py-2">{formatResponseScale(c.response_scale)}</td><td className="px-3 py-2">{variables(c)}</td>
          <td className="px-3 py-2 text-center tabular-nums">{predictive ? number(c.metrics.cv_mape, 2, "%") : number(c.aic, 1)}</td>
          <td className="px-3 py-2 text-center tabular-nums">{predictive ? number(c.cv_report?.confirm?.mape, 2, "%") : number(c.metrics.adj_r_squared, 3)}</td>
          {predictive && <td className="px-3 py-2 text-center tabular-nums">{number(stage1.predictive_judgments?.find(j => j.rank === c.rank)?.cv_gap_pp)}</td>}
          <td className="px-3 py-2">{same(c, recommended) ? "추천 모형" : data.stage1.predictive_judgments?.find(j => predictive && j.rank === c.rank)?.label.replace("예측 최소", "탐색 오차 최저") || "비교 후보"}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
    <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-700 space-y-3">
      <div className="flex items-center gap-2"><h3 className="text-base font-semibold">선택한 모형 상세 · {selected.rank}위</h3><span className="rounded bg-indigo-100 px-2 py-1 text-xs text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">{same(selected, recommended) ? "추천 모형 선택" : "비교 후보 선택"}</span></div>
      <p className="text-sm">{formatResponseScale(selected.response_scale)} · {variables(selected)}</p>
      {!same(selected, recommended) && <p className="text-sm text-slate-500 dark:text-slate-400">위 추천 요약은 유지됩니다. 아래 회귀식·계수·조건별 추정은 지금 선택한 후보의 결과입니다.</p>}
      <BasicRegressionEquation coefficients={selected.coefficients ?? []} responseScale={selected.response_scale} assetType={assetType} />
      <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">기준 범주는 아래 추정용 모형에서 확인할 수 있습니다. <Help candidate={selected} /></div>
      <details key={selectedKey} className="rounded-lg border border-slate-200 p-3 dark:border-slate-700"><summary className="cursor-pointer font-medium text-sm">회귀계수 상세</summary><div className="mt-3 space-y-3"><BasicRegressionCoefficients coefficients={selected.coefficients ?? []} responseScale={selected.response_scale} assetType={assetType} />
        {predictive && same(selected, recommended) && (data.coefficient_narratives?.length ?? 0) > 0 && <details className="text-sm"><summary className="cursor-pointer font-medium">계수 해석 더 보기</summary><ul className="mt-2 space-y-2">{data.coefficient_narratives!.map(c => <li key={c.name}>{c.text_ko}</li>)}</ul></details>}
      </div></details>
    </section>
    {onPredict && <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
      <button type="button" disabled={busy} aria-expanded={estimateOpen} className="flex w-full items-center justify-between text-base font-semibold disabled:opacity-50" onClick={() => {
        const open = !estimateOpen; setEstimateOpen(open);
        if (open) onPredict(selected.variables, selected.response_scale, selectedLabel);
      }}><span>조건별 추정</span><span>{estimateOpen ? "접기 −" : "펼치기 +"}</span></button>
      {estimateOpen && predictActiveLabel === selectedLabel && <div className="mt-3 space-y-3">
        {predictOptions && dummyReferenceRows(predictOptions, assetType).length > 0 && <p className="text-sm leading-relaxed"><strong>추정용 모형 기준 범주</strong> · {dummyReferenceRows(predictOptions, assetType).map(r => `${r.kind}: ${r.display}`).join(" · ")}</p>}
        {predictPanel}
      </div>}
    </section>}
    <details className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700"><summary className="cursor-pointer font-medium">표본과 추가 안내</summary><div className="mt-3 space-y-2 leading-relaxed">
      {[...(predictive ? data.warnings.slice(1) : data.warnings), ...(stage1.sample_drop_notes ?? []), ...(stage1.provision_notes ?? []), ...(stage1.parity_notes ?? []), ...(stage1.assessed_side?.note ? [stage1.assessed_side.note] : [])].map((note, index) => <p key={index}>{note}</p>)}
      {data.diagnostics_checklist?.map(check => <p key={check.check_id}>{check.label_ko}: {check.summary_ko}</p>)}
      {stage1.primary_cv_median_ape != null && predictive && <p>검증 절대오차율 중앙값: {number(stage1.primary_cv_median_ape, 1, "%")}</p>}
    </div></details>
  </div>;
}
