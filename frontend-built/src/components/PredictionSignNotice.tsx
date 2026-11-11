import type { RegressionPredictResponse } from "../types";
import { requestOpenMacroExplore } from "../utils/openMacroExplore";

/**
 * B-01: 선형식 음수 추정 — 값은 숨기거나 0으로 바꾸지 않고, 성격을 바로 아래에 알린다.
 * 하한만 음수면 하한을 별도 안내한다(음수 하한도 숨기지 않음).
 */
export default function PredictionSignNotice({ result, showMacroButton = true }: { result: RegressionPredictResponse; showMacroButton?: boolean }) {
  if (result.nonpositive_estimate) {
    return <div role="status" className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900 dark:border-amber-600/60 dark:bg-amber-950/30 dark:text-amber-100" data-nonpositive-estimate>
      <p className="font-medium">선형식 계산 결과이며 실제 거래금액을 의미하지 않습니다.</p>
      <p>선형식이 이 입력 조건에 맞지 않을 수 있습니다(표본 범위 안에서도 나옵니다). 다른 척도(log·log-log)나 변수 조합을 확인해 보세요.</p>
      {showMacroButton && <button type="button" className="btn btn-ghost text-xs" onClick={requestOpenMacroExplore}>Macro 모형 탐색 열기</button>}
    </div>;
  }
  if (result.negative_lower_bound) {
    return <p role="status" className="text-xs leading-relaxed text-amber-800 dark:text-amber-200" data-negative-lower-bound>
      구간 하한이 0 미만입니다. 선형식 구간 계산의 값을 그대로 보인 것이며 금액의 하한을 뜻하지 않습니다.
    </p>;
  }
  return null;
}
