import type { ReactNode } from "react";

/** 용도지역·지목·매트릭스 셀 구조 */
export function MatrixHelpContent(): ReactNode {
  return (
    <div className="space-y-2 text-[11px] text-slate-700 leading-relaxed">
      <p>
        <strong className="text-slate-800">용도지역</strong>은 토지의 계획적 이용 구역(주거·상업·
        녹지 등)을, <strong className="text-slate-800">지목</strong>은 대장상 토지 종류(전·답·
        임야 등)를 뜻합니다. 두 축을 교차한 <strong>칸</strong>은 해당 조건에 맞는 거래의{" "}
        <strong>만원/㎡ 단가</strong> 분포를 요약한 값입니다.
      </p>
      <p>
        칸 안 왼쪽 열은 <strong>거래수·평균·표준편차·95% 신뢰구간</strong>, 오른쪽은{" "}
        <strong>최소·분위·최대</strong>입니다. 건수가 적은 칸은 옅게 표시됩니다.
      </p>
    </div>
  );
}

/** 이상치 제거 (유료) */
export function OutlierHelpContent(): ReactNode {
  return (
    <div className="space-y-2 text-[11px] text-slate-700 leading-relaxed">
      <p>
        <strong className="text-slate-800">Tukey 펜스</strong>로 단가의 극단값을 뺀 뒤 평균·분위 등을
        다시 계산합니다. 구간은 대략{" "}
        <code className="text-[10px] bg-slate-100 px-0.5 rounded">Q1 − k×IQR</code> ~{" "}
        <code className="text-[10px] bg-slate-100 px-0.5 rounded">Q3 + k×IQR</code> 입니다.
      </p>
      <p>
        <strong>k</strong>가 작을수록 더 많은 극단 단가가 제외됩니다. 켜져 있으면 행 단위로 읽기
        때문에 분석 시간이 길어질 수 있습니다.
      </p>
    </div>
  );
}

/** 비교 모드 */
export function CompareHelpContent(): ReactNode {
  return (
    <div className="space-y-2 text-[11px] text-slate-700 leading-relaxed">
      <p>
        새 탭에서 법정동·리마다{" "}
        <strong className="text-slate-800">전체 단가 통계 한 블록씩</strong>을 세로로 쌓아 볼 수
        있습니다.
      </p>
      <p>
        아래쪽 <strong className="text-slate-800">통합 매트릭스</strong>는 선택 지역 전체를 합친 표본으로
        집계한 용도×지목표입니다. <strong>셀 단위로 지역별로 나눈 매트릭스</strong>는 현재 서버 한 번의 응답에
        포함되지 않습니다(추가 집계가 필요합니다).
      </p>
    </div>
  );
}
