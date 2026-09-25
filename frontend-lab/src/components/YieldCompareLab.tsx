import snap from "../../../docs/lab/yield_compare_national.json";
import { Fragment, useState } from "react";
import LabResume from "./LabResume";

type Point = { year: number; v: number | null };
type SeriesMap = Record<string, Point[]>;
type SampleCount = {
  year: number;
  n_rent: number | null;
  n_sale: number | null;
  n_buildings: number | null;
  r_pct: number | null;
};

const YEARS = snap.years;
const SAMPLE_LABELS: Record<string, string> = {
  apartment: "아파트",
  rowhouse: "연립다세대",
  officetel: "오피스텔",
  detached: "단독다가구",
};

type Row = { key: string; label: string; origin: string; group?: string };

const INCOME_ROWS: Row[] = [
  { key: "office", label: "오피스 소득수익률", origin: "공표 데이터", group: "대표 비교" },
  { key: "mid_retail", label: "중대형 상가 소득수익률", origin: "공표 데이터", group: "대표 비교" },
  { key: "small_retail", label: "소규모 상가 소득수익률", origin: "공표 데이터", group: "대표 비교" },
  { key: "strata", label: "집합 상가 소득수익률", origin: "공표 데이터", group: "대표 비교" },
  { key: "apartment_converted", label: "아파트 월세환산 소득수익률", origin: "원장 산출", group: "대표 비교" },
  { key: "ktb3", label: "국고채 3년 금리", origin: "한국은행 인용", group: "대표 비교" },
  { key: "apartment", label: "아파트 현금 월세 소득수익률", origin: "원장 산출", group: "주거 참고" },
  { key: "apartment_expense10", label: "아파트 현금 월세, 경비 10% 가정", origin: "원장 산출", group: "주거 참고" },
  { key: "apartment_converted_expense10", label: "아파트 월세환산, 경비 10% 가정", origin: "원장 산출", group: "주거 참고" },
  { key: "rowhouse_converted", label: "연립다세대 월세환산 소득수익률", origin: "원장 산출", group: "주거 참고" },
  { key: "officetel_converted", label: "오피스텔 월세환산 소득수익률", origin: "원장 산출", group: "주거 참고" },
  { key: "detached_converted", label: "단독다가구 월세환산 소득수익률", origin: "원장 산출", group: "주거 참고" },
  { key: "cd91", label: "CD 91일 금리", origin: "한국은행 인용", group: "시장 참고" },
  { key: "base_rate", label: "한국은행 기준금리", origin: "한국은행 인용", group: "시장 참고" },
  { key: "dividend", label: "코스피 배당수익률(배당 수준)", origin: "한국은행 인용", group: "시장 참고" },
];

const SPREAD_ROWS: Row[] = [
  { key: "office", label: "오피스 소득수익률 − 국고채 3년", origin: "차이 계산", group: "대표 비교" },
  { key: "mid_retail", label: "중대형 상가 소득수익률 − 국고채 3년", origin: "차이 계산", group: "대표 비교" },
  { key: "small_retail", label: "소규모 상가 소득수익률 − 국고채 3년", origin: "차이 계산", group: "대표 비교" },
  { key: "strata", label: "집합 상가 소득수익률 − 국고채 3년", origin: "차이 계산", group: "대표 비교" },
  { key: "apartment_converted", label: "아파트 월세환산 소득수익률 − 국고채 3년", origin: "차이 계산", group: "대표 비교" },
  { key: "apartment", label: "아파트 현금 월세 소득수익률 − 국고채 3년", origin: "차이 계산", group: "주거 참고" },
  { key: "apartment_expense10", label: "아파트 현금 월세, 경비 10% 가정 − 국고채 3년", origin: "차이 계산", group: "주거 참고" },
  { key: "apartment_converted_expense10", label: "아파트 월세환산, 경비 10% 가정 − 국고채 3년", origin: "차이 계산", group: "주거 참고" },
];

const CAPITAL_ROWS: (Row & { map: "capital" | "dividend" })[] = [
  { key: "office", label: "오피스 자본수익률", origin: "공표 데이터", map: "capital", group: "대표 비교" },
  { key: "mid_retail", label: "중대형 상가 자본수익률", origin: "공표 데이터", map: "capital", group: "대표 비교" },
  { key: "small_retail", label: "소규모 상가 자본수익률", origin: "공표 데이터", map: "capital", group: "대표 비교" },
  { key: "strata", label: "집합 상가 자본수익률", origin: "공표 데이터", map: "capital", group: "대표 비교" },
  { key: "apartment", label: "아파트 매매가격지수 변동률", origin: "가격지수 계산", map: "capital", group: "대표 비교" },
  { key: "rowhouse", label: "연립다세대 매매가격지수 변동률", origin: "가격지수 계산", map: "capital", group: "주거·시장 참고" },
  { key: "officetel", label: "오피스텔 매매가격지수 변동률", origin: "가격지수 계산", map: "capital", group: "주거·시장 참고" },
  { key: "detached", label: "단독 매매가격지수 변동률", origin: "가격지수 계산", map: "capital", group: "주거·시장 참고" },
  { key: "kospi_price", label: "코스피 가격수익률", origin: "가격지수 계산", map: "capital", group: "주거·시장 참고" },
];

const INVEST_ROWS: Row[] = [
  { key: "office", label: "오피스 투자수익률", origin: "공표 데이터", group: "상업용·주거 대표" },
  { key: "mid_retail", label: "중대형 상가 투자수익률", origin: "공표 데이터", group: "상업용·주거 대표" },
  { key: "small_retail", label: "소규모 상가 투자수익률", origin: "공표 데이터", group: "상업용·주거 대표" },
  { key: "strata", label: "집합 상가 투자수익률", origin: "공표 데이터", group: "상업용·주거 대표" },
  { key: "apartment_converted", label: "아파트 월세환산 소득+자본", origin: "원장 산출", group: "상업용·주거 대표" },
  { key: "apartment", label: "아파트 현금 월세 소득+자본", origin: "원장 산출", group: "참고 비교" },
  { key: "apartment_expense10", label: "아파트 현금 월세, 경비 10% 가정의 소득+자본", origin: "원장 산출", group: "참고 비교" },
  { key: "apartment_converted_expense10", label: "아파트 월세환산, 경비 10% 가정의 소득+자본", origin: "원장 산출", group: "참고 비교" },
  { key: "rowhouse_converted", label: "연립다세대 월세환산 소득+자본", origin: "원장 산출", group: "참고 비교" },
  { key: "officetel_converted", label: "오피스텔 월세환산 소득+자본", origin: "원장 산출", group: "참고 비교" },
  { key: "detached_converted", label: "단독다가구 월세환산 소득+자본", origin: "원장 산출", group: "참고 비교" },
  { key: "kospi_tr", label: "KODEX KOSPI TR 연간수익률", origin: "ETF 연간수익률", group: "참고 비교" },
];

function pct(series: Point[] | undefined, year: number): string {
  const hit = series?.find((p) => p.year === year);
  if (hit == null || hit.v == null) return "—";
  return hit.v.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function YearTable({
  caption,
  rows,
  unit = "%",
}: {
  caption: string;
  rows: { label: string; origin: string; cells: string[]; group?: string }[];
  unit?: string;
}) {
  let previousGroup: string | undefined;
  return (
    <div className="space-y-1 overflow-x-auto">
      <p className="text-xs text-slate-500">{caption}</p>
      <table className="data w-full text-[13px]">
        <thead>
          <tr>
            <th className="text-left">항목</th>
            <th className="text-left">산출·출처</th>
            {YEARS.map((year) => (
              <th key={year}>{year} ({unit})</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const showGroup = row.group != null && row.group !== previousGroup;
            previousGroup = row.group;
            return (
              <Fragment key={row.label}>
                {showGroup ? (
                  <tr>
                    <th
                      colSpan={YEARS.length + 2}
                      className="bg-slate-50 text-left text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                    >
                      {row.group}
                    </th>
                  </tr>
                ) : null}
                <tr>
                  <td className="text-left">{row.label}</td>
                  <td className="text-left text-slate-500">{row.origin}</td>
                  {row.cells.map((cell, index) => (
                    <td key={`${row.label}-${YEARS[index]}`}>{cell}</td>
                  ))}
                </tr>
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function rowsFrom(map: SeriesMap, spec: Row[]) {
  return spec.map((row) => ({
    label: row.label,
    origin: row.origin,
    group: row.group,
    cells: YEARS.map((year) => pct(map[row.key], year)),
  }));
}

function sampleCount(value: number | null): string {
  return value == null ? "—" : value.toLocaleString("ko-KR");
}

function ResidentialSampleTable() {
  const counts = snap.residential_counts as Record<string, SampleCount[]>;
  return (
    <div className="overflow-x-auto">
      <table className="data w-full text-xs">
        <thead>
          <tr>
            <th className="text-left">주거 유형</th>
            {YEARS.map((year) => (
              <th key={year}>
                {year} 임대/매매 (건)
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(SAMPLE_LABELS).map(([key, label]) => (
            <tr key={key}>
              <td className="text-left">{label}</td>
              {YEARS.map((year) => {
                const row = counts[key]?.find((item) => item.year === year);
                return (
                  <td key={`${key}-${year}`}>
                    {sampleCount(row?.n_rent ?? null)} / {sampleCount(row?.n_sale ?? null)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const TAB_DEFINITIONS = [
  {
    key: "income",
    label: "소득",
    description: "임대료와 금리 수준을 비교합니다.",
  },
  {
    key: "spread",
    label: "국고채와 비교",
    description: "각 소득수익률에서 국고채 3년 금리를 뺀 차이입니다.",
  },
  {
    key: "capital",
    label: "자본",
    description: "상업용·주거용 가격 변동과 코스피 가격수익률입니다.",
  },
  {
    key: "investment",
    label: "투자",
    description: "상업용 공표 투자수익률, 주거 소득+자본, KODEX 수익률입니다.",
  },
] as const;

export default function YieldCompareLab() {
  const income = {
    ...(snap.income_pct as SeriesMap),
    dividend: snap.kospi_dividend_yield_pct as Point[],
  };
  const spread = snap.spread_vs_ktb3_pct as SeriesMap;
  const capital = snap.capital_pct as SeriesMap;
  const investment = snap.investment_pct as SeriesMap;
  const capitalRows = CAPITAL_ROWS.map((row) => ({
    label: row.label,
    origin: row.origin,
    group: row.group,
    cells: YEARS.map((year) => pct(capital[row.key], year)),
  }));
  const [activeTab, setActiveTab] = useState<(typeof TAB_DEFINITIONS)[number]["key"]>("income");
  const activeTabDefinition = TAB_DEFINITIONS.find((tab) => tab.key === activeTab) ?? TAB_DEFINITIONS[0];

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-4 text-sm leading-relaxed">
      <LabResume
        resume={{
          next_id: "yield-compare-screen",
          title: "표는 관리자에 있고, 공개는 11번이다",
          say: "전국 2021–2025. 오피스는 상업 공표이고 오피스텔은 주거 실거래다. 주거 세 번째 줄은 소득+자본이다. 공개 글은 /insight/?q=11.",
          do_not: "오피스와 오피스텔을 한 줄로 부르기. 상가 세 유형을 평균하기. 주거를 분기로 쪼개 상업 복리와 같은 식이라고 적기. 코스피 종가 수익률에 배당수익률을 더하기. #1·#5에 붙이기.",
          how: "docs/lab/YIELD_COMPARE_LAB.md · docs/lab/yield_compare_national.json · python -m app.yield_compare.build",
        }}
      />
      <section className="space-y-3 rounded border border-slate-200 dark:border-slate-700 px-3 py-3">
        <div>
          <p className="font-medium">표를 읽는 방법</p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            대표 비교 행을 먼저 두고, 주거·시장 참고값은 아래에 따로 표시했습니다. 모든 연도 열의 단위는 %이며,
            국고채와 비교 탭의 단위는 %포인트입니다.
          </p>
        </div>
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="수익률 비교 표">
          {TAB_DEFINITIONS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.key}
              className={`rounded border px-3 py-1.5 text-sm ${
                activeTab === tab.key
                  ? "border-slate-800 bg-slate-800 text-white dark:border-slate-200 dark:bg-slate-200 dark:text-slate-900"
                  : "border-slate-300 text-slate-700 dark:border-slate-600 dark:text-slate-200"
              }`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-500">{activeTabDefinition.description}</p>
      </section>
      {activeTab === "income" ? (
        <YearTable
          caption="소득수익률과 금리 수준(%). 아파트 대표값은 월세환산입니다. 코스피 배당수익률은 소득수익률이 아니라 배당 수준입니다."
          rows={rowsFrom(income, INCOME_ROWS)}
        />
      ) : null}
      {activeTab === "spread" ? (
        <YearTable
          caption="소득수익률에서 국고채 3년 금리를 뺀 차이(%포인트). 양수이면 소득수익률이 국고채보다 높다는 뜻입니다."
          unit="%포인트"
          rows={rowsFrom(spread, SPREAD_ROWS)}
        />
      ) : null}
      {activeTab === "capital" ? (
        <YearTable
          caption="자본수익률(%). 주거는 매매가격지수의 12월 대비 변동률이고, 코스피는 연말 종가 기준 가격수익률입니다."
          rows={capitalRows}
        />
      ) : null}
      {activeTab === "investment" ? (
        <YearTable
          caption="연간 투자성과(%). 상업용은 공표된 1~4분기 복리, 주거는 그해 소득+자본, 주식은 KODEX KOSPI TR입니다."
          rows={rowsFrom(investment, INVEST_ROWS)}
        />
      ) : null}
      <details className="rounded border border-slate-200 px-3 py-2 dark:border-slate-700">
        <summary className="cursor-pointer font-medium">산식·표본·출처 상세</summary>
        <div className="mt-2 space-y-2">
          <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-1 list-disc pl-4">
            <li>기간은 2021–2025년 전국입니다. 상업용은 전국·합계 행의 1~4분기를 복리로 계산했습니다.</li>
            <li>아파트 소득수익률은 같은 주택의 수익률이 아니라, 임대료 가운데값과 매매가격 가운데값을 이용한 대표 지표입니다.</li>
            <li>월세환산 전환율은 국고채나 CD가 아니라, 유형별 건물 표본에서 계산한 그해 단순평균입니다.</li>
            <li>경비 10%는 측정된 경비나 공실률이 아니라 아파트 소득의 90%를 적용한 가정입니다.</li>
            <li>단독다가구는 임대 계약면적과 매매 연면적이 달라 다른 주거 유형과 수준을 직접 비교하지 않습니다.</li>
            <li>임대 또는 매매 거래가 100건 미만인 연도의 주거 소득은 계산하지 않았습니다.</li>
            <li>코스피 가격수익률과 배당수익률을 더해 총수익률로 만들지 않았습니다. 투자 표의 주식 행은 KODEX KOSPI TR입니다.</li>
          </ul>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            아파트 그해 전환율(%):{" "}
            {snap.residential_counts.apartment
              .map((row) => `${row.year} ${row.r_pct == null ? "—" : row.r_pct}`)
              .join(" · ")}
          </p>
          <p className="text-xs text-slate-500">주거 표본 수는 임대 건수 / 매매 건수 순서이며, 단위는 건입니다.</p>
          <ResidentialSampleTable />
          <ul className="text-xs text-slate-500 space-y-1 list-disc pl-4">
            {snap.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      </details>
    </div>
  );
}
