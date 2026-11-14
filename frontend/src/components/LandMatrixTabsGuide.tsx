import GuideDialog from "@ch2/macro-shell/GuideDialog";
import { useFeature } from "@ch2/macro-shell/features";

const tabs = [
  {
    title: "롤링 구간 · 선택 연도",
    feature: "현재 분석 조건에 해당하는 거래를 구간별로 나누어 단가와 거래 수의 변화를 확인합니다. 롤링 구간에서는 평균·중앙값과 25%·75% 값을 선택해 볼 수 있습니다.",
    caution: "거래 구성과 표본 수가 바뀌면 단가도 달라질 수 있습니다. 장기 추세 탭과 기간·필터 기준을 확인한 뒤 비교해 주세요.",
  },
  {
    title: "단가 분포",
    feature: "히스토그램과 박스플롯으로 단가가 어느 구간에 모여 있는지, 중앙값과 가격의 퍼짐 정도를 확인합니다. 전체 구간 또는 특정 구간을 선택할 수 있습니다.",
    caution: "표본이 적으면 분포 모양이 불안정합니다. 이상치 제외 여부와 선택 구간을 함께 확인해 주세요.",
  },
  {
    title: "거래 목록",
    feature: "개별 거래의 계약일, 지역, 면적, 금액, 단가 등을 확인하고 정렬·필터·집계하거나 CSV로 내보낼 수 있습니다.",
    caution: "전체 조회 대상이 1만 건을 넘으면 화면 목록과 집계는 불러온 거래만 반영합니다. CSV는 같은 분석 조건의 전체 거래를 대상으로 합니다.",
  },
  {
    id: "regression",
    title: "회귀 분석",
    feature: "면적, 도로조건, 거래유형 등 변수를 선택해 토지 단가와의 통계적 관계를 분석하고, 모형 비교와 조건별 추정을 살펴봅니다.",
    caution: "변수·결측치·이상치 처리에 따라 분석 표본이 달라집니다. {LEDGER}계수와 추정값을 인과관계나 개별 토지의 적정가격으로 해석하지 않도록 유의해 주세요.",
  },
  {
    title: "장기 추세",
    feature: "선택한 용도지역·지목 또는 지목군의 달력 연도별 평균·중앙단가와 거래 수를 확인합니다. 여러 지역의 흐름도 비교할 수 있습니다.",
    caution: "도로·면적·지분·이상치 등 추가 필터를 적용하지 않습니다. 롤링 구간과 기간·표본이 다를 수 있으며, 거래 15건 미만인 연도는 참고용으로 살펴봐 주세요.",
  },
];

const LEDGER_CAUTION = "공시지가 모형은 지분거래와 공시지가 미연결 거래를 제외합니다. ";
const COUNT_KO = ["", "한", "두", "세", "네", "다섯"];

export default function LandMatrixTabsGuide() {
  // D-085: 비공개 기능의 탭 설명은 보이지 않는다.
  const regressionOn = useFeature("land_regression");
  const ledgerOn = useFeature("land_ledger_link");
  const shown = tabs
    .filter((t) => regressionOn || t.id !== "regression")
    .map((t) => ({ ...t, caution: t.caution.replace("{LEDGER}", ledgerOn ? LEDGER_CAUTION : "") }));
  return (
    <GuideDialog
      id="land-matrix-tabs-guide"
      storageKey="ch2-macro:hide-land-matrix-tabs-guide"
      title="상세분석 탭 안내"
      triggerLabel="탭 안내"
      actionLabel="상세분석 살펴보기"
      oncePerVisit
    >
      <p id="land-matrix-tabs-guide-summary">
        선택한 매트릭스 셀을 {COUNT_KO[shown.length]} 가지 관점에서 살펴봅니다. 각 탭의 분석 범위와 주의사항을 확인해 주세요.
      </p>
      {shown.map(({ title, feature, caution }, index) => (
        <section key={title} className="analysis-guide__section">
          <h3>{index + 1}. {title}</h3>
          <p>{feature}</p>
          <div className="analysis-guide__note">
            <h4>이용 시 유의사항</h4>
            <p>{caution}</p>
          </div>
        </section>
      ))}
    </GuideDialog>
  );
}
