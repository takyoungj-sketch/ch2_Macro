import pubJson from "../../../docs/lab/land_road_jimok_ratio_public.json";

type RatioRow = {
  id: string;
  label: string;
  detail?: string;
  n: number;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  n_below_third: number | null;
};

type ThinRow = {
  id: string;
  label: string;
  n: number;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  n_below_third: number | null;
};

type AdjustedRow = {
  id: string;
  label: string;
  n: number | null;
  median: number | null;
  factor: number | null;
  n_reg_cells: number | null;
};

const pub = pubJson as {
  period_start: string;
  period_end: string;
  as_of_month: string;
  min_n: number;
  third_tick: number;
  main: RatioRow[];
  thin: ThinRow[];
  adjusted: AdjustedRow[];
  held_back: string[];
};

export const INSIGHT_06_SNAP = pub;

export const INSIGHT_06 = {
  listTitle: "도로로 등록된 땅은, 같은 동네 다른 땅의 몇 %에 거래됐나?",
  listSub: "같은 읍·면·동, 같은 용도지역에서 도로 땅과 다른 땅의 ㎡당 가격을 비교했습니다.",
  seeTitle: "이 글에서 보는 것",
  see: [
    "같은 읍·면·동, 같은 용도지역 안에서만 나눕니다. 서울의 도로와 군의 밭을 직접 비교하지 않습니다.",
    "가격은 필지 총액이 아니라 ㎡당 가격입니다. 가운데 값(중위)을 씁니다. 아주 비싼 한 건이 줄을 끌어올리지 않게 하기 위해서입니다.",
    "도시 전체를 하나의 퍼센트로 적지 않습니다. 주거지역과 녹지지역을 나눕니다.",
  ],
  s1Title: "① 무엇을 나눴나",
  s1Step1: "도로와 비교할 땅을 먼저 정했습니다.",
  s1Third:
    "감정평가에서는 도로 땅을 근처 땅의 3분의 1로 보는 말이 있습니다. 이 글의 3분의 1은 그 말을 놓아 둔 눈금입니다. 맞았는지 틀렸는지를 재는 합격선이 아닙니다.",
  s1JimokRest:
    "입니다. 대장에 도로로 적힌 땅이고, 땅이 길에 얼마나 접해 있는지나 평가에서 말하는 사도·공도와는 다른 말입니다.",
  s2Title: "② 주거지역 대지와 나누면",
  s2Lead: "일반주거·준주거에서, 도로 땅과 대지를 비교한 동네들입니다.",
  s3Title: "③ 녹지와 계획관리 대지와 나누면",
  s3Lead: "녹지지역과 도시 밖 계획관리지역의 대지와 나누면, 가운데 값이 주거지역보다 낮고 둘은 서로 비슷합니다.",
  s4Title: "④ 밭·논과 나누면",
  s4Lead:
    "밭과 논은 대지보다 토지 가격 자체가 낮은 경우가 많기 때문에, 같은 도로 가격이라도 비교 대상이 무엇인지에 따라 비율이 달라집니다.",
  s4After:
    "따라서 밭·논에서 비율이 높게 나온 것은, 도로가 대지와 비교해서 비싸다는 뜻이 아닙니다. 비교 대상인 밭·논의 가격이 대지보다 낮기 때문일 수 있습니다.",
  s5Title: "⑤ 땅 크기와 거래조건을 함께 고려하면",
  s5Before: "지금까지는 같은 동네·같은 용도지역 안에서 도로와 다른 땅의 가격을 단순 비교했습니다.",
  s5Diff: "하지만 도로 거래와 대지 거래는 땅의 크기나 접한 도로의 폭, 거래 연도 등이 서로 다를 수 있습니다.",
  s5Reg: "그래서 회귀분석을 이용해 이런 차이를 함께 고려해 봤습니다.",
  s5Note:
    "두 숫자는 계산 방법이 다르므로, 서로 같은 종류의 가운데 값은 아닙니다. 오른쪽 열을 새로운 도로 가격 비율로 단정하지 않습니다. 다른 조건을 함께 봤을 때, 도로라는 특성이 가격과 어떤 관계로 보이는지 보여주는 참고값입니다. 주거지역만, 녹지지역만 따로 본 회귀는 아직 없습니다. 도시 전체를 합친 회귀도 적지 않습니다.",
  tableCaption: "25%와 75%는 동네별 비율을 낮은 순으로 세었을 때 앞쪽 1/4, 앞쪽 3/4 지점입니다.",
  patternsTitle: "지금까지 보이는 그림",
  limitsTitle: "이 글의 한계",
  limits: [
    "이 실험은 도로라는 지목 때문에 가격이 몇 % 떨어지는가를 계산한 것이 아닙니다. 같은 동네에서 실제 거래된 도로와 다른 땅의 가격 수준을 비교한 것입니다.",
    "이번 기간과 비교 조건에서, 3분의 1이 모든 비교의 대표값으로 나타나지는 않았습니다. 3분의 1은 눈금입니다.",
    "대장의 지목 도로와, 평가에서 말하는 도로를 같은 말로 쓰지 않습니다.",
    "상업지역은 동네가 적고, 공업지역은 더 적습니다. 본문 표에 넣지 않았습니다.",
    "한 해만 잘라 거래가 많은 동네만 보면 비율이 달라 보입니다. 그 동네 묶음은 이 글의 5년 묶음과 다릅니다. 그 표는 올리지 않았습니다.",
    "읍·면은 동보다 넓은 단위입니다. 리까지 나누지 않았습니다.",
    "토지 앱의 회귀식을 바꾸거나 대신하지 않습니다. ⑤의 회귀는 이 글 안의 참고 계산입니다.",
  ],
  nextTitle: "다음에 볼 것",
  next: [
    "주거지역과 녹지지역 각각에서, 땅 크기와 접한 길을 회귀로 함께 본 값을 따로 냅니다.",
    "그 값이 해마다 바뀌었는지는 다른 질문입니다. 이 글은 5년을 한 창으로 봅니다.",
  ],
  relatedTitle: "관련 기능",
  related:
    "한 지역의 지목 사이 가격 차이는, 토지 앱에서 그 지역을 고른 뒤 기본통계에서 확인해 보는 것이 좋습니다.",
  relatedHref: "/land/",
  relatedLink: "토지 기본통계에서 보기",
};

export function formatPeriodRange(start: string, end: string): string {
  const fmt = (s: string) => s.replace(/-/g, ".");
  return `${fmt(start)}~${fmt(end)}`;
}
