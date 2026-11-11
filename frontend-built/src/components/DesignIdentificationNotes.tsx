import type { RegressionLevelResult } from "../types";

/** B-12: 설계행렬에서 뺀 더미와 식별 경고를 결과 카드에 그대로 보인다. */
export default function DesignIdentificationNotes({ result }: { result: RegressionLevelResult }) {
  const dropped = result.dropped_design_columns ?? [];
  const warning = result.identification_warning;
  if (!dropped.length && !warning) return null;
  const nested = dropped.filter(note => note.reason === "nested_duplicate");
  const zero = dropped.filter(note => note.reason === "all_zero");
  return <div className="space-y-1 text-xs leading-relaxed" data-design-identification>
    {warning && <p role="status" className="border-l-2 border-amber-500 pl-3 text-amber-800 dark:text-amber-200">{warning}</p>}
    {nested.map(note => <p key={note.name} className="border-l-2 border-slate-300 pl-3 text-slate-600 dark:border-slate-600 dark:text-slate-300">{note.detail}</p>)}
    {zero.length > 0 && <p className="border-l-2 border-slate-300 pl-3 text-slate-600 dark:border-slate-600 dark:text-slate-300">
      최종 표본에 거래가 없는 범주 {zero.length}개는 계수를 정할 수 없어 식에서 뺐습니다: {zero.map(note => note.detail.split(" 거래가")[0]).join(", ")}
    </p>}
  </div>;
}
