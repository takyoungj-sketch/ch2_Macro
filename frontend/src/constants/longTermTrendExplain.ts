import type { AnalysisExplain } from "../types";
import type { LongTermRegionTarget } from "../utils/longTermTargets";

const LEVEL_LABEL: Record<string, string> = {
  beopjungri: "법정동·리",
  eupmyeondong: "읍·면·동",
  sigungu: "시·군·구",
  city: "시(자치구 통합)",
  sido: "시·도",
};

export type LtPriceMetric = "mean" | "median";

export interface LongTermExplainContext {
  zoneType: string;
  landCategory: string;
  metric: LtPriceMetric;
  targets: LongTermRegionTarget[];
  yearFrom?: number | null;
  yearTo?: number | null;
  seriesCount?: number;
  referenceOnlyYears?: number;
}

export function buildLongTermTrendExplain(ctx: LongTermExplainContext): AnalysisExplain {
  const metricLabel = ctx.metric === "median" ? "중앙값" : "평균";
  const levels = [...new Set(ctx.targets.map((t) => t.region_level))];
  const levelText =
    levels.length === 1
      ? (LEVEL_LABEL[levels[0]!] ?? levels[0])
      : levels.map((l) => LEVEL_LABEL[l] ?? l).join(", ");

  const hints: string[] = [
    `용도×지목: ${ctx.zoneType} · ${ctx.landCategory}`,
    `추세선: 연도별 ${metricLabel}(만원/㎡)`,
    `지역 단위: ${levelText} — 선 ${ctx.seriesCount ?? ctx.targets.length}개 (합산 1선 없음)`,
  ];
  if (ctx.yearFrom != null && ctx.yearTo != null) {
    hints.push(`표시 연도: ${ctx.yearFrom}~${ctx.yearTo} (만년력 1/1~12/31)`);
  }
  if (ctx.referenceOnlyYears != null && ctx.referenceOnlyYears > 0) {
    hints.push(
      `⚠ 참고용 연도 ${ctx.referenceOnlyYears}개 — 해당 연도 거래 n<15 (흐리게 표시)`,
    );
  }

  return {
    spec_id: "land.long_term_trend.v1",
    spec_version: "1.0",
    title: "토지 장기 추세선 산출 방법",
    summary:
      "필터분석과 동일하게 만년력 연도(1월~12월)별 단가 추세를 보여 줍니다. " +
      "값은 실시간 집계가 아니라 사전 통계 DB에서 읽으며, " +
      "도로·면적·이상치·지분 등 고급 필터는 적용하지 않습니다.",
    formula:
      "단가(만원/㎡) = 거래금액(만원) ÷ 계약면적(㎡)\n" +
      `연도 y 의 ${metricLabel} = 해당 연도·지역·용도×지목 표본의 ${metricLabel === "중앙값" ? "median(unit_price_per_sqm)" : "mean(unit_price_per_sqm)"}`,
    reference:
      "집계 원장: land_transactions (is_valid=true, is_cancelled=false, 단가 not null)",
    floor_groups: [
      "법정동·리: land_annual_stats (beopjungri_code × calendar_year × zone × cat)",
      "시·군·구·읍면동·시(통합): land_annual_upper_stats (region_level × region_code × calendar_year × zone × cat)",
      "상위 1선 = 해당 행정구역 안 거래 전체를 한 표본으로 집계 (리별 선을 합치지 않음)",
    ],
    controls: [
      "포함: 선택 용도지역·지목 셀과 동일 zone_type × land_category",
      "미적용: 도로조건, 면적구분(광소/정상/광대), ㎡ 범위, 지분거래 제외, IQR 이상치 제외",
      "미적용: 필터분석에서 선택한 연도 칩 — 장기 탭은 사전 마트에 있는 전 연도 구간",
    ],
    interpretation: [
      "가로축은 calendar_year(만년력), 세로축은 만원/㎡ " + metricLabel + "입니다.",
      "복수 지역 선택 시 지역마다 선이 분리됩니다 — 한 선으로 합산하지 않습니다.",
      "거래 건수 n<15 인 연도는 「참고용」으로 표시합니다 (기본통계와 동일 정책).",
      "「선택 연도」 탭(필터분석)은 고급 필터가 반영된 연도별 값, 「장기 추세」는 필터 없는 연도 마트입니다.",
    ],
    limitations: [
      "행정구역 통·폐합·개명: v1은 region_code_history(코드 이력 remap)를 적용하지 않습니다. " +
        "국토부 원장·연도 마트는 현행 region_codes 기준이며, 시·도·시군구 등 상위 명칭은 소급 표기된 경우가 많고 " +
        "읍·면·동·리는 개편 전후로 표기·코드가 섞일 수 있습니다.",
      "리→동 통폐합·신설 행정동 등: 과거 거래가 옛 법정리·면 단위에만 남고, 현재 선택한 동·리 코드와 연도별 선이 이어지지 않을 수 있습니다 (세종 등 신도시뿐 아니라 소규모 개편 지역도 동일).",
      "선택 지역에 해당 연도·셀의 사전 마트(land_annual_stats / land_annual_upper_stats) 행이 없으면 그 구간은 표시되지 않습니다 — 「무거래」와 「집계 불가·미적재」를 구분해 해석하세요.",
      "기본통계 보기(롤링 3·5년)와 기간 축이 다릅니다 — 장기 추세는 필터분석 실행 후에만 열립니다.",
    ],
    interpretation_hints: hints,
    presets: [
      {
        id: "vs-filter",
        question: "필터분석 「선택 연도」와 숫자가 다른 이유는?",
        answer:
          "선택 연도 탭은 도로·면적·이상치 등 필터와 선택 연도 칩이 반영된 live 집계입니다. " +
          "장기 추세는 필터 없이 연도 마트(land_annual_stats / land_annual_upper_stats)만 조회합니다.",
      },
      {
        id: "vs-basic",
        question: "기본통계 보기와 무엇이 다른가요?",
        answer:
          "기본통계는 지난달 말 기준 롤링 3·5년 창과 1년 구간입니다. " +
          "장기 추세는 2010~ 등 만년력 연도별 한 점씩 이어 붙인 선이며, 필터분석과 같은 연도 축입니다.",
      },
      {
        id: "upper",
        question: "흥덕구처럼 상위만 고르면?",
        answer:
          "시·군·구 등 상위 코드 1개당 추세선 1개입니다. " +
          "산하 법정동·리를 각각 그리지 않으며, 해당 구역 전체 거래를 한 표본으로 연도별 집계합니다.",
      },
      {
        id: "metric",
        question: "중앙값과 평균 중 무엇을 보나요?",
        answer:
          "기본은 중앙값(극단값에 덜 민감). 평균은 소수 대형 거래의 영향을 더 받습니다. " +
          "토글로 전환할 수 있으며, 표와 차트가 함께 바뀝니다.",
      },
      {
        id: "admin-boundary",
        question: "행정구역 개편·개명 지역은 어떻게 해석하나요?",
        answer:
          "v1은 행정구역 코드 이력(region_code_history)을 쓰지 않습니다. " +
          "청원군→청원구처럼 상위 명칭만 소급된 경우는 연속적으로 보일 수 있으나, " +
          "리→동 통폐합·신설 읍면동 등은 과거 거래가 옛 리·면 코드에 남거나 원장에만 있고 장기 마트에는 없을 수 있습니다. " +
          "현재 선택한 동·읍·면 이름과 2010년대 선이 같은 지역을 가리킨다고 가정하지 마세요. " +
          "선이 끊기거나 비어 있으면 인접 상위(읍·면) 또는 잔존 법정리 단위를 참고하세요.",
      },
    ],
  };
}
