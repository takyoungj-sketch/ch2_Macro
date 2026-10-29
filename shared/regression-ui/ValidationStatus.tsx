// @ts-nocheck — React는 각 앱의 런타임에서 제공한다.
import type { RegressionValidationContext } from "./types";
import { validationCaption } from "./validation";

export default function ValidationStatus({ report }: { report?: RegressionValidationContext | null }) {
  if (!report) return null;
  const caption = validationCaption(report);
  return <div className="text-xs text-slate-700 dark:text-slate-200">
    {report.failures?.length ? <details>
      <summary className="cursor-pointer">{caption}</summary>
      <ul className="list-disc pl-5 mt-1">{report.failures.map(item => <li key={item.fold}>{item.year != null ? `${item.year}년` : `${item.fold}번 분할`}: {item.reason}</li>)}</ul>
      <p>{report.status === "partial" ? "표시한 오차는 완료한 평가 대상 기준이며, 예정된 전체 평가의 결과가 아닙니다." : "정상 예측 수는 계산 진행 기록입니다. 일부 성공만으로 전체 검증 오차를 제공하지 않습니다."}</p>
    </details> : <p>{caption}</p>}
    {report.excluded_n > 0 && <p>검증 전에 유한한 금액·설명변수를 갖추지 못한 {report.excluded_n.toLocaleString("ko-KR")}건을 제외했습니다.</p>}
  </div>;
}
