// @ts-nocheck — shared: React는 각 frontend의 런타임에서 제공한다.

export const STALE_RESULT_NOTE =
  "분석 조건이 바뀌었습니다. 아래 결과는 이전 조건으로 계산했습니다.";

export function SummaryHeading() {
  return <h3 className="text-xs font-semibold text-slate-800 dark:text-slate-100">결과 요약</h3>;
}

export function DetailAnalysis({ children }) {
  return (
    <details className="rounded border border-slate-200 dark:border-slate-700">
      <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-slate-800 dark:text-slate-100">
        상세 분석
      </summary>
      <div className="px-3 pb-3 space-y-3">{children}</div>
    </details>
  );
}
