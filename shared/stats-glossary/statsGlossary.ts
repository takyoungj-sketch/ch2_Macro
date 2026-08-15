export type StatsGlossaryEntry = {
  id: string;
  label: string;
  title: string;
  definition: string;
  formula?: string;
  interpretation: string[];
  thresholds?: string[];
  limitations: string[];
};

export const STATS_GLOSSARY: Record<string, StatsGlossaryEntry> = {
  r_squared: {
    id: "r_squared",
    label: "R²",
    title: "결정계수 (R²)",
    definition:
      "회귀모형이 종속변수(거래금액 등) 분산 중 얼마나 설명하는지를 0~1 사이로 나타낸 지표입니다.",
    formula: "R² = 1 − (잔차 제곱합 / 총 제곱합)",
    interpretation: [
      "값이 클수록 선택한 설명변수가 가격 변동을 많이 설명한다는 뜻입니다.",
      "표본·변수 구성·지역에 따라 달라지므로 절대값만으로 좋다/나쁘다를 단정하지 않습니다.",
    ],
    limitations: [
      "변수를 많이 넣으면 R²는 거의 항상 올라갑니다.",
      "인과관계나 예측 정확도를 단독으로 보장하지 않습니다.",
    ],
  },
  adj_r_squared: {
    id: "adj_r_squared",
    label: "Adj R²",
    title: "수정 결정계수 (Adj R²)",
    definition:
      "변수 개수와 표본 크기를 반영해 R²를 조정한 값입니다. 불필요한 변수 추가를 어느 정도 벌점으로 봅니다.",
    formula: "Adj R² = 1 − [(1−R²)(n−1) / (n−k−1)]",
    interpretation: [
      "같은 표본에서 변수를 늘릴 때 R²보다 Adj R²가 더 보수적으로 움직입니다.",
      "CH2에서는 scope·자산유형별로 설명력의 참고 지표로 씁니다.",
    ],
    thresholds: ["0.7 이상: 비교적 높은 설명력(참고)", "0.4~0.7: 중간", "0.4 미만: 제한적 설명력 — 표본·변수·잔차를 함께 봅니다"],
    limitations: [
      "높다고 해서 개별 거래 예측이 정확하다는 뜻은 아닙니다.",
      "표본 n이 작으면 Adj R²도 불안정할 수 있습니다.",
    ],
  },
  mape: {
    id: "mape",
    label: "MAPE",
    title: "MAPE (Mean Absolute Percentage Error)",
    definition: "적합(in-sample) 데이터에서 예측값과 실제값의 상대 오차 평균(%)입니다.",
    interpretation: [
      "값이 작을수록 같은 표본 안에서 예측이 실제에 가깝다는 뜻입니다.",
      "CH2 복합 회귀 카드 MAPE 옆 뱃지(매우 우수·우수·보통·주의·예측 부적합)는 CV-MAPE 등급표를 참고한 **예측 적합 라벨**입니다.",
    ],
    thresholds: [
      "<15%: 매우 우수",
      "<25%: 우수",
      "<40%: 보통",
      "<60%: 주의 — 예측 오차가 커 개별 금액 예측에 부적합에 가까움",
      "≥60%: 예측 부적합",
    ],
    limitations: [
      "표본 밖(신규 거래) 일반화 성능과 다를 수 있습니다.",
      "in-sample MAPE와 CV-MAPE는 다릅니다 — 모형 추천 화면은 CV-MAPE를 우선합니다.",
    ],
  },
  cv_mape: {
    id: "cv_mape",
    label: "CV-MAPE",
    title: "CV-MAPE (교차검증 MAPE)",
    definition: "표본을 나눠 반복 검증한 뒤 평균낸 MAPE(%)입니다. in-sample MAPE보다 일반화 성능에 가깝습니다.",
    interpretation: [
      "모형 추천·비교 화면에서 후보 모형 간 상대 비교에 유용합니다.",
      "값이 낮을수록 검증 fold에서 오차가 작았다는 뜻입니다.",
    ],
    limitations: ["표본이 적으면 fold마다 변동이 커질 수 있습니다."],
  },
  vif: {
    id: "vif",
    label: "VIF",
    title: "VIF (분산팽창계수)",
    definition:
      "한 독립변수를 나머지 변수들로 회귀했을 때의 R²로 다중공선성(변수 간 중복 정보)을 봅니다.",
    formula: "VIF_j = 1 / (1 − R²_j)",
    interpretation: [
      "VIF가 높을수록 해당 변수가 다른 변수와 정보를 많이 겹칩니다.",
      "개별 계수(예: 연식)의 부호·크기·유의성이 불안정해질 수 있습니다.",
    ],
    thresholds: ["≥10: 주의", "5~10: 참고", "<5: 보통 양호(맥락에 따라 다름)"],
    limitations: [
      "VIF는 연속변수 위주로 보고, 범주형 더미는 별도 해석이 필요합니다.",
      "VIF가 낮아도 표본·누락변수 문제는 남을 수 있습니다.",
    ],
  },
  p_value: {
    id: "p_value",
    label: "p",
    title: "p-value (유의확률)",
    definition:
      "귀무가설(계수=0)이 참일 때, 현재 데이터만큼 극단적인 계수가 나올 확률입니다.",
    interpretation: [
      "보통 0.05 미만이면 '통계적으로 유의'하다고 표현합니다.",
      "유의하다는 것은 '영향이 있다'는 뜻이지, 경제적으로 크다는 뜻은 아닙니다.",
    ],
    thresholds: ["<0.05: 유의(일반적 기준)", "≥0.05: 유의하지 않음 — 방향만 참고"],
    limitations: [
      "표본이 크면 작은 효과도 유의해질 수 있습니다.",
      "다중검정·모형 설정에 따라 해석이 달라집니다.",
    ],
  },
  coefficient: {
    id: "coefficient",
    label: "계수",
    title: "회귀 계수",
    definition:
      "다른 변수를 고정했을 때 해당 변수가 1단위 변할 때 종속변수(금액·로그금액 등)가 얼마나 변하는지 나타냅니다.",
    interpretation: [
      "부호(+/−)는 방향, 크기는 스케일(선형·로그)에 따라 달리 읽습니다.",
      "CH2 회귀식 옆 '계수 상세'에서 SE·t·p와 함께 봅니다.",
    ],
    limitations: [
      "계수는 조건부 연관(통제 후)이며 인과를 단정하지 않습니다.",
      "범주형 변수는 기준 범주 대비 효과입니다.",
    ],
  },
  fit_n: {
    id: "fit_n",
    label: "적합 n",
    title: "적합 표본수 (fit_n / n)",
    definition: "선택 변수에 결측이 없는 complete-case 거래 건수입니다. 회귀 적합에 실제 사용된 n입니다.",
    interpretation: [
      "n이 클수록 추정이 안정적일 가능성이 높습니다.",
      "scope·필터·자산유형에 따라 n이 크게 달라집니다.",
    ],
    thresholds: ["n<30: 해석 매우 제한", "30~100: 주의", "100+: 비교적 안정(맥락 의존)"],
    limitations: ["전체 거래수와 다를 수 있습니다 — 결측·필터 반영 후 n입니다."],
  },
  f_p_value: {
    id: "f_p_value",
    label: "F p",
    title: "F-검정 p-value",
    definition: "회귀모형 전체(모든 설명변수)가 종속변수를 설명하는지 검정한 p-value입니다.",
    interpretation: [
      "값이 작을수록 '모형 전체가 우연이 아니다'는 신호입니다.",
      "개별 변수 유의성과는 별개로 봅니다.",
    ],
    limitations: ["표본이 크면 거의 항상 유의해질 수 있습니다."],
  },
  se: {
    id: "se",
    label: "SE",
    title: "표준오차 (Standard Error)",
    definition: "계수 추정값의 불확실성(표본 변동)을 나타내는 지표입니다.",
    interpretation: ["SE가 크면 같은 표본을 다시 뽑으면 계수 추정이 크게 달라질 수 있습니다."],
    limitations: ["모형 가정·이상치·공선성에 민감합니다."],
  },
  pearson_r: {
    id: "pearson_r",
    label: "r",
    title: "피어슨 상관계수 (r)",
    definition: "두 연속변수 사이의 선형 관련성 강도(−1~+1)입니다. 다른 변수를 통제하지 않습니다.",
    interpretation: [
      "|r|이 클수록 직선에 가까운 동반 움직임입니다.",
      "회귀 계수(β)와 부호·크기가 다를 수 있습니다 — 통제 전/후 차이를 함께 봅니다.",
    ],
    limitations: ["인과가 아닙니다.", "비선형·이상치에 왜곡될 수 있습니다."],
  },
  ols: {
    id: "ols",
    label: "OLS",
    title: "OLS (최소제곱 회귀)",
    definition: "잔차 제곱합을 최소화하는 선형 회귀 추정 방법입니다. CH2 기본 회귀입니다.",
    interpretation: ["화면에 표시된 계수·R²·MAPE는 이 적합 결과입니다."],
    limitations: ["선형·잔차 가정에 민감", "인과·적정가를 의미하지 않음"],
  },
  aic: {
    id: "aic",
    label: "AIC",
    title: "AIC (Akaike Information Criterion)",
    definition: "모형 적합도와 변수 수 벌점을 합친 정보량 기준입니다. 값이 작을수록 선호됩니다.",
    interpretation: ["설명형·모형 비교에서 상대 순위에 사용합니다."],
    limitations: ["절대값보다 후보 간 차이가 중요합니다."],
  },
  bic: {
    id: "bic",
    label: "BIC",
    title: "BIC (Bayesian Information Criterion)",
    definition: "AIC와 비슷하나 표본 크기에 따라 변수 수 벌점이 더 큽니다. 값이 작을수록 선호됩니다.",
    interpretation: ["AIC보다 단순한 모형을 더 선호하는 경향이 있습니다."],
    limitations: ["표본이 작으면 불안정할 수 있습니다."],
  },
  prediction_interval: {
    id: "prediction_interval",
    label: "PI",
    title: "예측구간 (Prediction Interval)",
    definition: "개별 거래 1건의 예측값이 들어갈 것으로 기대되는 구간입니다. 잔차 변동을 포함합니다.",
    interpretation: ["CI보다 넓습니다. n이 작거나 잔차 분산이 크면 더 넓어집니다."],
    limitations: ["적정가 구간이 아닙니다.", "학습 범위 밖 입력은 외삽입니다."],
  },
  confidence_interval: {
    id: "confidence_interval",
    label: "CI",
    title: "신뢰구간 (Confidence Interval)",
    definition: "평균 예측값(조건부 기대)의 불확실성 구간입니다. 개별 거래 변동은 포함하지 않습니다.",
    interpretation: ["PI와 구분하세요 — CI는 평균 추정의 정밀도입니다."],
    limitations: ["개별 물건 가격 범위로 해석하지 마세요."],
  },
  log_model: {
    id: "log_model",
    label: "로그",
    title: "로그·반로그 모형",
    definition:
      "종속변수에 로그를 취한 회귀(semi-log)입니다. 계수 1단위 변화가 대략 % 변화로 읽히는 경우가 많습니다.",
    interpretation: [
      "양의 왜도가 큰 금액 분포에서 잔차를 안정화하는 선택지입니다.",
      "log-log는 독립변수에도 로그를 취한 형태입니다.",
    ],
    limitations: ["선형(총액) 모형과 계수 스케일이 다릅니다 — 직접 비교에 주의."],
  },
  rent_conversion_rate: {
    id: "rent_conversion_rate",
    label: "적용 전환율",
    title: "적용 전환율 (CH2 분석용)",
    definition:
      "한국부동산원이 공표하는 공식 전월세전환율이 아닙니다. 같은 건물에 전세와 반전세 거래가 함께 있을 때 건물별 전환율(r_b)을 구한 뒤, 지역·주택유형·선택한 연수(3·5·7년) 거래로 단순평균한 CH2 분석용 값입니다.",
    formula: "r_b = 12M / (J − D)  →  r = 평균(r_b)",
    interpretation: [
      "반전세를 전세·월세 축으로 맞춰 비교하기 위한 상수입니다. 그 지역 공식 시장 금리가 아닙니다.",
      "2026-08 서울 실험(동일기간 + 마지막 1년 hold-out, 시군구·동 × 3·5·7년)에서 단순평균이 네 방법 중 hold-out MAPE 전부 1위여서 채택했습니다.",
      "원점회귀·가중평균은 실험 화면에만 남겨 두었습니다. 목록에는 쓰지 않습니다.",
      "읍면동 표본이 부족하면 같은 창의 시군구 전환율을 씁니다.",
    ],
    thresholds: [
      "식별: 창 안 같은 건물에 전세·반전세가 모두 있을 때만",
      "시군구 게이트: 식별 건물 5+ · 전세/반전세 각 30건+",
      "읍면동 게이트: 식별 건물 3+ · 각 15건+",
    ],
    limitations: [
      "환산 P50은 비교값이지 그 건물의 시세·적정 전세가 아닙니다.",
      "연립은 건물별 r_b 편차가 큰 것이 자연스럽습니다. 유형별 산식을 나누지 않습니다.",
      "REB 5% 고정값이 아닙니다. 실험 기록: docs/RENT_CONVERSION_EXPERIMENT.md",
    ],
  },
  jeonse_equiv: {
    id: "jeonse_equiv",
    label: "전세전환값",
    title: "전세전환값 (만원/㎡)",
    definition:
      "전세는 보증금/㎡ 그대로, 반전세는 적용 전환율로 전세 상당액을 만든 뒤 건물 P50입니다. 월세(보증금 0)는 같은 r로 환산합니다.",
    formula: "전세환산/㎡ = D + 12M / (r/100)",
    interpretation: [
      "목록에서 전세·반전세·월세를 한 축으로 보기 위한 값입니다.",
      "원 보증금·월세는 건물 상세에 그대로 둡니다.",
    ],
    limitations: [
      "적용 전환율이 없는 칸(게이트 미달)은 비어 있을 수 있습니다.",
      "감정·시세가 아닙니다.",
    ],
  },
  monthly_equiv: {
    id: "monthly_equiv",
    label: "월세전환값",
    title: "월세전환값 (만원/㎡)",
    definition:
      "전세·반전세를 적용 전환율로 월세 상당액으로 맞춘 뒤 건물 P50입니다. 순수월세는 월세/㎡를 씁니다.",
    formula: "월세환산/㎡ = M + D × (r/100) / 12",
    interpretation: ["전세전환값과 같은 r, 같은 창을 씁니다."],
    limitations: ["비교용입니다. 실제 월세 시세가 아닙니다."],
  },
  sangkwon_survey: {
    id: "sangkwon_survey",
    label: "상권 공표",
    title: "상업용부동산 임대동향조사 (상권)",
    definition:
      "한국부동산원이 전국 오피스·상가의 임대·공실·투자성과를 분기 표본조사한 국가통계(제408001호)입니다. 공표 단위는 행정동이 아니라 상권(하위시장)입니다. CH2는 이 숫자를 다시 계산하지 않고 공표를 연간 단위로 묶어 보여 줍니다.",
    interpretation: [
      "주거 전월세(국토부 원장·CH2 전환율·3/5/7년)와 출처·단위·기간이 다릅니다. 한 표에 섞지 않습니다.",
      "오피스·중대형·소규모는 동 표본, 집합 상가는 호 표본입니다. 빈 칸은 오류가 아니라 그 유형 층이 없는 것입니다.",
      "화면 범위는 선택한 시군구(구) 경계와 기하 교차하는 상권입니다.",
    ],
    limitations: [
      "전수조사가 아닙니다. 목표 RSE는 오피스 상권 7% 이하, 상가 7~15%입니다.",
      "2024.3분기 상권구획 변경으로 일부 시계열이 단절됩니다.",
      "개별 건물 원장·시세·적정가가 아닙니다. 설명자료: docs/REB_COMMERCIAL_RENT_SURVEY.md",
    ],
  },
  sangkwon_building_count: {
    id: "sangkwon_building_count",
    label: "동수·호수",
    title: "동수·호수 (표본 재고)",
    definition:
      "그 상권·유형의 조사 표본 규모입니다. 오피스·중대형·소규모 상가는 동, 집합 상가는 호입니다.",
    interpretation: [
      "연간 화면은 그 해 마지막 유효 분기 값(재고 스냅샷)을 씁니다.",
      "모집단 전체가 아니라 표본 수입니다.",
    ],
    limitations: ["집합 상가를 동 단위 건물 목록처럼 읽으면 안 됩니다."],
  },
  sangkwon_avg_floors: {
    id: "sangkwon_avg_floors",
    label: "평균층수",
    title: "평균층수",
    definition: "해당 상권·유형 표본 건물의 평균 층수입니다.",
    interpretation: ["연간은 그 해 마지막 유효 분기 값입니다."],
    limitations: ["재고 스냅샷이며 거래 건수 가중과 다릅니다."],
  },
  sangkwon_avg_area: {
    id: "sangkwon_avg_area",
    label: "평균면적",
    title: "평균면적 (㎡)",
    definition:
      "표본의 평균 연면적(오피스) 또는 평균 임대면적(상가)입니다. 공표 항목명을 그대로 따릅니다.",
    interpretation: ["연간은 그 해 마지막 유효 분기 값입니다."],
    limitations: ["유형마다 면적 정의가 다를 수 있습니다."],
  },
  sangkwon_rent: {
    id: "sangkwon_rent",
    label: "임대료",
    title: "임대료 (만원/㎡·년)",
    definition:
      "임차인이 공간을 쓰기 위해 내는 총비용을 시장임대료로 본 환산월세 단가입니다. 공표는 분기 월 단가(천원/㎡)입니다. 관리비·부가세는 제외합니다.",
    formula: "환산임대료 = (보증금 × 전환율 / 12) + 월세  →  단가 = 환산임대료 / 임대면적(전용+공용)",
    interpretation: [
      "오피스는 3층~최상층 평균, 상가는 1층(없으면 2층)입니다.",
      "CH2 연간: 4분기 월단가 평균 × 12, 천원→만원. 4분기가 없으면 빈칸입니다.",
      "임대수입(NOI 구성)과 다른 수치입니다. 임대료에 순영업소득%를 곱해 NOI를 만들지 마세요.",
    ],
    limitations: [
      "월 단가 네 개를 더하면 4개월분이지 연간이 아닙니다.",
      "이 전환율은 상업용 공표용이며 주거 mean_simple과 다릅니다.",
    ],
  },
  sangkwon_rent_index: {
    id: "sangkwon_rent_index",
    label: "임대가격지수",
    title: "임대가격지수 (2024.2Q=100)",
    definition:
      "기준층 시장임대료의 시점 간 변화(Dutot)입니다. 기준시점은 2024년 2분기=100입니다.",
    interpretation: [
      "오피스 기준층은 (최고층+3)/2 (소수면 올림), 매장용은 1층(없으면 2층)입니다.",
      "CH2 연간은 4분기 지수의 산술평균입니다. 복리가 아닙니다.",
    ],
    limitations: ["수준 지수입니다. 연간 임대료(만원/㎡)와 단위가 다릅니다."],
  },
  sangkwon_noi_per_m2: {
    id: "sangkwon_noi_per_m2",
    label: "순영업소득",
    title: "순영업소득 (만원/㎡·년)",
    definition:
      "유효조소득에서 운영경비를 뺀 순액(NOI)의 면적당 금액입니다. 공표는 그 분기 동안 난 유량(천원/㎡)입니다.",
    formula: "NOI = (임대수입 + 기타수입 − 대손충당금 1%) − 운영경비",
    interpretation: [
      "CH2 연간: 4분기 합 후 천원→만원. 3분기에 경비가 뛰면 연간 합에 그대로 남습니다.",
      "환원법에 쓸 금액은 이 칸입니다. 공실률을 다시 곱하지 않습니다.",
    ],
    limitations: [
      "임대료(시장 환산월세) × 순영업소득% 와 숫자가 맞지 않는 것이 정상입니다. 분모가 다릅니다.",
      "개별 물건 NOI가 아닙니다.",
    ],
  },
  sangkwon_rent_income: {
    id: "sangkwon_rent_income",
    label: "임대수입(%)",
    title: "임대수입 구성비 (%)",
    definition:
      "NOI 손익에서 받은 임대수입이 차지하는 비중입니다. 월세 합, 보증금 운용이익, 실비·관리비(임차인 직접 실비 제외)입니다.",
    interpretation: [
      "구성비 분모입니다. 기타수입이 0이면 보통 100입니다.",
      "항등식: 임대수입% + 기타수입% − 운영경비% ≒ 순영업소득%.",
      "공실로 못 받은 월세는 이미 임대수입 금액에서 빠져 있습니다. 이 %에 (1−공실)을 곱하지 마세요.",
    ],
    limitations: [
      "시장 임대료(천원·만원/㎡)가 아닙니다.",
      "CH2 연간은 4분기 평균입니다.",
    ],
  },
  sangkwon_other_income: {
    id: "sangkwon_other_income",
    label: "기타수입(%)",
    title: "기타수입 구성비 (%)",
    definition: "주차, 회의실, 자판기, 광고탑·안테나, 창고 등 임대 외 수입의 구성비입니다.",
    interpretation: [
      "임대수입과 더해 유효수입 쪽 분모를 이룹니다.",
      "CH2 연간은 4분기 평균입니다.",
    ],
    limitations: ["0이어도 오류가 아닙니다. 그 상권 표본에 기타수입이 거의 없는 경우입니다."],
  },
  sangkwon_opex: {
    id: "sangkwon_opex",
    label: "운영경비(%)",
    title: "운영경비 구성비 (%)",
    definition:
      "청소, 설비, 수도광열, 주차관리, 세금과공과, 경비, 조경, 임대 관련, 일반관리 등 운영경비의 구성비입니다.",
    interpretation: [
      "한 분기에 경비가 크게 오르면 그 분기 순영업소득%·금액이 함께 떨어집니다.",
      "CH2 연간은 4분기 평균입니다.",
    ],
    limitations: ["연간 합이 아닙니다. 비율을 더하면 안 됩니다."],
  },
  sangkwon_noi_pct: {
    id: "sangkwon_noi_pct",
    label: "순영업소득(%)",
    title: "순영업소득 구성비 (%)",
    definition:
      "유효조소득 대비 NOI 비율입니다. 표에서는 임대수입%(+기타수입%)에서 운영경비를 뺀 구성비로 읽습니다.",
    formula: "임대수입% + 기타수입% − 운영경비% ≒ 순영업소득%",
    interpretation: [
      "CH2 연간은 4분기 평균입니다. 광화문 소규모 2025처럼 3분기 경비 급등이 평균을 깎습니다.",
      "이 %를 연간 임대료에 곱아 연간 NOI 금액을 만들지 마세요.",
    ],
    limitations: ["구성비이지 수익률(소득수익률)이 아닙니다."],
  },
  sangkwon_vacancy: {
    id: "sangkwon_vacancy",
    label: "공실률",
    title: "공실률 (%)",
    definition:
      "임대·자가사용·무상사용이 아닌 빈 면적을 임대가능(표본 건축) 면적으로 나눈 값입니다.",
    formula: "공실률 = Σ 공실면적 / Σ 임대가능면적",
    interpretation: [
      "면적 통계입니다. 손익 구성(임대·기타·경비·NOI%)과 별개입니다.",
      "받은 임대수입 금액에는 공실이 이미 반영되어 있습니다. (1−공실)을 NOI에 다시 곱하지 마세요.",
      "CH2 연간은 4분기 평균입니다.",
    ],
    limitations: [
      "수익환원법의 경제적 공실과 정의가 다를 수 있습니다.",
      "환원법에 쓸 값은 공표 순영업소득(만원/㎡·년)과 소득수익률입니다.",
    ],
  },
  sangkwon_income_yield: {
    id: "sangkwon_income_yield",
    label: "소득수익률",
    title: "소득수익률 (%)",
    definition: "그 분기 영업으로 얻은 순소득을 기초 자산가치로 나눈 값입니다.",
    formula: "I = NOI / V0   (상권은 건물 연면적 가중 평균)",
    interpretation: [
      "공표는 분기 수익률입니다. CH2 연간은 부동산원과 같이 4분기 복리 연결입니다: [∏(1+r_q/100)−1]×100.",
      "4분기가 없으면 빈칸입니다.",
    ],
    limitations: [
      "분기에는 I+C=T 이나, 연간 복리 소득+자본이 연간 투자와 같지 않습니다.",
      "자산가치 V0는 공표되지 않아 ‘연간 NOI÷연초가치’로 검증할 수 없습니다.",
      "환원율로 가치를 단정하지 마세요. 감정·투자 판단이 아닙니다.",
    ],
  },
  sangkwon_capital_yield: {
    id: "sangkwon_capital_yield",
    label: "자본수익률",
    title: "자본수익률 (%)",
    definition: "토지·건물 가치 변동을 기초 자산가치로 나눈 값입니다.",
    formula: "C = (V1 − V0) / V0   (상권은 연면적 가중)",
    interpretation: ["CH2 연간은 4분기 복리 연결입니다. 산술평균이 아닙니다."],
    limitations: ["연간 복리값은 소득수익률과 더해서 투자수익률이 되지 않습니다."],
  },
  sangkwon_investment_yield: {
    id: "sangkwon_investment_yield",
    label: "투자수익률",
    title: "투자수익률 (%)",
    definition: "소득수익률과 자본수익률의 합(당해 분기)입니다. 부동산원 연간 공표는 최근 4분기를 복리로 잇습니다.",
    formula: "분기 T = I + C    연간 = [∏(1+T_q/100) − 1] × 100",
    interpretation: [
      "CH2 연간 투자수익률은 이 복리식입니다. 예전 화면의 분기 산술평균과 다릅니다.",
      "상권 집계는 연면적 가중입니다.",
    ],
    limitations: [
      "연간 소득 복리 + 연간 자본 복리 ≠ 연간 투자 복리인 것이 정상입니다.",
      "투자 권유·적정 수익률이 아닙니다.",
    ],
  },
  sangkwon_conversion: {
    id: "sangkwon_conversion",
    label: "전환율",
    title: "상업용 공표 전환율 (%)",
    definition:
      "부동산원이 상업용 환산임대료를 만들 때 쓰는 전환율입니다. 보증금을 월세로 나눌 때 사용합니다.",
    formula: "환산임대료 = (보증금 × 전환율 / 12) + 월세",
    interpretation: [
      "그 분기 시장 전환율(수준)입니다. CH2 연간은 4분기 평균입니다. 복리·12배가 아닙니다.",
      "주거 목록의 적용 전환율(mean_simple)과 식·표본·목적이 다릅니다.",
    ],
    limitations: ["주거 전세·반전세 환산에 쓰지 마세요."],
  },
  twin_region: {
    id: "twin_region",
    label: "Twin",
    title: "Twin (유사 지역)",
    definition: "지역 프로필이 비슷한 다른 행정구역을 후보로 쓰는 보조 기능입니다. 기본 추천이 아닙니다.",
    interpretation: ["표본이 부족할 때 참고 pool로 쓸 수 있습니다."],
    limitations: ["유사 ≠ 동일 시장. 조건부·실험적 성격이 있습니다."],
  },
};

export function getGlossaryEntry(id: string): StatsGlossaryEntry | undefined {
  return STATS_GLOSSARY[id];
}
