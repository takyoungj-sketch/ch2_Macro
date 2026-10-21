const TEXT = `용도지역 변수에 관한 유의사항
본 회귀분석은 하나의 필지가 둘 이상의 용도지역에 걸쳐 있는 경우, 원본 자료의 제1용도지역을 대표 설명변수로 사용합니다.
제1용도지역은 반드시 면적 비율이 가장 높거나 가격형성에 가장 큰 영향을 미치는 용도지역을 의미하지 않습니다. 따라서 복수 용도지역에 해당하는 거래의 분석 결과에는 이러한 한계가 반영될 수 있습니다.`;

export default function ZoneCaution() {
  return (
    <p className="whitespace-pre-line text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
      {TEXT}
    </p>
  );
}
