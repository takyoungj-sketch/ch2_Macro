import GuideDialog from "@ch2/macro-shell/GuideDialog";

const features = [
  {
    title: "기본통계",
    description: "지역별 용도지역·지목 매트릭스에서 평균단가, 거래량, 가격 분포를 비교합니다. 여러 지역을 함께 선택할 수도 있습니다.",
    icon: "M4 4h16v16H4zM4 10h16M10 4v16",
  },
  {
    title: "조건별 필터분석",
    description: "연도, 도로조건, 면적, 거래유형, 이상치 등을 필터링한 후 통계분석을 실시합니다.",
    icon: "M4 6h16M4 12h16M4 18h16M9 4v4m6 2v4m-5 2v4",
  },
  {
    title: "상세분석",
    description: "용도지목 매트릭스의 셀을 클릭하면 해당 셀의 거래목록, 장기추세선 등 추가분석이 가능합니다.",
    icon: "m4 13 5-5 4 3 7-7M6 20v-4m4 4v-7m4 7v-5m4 5v-9",
  },
];

export default function LandAnalysisGuide() {
  return (
    <GuideDialog
      id="land-analysis-guide"
      storageKey="ch2-macro:hide-land-analysis-guide"
      title="토지 실거래 통계"
      triggerLabel="토지 분석 안내"
      actionLabel="토지 분석 시작하기"
    >
      <p className="analysis-guide__tagline">지역과 거래조건에 따라 토지시장을 분석합니다.</p>
      <p id="land-analysis-guide-summary">
        전국 토지 실거래 자료를 용도지역과 지목별로 구분하여 가격 수준, 분포, 거래량과 시간에 따른 변화를 살펴볼 수 있습니다.
      </p>
      <section className="analysis-guide__section">
        <h3>주요 기능</h3>
        <ul className="analysis-guide__features">
          {features.map(({ title, description, icon }) => (
            <li key={title}>
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d={icon} />
              </svg>
              <div>
                <h4>{title}</h4>
                <p>{description}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
      <section className="analysis-guide__section">
        <h3>사용방법</h3>
        <ol className="analysis-guide__steps">
          <li>지역을 검색하고 분석할 지역을 선택합니다.</li>
          <li>3·5·7년 롤링 구간을 선택하고 <strong>기본 통계 보기</strong>를 누릅니다.</li>
          <li>필요하면 세부 조건을 변경해 <strong>필터 분석 실행</strong>을 누르고, 통계표의 셀을 선택해 상세분석을 확인합니다.</li>
        </ol>
      </section>
      <section className="analysis-guide__note">
        <h3>분석할 때 유의하세요</h3>
        <ul>
          <li>용도지역과 지목이 같더라도 위치, 도로접근성, 형상 및 개별 특성에 따라 가격 차이가 발생합니다.</li>
          <li>거래 건수가 적거나 표본이 편중된 경우 통계의 대표성이 낮아질 수 있습니다.</li>
          <li>단순 평균과 추세는 개별 토지의 적정가격이나 미래 가격을 의미하지 않습니다.</li>
        </ul>
      </section>
    </GuideDialog>
  );
}
