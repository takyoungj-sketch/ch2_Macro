import { useEffect, useState, type ReactNode } from "react";
import type { AnalysisExplain, RecommendationPoolCandidate, TwinExperimentStep } from "../types";
import type { RecommendStagePanelProps } from "./RecommendStagePanel";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { createReadableHelpContent } from "@ch2/analysis-help";
import { formatResponseScale } from "../utils/recommendationLabels";
import { contentSignature } from "../../../shared/regression-ui/signature";

const BLOCKS: Record<string, string> = { gross_area: "연면적", land_area: "대지면적", building_age: "연식", zone_type: "용도지역", road_width: "도로조건", asset_type: "유형", structure: "구조", building_use: "건축물용도", assessed_land_price: "개별공시지가", region_leaf: "지역" };
const blocks = (names: string[]) => names.map(n => BLOCKS[n] ?? "추가 변수").join(" · ") || "절편만";
const value = (v?: number | null, digits = 2, unit = "") => v != null && Number.isFinite(v) ? `${v.toLocaleString("ko-KR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}${unit}` : "—";

const TwinHelpContent = createReadableHelpContent(() => undefined);
function TwinRegionHelp() {
  const explain: AnalysisExplain = {
    spec_id: "built_twin_regions_ui", spec_version: "1", title: "쌍둥이 지역과 유사도",
    summary: "쌍둥이 지역은 선택 지역과 특성이 비슷한 지역을 지역프로필에서 찾은 추가 분석 후보입니다. 반드시 인접한 지역은 아닙니다.",
    interpretation: ["지역프로필에서 제공한 순위와 유사도를 그대로 표시합니다. 유사도는 지역 특성의 비슷한 정도이며, 거래가격이나 회귀모형의 정확도를 뜻하지 않습니다.", "체크한 지역은 다음 확장 실행에 요청할 후보입니다. 실제 모형에 포함된 지역은 Twin1·Twin2 결과에서 확인해 주세요.", "Twin1은 지역을 추가해 기존 식을 다시 적합하고, Twin2는 확장 표본에서 변수 조합을 다시 탐색합니다."],
    limitations: ["유사도가 높아도 확장으로 예측 성능이 좋아진다고 보장할 수 없습니다. 적합 표본과 검증 결과를 함께 확인해 주세요."],
    interpretation_hints: [], presets: [],
  };
  return <AnalysisHelpPanel explain={explain} />;
}
function TwinHelp() {
  const explain: AnalysisExplain = {
    spec_id: "built_twin_comparison_ui", spec_version: "1", title: "쌍둥이 확장 비교 기준",
    summary: "Local은 선택 지역의 기준선입니다. Twin1은 지역을 보태 같은 식을 다시 적합하고, Twin2는 확장 표본에서 예측형 식을 다시 탐색합니다.",
    interpretation: ["모형마다 적합 표본과 검증 거래·기간이 다를 수 있습니다. 표의 숫자만으로 성능 우열을 판단하지 마세요.", "탐색 CV는 후보 선정에 사용한 오차이고, 확인 CV는 선정에 쓰지 않은 자료의 오차입니다. 산출되지 않은 값은 대시로 표시합니다.", "현재 선택한 지역은 다음 실행의 설정입니다. 마지막 실행의 선택 지역과 실제 모형에 포함된 지역을 구분해 주세요."],
    controls: ["Twin1은 Local의 변수 구성을 유지하며 지역별 금액 수준 차이를 구분하는 변수를 추가해 적합합니다. 기존 예측오차·계수 방향·표본 기준으로 결과를 판단합니다.", "Twin1과 Twin2는 인접 문을 통과한 선택 지역을 함께 사용합니다. Twin1 추정은 확인용 확장 모형을, Twin2 추정은 재탐색 모형을 사용합니다.", "지역별 회귀계수는 기준 지역과의 차이입니다. 범주 선택에 표시된 기준을 함께 확인해 주세요.", "로그모형의 금액 환산과 평균 보정은 기존 추정 계산을 그대로 사용합니다. 적용된 보정과 개별 예측범위는 추정 결과의 상세 안내에서 확인할 수 있습니다."],
    limitations: ["Twin 오차는 추가 지역을 포함한 거래로 계산합니다. 원래 지역 거래만의 예측이 좋아졌다는 뜻이 아닙니다.", "Twin2의 탐색 오차는 독립적인 확인 검증 결과가 아닙니다. 확인 CV가 제공된 경우에만 해당 값을 표시합니다.", "지역이나 입력 조건이 달라지면 추정값과 범위도 달라집니다. 결과는 회귀모형의 통계적 참고값이며 가격평가가 아닙니다."], interpretation_hints: [], presets: [],
  };
  return <AnalysisHelpPanel title="쌍둥이 확장 비교 기준 설명" explain={explain} content={<TwinHelpContent explain={explain} />} />;
}
function Card({ title, status, description, children }: { title: string; status: string; description: string; children?: ReactNode }) {
  return <section className="space-y-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-base font-semibold">{title}</h3><span className="rounded bg-slate-100 px-2 py-1 text-sm dark:bg-slate-800" role="status">{status}</span></div>
    <p className="text-sm text-slate-600 dark:text-slate-300">{description}</p>{children}
  </section>;
}

export default function MacroTwinResults(props: RecommendStagePanelProps) {
  const { data, busy = false, twinCandidateStatus = "none", twinChoices = [], checkedTwinCodes = [], resultTwinCodes = [],
    regionNameByCode = {}, onToggleTwinCode, onRunTwin, onRunTwinResearch, twinRunning, twinResearchRunning,
    twinSelectionChanged = false, twinStatus, researchStatus, onPredict, twin1PredictPanel, researchPredictPanel,
    twin1PredictActiveLabel, researchPredictActiveLabel, twin1PredictIdentity, researchPredictIdentity, onAdoptPool, adopting, minePrimary, mineScale } = props;
  const { stage1, stage2, analysis_scope } = data;
  const [poolIndex, setPoolIndex] = useState(0);
  const pools = stage2?.pools ?? [];
  const visiblePool = pools[Math.min(poolIndex, Math.max(0, pools.length - 1))] ?? stage2?.inspect_pool ?? undefined;
  const twin1 = stage2?.inspect_pool ?? visiblePool;
  const twin2 = stage2?.research;
  const local = stage1.primary;
  const unitName = (code: string) => regionNameByCode[code] || analysis_scope.region_units.find(u => u.code === code)?.name || (analysis_scope.anchor_unit?.code === code ? analysis_scope.anchor_unit.name : "지역명 미제공");
  const regionNames = (codes?: string[]) => codes?.length ? codes.map(unitName).join(" · ") : "지역 정보 미제공";
  const currentRegions = checkedTwinCodes.length ? regionNames(checkedTwinCodes) : "선택한 지역 없음";
  const requestedRegions = resultTwinCodes.length ? regionNames(resultTwinCodes) : "실행 기록 없음";
  const twin1State = twinStatus ?? (twinRunning ? "계산 중" : stage2?.ran ? "계산 완료" : "미실행");
  const twin2State = researchStatus ?? (twinResearchRunning ? "계산 중" : stage2?.research_ran ? "계산 완료" : "미실행");
  const modelValues = [
    { title: "Local", n: stage1.fit_n, adj: local.metrics.adj_r_squared, search: local.metrics.cv_mape, confirm: local.cv_report?.confirm?.mape, status: stage1.representative_confirmed === false ? "대표모형 미확정" : "기준선", scale: local.response_scale },
    { title: "Twin1", n: stage2?.ran ? twin1?.n : null, adj: stage2?.ran ? twin1?.adj_r_squared : null, search: stage2?.ran ? twin1?.cv_mape : null, confirm: stage2?.ran ? twin1?.confirm_cv_mape : null, status: twin1State, scale: stage2?.ran ? twin1?.response_scale ?? stage2.fixed_response_scale : null },
    { title: "Twin2", n: stage2?.research_ran ? twin2?.n : null, adj: stage2?.research_ran ? twin2?.adj_r_squared : null, search: stage2?.research_ran ? twin2?.cv_mape : null, confirm: stage2?.research_ran ? twin2?.confirm_cv_mape : null, status: twin2State, scale: stage2?.research_ran ? twin2?.response_scale : null },
  ];
  const poolVars = (pool: RecommendationPoolCandidate) => ({ vars: pool.variables ?? local.variables, scale: pool.response_scale ?? stage2?.fixed_response_scale ?? local.response_scale });
  const poolIdentity = (pool: RecommendationPoolCandidate) => { const { vars, scale } = poolVars(pool); return contentSignature({ vars, scale, fitN: pool.n, regionCodes: pool.region_codes }); };
  const canRun = twinCandidateStatus === "ready" && checkedTwinCodes.length > 0 && Boolean(onRunTwin) && !busy;
  const canResearch = Boolean(stage2?.ran && onRunTwinResearch) && !busy;
  const steps = stage2?.twin_experiments ?? [];
  const twin1Active = Boolean(twin1PredictActiveLabel?.startsWith("Twin 재적합")) && Boolean(twin1 && twin1PredictIdentity === poolIdentity(twin1));
  const twin2Active = Boolean(researchPredictActiveLabel?.startsWith("Twin 실험2")) && Boolean(twin2 && researchPredictIdentity === poolIdentity(twin2));
  useEffect(() => {
    if (!stage2?.ran || !twin1 || twin1Active || busy || twinSelectionChanged || !onPredict) return;
    const { vars, scale } = poolVars(twin1);
    onPredict(vars, scale, "Twin 재적합 · Twin1", { regionCodes: twin1.region_codes, fitN: twin1.n, slot: "twin1" });
  }, [stage2?.ran, twin1, twin1Active, busy, twinSelectionChanged, onPredict]);
  useEffect(() => {
    if (!stage2?.research_ran || !twin2 || twin2Active || busy || twinSelectionChanged || !onPredict) return;
    const { vars, scale } = poolVars(twin2);
    onPredict(vars, scale, "Twin 실험2 · Twin2", { regionCodes: twin2.region_codes, fitN: twin2.n, slot: "twin2" });
  }, [stage2?.research_ran, twin2, twin2Active, busy, twinSelectionChanged, onPredict]);
  function estimate(pool: RecommendationPoolCandidate, slot: "twin1" | "twin2", active: boolean, panel: ReactNode) {
    return <section key={`${slot}:${contentSignature(pool)}`} className="space-y-3 text-sm">
      <p>{formatResponseScale(pool.response_scale ?? stage2?.fixed_response_scale)} · {blocks(pool.blocks ?? local.blocks)}</p>
      <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-3 dark:bg-slate-900/60 sm:grid-cols-4">
        {[["적합 표본", value(pool.n, 0) + "건"], ["조정 R²", value(pool.adj_r_squared, 3)], ["탐색 CV-MAPE", value(pool.cv_mape, 2, "%")], ["확인 CV-MAPE", value(pool.confirm_cv_mape, 2, "%")]].map(([label, metric]) => <div key={label}><p className="text-slate-500 dark:text-slate-400">{label}</p><p className="mt-1 text-lg font-semibold tabular-nums">{metric}</p></div>)}
      </div>
      {pool.mape != null && <p className="text-slate-500 dark:text-slate-400">학습 MAPE {value(pool.mape, 2, "%")}</p>}
      {twinSelectionChanged ? <p className="text-amber-800 dark:text-amber-300">지역 선택이 변경됐습니다. 확장을 다시 실행한 뒤 결과를 확인해 주세요.</p> : active ? panel : <p role="status">{busy ? "확장 계산이 끝나면 회귀식을 표시합니다." : "회귀식과 추정용 모형을 준비하고 있습니다."}</p>}
    </section>;
  }
  return <div role="tabpanel" aria-label="쌍둥이 확장 결과" className="space-y-4 pt-3">
    <Card title="추가 지역" status={`${checkedTwinCodes.length}개 선택`} description="다음 실행에 추가할 지역을 선택합니다.">
      <div className="flex items-center gap-2 text-sm font-medium">쌍둥이 지역<TwinRegionHelp /></div>
      <div className="space-y-1 text-sm"><p><strong>현재 선택</strong> · {currentRegions}</p><p className="text-slate-500 dark:text-slate-400"><strong>마지막 완료 결과의 선택</strong> · {requestedRegions}</p></div>
      {twinSelectionChanged && <p role="status" className="text-sm text-amber-800 dark:text-amber-300">설정이 변경됐습니다. 아래 결과는 마지막 실행 기준이며, 다시 실행해야 새 선택이 반영됩니다.</p>}
      {twinCandidateStatus === "loading" && <p role="status" className="text-sm">유사 지역 후보를 불러오는 중입니다.</p>}
      {twinCandidateStatus === "none" && <p className="text-sm">현재 분석 범위에서는 추가할 쌍둥이 지역 후보를 제공하지 않습니다.</p>}
      {twinChoices.length > 0 && <details open className="rounded-lg border border-slate-200 p-3 dark:border-slate-700"><summary className="cursor-pointer text-sm font-medium">추가 지역 선택표 · 후보 {twinChoices.length}개</summary>
        <div className="mt-3 overflow-x-auto"><table className="w-full text-sm"><thead><tr>{["선택", "순위", "지역", "유사도"].map(t => <th key={t} className="px-3 py-2 text-left font-medium">{t}</th>)}</tr></thead><tbody>{twinChoices.map(row => <tr key={row.code} className="border-t border-slate-200 dark:border-slate-700"><td className="px-3 py-2"><input type="checkbox" checked={checkedTwinCodes.includes(row.code)} onChange={() => onToggleTwinCode?.(row.code)} disabled={busy} aria-label={`${row.rank}위 ${row.label}`} /></td><td className="px-3 py-2 tabular-nums">{row.rank}</td><td className="px-3 py-2 whitespace-normal break-words">{row.label}</td><td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">{row.similarityScore != null && Number.isFinite(row.similarityScore) ? value(row.similarityScore * 100, 1, "%") : "—"}</td></tr>)}</tbody></table></div>
      </details>}
      <button type="button" className="btn btn-primary text-sm" disabled={!canRun || twinRunning} onClick={onRunTwin}>{twinRunning ? "Twin1 계산 중…" : "Twin1 통합회귀 실행"}</button>
    </Card>
    <Card title="Twin1 · 기존 식 재적합" status={twin1State} description="선택한 지역의 거래를 보태 Local 식을 다시 적합합니다.">
      {stage2?.ran && twin1 && <p className="text-sm text-slate-500 dark:text-slate-400">실제 사용 지역 · {regionNames(twin1.region_codes)}</p>}
      {!!stage2?.ran && <p className="text-sm">{stage2.twin_validation?.twin_adopt_recommended ? "추가 지역을 포함한 표본의 오차가 더 낮습니다. 원래 지역 거래만의 예측이 좋아졌다는 뜻은 아닙니다." : "기존 검증 기준에서는 Local 기준선을 유지합니다."}</p>}
      {stage2?.ran && !twin1 && <p className="text-sm text-amber-800 dark:text-amber-300">확장은 완료했지만 적합된 Twin1 모형이 제공되지 않았습니다.</p>}
      {stage2?.skipped_reason && !stage2.ran && <p className="text-sm text-amber-800 dark:text-amber-300">{stage2.skipped_reason}</p>}
      {twin1 && stage2?.ran && estimate(twin1, "twin1", twin1Active, twin1PredictPanel)}
      {steps.length > 0 && <details className="rounded-lg border border-slate-200 p-3 dark:border-slate-700"><summary className="cursor-pointer text-sm font-semibold">Twin1 상세 검증</summary><div className="mt-3 space-y-3 text-sm">
        <StepTable steps={steps} regionNames={regionNames} />
        {stage2?.decision_reason && <p className="leading-relaxed">{stage2.decision_reason}</p>}
        {stage2?.region_effect && <p>{stage2.region_effect}</p>}
        {visiblePool && <div className="flex flex-wrap items-center gap-2"><span>확장 후보 {Math.min(poolIndex + 1, pools.length)}/{pools.length}</span><span>{regionNames(visiblePool.region_codes)}</span>
          {pools.length > 1 && <><button type="button" className="btn btn-ghost" aria-label="이전 확장 후보" disabled={poolIndex <= 0} onClick={() => setPoolIndex(i => Math.max(0, i - 1))}>←</button><button type="button" className="btn btn-ghost" aria-label="다음 확장 후보" disabled={poolIndex >= pools.length - 1} onClick={() => setPoolIndex(i => Math.min(pools.length - 1, i + 1))}>→</button></>}
          {onAdoptPool && <button type="button" className="btn btn-ghost" disabled={adopting || busy || twinSelectionChanged} onClick={() => { const { vars, scale } = poolVars(visiblePool); onAdoptPool({ vars, scale, regionCodes: visiblePool.region_codes, label: visiblePool.label }); }}>이 확장 모형을 기본 통계에 적용</button>}
        </div>}
      </div></details>}
    </Card>
    <Card title="Twin2 · 확장 표본 재탐색" status={twin2State} description="확장한 표본에서 예측형 변수 조합을 다시 탐색합니다.">
      {stage2?.research_ran && <p className="text-sm text-amber-800 dark:text-amber-300">Twin2 탐색 오차는 독립적인 확인 검증 결과가 아닙니다.</p>}
      {stage2?.research_ran && twin2 && <p className="text-sm text-slate-500 dark:text-slate-400">실제 사용 지역 · {regionNames(twin2.region_codes)}</p>}
      {!stage2?.ran && <p className="text-sm text-slate-500 dark:text-slate-400">Twin1을 실행한 뒤 재탐색할 수 있습니다.</p>}
      {stage2?.ran && !stage2.research_ran && <button type="button" className="btn btn-primary text-sm" disabled={!canResearch || twinResearchRunning} onClick={onRunTwinResearch}>{twinResearchRunning ? "Twin2 계산 중…" : "Twin2 재탐색 실행"}</button>}
      {stage2?.research_ran && !twin2 && !stage2.research_skipped_reason && <p className="text-sm text-amber-800 dark:text-amber-300">재탐색은 완료했지만 Twin2 모형이 제공되지 않았습니다.</p>}
      {stage2?.research_skipped_reason && !twin2 && <p className="text-sm text-amber-800 dark:text-amber-300">{stage2.research_skipped_reason}</p>}
      {twin2 && stage2?.research_ran && estimate(twin2, "twin2", twin2Active, researchPredictPanel)}
    </Card>
    <details className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700"><summary className="cursor-pointer font-medium">표본·검증 안내</summary><div className="mt-3 space-y-2 leading-relaxed">
      {data.diagnostics_checklist?.map(check => <p key={check.check_id}>{check.label_ko}: {check.summary_ko}</p>)}
      {stage1.provision_notes?.map(note => <p key={note}>{note}</p>)}
      {data.termination.reasons.map((reason, index) => <p key={index}>{reason}</p>)}
    </div></details>
    <details className="space-y-3 rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 dark:border-indigo-800 dark:bg-indigo-950/20">
      <summary className="cursor-pointer text-base font-semibold">Local·Twin1·Twin2 비교</summary>
      <div className="flex items-center gap-2 text-sm">비교 기준<TwinHelp /></div>
      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700"><table className="w-full min-w-[560px] text-sm">
        <thead className="bg-slate-100 dark:bg-slate-900"><tr><th className="px-3 py-2 text-left font-medium">지표</th>{modelValues.map(m => <th key={m.title} className="px-3 py-2 text-center font-semibold">{m.title}</th>)}</tr></thead>
        <tbody className="bg-white/60 dark:bg-slate-900/40">
          {([ ["상태", (m: typeof modelValues[number]) => m.status], ["적합 표본 수", (m: typeof modelValues[number]) => value(m.n, 0)], ["조정 R²", (m: typeof modelValues[number]) => value(m.adj, 3)], ["탐색 CV-MAPE", (m: typeof modelValues[number]) => value(m.search, 2, "%")], ["확인 CV-MAPE", (m: typeof modelValues[number]) => value(m.confirm, 2, "%")], ["척도", (m: typeof modelValues[number]) => m.scale ? formatResponseScale(m.scale) : "—"] ] as const).map(([label, display]) => <tr key={label} className="border-t border-slate-200 dark:border-slate-700"><th className="px-3 py-2 text-left font-medium">{label}</th>{modelValues.map(m => <td key={m.title} className="px-3 py-2 text-center tabular-nums">{display(m)}</td>)}</tr>)}
        </tbody>
      </table></div>
      <p className="text-sm text-slate-600 dark:text-slate-300">모형별 표본과 검증 조건이 다를 수 있습니다. 수치만으로 성능 우열을 판단하지 마세요.</p>
      {stage1.representative_confirmed === false && <p className="text-sm text-amber-800 dark:text-amber-300">Local은 탐색 1위 후보입니다. 대표 예측모형은 미확정입니다.</p>}
      {stage2?.research_ran && <p className="text-sm text-amber-800 dark:text-amber-300">Twin2 탐색 오차는 독립적인 확인 검증 결과가 아닙니다.</p>}
      {minePrimary && <details className="text-sm"><summary className="cursor-pointer font-medium">기본회귀 결과도 확인하기</summary><p className="mt-2 leading-relaxed">{formatResponseScale(mineScale)} · 적합 {value(minePrimary.n, 0)}건 · 조정 R² {value(minePrimary.adj_r_squared, 3)} · 학습 MAPE {value(minePrimary.mape, 2, "%")}</p><p className="mt-1 text-slate-500 dark:text-slate-400">기본회귀와 확장 모형은 분석 조건과 평가 표본이 다를 수 있습니다.</p></details>}
    </details>
  </div>;
}

function StepTable({ steps, regionNames }: { steps: TwinExperimentStep[]; regionNames: (codes: string[]) => string }) {
  const status = { ok: "양호", warn: "주의", fail: "불안정" };
  return <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-sm"><thead className="bg-slate-100 dark:bg-slate-900"><tr>{["모형·사용 지역", "적합 표본 수", "탐색 CV-MAPE", "확인 CV-MAPE", "계수 안정", "주요 계수 방향"].map(t => <th key={t} className="px-3 py-2 text-left font-medium">{t}</th>)}</tr></thead><tbody>
    {steps.map((step) => <tr key={step.step_id} className="border-t border-slate-200 dark:border-slate-700"><td className="px-3 py-2">{step.step_id === "local" ? "Local" : "확장 모형"}<div className="mt-1 text-slate-500 dark:text-slate-400">{regionNames(step.region_codes)}</div>{step.search_picked && <span>탐색 선택</span>}{step.selected && <span> · 최종 선택</span>}<p className="mt-1">{step.verdict_ko}</p></td><td className="px-3 py-2 text-center tabular-nums">{value(step.n, 0)}</td><td className="px-3 py-2 text-center tabular-nums">{value(step.search_cv_mape, 2, "%")}</td><td className="px-3 py-2 text-center tabular-nums">{value(step.confirm_cv_mape, 2, "%")}</td><td className="px-3 py-2">{status[step.stability]}</td><td className="px-3 py-2">{Object.entries({ gross_area: "연면적", land_area: "대지면적", building_age: "연식" }).flatMap(([key, label]) => { const n = step.key_coefficients?.[key]; return n != null && Number.isFinite(n) ? [`${label} ${n >= 0 ? "+" : "−"}`] : []; }).join(" · ") || "—"}</td></tr>)}
  </tbody></table></div>;
}
