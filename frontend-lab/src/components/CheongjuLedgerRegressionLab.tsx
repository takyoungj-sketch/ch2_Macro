import { useState } from "react";
import summary from "../../../docs/lab/cheongju_ledger_lab_summary.json";
import historicalTraits from "../../../docs/lab/cheongju_historical_traits_20261004.json";

const models: Record<string, string> = {
  baseline: "기존 변수", assessed: "+ 공시지가", traits: "+ 토지특성",
  combined: "+ 공시지가·토지특성", combined_restrictions: "+ 공시지가·특성·지구",
};
const fmt = (n: number, digits = 3) => n.toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
const th = "py-2 pr-3 text-left font-medium whitespace-nowrap";
const td = "py-2 pr-3 whitespace-nowrap";

export default function CheongjuLedgerRegressionLab() {
  const [policy, setPolicy] = useState("prior");
  const [year, setYear] = useState(2026);
  const rows = summary.results.filter(r => r.policy === policy && r.test_year === year);
  const baseline = rows.find(r => r.model === "baseline")!;
  const policyKey = policy === "prior" ? "observed_before_trade" : "annual";
  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6 text-sm leading-relaxed">
      <section className="card p-4 space-y-2">
        <h2 className="font-semibold">청주 연도별 대장 보강 · 고정된 실험 결과</h2>
        <p>계산일 {summary.run_date}. 2023~26년 토지특성·토지이용계획을 연결한 로컬 실험입니다. 선택은 저장된 결과를 바꾸어 봅니다. 제품 회귀식은 변경하지 않습니다.</p>
        <p className="text-amber-800 dark:text-amber-200">후보가 하나여도 실제 필지가 맞는지는 검증되지 않았습니다. 동일 필지로 연결된 공통 표본만 비교하므로, 청주 전체 거래에 일반화할 수 없습니다.</p>
        <p>전체 거래 {fmt(summary.transaction_rows, 0)}건 → 회귀 비교 {fmt(summary.sample, 0)}건. 연결 정책 간 필지 충돌 {summary.conflicting_pnu_excluded}건, 면적·가격 조건 미충족 {summary.positive_filter_excluded}건은 제외했습니다. 2026년은 적재된 기간까지입니다.</p>
      </section>
      <section className="card p-4 space-y-2">
        <h3 className="font-semibold">추가 확보 · 2019~2022년 토지특성</h3>
        <p>청주 4개 구 × 4개 연도 ZIP 16개를 전수 읽었습니다. 아래는 원천 자료 검사이며 위 회귀 실험의 기간을 확장한 결과가 아닙니다.</p>
        <div className="overflow-x-auto"><table className="w-full tabular-nums"><thead><tr className="border-b"><th className={th}>기준연도</th><th className={th}>원천 행 수</th><th className={th}>해당 연도·양수 공시지가 행</th></tr></thead>
          <tbody>{Object.entries(historicalTraits.year_summary).map(([y, s]) => <tr key={y} className="border-b"><td className={td}>{y}</td><td className={td}>{fmt(s.rows, 0)}</td><td className={td}>{fmt(s.year_with_positive_price, 0)}</td></tr>)}</tbody>
        </table></div>
        <p className="text-amber-800 dark:text-amber-200">2019년 중복 PNU 15행은 보강 속성이 동일했습니다. 2022년은 주요 특성 명칭이 비어 있어 코드 원값을 보존했습니다. 공시지가가 존재하는 행 수는 거래 연결률이나 정확도가 아닙니다.</p>
        <p>관측 기준일: 2019-08-20 · 2020-08-20 · 2021-11-15 · 2022-11-09. 연초 계약 당시 자료로 표시하지 않습니다. 2019~2022년 토지특성만 사용하는 연결 방식과 회귀 확대는 후속 검증입니다.</p>
      </section>
      <div className="flex flex-wrap gap-4">
        <label>대장 연결 방식 <select className="ml-2 rounded border bg-white dark:bg-slate-900 p-2" value={policy} onChange={e => setPolicy(e.target.value)}>
          <option value="prior">거래 전 관측된 최신 자료</option><option value="annual">계약연도 대표 자료 · 사후 비교</option>
        </select></label>
        <label>검증연도 <select className="ml-2 rounded border bg-white dark:bg-slate-900 p-2" value={year} onChange={e => setYear(Number(e.target.value))}>
          <option value={2025}>2025</option><option value={2026}>2026</option>
        </select></label>
      </div>
      <p>{policy === "prior" ? "토지특성과 이용계획의 관측일이 모두 계약일 이전인 자료만 연결합니다. 그래도 관측일이 법적 효력일을 뜻하지는 않습니다." : "같은 계약연도의 대표 자료를 연결합니다. 계약일 이후 관측 자료가 포함될 수 있어 미래 예측 성능으로 해석할 수 없습니다."}</p>
      <section className="space-y-2">
        <h3 className="font-semibold">집단 평균 오차 비교</h3>
        <p>학습 {year === 2025 ? "2024" : "2024~25"}년 {fmt(baseline.n_train, 0)}건 → 검증 {year}년 {fmt(baseline.n_test, 0)}건. 각 모형은 같은 거래를 사용합니다.</p>
        <div className="overflow-x-auto"><table className="w-full tabular-nums">
          <caption className="text-left text-xs text-slate-500 mb-2">용도지역×지목 집단 중 20건 이상인 {baseline.cells_n20}개 집단의 평균을 비교합니다. 가격 오차 단위: 만 원/㎡.</caption>
          <thead><tr className="border-b"><th className={th}>변수 구성</th><th className={th}>집단 평균 오차</th><th className={th}>기존 대비 감소</th><th className={th}>로그 RMSE</th><th className={th}>학습 조정 R²</th></tr></thead>
          <tbody>{rows.map(r => <tr key={r.model} className="border-b border-slate-200 dark:border-slate-700">
            <td className={td}>{models[r.model]}</td><td className={td}>{fmt(r.cell_mean_mae_n20_10k_sqm)}</td>
            <td className={td}>{r.model === "baseline" ? "—" : `${fmt((1 - r.cell_mean_mae_n20_10k_sqm / baseline.cell_mean_mae_n20_10k_sqm) * 100, 1)}%`}</td>
            <td className={td}>{fmt(r.test_log_rmse)}</td><td className={td}>{fmt(r.train_adj_r2)}</td>
          </tr>)}</tbody>
        </table></div>
        <details className="rounded border p-3"><summary className="cursor-pointer">지표·변수 설명</summary>
          <p className="mt-2">집단 평균 오차는 거래 단가의 관측 평균과 모형 평균의 절대 차이를 집단 거래 건수로 가중한 값입니다. 감소율이 음수이면 악화입니다. 로그 RMSE는 개별 거래의 로그 단가 오차로, 낮을수록 좋지만 원가격의 정확도 비율은 아닙니다. 조정 R²는 학습 표본의 설명력입니다.</p>
          <p className="mt-2">기존 변수: 로그 면적·연도 추세·법정동·거래 지목·용도지역·도로·거래유형. 토지특성: 이용상황·고저·형상·도로. 연도별 명칭 차이는 원자료 코드로 통일했습니다. 지구: 고도·경관·자연취락·지구단위계획의 포함/저촉 여부이며 접함은 제외했습니다. 운영 회귀 모달을 그대로 재현한 실험은 아닙니다.</p>
        </details>
      </section>
      <section className="space-y-2">
        <h3 className="font-semibold">검증 표본 전체의 평균 · 근사 95% 신뢰구간</h3>
        <p>관측 평균 {fmt(baseline.test_actual_mean_10k_sqm)}만 원/㎡. 아래는 검증 표본의 특성 구성에 대한 조건부 평균입니다.</p>
        <div className="overflow-x-auto"><table className="w-full tabular-nums"><thead><tr className="border-b"><th className={th}>변수 구성</th><th className={th}>모형 평균</th><th className={th}>근사 95% 구간</th></tr></thead>
          <tbody>{rows.map(r => <tr key={r.model} className="border-b"><td className={td}>{models[r.model]}</td><td className={td}>{fmt(r.test_predicted_mean_10k_sqm)}</td><td className={td}>{r.mean_ci95_approx.map(n => fmt(n)).join(" ~ ")}</td></tr>)}</tbody>
        </table></div>
        <p className="text-amber-800 dark:text-amber-200">평균 과대추정이 남아 있습니다. 구간이 좁아진 것만으로 성공을 판단하지 않습니다. 필지 단위 군집 공분산·델타 방법의 근사 구간이며, 매칭 오류·원자료 시점·로그 역변환 보정의 불확실성은 포함하지 않습니다. 개별 물건 예측구간이 아닙니다.</p>
      </section>
      <section className="space-y-2">
        <h3 className="font-semibold">연결 표본과 원자료 관측일</h3>
        <div className="overflow-x-auto"><table className="w-full tabular-nums"><thead><tr className="border-b"><th className={th}>거래연도</th><th className={th}>비교 대상</th><th className={th}>후보 1개</th><th className={th}>복수 후보</th><th className={th}>후보 없음</th></tr></thead>
          <tbody>{[2024, 2025, 2026].map(y => {
            const c = summary.counts[`${y}:${policyKey}` as keyof typeof summary.counts];
            return <tr key={y} className="border-b"><td className={td}>{y}</td><td className={td}>{fmt(c.unique_candidate + c.ambiguous + c.no_candidate, 0)}</td><td className={td}>{fmt(c.unique_candidate, 0)}</td><td className={td}>{fmt(c.ambiguous, 0)}</td><td className={td}>{fmt(c.no_candidate, 0)}</td></tr>;
          })}</tbody></table></div>
        <p>비교 대상은 지분·해제·지원하지 않는 용도 등을 제외한 거래입니다. 후보 1개는 매칭 정확도와 다릅니다.</p>
        <div className="text-xs text-slate-500 space-y-1">{Object.entries(summary.source_join).map(([y, s]) => <p key={y}>{y}년: 토지특성 {s.trait_asof} · 이용계획 {s.plan_asof} · {fmt(s.parcels, 0)}필지</p>)}</div>
      </section>
      <section className="card p-4 space-y-3">
        <h3 className="font-semibold">추가 검증 · 학습에 없던 필지와 지역별 차이</h3>
        <p>아래는 동일한 시간 순서 모형에서 학습에 없던 PNU의 검증 거래만 따로 집계한 결과입니다. 모든 연결은 여전히 정확도 미검증입니다.</p>
        <div className="overflow-x-auto"><table className="w-full tabular-nums">
          <thead><tr className="border-b"><th className={th}>변수 구성</th><th className={th}>새 필지 거래 수</th><th className={th}>로그 RMSE</th><th className={th}>거래 절대오차 · 만 원/㎡</th></tr></thead>
          <tbody>{rows.map(r => <tr className="border-b" key={r.model}><td className={td}>{models[r.model]}</td><td className={td}>{fmt(r.unseen_parcel_test.n, 0)}</td><td className={td}>{r.unseen_parcel_test.log_rmse == null ? "—" : fmt(r.unseen_parcel_test.log_rmse)}</td><td className={td}>{r.unseen_parcel_test.mae_10k_sqm == null ? "—" : fmt(r.unseen_parcel_test.mae_10k_sqm)}</td></tr>)}</tbody>
        </table></div>
        <details><summary className="cursor-pointer">구별 관측 평균과 모형 평균</summary>
          <p className="mt-2">각 구의 같은 검증 거래에서 비교합니다. 로그 RMSE는 개별 거래 지표이며 구 평균의 정확도와 구분합니다. 가격 단위: 만 원/㎡.</p>
          <div className="overflow-x-auto"><table className="w-full tabular-nums"><thead><tr><th className={th}>구</th><th className={th}>변수 구성</th><th className={th}>거래 수</th><th className={th}>관측 평균</th><th className={th}>모형 평균</th><th className={th}>로그 RMSE</th></tr></thead>
            <tbody>{rows.filter(r => r.model === "baseline" || r.model === "assessed").flatMap(r => r.district_validation.map(d => <tr key={`${r.model}:${d.sigungu}`} className="border-b"><td className={td}>{{"43111":"상당", "43112":"서원", "43113":"흥덕", "43114":"청원"}[d.sigungu] ?? d.sigungu}</td><td className={td}>{models[r.model]}</td><td className={td}>{fmt(d.n, 0)}</td><td className={td}>{fmt(d.actual_mean)}</td><td className={td}>{fmt(d.predicted_mean)}</td><td className={td}>{fmt(d.log_rmse)}</td></tr>))}</tbody>
          </table></div>
        </details>
      </section>
      <section className="card p-4 space-y-2">
        <h3 className="font-semibold">연결 표본 편향과 독립 검증 상태</h3>
        <p>취소·지분·지원 불가 입력을 제외한 비교 대상 안에서 연결/미연결 집단을 비교합니다. 회귀 공통 표본과는 범위가 다릅니다.</p>
        {summary.link_review.selection_bias_groups.filter(g => g.policy === policyKey).map(g => <p key={g.group}>{g.group === "unique_candidate" ? "후보 1개" : "미연결·복수 후보"}: {fmt(g.n, 0)}건 · 면적 중앙값 {fmt(g.area_sqm_transaction.median, 1)}㎡ · 단가 중앙값 {fmt(g.unit_price_per_sqm_transaction.median, 1)}만 원/㎡.</p>)}
        <p className="text-amber-800 dark:text-amber-200">표본 구성이 다르므로 연결 거래의 개선을 전체 거래에 일반화하지 않습니다. 독립 근거로 검증된 연결은 {summary.link_review.independently_validated_matches}건입니다. 정책 충돌 {summary.link_review.policy_conflicts}건을 포함한 로컬 검토 대기열 {summary.link_review.review_queue_rows}행은 동일 거래 중복을 포함하며 정답 인증 결과가 아닙니다.</p>
      </section>
      <p className="text-xs text-slate-500">새 범주는 학습된 기타 그룹으로 처리하며, 기타 그룹이 없으면 학습 최빈 범주로 대체하고 실험 원결과에 건수를 기록합니다. 관측일 검사는 후보 필지 전체의 가장 늦은 원천 날짜를 기준으로 수행합니다. 과거 원천 기준일은 당시 CH2의 입수 가능성을 증명하지 않습니다. 결과 출처: cheongju_regression_pilot_20261004.json · cheongju_link_review_20261004.json.</p>
    </div>
  );
}
