import screen from "../../../docs/lab/macro_annual_scale_screen.json";

type YearPt = { year: number; v: number };

export const INSIGHT_05_SNAP = {
  asOf: screen.as_of as string,
  yearStart: screen.year_start as number,
  yearEnd: screen.year_end as number,
  years: screen.years as number[],
  types: screen.types as string[],
  reTotal: screen.levels_eok.re_total as YearPt[],
  gdp: screen.levels_eok.gdp as YearPt[],
  m2: screen.levels_eok.m2 as YearPt[],
  stock: screen.levels_eok.stock as YearPt[],
  vsGdp: screen.ratios.vs_gdp as YearPt[],
  vsM2: screen.ratios.vs_m2 as YearPt[],
  vsStock: screen.ratios.vs_stock as YearPt[],
  mixShare: screen.mix.share as Record<string, YearPt[]>,
  mixAmount: screen.mix.amount_eok as Record<string, YearPt[]>,
  typeVsGdp: screen.type_vs_gdp as Record<string, YearPt[]>,
  corr: screen.corr as {
    n_level: number;
    n_yoy: number;
    level: Record<string, number | null>;
    yoy: Record<string, number | null>;
    read: string;
  },
  smoke: screen.smoke as Record<
    string,
    { year: number; vs_gdp_pct: number | null; vs_m2_pct: number | null; vs_stock_pct: number | null; unit_ok: boolean }
  >,
};

export const INSIGHT_05 = {
  listTitle: "부동산 거래액은 경제 규모와 비교하면 얼마나 클까?",
  listSub: "GDP·M2·주식 거래대금과 비교하고, 부동산 시장의 유형별 구성을 살펴봅니다.",
  listMeta: "전국 · 연별",
  lead:
    "한 해 부동산 거래액은 그해 국내총생산이나 시중 돈(M2)보다 작지 않은 규모로 나타난 해도 있었습니다. 다만 이는 부동산이 경제에서 차지하는 비중이 아니라, 기존 자산이 그해 얼마나 거래됐는지를 다른 규모와 나란히 본 숫자입니다. 유형 구성은 해가 바뀌며 달라졌습니다.",
  intro: [
    "금리가 변할 때 거래가 같이 움직였는지는 다른 글에서 월 자료로 살펴본 질문입니다.",
    "이 글은 한 해를 단위로, 거래액이 경제·시중 돈·주식 거래 대비 얼마나 컸는지와 여덟 유형의 구성이 어떻게 바뀌었는지를 봅니다.",
  ],
  s1Title: "① 무엇을 비교하나",
  s1Body: [
    "전국 토지·상가·공장·단독다가구·아파트·오피스텔·연립다세대·분양권의 거래액을 더한 값을 분자로 씁니다. 모든 부동산이 아닙니다.",
    "분모는 세 가지입니다. 그해 명목 국내총생산, 시중 돈(M2) 잔액, 코스피와 코스닥의 주식 거래대금입니다.",
    "먼저 각 총액을 같은 조 원 눈금으로 보고, 한 그림에 겹쳐 크기를 가늠한 뒤, 거래액을 각 분모로 나눈 비율을 봅니다. 이중축은 쓰지 않습니다.",
  ],
  sLevelsTitle: "② 한 해의 총액",
  sLevelsLead: [
    "세로축은 네 그림이 같은 조 원입니다. 선의 높이를 관계의 증거로 읽지 않습니다.",
    "각 지표는 측정 대상과 의미가 서로 다르므로 절대액의 크기 자체를 서로 비교하기보다는, 아래의 비율과 변화 흐름을 중심으로 봅니다.",
  ],
  sLevelRe: "부동산 거래액 (8유형 합)",
  sLevelGdp: "명목 GDP",
  sLevelM2: "시중 돈(M2) 잔액",
  sLevelStock: "주식 거래대금",
  sLevelsTogether: "네 총액 (같은 조 원)",
  s2Title: "③ 경제·시중 돈·주식 대비",
  s2Lead: "세로축은 거래액이 각 분모에서 차지하는 비율입니다.",
  s2Body: [
    "거래액 / GDP는 부동산 거래액이 그해 GDP에 비해 어느 정도 규모였는지를 보여주는 지표입니다. 부동산이 GDP에서 차지하는 비중이나 부동산이 만들어낸 부가가치를 의미하지 않습니다.",
    "거래액 / M2는 시중 돈이 부동산으로 이동했다는 뜻이 아닙니다. M2는 잔액이고 거래액은 그해 발생한 거래액이므로, 두 시장 규모를 비교한 지표입니다.",
  ],
  s2Gdp: "거래액 / 명목 GDP",
  s2M2: "거래액 / 시중 돈(M2) 잔액",
  s2Stock: "거래액 / 주식 거래대금",
  s2Together: "세 비율을 한 그림에",
  s3Title: "④ 부동산 시장의 유형 구성은 어떻게 달라졌나",
  s3AmountLead: "세로축은 조 원입니다. 그해 각 유형이 거래된 금액입니다. 구성비가 아닙니다.",
  s3AmountStack: "유형별 거래액",
  s3AmountLines: "여덟 유형 거래액 (같은 조 원)",
  s3Lead: "그해 여덟 유형을 더한 거래액에서 각 유형이 차지하는 몫입니다. 지역을 나눈 구성비가 아닙니다.",
  s3ShareLabel: "유형 구성비",
  sCorrTitle: "⑤ 같은 해에 같이 움직였나",
  sCorrLead:
    "표 안의 숫자는 피어슨 상관계수입니다. 인과가 아닙니다. 수준 자료의 상관계수는 장기적인 추세의 영향을 받을 수 있습니다. 전년 대비가 같은 해 동조에 더 가깝습니다.",
  sCorrLevel: "총액(수준)",
  sCorrYoy: "전년 대비",
  sCorrCaption:
    "거래액과 GDP·M2는 수준 자료에서는 일정한 양의 상관관계가 나타나지만, 전년 대비로 보면 관계가 거의 없습니다. 주식 거래대금의 전년 대비 변화와는 상대적으로 높은 양의 상관관계가 나타났지만, 관측연도가 15개에 불과하므로 이를 안정적인 관계로 해석하지 않습니다.",
  s4Title: "⑥ 유형별로 GDP와 나누면",
  s4Lead: "본문 비율의 확인용입니다. 유형 하나의 GDP 기여도가 아닙니다.",
  s4Toggle: "유형별 거래액/GDP 보기",
  s4Hide: "유형별 거래액/GDP 접기",
  patternsTitle: "지금까지 보이는 그림",
  patterns: [
    "부동산 거래액과 명목 GDP, 시중 돈, 주식 거래대금은 각각 해가 바뀌며 커지거나 줄었습니다. 총액 선의 높이를 서로 비교하지 않습니다.",
    "거래액이 GDP나 시중 돈 대비 차지하는 비율은 해가 바뀌며 움직였습니다. 한 해의 숫자를 전국 공통 비중으로 읽지 않습니다.",
    "여덟 유형의 거래액 규모와 구성비는 해가 바뀌며 달라졌습니다.",
    "거래액 총액은 GDP·M2와의 수준 자료에서는 어느 정도 함께 움직이는 모습이 보이지만, 전년 대비 변화로 보면 그 관계는 거의 사라집니다.",
  ],
  limitsTitle: "이 분석의 한계",
  limits: [
    "거래액 나누기 GDP는 부동산이 경제에서 차지하는 비중이 아닙니다. 기존 자산의 거래액을 그해 생산된 GDP와 비교한 규모 지표입니다.",
    "거래액 나누기 M2는 시중 돈이 부동산으로 이동했다는 뜻이 아닙니다. M2는 잔액이고 거래액은 그해 발생한 거래액이므로, 두 시장 규모를 비교한 지표입니다.",
    "주식 거래대금과 비교한 것은 대체 투자나 자금 이동의 증거가 아닙니다.",
    "합계는 여덟 유형을 더한 값이며 규모가 큰 유형에 기울 수 있습니다.",
    "총액 그래프는 각 숫자의 흐름을 보기 위한 것입니다. 선의 높이를 관계의 증거로 읽지 않습니다.",
    "완결된 연만 봤습니다. 월별 변화와 금리·유동성과의 동조는 이 글이 말하지 않습니다.",
    "연 상관계수는 관측이 열댓 개입니다. 월 시차 r(1번 글)과 같은 질문이 아닙니다.",
    "인과관계나 전망을 검증한 분석이 아닙니다.",
  ],
  close:
    "부동산 거래액은 경제·금융 규모와 비교할 수 있는 상당한 규모의 시장이지만, 그 상대적 규모와 유형 구성은 시기에 따라 크게 달라졌습니다. 단순한 수준의 동행이 곧 연간 변화의 동행을 의미하지는 않습니다.",
  nextTitle: "다음 실험",
  next: [
    "시중 유동성의 구성 변화와 부동산 시장의 유형 구성은 함께 움직였을까?",
    "시중 돈(M2)의 현금통화·요구불예금·저축성예금·금융상품 등과, 부동산의 토지·아파트·단독다가구·상가·공장·오피스텔 등이 같이 바뀌는지는 이 글이 말하지 않습니다.",
  ],
  relatedTitle: "관련 실험",
  related: [
    "금리와 유동성이 변할 때 거래가 같이 움직였는지는 월 자료로 본 다른 질문입니다. 이 글의 비율 그래프와 섞어 읽지 않습니다.",
  ],
  relatedHref: "/insight/?q=1",
  relatedLink: "1번: 금리와 유동성은 부동산 거래와 어떤 관계가 있을까?",
};
