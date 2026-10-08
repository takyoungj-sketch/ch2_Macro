import { useState } from "react";
import data from "../../../docs/lab/cheongju_historical_lab_summary.json";

const names: Record<string,string> = { baseline:"기존 변수", assessed:"+ 공시지가", traits:"+ 토지특성", combined:"+ 공시지가·특성" };
const districts: Record<string,string> = {"43111":"상당", "43112":"서원", "43113":"흥덕", "43114":"청원"};
const fmt = (n: number | null, digits=3) => n == null ? "—" : n.toLocaleString("ko-KR",{maximumFractionDigits:digits});
const cell="p-2 text-left whitespace-nowrap";

export default function CheongjuHistoricalLedgerLab() {
  const [policy,setPolicy]=useState("observed_before_trade");
  const [year,setYear]=useState(2022);
  const [scope,setScope]=useState("historical_trait");
  const years=scope==="historical_trait" ? [2020,2021,2022,2023,2024,2025,2026] : [2024,2025,2026];
  const rows=data.results.filter(r=>r.policy===policy && r.test_year===year && (scope==="historical_trait" ? r.scope===scope : r.scope!=="historical_trait"));
  const counts=data.counts as Record<string,Record<string,number>>;
  return <div className="max-w-5xl mx-auto p-4 space-y-6 text-sm leading-relaxed">
    <section className="card p-4 space-y-2">
      <h2 className="font-semibold">청주 2019년 확대 · 토지특성 코드 기반 실험</h2>
      <p>계산일 {data.run_date}. 2019~2026년 거래 {fmt(data.transaction_rows,0)}건을 두 관측 정책으로 연결했습니다. 화면은 저장 결과를 보여주며 재학습·DB 갱신을 실행하지 않습니다.</p>
      <p className="text-amber-800 dark:text-amber-200">후보 하나는 정답 인증이 아닙니다. 토지특성의 용도지역 1·2는 토지이용계획의 모든 지정 정보를 대체하지 않습니다. 2019년 중복 15행은 동일 속성 확인 후 PNU 기준으로 제거했습니다.</p>
      <p>2019년은 첫 학습 연도입니다. 2019년 이전 자료가 없어 초기 거래의 사전 관측 연결은 불가합니다. 연도 대표 자료는 사후 참고이며, 관측일 이전 자료도 당시 공개·입수 가능성을 보장하지 않습니다.</p>
    </section>
    <div className="flex flex-wrap gap-3">
      <label>관측 정책 <select className="border rounded p-2 bg-white dark:bg-slate-900" value={policy} onChange={e=>setPolicy(e.target.value)}><option value="observed_before_trade">거래 전 관측 자료</option><option value="annual">계약연도 대표 · 사후 참고</option></select></label>
      <label>비교 범위 <select className="border rounded p-2 bg-white dark:bg-slate-900" value={scope} onChange={e=>{setScope(e.target.value);setYear(e.target.value==="historical_trait" ? 2022 : 2026);}}><option value="historical_trait">2019년부터 학습 · 연도별 검증</option><option value="method">동일 필지·거래 · 두 방식 비교</option></select></label>
      <label>검증연도 <select className="border rounded p-2 bg-white dark:bg-slate-900" value={year} onChange={e=>setYear(Number(e.target.value))}>{years.map(y=><option key={y} value={y}>{y}</option>)}</select></label>
    </div>
    <section className="space-y-2">
      <h3 className="font-semibold">회귀 검증 결과</h3>
      <p>{scope==="historical_trait" ? "선택 연도 이전의 연결 거래로 학습합니다. 같은 정책·검증연도 안의 모형은 동일 표본입니다." : "2023년부터 학습하며 두 방식에서 같은 PNU로 연결된 거래만 비교합니다. 공시지가 사용 판본은 관측 정책에 따라 달라질 수 있습니다."} 정책 간 표본은 달라 수치를 직접 우열로 해석하지 않습니다.</p>
      <div className="overflow-x-auto"><table className="w-full tabular-nums"><thead><tr className="border-b">{["연결 방식","변수","학습 n","검증 n","집단 평균 오차","로그 RMSE","새 필지 n","새 필지 RMSE"].map(s=><th key={s} className={cell}>{s}</th>)}</tr></thead><tbody>{rows.map(r=><tr className="border-b" key={`${r.scope}:${r.model}`}><td className={cell}>{r.scope==="plan_same_sample" ? "특성+이용계획" : "토지특성"}</td><td className={cell}>{names[r.model]}</td><td className={cell}>{fmt(r.n_train,0)}</td><td className={cell}>{fmt(r.n_test,0)}</td><td className={cell}>{fmt(r.cell_mean_mae_n20)}</td><td className={cell}>{fmt(r.test_log_rmse)}</td><td className={cell}>{fmt(r.unseen_parcel.n,0)}</td><td className={cell}>{fmt(r.unseen_parcel.log_rmse)}</td></tr>)}</tbody></table></div>
      {!rows.length && <p>학습·검증 최소 표본을 충족하는 결과가 없습니다.</p>}
      <p>집단 평균 오차는 용도지역×지목의 검증 거래 20건 이상 집단에서 건수로 가중했습니다. 단위는 만 원/㎡입니다. 로그 RMSE는 개별 거래 지표입니다.</p>
      {rows.length>0 && <p>집단 평균 평가 범위: {rows[0].cells_n20}개 집단 · {fmt(rows[0].cell_covered_transactions,0)}거래. 같은 PNU가 학습에 없던 검증 거래만 새 필지 지표에 포함합니다.</p>}
      <details><summary className="cursor-pointer">평균·근사 신뢰구간·구별 차이</summary><div className="overflow-x-auto"><table className="w-full tabular-nums"><thead><tr><th className={cell}>모형·방식</th><th className={cell}>관측 평균</th><th className={cell}>모형 평균</th><th className={cell}>평균 근사 95% 구간</th></tr></thead><tbody>{rows.map(r=><tr key={`${r.scope}:${r.model}`}><td className={cell}>{names[r.model]} · {r.scope==="plan_same_sample" ? "이용계획" : "특성"}</td><td className={cell}>{fmt(r.actual_mean)}</td><td className={cell}>{fmt(r.predicted_mean)}</td><td className={cell}>{r.mean_ci95_approx.map(n=>fmt(n)).join(" ~ ")}</td></tr>)}</tbody></table></div>
      <p>근사 구간은 매칭·원천 시점·역변환 보정의 불확실성을 포함하지 않습니다. 개별 가격 예측구간이 아닙니다.</p>
      {rows.filter(r=>r.model==="baseline" || r.model==="assessed").map(r=><p key={`${r.scope}:${r.model}`} className="mt-2">{names[r.model]} · {r.scope==="plan_same_sample" ? "이용계획" : "특성"}: {r.districts.map(d=>`${districts[d.sigungu] ?? d.sigungu} n=${d.n}, 관측 ${fmt(d.actual_mean)}, 모형 ${fmt(d.predicted_mean)}, 로그 RMSE ${fmt(d.log_rmse)}`).join(" / ")}</p>)}</details>
    </section>
    <section className="card p-4 space-y-2">
      <h3 className="font-semibold">연도별 연결 · 후보 수와 제외</h3>
      <div className="overflow-x-auto"><table className="w-full tabular-nums"><thead><tr>{["거래연도","비교 대상","후보 1개","복수 후보","후보 없음","이전 판본 없음"].map(s=><th className={cell} key={s}>{s}</th>)}</tr></thead><tbody>{[2019,2020,2021,2022,2023,2024,2025,2026].map(y=>{const c=counts[`${y}:${policy}`] ?? {};return <tr key={y} className="border-b"><td className={cell}>{y}</td><td className={cell}>{fmt((c.unique_candidate??0)+(c.ambiguous??0)+(c.no_candidate??0)+(c.no_prior_snapshot??0),0)}</td>{["unique_candidate","ambiguous","no_candidate","no_prior_snapshot"].map(k=><td className={cell} key={k}>{fmt(c[k]??0,0)}</td>)}</tr>;})}</tbody></table></div>
      <p>비교 대상은 해제·무효·지분·지원 불가 입력을 제외합니다. 회귀는 추가로 양수 면적·실거래 단가·공시지가가 필요합니다.</p>
      <details><summary className="cursor-pointer">연결·미연결 표본의 면적과 단가 중앙값</summary>{data.selection_bias.filter(r=>r.policy===policy).map(r=><p key={`${r.year}:${r.group}`}>{r.year} · {r.group==="unique_candidate" ? "후보 1개" : "미연결"}: {fmt(r.n,0)}건 · 면적 {fmt(r.area_median,1)}㎡ · 단가 {fmt(r.price_median,1)}만 원/㎡</p>)}</details>
    </section>
    <section className="space-y-2">
      <h3 className="font-semibold">2023~2026년 · 기존 이용계획 방식과 연결 비교</h3>
      <div className="overflow-x-auto"><table className="w-full tabular-nums"><thead><tr>{["연도","특성 후보 1개","기존 후보 1개","같은 필지","다른 필지","특성만 유일","기존만 유일"].map(s=><th className={cell} key={s}>{s}</th>)}</tr></thead><tbody>{data.method_comparison.filter(r=>r.policy===policy).map(r=><tr key={r.year} className="border-b"><td className={cell}>{r.year}</td>{[r.trait_unique,r.plan_unique,r.same_pnu,r.different_pnu,r.trait_only_unique,r.plan_only_unique].map((n,i)=><td className={cell} key={i}>{fmt(n,0)}</td>)}</tr>)}</tbody></table></div>
      <p className="text-amber-800 dark:text-amber-200">특성만 유일한 후보는 추가 정답이 아닙니다. 필터 정의와 판본 시점이 달라 생긴 후보일 수 있습니다. 2023년 거래 전 이용계획 방식은 2022년 판본이 없어 일부 거래를 연결할 수 없습니다.</p>
    </section>
    <p className="text-xs text-slate-500">로컬 연구 결과입니다. 제품 회귀·운영 DB 변경 없음. 원자료·후보·규칙·입력 해시는 로컬 연구 폴더에 보존합니다. 독립적인 연결 정확도 인증과 공개 제품 적용은 후속 판단입니다.</p>
  </div>;
}
