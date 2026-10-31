import { getGlossaryEntry, getStatsLearnUrl } from "@ch2/stats-glossary";
import type { AnalysisExplain } from "../types";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import BuiltHelpContent from "./BuiltHelpContent";

const COPY: Record<string, { title: string; summary: string; points: string[]; notes: string[] }> = {
  r_squared: { title: "결정계수 R²", summary: "모형이 거래금액의 변동을 얼마나 설명하는지 나타내는 적합도 지표입니다.", points: ["같은 분석 조건에서는 값이 클수록 표본 안의 변동을 많이 설명합니다.", "로그 척도의 R²와 원래 금액 척도의 R²는 직접 비교하지 마세요."], notes: ["높은 R²가 새로운 거래의 정확한 예측이나 인과관계를 보장하지는 않습니다."] },
  adj_r_squared: { title: "조정 R²", summary: "표본 수와 변수 수를 고려해 결정계수를 조정한 값입니다.", points: ["같은 표본에서 변수를 늘렸을 때 설명력이 실제로 개선되는지 참고할 수 있습니다."], notes: ["표본이나 척도가 다르면 수치만으로 모형의 우열을 판단하기 어렵습니다. 개별 거래의 예측 정확도와도 다릅니다."] },
  mape: { title: "학습 MAPE", summary: "분석에 사용한 거래에서 예측금액과 실제금액의 차이를 절대오차율로 계산한 평균입니다.", points: ["같은 표본과 계산 기준에서는 값이 낮을수록 오차가 작습니다.", "오차의 방향은 나타내지 않습니다. 높게 추정했는지는 잔차 진단에서 확인해 주세요."], notes: ["새로운 거래의 예측오차가 아닙니다. 실제 거래금액이 작으면 오차율이 크게 나타날 수 있습니다."] },
  cv_mape: { title: "CV-MAPE", summary: "학습에 사용하지 않은 거래를 예측해 계산한 절대오차율의 평균입니다.", points: ["복합 회귀는 과거 연도로 학습하고 다음 연도를 예측하는 방식으로 확인합니다.", "완료한 평가 연도와 거래 수, 생략 사유를 함께 확인해 주세요."], notes: ["모형을 고르는 데 사용한 검증 오차는 낙관적일 수 있습니다. 마지막 연도 확인과 미래의 실제 정확도를 같은 것으로 보지 마세요."] },
  fit_n: { title: "적합 표본 수", summary: "현재 회귀계수를 계산하는 데 실제로 사용한 거래 수입니다.", points: ["조회한 거래에서 결측치·지분거래·이상치 등의 처리 뒤 남은 표본입니다.", "제외 이유와 거래 수는 결과의 표본 상세에서 확인할 수 있습니다."], notes: ["표본이 많아도 거래 구성과 변수의 상태에 따라 계수 해석이 제한될 수 있습니다."] },
  coefficient: { title: "회귀계수", summary: "다른 조건이 같을 때 각 변수와 거래금액이 어떤 관계를 보이는지 나타냅니다.", points: ["숫자 변수는 단위 변화에 따른 차이로, 범주형 변수는 기준 범주와의 차이로 읽습니다.", "선형·로그·로그-로그 모형은 계수의 의미가 다릅니다. 계수 표의 효과 해석을 함께 확인해 주세요."], notes: ["통계적으로 유의하더라도 인과관계를 뜻하지 않습니다. 변수 간 정보가 겹치면 계수를 따로 해석하기 어려울 수 있습니다."] },
  se: { title: "표준오차 SE", summary: "추정한 회귀계수의 불확실성을 나타냅니다.", points: ["같은 계수와 단위에서 값이 클수록 추정의 불확실성이 큽니다.", "계수의 크기, t값과 p값을 함께 확인해 주세요."], notes: ["단위가 다른 변수의 표준오차 크기를 그대로 비교하지 마세요."] },
  p_value: { title: "p값", summary: "해당 검정의 기준 가정 아래에서 관측한 결과 이상으로 극단적인 결과가 나타날 확률입니다.", points: ["회귀계수 검정에서는 일반적으로 계수가 0이라는 가정과 자료가 얼마나 어긋나는지 살펴봅니다.", "작은 p값이 큰 효과나 높은 예측 정확도를 뜻하지는 않습니다."], notes: ["가정이 참일 확률이나 분석이 틀렸을 확률로 읽지 마세요. 검정의 가정과 표본 상태도 영향을 줍니다."] },
  f_p_value: { title: "모형 전체의 F 검정", summary: "설명변수를 함께 고려한 모형의 통계적 연관성을 확인하는 검정입니다.", points: ["일반적으로 절편을 제외한 설명변수의 계수가 모두 0이라는 가정을 검정합니다."], notes: ["유의한 결과가 개별 거래의 예측 정확도나 모든 변수의 유의성을 보장하지는 않습니다."] },
  vif: { title: "다중공선성 VIF", summary: "설명변수끼리 정보가 얼마나 겹치는지 살펴보는 지표입니다.", points: ["값이 크면 해당 변수의 계수 크기나 부호가 불안정할 수 있습니다.", "이 화면에서 제공하는 변수별 값과 실제 포함 변수를 함께 확인해 주세요."], notes: ["참고 기준을 넘었다는 이유만으로 변수를 자동으로 제외하거나 모형이 틀렸다고 판단하지 마세요."] },
  confidence_interval: { title: "95% 평균 추정범위", summary: "입력한 조건에서 평균적인 금액 수준에 대한 불확실성을 나타내는 범위입니다.", points: ["개별 거래마다 생기는 변동은 포함하지 않습니다. 개별 거래 예측범위와 구분해 주세요."], notes: ["개별 부동산의 적정가격 범위나 실제 거래금액의 보장 범위가 아닙니다."] },
  prediction_interval: { title: "95% 개별 거래 예측범위", summary: "입력한 조건에서 개별 거래의 변동까지 고려한 통계적 범위입니다.", points: ["평균 추정범위보다 넓을 수 있습니다. 표본과 잔차의 변동에 따라 달라집니다."], notes: ["모형의 가정에 따른 범위입니다. 실제 거래금액이 반드시 포함되는 것은 아니며 감정평가 구간도 아닙니다."] },
  aic: { title: "AIC", summary: "모형의 적합도와 변수 수를 함께 고려하는 비교 기준입니다.", points: ["비교 가능한 후보 사이에서는 값이 낮은 모형을 선호합니다."], notes: ["표본과 종속변수 척도 등 비교 조건을 먼저 확인해 주세요. 절대값을 정확도 점수로 읽지 마세요."] },
  bic: { title: "BIC", summary: "적합도와 변수 수를 함께 고려하며, 표본 수에 따라 복잡한 모형에 더 큰 부담을 주는 비교 기준입니다.", points: ["비교 가능한 후보 사이에서는 값이 낮은 모형을 선호합니다. AIC보다 단순한 모형을 선호하는 경향이 있습니다."], notes: ["표본과 척도가 다른 후보는 수치만으로 비교하지 마세요."] },
};

export function StatsGlossaryHelp({ termId, className, size = "sm" }: { termId: string; className?: string; size?: "sm" | "xs" }) {
  const entry = getGlossaryEntry(termId);
  if (!entry) return null;
  const copy = COPY[termId];
  const explain: AnalysisExplain = {
    spec_id: `built.glossary.${termId}`, spec_version: "1", title: copy?.title ?? entry.title,
    summary: copy?.summary ?? entry.definition, interpretation: copy?.points ?? entry.interpretation,
    limitations: copy?.notes ?? entry.limitations, formula: entry.formula,
    controls: entry.thresholds, interpretation_hints: [], presets: [],
  };
  return <AnalysisHelpPanel explain={explain} title={`${entry.label} 용어 설명`} className={`${size === "xs" ? "h-5 w-5" : ""} ${className ?? ""}`}
    content={<BuiltHelpContent explain={explain} learnUrl={getStatsLearnUrl(termId)} />} />;
}
