import type { AnalysisExplain } from "../types";

/** 회귀 실행 전·API explain 없을 때 */
export const BUILT_REGRESSION_HELP: AnalysisExplain = {
  spec_id: "built_regression_static_v1",
  spec_version: "1",
  title: "복합부동산 OLS 회귀",
  summary:
    "금액(또는 log 금액)에 대한 OLS 회귀. **탐색(통제 전) → 분석(통제 후) → 예측** 순으로 해석하세요.",
  formula: "금액 ~ 연면적·대지·연식·용도·도로 등",
  interpretation: [
    "Adj R²·계수·VIF는 scope 내 **통계적 패턴** 참고.",
    "산점도 탭으로 r과 β를 비교하세요.",
    "예측 패널은 변수 고정 후 한 점 예측.",
  ],
  limitations: ["인과·적정가격 아님", "표본·필터에 민감", "지분거래는 중위·회귀에서 기본 제외"],
  interpretation_hints: [],
  presets: [
    {
      id: "share_tx",
      question: "지분거래를 왜 분석에서 빼나요?",
      answer:
        "국토부 지분 행은 연면적(건물 전체)과 대지(지분)의 기준이 건마다 다를 수 있습니다. 목록에는 그대로 두고, ㎡당·회귀만 기본에서 뺍니다. 포함할지는 분석 패널에서 고릅니다. 토지 앱은 포함이 기본입니다.",
    },
  ],
};

export const BUILT_SCATTER_RAW_HELP: AnalysisExplain = {
  spec_id: "built_scatter_raw_v1",
  spec_version: "1",
  title: "상관관계 (통제 전)",
  summary: "원시 X vs 금액 산점도·Pearson r — **실제 시장 거래 분포** 탐색.",
  formula: "r = corr(X, 금액)",
  interpretation: [
    "다른 변수 영향이 섞여 있습니다.",
    "r과 β가 다르면 **부분회귀도** 탭으로 전환.",
  ],
  limitations: ["인과 해석 불가"],
  interpretation_hints: [],
  presets: [
    {
      id: "why_raw",
      question: "왜 통제 전도 필요한가요?",
      answer:
        "현장 데이터의 **실제 모양**을 먼저 봅니다. 통제 후만 보면 시장 분포 감각이 약해질 수 있어 둘 다 제공합니다.",
    },
  ],
};

export const BUILT_SCATTER_PARTIAL_HELP: AnalysisExplain = {
  spec_id: "built_scatter_partial_v1",
  spec_version: "1",
  title: "부분회귀도 (통제 후)",
  summary: "모형과 동일하게 다른 변수를 제거한 **잔차 vs 잔차**. 기울기 = 회귀 β.",
  formula: "Y잔차 vs X잔차 (Added Variable Plot)",
  interpretation: [
    "회귀 계수표와 **같은 의미**.",
    "파란 기울기선 = OLS β.",
    "부분 R² = 통제 후 추가 설명력 참고.",
  ],
  limitations: ["연속 변수만", "log 모형은 log 잔차 공간"],
  interpretation_hints: [],
  presets: [
    {
      id: "beta_line",
      question: "파란 기울기선은?",
      answer: "원점 기준 직선의 기울기가 **회귀 β**와 같습니다.",
    },
  ],
};

export const BUILT_RESIDUAL_HELP: AnalysisExplain = {
  spec_id: "built_residual_diagnostics_v1",
  spec_version: "1",
  title: "잔차 진단 — 이 식이 어디서 틀리나",
  summary:
    "Adj R²와 MAPE는 «평균적으로 얼마나» 틀리는지만 말합니다. 이 진단은 «어디서» 틀리는지를 봅니다 — 특정 지역·용도지역·연식대에서 계속 한쪽으로 치우치는지, 어느 금액대가 더 위험한지, 어떤 거래가 결과를 끌고 있는지.",
  formula: "오차% = (실제 − 예측) ÷ 실제 × 100",
  interpretation: [
    "양수 = 모형이 **싸게 봤다**(실제가 예측보다 높다). 음수는 비싸게 봤다는 뜻입니다.",
    "예측은 화면 상단 MAPE와 **같은 방식**으로 계산합니다. log 모형이면 Duan 보정을 건 값입니다.",
    "집단별로는 **전체 대비**(%p)를 읽으세요. 표본 전체가 공통으로 가진 치우침을 뺀 값이라, 그 집단만 다르게 틀리는 정도를 나타냅니다.",
    "● 표시 = 그 집단 오차 분포가 나머지 표본과 다름(Mann–Whitney p<0.05). 표시가 없으면 n이 얇아 흔들린 것일 수 있으니 구조적 편향으로 읽지 마세요.",
    "특정 지역이 계속 치우치면 **지역 더미 추가**나 **Twin(상위지역 붙임)**을 검토할 근거가 됩니다.",
    "연식 구간이 계단처럼 치우치면 연식을 직선으로 본 가정이 부족하다는 신호입니다.",
    "계약연도가 치우치면 조회 기간 중 시장이 움직였다는 뜻입니다. 기간을 좁히면 줄어듭니다.",
  ],
  limitations: [
    "in-sample 잔차입니다 — 같은 자료로 적합하고 같은 자료로 재므로 실제 예측오차보다 낙관적입니다. 예측력은 모형 탐색의 CV-MAPE를 보세요.",
    "«전체 중위 오차»가 음수로 나오는 것은 흔합니다. 금액이 작은 거래에서 백분율 오차가 한쪽으로만 크게 벌어지기 때문이며(−300%는 가능하지만 +300%는 불가) 모형이 과대평가한다는 뜻이 아닙니다.",
    "10건 미만 집단은 표에 넣지 않습니다.",
    "분석 초점 모형에만 붙습니다. 상위지역 재적합에는 없습니다.",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "excess_bias",
      question: "«전체 대비»와 «중위 오차»는 왜 다른가요?",
      answer:
        "중위 오차는 그 집단의 절대 치우침이고, 전체 대비는 거기서 **나머지 표본의 치우침을 뺀** 값입니다. 표본 전체가 −6% 치우쳐 있는데 어떤 집단도 −6%면 그 집단은 특별하지 않습니다. 진단에서 의미 있는 건 차이 쪽입니다.",
    },
    {
      id: "influential",
      question: "«결과를 끌고 있는 거래»는 어떻게 고르나요?",
      answer:
        "Cook 거리 상위입니다. 오차가 크기만 한 게 아니라 **그 거래를 빼면 계수가 얼마나 움직이는지**를 함께 보는 지표입니다. 아래 «계수 변화»에서 표준오차 몇 배만큼 움직였는지 확인할 수 있고, 1 SE를 넘으면 소수 거래가 결과를 실질적으로 끌고 있다는 뜻입니다.",
    },
    {
      id: "spread",
      question: "«오차 산포»가 분위마다 다르면?",
      answer:
        "그 금액대의 예상값을 더 넓게 봐야 합니다. 작은 거래 쪽 산포가 크면 소형 물건 추정이 불안정하다는 뜻입니다. 계수의 p값도 액면대로 믿기 어려워집니다.",
    },
  ],
};

export const BUILT_PREDICTION_HELP: AnalysisExplain = {
  spec_id: "built_prediction_static_v1",
  spec_version: "2",
  title: "복합부동산 회귀 예측",
  summary:
    "나머지 변수를 고정한 **한 점 OLS 통계적 추정**. 평균 추정범위(CI)·개별 거래 예측범위(PI)는 모형의 불확실성 참고입니다.",
  formula: "ŷ = Xβ",
  interpretation: [
    "통계적 추정값: 선택한 거래자료와 회귀모형의 중심값입니다. AVM·감정평가액이 아닙니다.",
    "95% 평균 추정범위: 이 조건에서 평균적인 가격수준.",
    "95% 개별 거래 예측범위: 개별 거래 변동까지 포함한 통계적 범위.",
    "n이 작으면 범위가 넓습니다.",
  ],
  limitations: ["적정가·감정 아님", "학습 범위 밖 입력은 외삽", "범위는 가액을 보증하지 않음"],
  interpretation_hints: [],
  presets: [
    {
      id: "pi",
      question: "평균 추정범위와 개별 거래 예측범위 차이는?",
      answer:
        "평균 추정범위(CI)는 **평균 가격수준**의 불확실성입니다. 개별 거래 예측범위(PI)는 **개별 거래 변동**을 포함해 더 넓습니다. 실제 대상물건이 반드시 그 안에 있다는 뜻이 아닙니다.",
    },
  ],
};

export const BUILT_MODEL_SELECTION_SUGGEST_HELP: AnalysisExplain = {
  spec_id: "built_model_selection_suggest_static_v1",
  spec_version: "2",
  title: "추천 후보 (Pareto)",
  summary:
    "후보 블록 조합에서 **설명형·균형형·예측형** 3후보를 제시합니다. 「최적」·「정답」이 아니라 **목적별 추천** — 채택은 사용자.",
  formula: "Best Subset pool → Adj R² 1위 · MAPE 1위 · 균형 점수 1위 (vs 현재 baseline)",
  interpretation: [
    "설명형 — Adj R²(log) 우선 · 보고서·요인 해석.",
    "예측형 — 금액 MAPE 우선 · 예측·오차 최소화.",
    "균형형 — Adj R²·MAPE·AIC·변수 수 trade-off.",
    "추천 신뢰도 + reasons — MAPE만으로 추천된 것이 아님을 표시.",
    "Forward 제외 사유 — 참고용 (AIC greedy).",
  ],
  limitations: ["적정가·최적 회귀식 아님", "in-sample MAPE · CV 아님", "n<30 주의"],
  interpretation_hints: [],
  presets: [
    {
      id: "vs_compare",
      question: "추천과 모형 비교 차이는?",
      answer:
        "추천=목적별 3후보 + baseline 대비 trade-off. 모형 비교=AIC/BIC/MAPE 탭별 상위 k — 전체 조합 탐색.",
    },
    {
      id: "purpose",
      question: "어떤 후보를 쓰면 되나요?",
      answer:
        "가격 예측 → 예측형 · 보고서 설명 → 설명형 · 둘 다 → 균형형. AI에게 목적을 말하면 차이를 설명합니다.",
    },
  ],
};

export const BUILT_MODEL_SELECTION_COMPARE_HELP: AnalysisExplain = {
  spec_id: "built_model_selection_compare_static_v1",
  spec_version: "1",
  title: "모형 비교 (Group Best Subset)",
  summary: "후보 블록 부분집합을 평가해 **AIC·BIC·MAPE** 탭별 상위 후보 — 사용자 채택.",
  formula: "2^k−1 subset OLS · subset당 linear/log/log-log 중 원척도 CV-MAPE 최소 (설명형 AIC는 log 가족만)",
  interpretation: [
    "기준별 1위가 다를 수 있음 — 정답 아님.",
    "카드에서 model_comparison 확인.",
    "이 모형으로 분석 → /regression/run.",
  ],
  limitations: ["≤128 subset", "표본·필터에 민감"],
  interpretation_hints: [],
  presets: [
    {
      id: "aic_bic",
      question: "AIC와 BIC 차이는?",
      answer: "AIC=2k 페널티, BIC=k·ln(n) — BIC가 더 단순한 모형 선호.",
    },
  ],
};

export const BUILT_RECOMMEND_HELP: AnalysisExplain = {
  spec_id: "built_recommend_static_v1",
  spec_version: "12",
  title: "Macro 모형 탐색",
  summary:
    "① CV-MAPE로 대표 예측모형을 고르고 → ② 그 식을 이 지역 거래의 Local 기준선으로 두고 → ③ Twin1은 같은 식에 쌍둥이 1위만 보태며 → ④ Twin2는 그 표본에서 식을 다시 고르고 → ⑤ Local · Twin1 · Twin2 숫자를 나란히 봅니다. 탐색 자체는 기본 통계 식을 바꾸지 않습니다. 「기본 통계에 이 식 적용」을 확인하면 왼쪽 변수·척도만 바뀌고, 오른쪽 숫자는 「통계분석」을 다시 눌러야 갱신됩니다.",
  interpretation: [
    "①은 왜 이 식인가만 답합니다. 순위 표에는 CV-MAPE만 둡니다.",
    "마지막 연도는 후보를 고르는 데 일절 쓰지 않고 떼어 둡니다. ①의 CV-MAPE는 그 앞의 연도들만으로 낸 값이고, 「마지막 연도로 확인」은 고르는 데 쓰지 않은 그 해로만 잰 값입니다. 그래도 ①은 수백 개 후보 중 최소값이라 여전히 낙관적이므로, 두 값이 크게 벌어지면 그 식은 이 지역에서 덜 안정적입니다.",
    "CV-MAPE는 과거 연도로 학습해 다음 연도를 맞혀 본 오차이며, fold 평균이 아니라 거래 가중 평균입니다. 거래가 많은 연도가 지표를 더 끌어당깁니다.",
    "예측을 자르지 않은 값이라, 크게 틀린 예측이 있으면 오차에 그대로 들어갑니다. 예측을 잘라 내면 크게 실패한 식이 덜 실패한 것처럼 보이기 때문입니다. 대신 「범위 밖 예측」 비율을 따로 보여 주는데, 이는 성능이 아니라 그 식의 예측이 얼마나 튀는지를 나타냅니다.",
    "「중위 오차」가 CV-MAPE보다 훨씬 낮으면 평균을 몇몇 거래가 끌고 있다는 뜻입니다. 그때는 대다수 거래에서의 오차는 중위값에 가깝습니다. 다만 식을 고르는 기준은 평균으로 둡니다. 중위로 고르면 대다수 거래는 잘 맞히지만 크게 틀리는 거래가 많은 식이 1위가 될 수 있고, 정작 설명이 필요한 쪽은 그 크게 틀린 거래입니다.",
    "만족도 등급은 두 CV 중 나쁜 쪽으로 냅니다. 마지막 연도가 더 좋게 나와도 등급을 올려 주지 않는데, 그 해 하나만으로 잰 값이라 그 해가 쉬웠을 뿐일 수 있기 때문입니다.",
    "거래시점은 보정하지 않습니다. 조회 기간(기본 5년)의 거래를 함께 넣어 적합하므로, 값 계산 결과는 특정 연도의 시세가 아니라 그 기간의 명목 가격 수준입니다. 최근 시세만 보려면 조회 연도를 좁히세요.",
    "표본 게이트는 적합 표본 10건, 지역 표본 15건, 신뢰 권장 30건입니다. 유효 값이 10건 미만인 변수 블록은 탐색 풀에서 빠지고 ①의 경고에 이유가 적힙니다.",
    "②는 기본 통계 회귀실험과 같은 골격입니다. 식·계수·적합 표본·CV-MAPE를 여기서 읽습니다. Twin 실험1을 눌러도 이 Local 식은 바뀌지 않습니다.",
    "척도는 선형·log(금액)·log-log를 같은 표본에서 비교합니다. log-log는 면적 블록이 있을 때만, 면적만 log입니다.",
    "③ Twin1은 Local 식·척도를 유지한 채 쌍둥이 1위 거래만 보태고, Local에 지역 더미가 있었든 없었든 지역 더미를 넣습니다. 예측오차와 주요 계수 방향을 같이 보고 적용 여부를 판단합니다. Local 식은 ②에 그대로 남습니다.",
    "Twin1 예측은 채택과 별개입니다. CV가 나아지지 않아도 1위 표본 + 지역 더미로 다시 적합한 값·범위를 ③에서 봅니다.",
    "④ Twin 실험2는 Local + Twin 1위 표본에서 예측형(선형·log·log-log, CV-MAPE) 식을 다시 고르는 출시 전 확인용입니다. 설명형 AIC는 쓰지 않으며 기본 통계 식은 바꾸지 않습니다.",
    "판단 순서는 예측력 → 계수 안정 → 표본입니다. n만으로 채택하지 않고, Twin 후보는 거래가격이 아니라 구성·체급으로 고릅니다.",
    "⑤는 Local · Twin1(식 고정) · Twin2(재탐색) 숫자를 나란히 봅니다. Twin2는 확인용이며 Twin이 이겨도 기본 통계 식을 덮지 않습니다.",
    "「기본 통계에 이 식 적용」은 ①의 대표 예측모형 변수·척도를 왼쪽에 옮깁니다. 확인을 거쳐야 하고 통계분석은 자동으로 돌지 않습니다. Twin 식 적용 버튼은 지역 범위를 바꾸므로 아직 연결하지 않았습니다.",
    "값 계산은 ②(Local), ③ Twin1 재적합, ④ Twin 실험2에서 각각 열 수 있습니다. 통계적 추정값이며 개별 적정가·AVM이 아닙니다.",
  ],
  limitations: ["적정가·투자 판단 아님", "통계적 추정이며 현장 판단을 대체하지 않음"],
  interpretation_hints: [],
  presets: [
    {
      id: "ai_diagnosis",
      question: "AI 진단을 요약해 주세요.",
      answer: "",
    },
    {
      id: "why_error_intensity",
      question: "예측 오차는 어떻게 읽나요?",
      answer: "",
    },
  ],
};

export const BUILT_VAR_SELECT_HELP: AnalysisExplain = {
  spec_id: "built_var_select_v1",
  spec_version: "2",
  title: "변수 선택",
  summary:
    "이 칸은 「통계분석」으로 돌리는 이 지역 회귀의 설명변수(X)를 고르는 곳입니다. 체크한 항목만 금액(또는 log 금액)을 설명하는 식에 들어갑니다.",
  formula: "금액(또는 log 금액) ~ 체크한 변수",
  interpretation: [
    "연면적·대지면적·연식은 연속 변수입니다. 면적이 클수록·연식이 낮을수록 금액이 어떻게 다른지를 봅니다.",
    "도로조건·용도지역·건축물용도(단독은 주택유형)·유형 더미는 범주입니다. 기준 범주 대비 금액 수준 차이를 통제합니다.",
    "구조 더미는 건축물대장 보강을 켠 뒤에만 쓸 수 있습니다. 원장 MOLIT만으로는 구조가 없습니다.",
    "지역(읍·면·동 또는 법정리) 더미는 둘 이상 지역을 함께 돌릴 때만 나옵니다. 지역 간 가격 수준 차이를 통제하며, 시군구·구 한곳 회귀에는 넣지 않습니다.",
    "여기는 오른쪽 「회귀 실험」 한 식의 변수입니다. 아래 「통계분석」을 눌러야 결과가 바뀝니다.",
    "오른쪽 「Macro 모형 탐색」은 이 체크와 무관합니다. 서버가 따로 정한 변수 풀에서 후보 식을 찾습니다. 왼쪽이 꺼져 있어도 탐색 결과는 달라질 수 있습니다.",
    "변수를 많이 넣을수록 R²는 잘 오르지만, 겹치는 변수는 VIF가 커지고 계수 해석이 불안정해질 수 있습니다.",
  ],
  limitations: [
    "계수는 이 표본·이 창에서의 통계적 관계이지, 인과나 적정가가 아닙니다.",
    "체크하지 않은 요인은 식에 없습니다. 빠진 변수 영향이 잔차에 남을 수 있습니다.",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "vs_explore",
      question: "왼쪽 체크와 모형 탐색이 다른 이유?",
      answer:
        "왼쪽은 지금 보고 싶은 식입니다. 모형 탐색은 같은 지역 표본에서 서버 변수 풀을 탐색해 비교용 후보를 줍니다. 둘이 다르다고 버그가 아닙니다. 탐색 결과를 쓰려면 「기본 통계에 이 식 적용」을 확인한 뒤 「통계분석」을 다시 누르세요.",
    },
    {
      id: "structure",
      question: "구조 더미가 비활성인 이유?",
      answer:
        "구조는 건축물대장과 연결된 거래에만 있습니다. 「3. 분석 표본」에서 건축물대장 보강을 켜야 구조 더미를 쓸 수 있습니다.",
    },
  ],
};

export const BUILT_RESPONSE_SCALE_HELP: AnalysisExplain = {
  spec_id: "built_response_scale_v1",
  spec_version: "2",
  title: "회귀모형 선택",
  summary:
    "종속변수(거래금액)를 어떤 척도로 맞출지 고르는 곳입니다. 같은 변수라도 척도가 바뀌면 계수 의미와 외삽 행동이 달라집니다.",
  formula:
    "선형: 금액 ~ 변수\nlog(semi-log): log(금액) ~ 변수\nlog-log: log(금액) ~ log(면적) + 그 외 변수",
  interpretation: [
    "선형(기본): 금액을 그대로 맞춥니다. 계수 단위는 만원입니다. 면적 1㎡당 얼마인지처럼 읽기 쉽습니다.",
    "log: 금액에 로그를 취합니다. 계수는 대략 % 변화로 읽습니다. 학습 범위보다 훨씬 큰 값을 넣으면 exp가 급격히 커질 수 있습니다.",
    "log-log: 금액과 면적(연면적 또는 대지면적)에 로그를 취합니다. 면적 탄성에 가깝게 읽고, 광평수 외삽에 상대적으로 유리합니다. 면적 변수가 하나도 없으면 고를 수 없습니다. 면적만 log이고 다른 변수는 그대로입니다.",
    "이 선택은 「통계분석」으로 돌리는 이 지역 식에만 적용됩니다. 라디오만 바꾸고 분석을 다시 누르지 않으면 오른쪽 결과는 이전 척도입니다. Macro 탐색에서 「기본 통계에 이 식 적용」을 눌러도 마찬가지입니다 — 왼쪽 선택만 바뀌고, 결과는 통계분석을 다시 눌러야 갱신됩니다.",
    "세 척도 중 무엇이 ‘정답’인지는 없습니다. 해석 목적(금액 단위 vs % vs 면적 탄성)에 맞게 고릅니다.",
  ],
  limitations: [
    "어느 척도든 통계적 적합이지 개별 물건의 적정가·감정평가가 아닙니다.",
    "학습 표본 밖의 면적·연식에 넣는 예측은 외삽입니다.",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "which",
      question: "어떤 모형을 쓰면 되나요?",
      answer:
        "금액 만원 단위로 읽고 싶으면 선형, 비율(%)로 읽고 싶으면 log, 면적이 크게 달라지는 비교·외삽이면 log-log를 검토합니다. 같은 표본에서 세 척도를 비교하는 창은 Macro 모형 탐색입니다.",
    },
  ],
};

export const BUILT_SAMPLE_HELP: AnalysisExplain = {
  spec_id: "built_sample_v1",
  spec_version: "1",
  title: "분석 표본",
  summary:
    "중위·평균 단가, 회귀, 예측에 어떤 거래를 넣을지 정하는 곳입니다. 거래목록에 무엇이 보이는지와, 식에 무엇이 들어가는지는 다를 수 있습니다.",
  controls: [
    "지분거래 포함(기본 해제): 목록에는 지분 행이 그대로 보입니다. 끄면 면적·단가·회귀·예측 표본에서만 뺍니다. 켜면 연면적(건물 전체)과 대지(지분) 기준이 행마다 다를 수 있어 면적·단가가 달라집니다. 단독은 원천에 지분 칸이 없어 이 체크 대상이 아닙니다.",
    "건축물대장 보강(기본 해제): 켜기 전 안내 창이 열립니다. 국토부 실거래에 없는 상업용 구조·단독다가구 용도지역을 채웁니다. 연결되지 않은 건은 실거래 값을 그대로 둡니다. 구조 더미는 이 옵션을 켠 뒤에만 쓸 수 있습니다.",
    "IQR 금액 이상치 제외: 거래금액의 사분위 범위로 극단값을 뺍니다. 지분 제외 이후에 적용합니다. 배수 k가 클수록 덜 깎습니다(1.5가 가장 엄격).",
  ],
  interpretation: [
    "표본을 바꾸면 「통계분석」을 다시 실행해야 회귀가 갱신됩니다.",
    "지분을 숨기는 기능이 아닙니다. 숨기지 않고, 면적이 필요한 분석의 기본만 일반 거래를 씁니다.",
  ],
  limitations: [
    "IQR은 금액 기준입니다. 면적·단가 이상치와는 다를 수 있습니다.",
    "건축물대장 매칭 정확도 인증은 서울·충북입니다. 다른 시도는 같은 규칙을 쓰되 실측 인증은 아닙니다.",
  ],
  interpretation_hints: [],
  presets: [
    {
      id: "share_why",
      question: "지분을 분석에서 왜 빼 두나요?",
      answer:
        "국토부 지분 행은 연면적이 건물 전체이고 대지는 지분인 경우가 있습니다. 같은 ㎡ 변수로 섞으면 단가·회귀가 시세처럼 보이지 않습니다. 목록은 남기고, 면적이 필요한 분석만 기본에서 뺍니다.",
    },
  ],
};

export const BUILT_UPPER_SCOPE_HELP: AnalysisExplain = {
  spec_id: "built_upper_scope_static_v1",
  spec_version: "1",
  title: "상위 scope 비교",
  summary:
    "분석 초점(예: 읍면동)과 직계 상위(시군구·시도 등)에서 **같은 변수·모형**으로 회귀한 결과를 나란히 봅니다.",
  interpretation: [
    "상위는 표본이 커져 계수가 안정될 수 있으나, 지역 이질성이 섞입니다.",
    "초점과 상위 계수 부호·크기가 다르면 해상도·구성 차이를 의심하세요.",
  ],
  limitations: ["동일 시장이 아님", "인과·적정가 아님"],
  interpretation_hints: [],
  presets: [
    {
      id: "when",
      question: "언제 보나요?",
      answer: "초점 n이 작거나 계수 불안정할 때, 상위 패턴이 같은 방향인지 참고합니다.",
    },
  ],
};
