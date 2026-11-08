import type { ReactNode } from "react";
import clsx from "clsx";
import type { FloorIndexResponse } from "../types";
import { utilityNumber, utilityP, utilityWarnings, unavailableUtilityReason } from "../utils/residentialUtilityPresentation";

export type UtilityIndexData = Pick<FloorIndexResponse, "cells" | "n_total" | "dimension" | "method" | "reference_floor" | "n_regression" | "r_squared" | "warnings">;

export default function UtilityIndexResults({ data, header, intro, columnLabel, notice, children }: { data: UtilityIndexData; header: ReactNode; intro: string; columnLabel: string; notice?: ReactNode; children: ReactNode }) {
  const { cells, n_total, dimension: dim, method, reference_floor, n_regression, r_squared, warnings } = data;
  const isRegression = method === "regression_semilog";
  const notes = utilityWarnings(warnings);
  const missingCount = cells.filter(c => c.index == null || !Number.isFinite(c.index)).length;
  const referenceTitle = dim === "floor" ? "기준층" : "기준 구간";
  return <div className="space-y-4">
    {header}
    <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{intro}</p>
    <div className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900/50 sm:grid-cols-4">
      {[["조회 거래", `${n_total.toLocaleString("ko-KR")}건`], ["분석 거래", n_regression == null ? "—" : `${n_regression.toLocaleString("ko-KR")}건`], ["결정계수 R²", utilityNumber(r_squared, 3)], [referenceTitle, reference_floor || "미제공"]].map(([label,value]) => <div key={label}><p className="text-sm text-slate-500 dark:text-slate-400">{label}</p><p className="mt-1 text-base font-semibold tabular-nums text-slate-800 dark:text-slate-100">{value}</p></div>)}
    </div>
    {notice}
    {!isRegression && <p role="status" className="text-sm text-amber-700 dark:text-amber-300">{cells.some(c => c.index != null) ? "모형을 적합하지 못했습니다. 기준 구간의 100은 참고용이며, 나머지 구간의 효용지수는 산출하지 않았습니다." : "분석 표본 또는 비교 구간이 부족해 효용지수를 산출하지 못했습니다."}</p>}
    {notes.important.length > 0 && <ul role="status" className="space-y-1 text-sm text-amber-800 dark:text-amber-300">{notes.important.map(text => <li key={text}>{text}</li>)}</ul>}
    {(notes.hasExcludedControls || notes.hasCollinearity) && <p className="text-sm text-slate-600 dark:text-slate-300">{notes.hasExcludedControls && "일부 통제변수가 제외됐습니다. "}{notes.hasCollinearity && "공선성·수치 불안정에 주의가 필요합니다. "}상단 도움말에서 실제 반영 변수와 사유를 확인해 주세요.</p>}
    {children}
    {missingCount > 0 && <p className="text-sm text-slate-500 dark:text-slate-400">효용지수 미산출 {missingCount}개 구간 · 아래 표에서 확인할 수 있습니다.</p>}
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700"><table className="w-full min-w-[620px] border-collapse text-sm">
      <thead className="bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-300"><tr>{[columnLabel,"전체 거래","분석 거래","평균 단가(만원/㎡)","효용지수", ...(isRegression ? ["95% 신뢰구간","p값"] : [])].map(label => <th key={label} className={clsx("border border-slate-200 px-2 py-2 font-medium dark:border-slate-600", label === columnLabel ? "text-left" : "text-right", label === "효용지수" && "font-bold text-indigo-700 dark:text-indigo-300")}>{label}</th>)}</tr></thead>
      <tbody className="text-slate-800 dark:text-slate-200">
        {cells.length === 0 && <tr><td colSpan={isRegression ? 7 : 5} className="border border-slate-200 px-2 py-5 text-center text-slate-500 dark:border-slate-600">표시할 데이터가 없습니다.</td></tr>}
        {cells.map(c => {
          const available = c.index != null && Number.isFinite(c.index);
          return <tr key={c.label} className={clsx(c.is_reference && available ? "bg-indigo-50 dark:bg-indigo-950/40" : !available ? "bg-slate-50 dark:bg-slate-900/40" : undefined)}>
            <td className="border border-slate-200 px-2 py-2 dark:border-slate-600"><span className="whitespace-nowrap">{c.label}</span>{c.is_reference && <span className="ml-2 rounded bg-indigo-100 px-1.5 py-0.5 text-xs font-medium text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">{isRegression ? "기준" : "기준·참고"}</span>}{available && !c.is_reliable && c.count > 0 && !c.is_reference && <span className="ml-2 text-xs text-amber-700 dark:text-amber-300">참고용</span>}</td>
            <td className="border border-slate-200 px-2 py-2 text-right tabular-nums dark:border-slate-600">{(c.count_raw ?? c.count).toLocaleString("ko-KR")}</td>
            <td className="border border-slate-200 px-2 py-2 text-right tabular-nums dark:border-slate-600">{c.count.toLocaleString("ko-KR")}</td>
            <td className="border border-slate-200 px-2 py-2 text-right tabular-nums dark:border-slate-600">{utilityNumber(c.mean_unit_price)}</td>
            <td className="border border-slate-200 px-2 py-2 text-right dark:border-slate-600">{available ? <span className="text-base font-bold tabular-nums text-indigo-700 dark:text-indigo-300">{utilityNumber(c.index)}</span> : <span className="text-xs text-slate-500 dark:text-slate-400">미산출 · {unavailableUtilityReason(c,warnings)}</span>}</td>
            {isRegression && <><td className="border border-slate-200 px-2 py-2 text-right tabular-nums text-slate-600 dark:border-slate-600 dark:text-slate-300">{c.index_lo != null && c.index_hi != null ? `${utilityNumber(c.index_lo)}–${utilityNumber(c.index_hi)}` : "—"}</td><td className="border border-slate-200 px-2 py-2 text-right tabular-nums text-slate-600 dark:border-slate-600 dark:text-slate-300">{utilityP(c.p_value)}</td></>}
          </tr>;
        })}
      </tbody>
    </table></div>
  </div>;
}
