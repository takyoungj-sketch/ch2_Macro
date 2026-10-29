// @ts-nocheck — shared: React는 각 frontend의 런타임에서 제공한다.
import type { RegressionAnalysisContext } from "./types";
import ValidationStatus from "./ValidationStatus";

const labels: Record<string, string> = {
  area_sqm: "토지면적", exclusive_area: "전용면적", gross_area: "연면적", land_area: "대지면적",
  building_age: "연식", floor: "층", households: "세대수", max_floor: "최고층",
  parking: "세대당 주차", parking_per_household: "세대당 주차", structure: "구조",
  builder: "시공사", assessed_land_price: "개별공시지가", contract_period: "계약시점",
  region_dummy: "지역 차이", beopjungri_fe: "법정동 차이", region_leaf_dummy: "지역 차이",
  zone_type: "용도지역", zone_type_dummy: "용도지역", building_use_dummy: "건축물 용도",
  structure_dummy: "구조", asset_type_dummy: "유형", road_width_dummy: "도로조건",
  road_code: "도로폭", dong: "동", deal_type: "거래유형", partial_ownership: "지분 여부",
  log_area: "면적 로그 변환", road_condition: "도로조건", year_trend: "연도추세",
  housing_subtype: "권리유형", building_use: "건축물 용도", road_width: "도로조건",
  region_population: "지역 인구", region_land_p50: "지역 토지 중앙단가",
  region_apt_p50: "지역 아파트 중앙단가", region_apt_n: "지역 아파트 거래수",
  region_comm_p50: "지역 상업 중앙단가", region_comm_n: "지역 상업 거래수",
};
const methods: Record<string, string> = {
  in_sample: "학습 표본", random_kfold_5: "5겹 교차검증", rolling_year: "연도별 순차 검증",
  last_year: "마지막 연도 확인", random_holdout_seed42: "무작위 분리 검증",
};
const reasons: Record<string, string> = {
  constant: "단지 간 값이 같아 생략", no_data: "자료 없음", missing_after_filter: "결측 제외 후 차이가 없어 생략",
  not_identifiable: "단일 단지의 상수여서 효과를 구분할 수 없음", not_in_model: "계수 열이 생성되지 않음",
};
const categories: Record<string, string> = {
  apartment: "아파트", rowhouse: "연립·다세대", officetel: "오피스텔", presale: "분양권",
  commercial: "상업", factory: "공장", detached: "단독", collective_shop: "집합상가", collective_factory: "집합공장",
};

export function primaryCaution(analysis?: RegressionAnalysisContext | null): string | null {
  if (!analysis) return null;
  if (analysis.design_rank != null && analysis.design_rank < analysis.coefficient_n) {
    return "일부 변수의 효과를 따로 구분하기 어렵습니다. 계수 해석에 주의해 주세요.";
  }
  if (analysis.provision?.tier === "caution") {
    return "표본이 적어 계수가 불안정할 수 있습니다. 이 표본의 적합 결과이며, 새 대상의 정확도를 보장하지 않습니다.";
  }
  return null;
}

export default function AnalysisSummary({ analysis }: { analysis?: RegressionAnalysisContext | null }) {
  if (!analysis) return null;
  const unit = analysis.observation_unit === "complex" ? "곳" : "건";
  const target = analysis.target === "complex_median_unit_price" ? "단지 중앙단가"
    : analysis.target === "unit_price" ? "토지 단가" : "거래금액";
  const omitted = analysis.variables.filter(v => v.state !== "included");
  const included = analysis.variables.filter(v => v.state === "included");
  const evaluations = analysis.metrics.filter(m => m.role !== "training");
  return (
    <details className="rounded border border-slate-200 dark:border-slate-700 text-xs text-slate-700 dark:text-slate-200">
      <summary className="cursor-pointer px-3 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500">
        {target} · {analysis.target_unit} · 적합 {analysis.fit_n.toLocaleString("ko-KR")}{unit} · 분석에 사용한 자료
      </summary>
      <div className="px-3 pb-3 space-y-1.5 leading-relaxed">
        <p>종속변수: {target} ({analysis.target_unit}) · {analysis.response_scale === "linear" ? "원척도" : "로그 척도"}</p>
        {analysis.provision && <p role="status" className={analysis.provision.tier === "caution" ? "text-amber-800 dark:text-amber-300" : ""}>
          표본 제공 상태: {analysis.provision.tier === "standard" ? "일반" : analysis.provision.tier === "caution" ? "참고용 · 표본이 30개 미만이거나 독립 계수당 관측이 5개 미만입니다." : "계산 불가"}
          {" (CH2의 제공 기준이며 통계적 정확성을 보증하지 않습니다)"}
        </p>}
        {!!analysis.fit_years?.length && <p>적합 거래 연도: {analysis.fit_years.join(", ")}년</p>}
        {!!analysis.assessed_years?.length && <p>모형에 연결된 공시지가 기준연도: {analysis.assessed_years.join(", ")}년 (거래연도와 다를 수 있습니다)</p>}
        {!!analysis.sample_steps?.length && <ol className="space-y-1" aria-label="순서대로 적용한 표본 확인">
          {analysis.sample_steps.map((step, i) => <li key={i}>{step.label}: {step.n.toLocaleString("ko-KR")}{unit}
            {step.excluded > 0 ? ` · 이 단계에서 ${step.excluded.toLocaleString("ko-KR")}${unit} 제외` : ""}
          </li>)}
        </ol>}
        <p>계수 {analysis.coefficient_n}개 (절편 포함)
          {analysis.design_rank != null && ` · 독립적으로 구분되는 계수 ${analysis.design_rank}개`}</p>
        {included.length > 0 && <p>실제 반영 변수: {included.map(v => labels[v.name] ?? v.name).join(", ")}</p>}
        {analysis.feature_names.some(name => name.startsWith("bld_")) && <p>단지 차이의 비교 기준: {analysis.feature_names.filter(name => name.startsWith("bld_")).length}개 계수 (기준 단지 제외)</p>}
        {analysis.design_rank != null && analysis.design_rank < analysis.coefficient_n && (
          <p className="text-amber-700 dark:text-amber-300">일부 변수의 효과를 따로 구분하기 어렵습니다. 계수 해석에 주의해 주세요.</p>
        )}
        {omitted.length > 0 && <p>선택했지만 반영되지 않은 변수: {omitted.map(v => `${labels[v.name] ?? v.name} (${reasons[v.state] ?? "상태 미확인"})`).join(", ")}</p>}
        {Object.keys(analysis.reference_categories ?? {}).length > 0 && <p>실제 기준 범주: {Object.entries(analysis.reference_categories ?? {}).map(([key, value]) => `${key} ${categories[value] ?? value}`).join(" · ")}</p>}
        {!!analysis.sample_groups?.length && <details className="pt-1">
          <summary className="cursor-pointer">대상별 조회·적합 표본 ({analysis.sample_groups.length}개)</summary>
          <div className="overflow-auto max-h-64 mt-1" tabIndex={0} aria-label="대상별 표본 표">
            <table className="w-full text-left tabular-nums">
              <thead><tr><th className="p-1">대상</th><th className="p-1 text-right">조회</th><th className="p-1 text-right">적합</th><th className="p-1">고정효과</th></tr></thead>
              <tbody>{analysis.sample_groups.map(group => <tr key={group.key} className="border-t border-slate-200 dark:border-slate-700">
                <td className="p-1">{group.label}{group.address && <span className="block text-slate-600 dark:text-slate-300">{group.address}</span>}
                  {group.structural_excluded_n != null && <span className="block">지분 제외 {group.structural_excluded_n}건 · 비지분 공시지가 연결 {group.linked_n}건 / 미연결 {group.unlinked_n}건</span>}</td>
                <td className="p-1 text-right">{group.source_n.toLocaleString("ko-KR")}</td>
                <td className="p-1 text-right">{group.fit_n.toLocaleString("ko-KR")}</td>
                <td className="p-1">{{reference:"기준 범주", estimated:"계수 포함", not_in_model:"미포함", no_fit:"적합 거래 없음"}[group.fe_state]}</td>
              </tr>)}</tbody>
            </table>
          </div>
          <p className="mt-1">조회 수와 적합 수의 차이에는 결측·이상치·선택 변수 조건이 반영됩니다. 고정효과 미포함이 거래 제외를 뜻하지는 않습니다.</p>
        </details>}
        {evaluations.map((metric, i) => <div key={`${metric.role}-${i}`}><p>
          {methods[metric.method ?? ""] ?? "검증"}: {metric.status === "available" && metric.value != null
            ? `MAPE ${metric.value.toFixed(2)}%${metric.n != null ? ` · 평가 ${metric.n.toLocaleString("ko-KR")}${unit}` : " · 평가 표본 수 미제공"}`
            : metric.validation ? "미제공" : `미제공 · ${metric.reason ?? "계산되지 않았습니다."}`}
        </p><ValidationStatus report={metric.validation} /></div>)}
        {evaluations.length === 0 && <p>검증 오차: 이 결과에서 제공하지 않습니다.</p>}
        <p className="text-slate-500 dark:text-slate-400">표본·변수·검증 대상이 다르면 결과 수치만으로 모형의 우열을 판단하기 어렵습니다.</p>
      </div>
    </details>
  );
}
