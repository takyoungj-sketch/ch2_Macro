type FloorIndexMethodGuideProps = {
  dimension: string;
  floorMode?: string;
  isCluster?: boolean;
  isFactory?: boolean;
  isRegression?: boolean;
  referenceLabel?: string | null;
};

export function floorIndexGuideText({
  dimension,
  floorMode = "relative",
  isCluster = false,
  isFactory = false,
  isRegression = true,
  referenceLabel,
}: FloorIndexMethodGuideProps): { title: string; body: string } {
  const ref = referenceLabel || (dimension === "floor" ? "1층" : "중앙 면적형");
  if (!isRegression) {
    return {
      title: "이번 결과는 참고용입니다",
      body:
        "회귀를 맞출 표본이 부족해 기준 칸만 100으로 두고 나머지 지수는 비웠습니다. 평균(만원/㎡)은 그 칸 원자료입니다.",
    };
  }
  if (dimension === "floor") {
    const groups = isCluster
      ? "지하심층(B2 이하) · 지하1층 · 1층 · 2층 · 저층(3–4) · 중층(5–9) · 고층(10–19) · 초고층(20+). 지하를 주거 ‘중층부’로 넣지 않습니다."
      : floorMode === "dummy"
        ? "거래가 있는 개별 층마다 칸을 만듭니다."
        : floorMode === "grouped"
          ? "절대 층 구간 1–5층 · 6–15층 · 16층+입니다."
          : "단지 최고층 대비 1층 · 저층부 · 중층부 · 고층부 · 최상층입니다.";
    return {
      title: "층별 지수",
      body:
        `같은 ${isCluster ? "도로(cluster)" : "단지"} 실거래의 ㎡당 단가(로그)를 회귀합니다. ${groups} ` +
        `${isCluster ? "연면적" : "전용면적"}·연식·거래시점(반기)을 맞춘 뒤, ${ref}=100으로 층만 비교합니다. ` +
        "표의 평균은 통제 없는 원자료라 지수와 방향이 다를 수 있습니다.",
    };
  }
  if (dimension === "area") {
    const buckets = isFactory
      ? "연면적 100㎡ 미만 · 100~300㎡ · 300~1000㎡ · 1000㎡ 이상입니다 (30㎡ 눈금이 아닙니다)."
      : `${isCluster ? "연면적" : "전용면적"}을 30㎡로 반올림한 면적형입니다.`;
    return {
      title: "면적별 지수",
      body:
        `${buckets} 기준(${ref}=100)은 표본 ${isCluster ? "연면적" : "전용면적"} 중앙값이 속한 칸입니다. ` +
        "면적은 구간 더미로만 넣고 연속 ln(면적)은 빼, 규모 효과를 한 번만 봅니다. 층·연식·시점은 통제합니다.",
    };
  }
  if (dimension === "dong") {
    return {
      title: "동별 지수",
      body: `거래가 가장 많은 동=100. 전용면적·연식·시점·상대 층을 맞춘 뒤 동만 비교합니다.`,
    };
  }
  if (dimension === "rights") {
    return {
      title: "권리별 지수",
      body: "분양권·입주권 등 거래가 가장 많은 권리=100. 면적·연식·시점·층을 맞춘 뒤 권리만 비교합니다.",
    };
  }
  return {
    title: "효용지수",
    body: `기준 ${ref}=100인 상대 ㎡당 단가(%)입니다. 적정가가 아닙니다.`,
  };
}

export default function FloorIndexMethodGuide(props: FloorIndexMethodGuideProps) {
  const { title, body } = floorIndexGuideText(props);
  return (
    <div className="text-[11px] text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded px-2.5 py-2 space-y-0.5">
      <p className="font-medium text-slate-700 dark:text-slate-200">{title}</p>
      <p className="leading-relaxed">{body}</p>
    </div>
  );
}
