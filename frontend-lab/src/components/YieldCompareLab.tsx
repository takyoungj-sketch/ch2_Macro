import snap from "../../../docs/lab/yield_compare_national.json";
import LabResume from "./LabResume";

type Point = { year: number; v: number | null };
type SeriesMap = Record<string, Point[]>;

const YEARS = snap.years;

type Row = { key: string; label: string; origin: string };

const INCOME_ROWS: Row[] = [
  { key: "office", label: "오피스", origin: "공표" },
  { key: "mid_retail", label: "중대형 상가", origin: "공표" },
  { key: "small_retail", label: "소규모 상가", origin: "공표" },
  { key: "strata", label: "집합 상가", origin: "공표" },
  { key: "apartment", label: "아파트 현금 월세", origin: "산출" },
  { key: "apartment_converted", label: "아파트 월세환산", origin: "산출" },
  { key: "apartment_expense10", label: "아파트 현금, 경비 10%", origin: "산출" },
  { key: "apartment_converted_expense10", label: "아파트 환산, 경비 10%", origin: "산출" },
  { key: "rowhouse", label: "연립다세대 현금 월세", origin: "산출" },
  { key: "rowhouse_converted", label: "연립다세대 월세환산", origin: "산출" },
  { key: "officetel", label: "오피스텔 현금 월세", origin: "산출" },
  { key: "officetel_converted", label: "오피스텔 월세환산", origin: "산출" },
  { key: "detached", label: "단독다가구 현금 월세", origin: "산출" },
  { key: "detached_converted", label: "단독다가구 월세환산", origin: "산출" },
  { key: "ktb3", label: "국고채 3년", origin: "인용" },
  { key: "cd91", label: "CD 91일", origin: "인용" },
  { key: "base_rate", label: "기준금리", origin: "인용" },
  { key: "dividend", label: "코스피 배당수익률", origin: "인용" },
];

const SPREAD_ROWS: Row[] = [
  { key: "office", label: "오피스 − 국고 3년", origin: "공표−인용" },
  { key: "mid_retail", label: "중대형 상가 − 국고 3년", origin: "공표−인용" },
  { key: "small_retail", label: "소규모 상가 − 국고 3년", origin: "공표−인용" },
  { key: "strata", label: "집합 상가 − 국고 3년", origin: "공표−인용" },
  { key: "apartment", label: "아파트 현금 − 국고 3년", origin: "산출−인용" },
  { key: "apartment_converted", label: "아파트 환산 − 국고 3년", origin: "산출−인용" },
  { key: "apartment_expense10", label: "아파트 현금 10% − 국고 3년", origin: "산출−인용" },
  { key: "apartment_converted_expense10", label: "아파트 환산 10% − 국고 3년", origin: "산출−인용" },
];

const CAPITAL_ROWS: (Row & { map: "capital" | "dividend" })[] = [
  { key: "office", label: "오피스", origin: "공표", map: "capital" },
  { key: "mid_retail", label: "중대형 상가", origin: "공표", map: "capital" },
  { key: "small_retail", label: "소규모 상가", origin: "공표", map: "capital" },
  { key: "strata", label: "집합 상가", origin: "공표", map: "capital" },
  { key: "apartment", label: "아파트 매매가격지수", origin: "지수 계산", map: "capital" },
  { key: "rowhouse", label: "연립다세대 매매가격지수", origin: "지수 계산", map: "capital" },
  { key: "officetel", label: "오피스텔 매매가격지수", origin: "지수 계산", map: "capital" },
  { key: "detached", label: "단독 매매가격지수", origin: "지수 계산", map: "capital" },
  { key: "kospi_price", label: "코스피 가격수익률", origin: "지수 계산", map: "capital" },
];

const INVEST_ROWS: Row[] = [
  { key: "office", label: "오피스", origin: "공표" },
  { key: "mid_retail", label: "중대형 상가", origin: "공표" },
  { key: "small_retail", label: "소규모 상가", origin: "공표" },
  { key: "strata", label: "집합 상가", origin: "공표" },
  { key: "apartment", label: "아파트 현금+자본", origin: "산출" },
  { key: "apartment_converted", label: "아파트 환산+자본", origin: "산출" },
  { key: "apartment_expense10", label: "아파트 현금 10%+자본", origin: "산출" },
  { key: "apartment_converted_expense10", label: "아파트 환산 10%+자본", origin: "산출" },
  { key: "rowhouse", label: "연립다세대 현금+자본", origin: "산출" },
  { key: "rowhouse_converted", label: "연립다세대 환산+자본", origin: "산출" },
  { key: "officetel", label: "오피스텔 현금+자본", origin: "산출" },
  { key: "officetel_converted", label: "오피스텔 환산+자본", origin: "산출" },
  { key: "detached", label: "단독다가구 현금+자본", origin: "산출" },
  { key: "detached_converted", label: "단독다가구 환산+자본", origin: "산출" },
  { key: "kospi_tr", label: "KODEX KOSPI TR", origin: "ETF" },
];

function pct(series: Point[] | undefined, year: number): string {
  const hit = series?.find((p) => p.year === year);
  if (hit == null || hit.v == null) return "—";
  return hit.v.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function YearTable({
  caption,
  rows,
}: {
  caption: string;
  rows: { label: string; origin: string; cells: string[] }[];
}) {
  return (
    <div className="space-y-1 overflow-x-auto">
      <p className="text-xs text-slate-500">{caption}</p>
      <table className="data w-full text-[13px]">
        <thead>
          <tr>
            <th className="text-left">항목</th>
            <th className="text-left">출처</th>
            {YEARS.map((year) => (
              <th key={year}>{year}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td className="text-left">{row.label}</td>
              <td className="text-left">{row.origin}</td>
              {row.cells.map((cell, index) => (
                <td key={`${row.label}-${YEARS[index]}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function rowsFrom(map: SeriesMap, spec: Row[]) {
  return spec.map((row) => ({
    label: row.label,
    origin: row.origin,
    cells: YEARS.map((year) => pct(map[row.key], year)),
  }));
}

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
    cells: YEARS.map((year) => pct(capital[row.key], year)),
  }));

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
      <section className="space-y-2 rounded border border-slate-200 dark:border-slate-700 px-3 py-2">
        <p className="font-medium">출처</p>
        <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-1 list-disc pl-4">
          <li>공표: 부동산원 상업용 임대동향의 전국·합계. 그해 1–4분기를 공표된 연간 복리로 잇는다. 상권 평균이 아니다.</li>
          <li>인용: 한은 연간 CSV의 금리 수준, 코스피 배당수익률 수준. 변화가 아니다.</li>
          <li>지수 계산: 부동산원 전국 매매가격지수 PDF의 12월/전년 12월−1. 코스피 가격수익률은 연말 종가/전년 종가−1. 지수를 우리가 만든 것이 아니다.</li>
          <li>ETF: KODEX KOSPI TR(359210)의 연간 수익률. KRX KOSPI TR 원지수가 아니다. 보수와 추적오차만큼 원지수와 다르다.</li>
          <li>산출: 국토부 실거래로 만든 임대료/매매가, 월세환산, 경비 10% 가정, 주거 소득+자본, 국고채와의 차이.</li>
        </ul>
        <p className="font-medium">전제</p>
        <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-1 list-disc pl-4">
          <li>기간은 달력 연 2021–2025, 전국. 2026년은 상권이 2분기, 지수가 8월까지라 넣지 않는다.</li>
          <li>오피스는 상업 공표의 오피스다. 오피스텔은 주거 실거래다. 둘을 한 줄로 부르지 않는다.</li>
          <li>상가통합 수익률 행이 없어 중대형·소규모·집합을 각각 둔다. 평균하지 않는다.</li>
          <li>현금 월세는 월세가 0보다 큰 계약의 ㎡당 월세 가운데값×12다. 전세는 빠진다. 보증금은 더하지 않는다. 보증금 0인 계약만 고른 것도 아니다.</li>
          <li>
            월세환산은 같은 계약에 보증금×그해 전환율/12를 더한다. 전환율은 그해·그 유형에서 전세와 보증부월세가 함께 있는 건물의 단순평균이다. 건물마다 전세·보증부월세가 각 3건 이상이고, 1% 미만·15% 초과는 뺀다. 국고채·CD로 환산하지 않는다. 전세 계약은 표본에 넣지 않는다. 단독은 그런 건물이 없어 환산 칸이 비어 있다.
          </li>
          <li>분모는 같은 해 매매 ㎡당 가격 가운데값이다. 같은 집을 짝짓지 않는다. 아파트·연립·오피스텔은 전용면적, 단독 임대는 계약면적, 단독 매매는 연면적이다.</li>
          <li>경비 10%는 아파트만, 해당 소득의 0.9배다. 측정된 경비도 공실도 아니다.</li>
          <li>주거 투자는 그해 소득+그해 자본이다. 상업 4분기 복리와 같은 식이 아니다.</li>
          <li>코스피 배당수익률은 소득 칸의 그해 수준이다. 가격수익률은 자본 칸만이다. 둘을 더해 총수익으로 두지 않는다. 거래대금은 쓰지 않는다.</li>
          <li>임대 건수 또는 매매 건수가 100 미만이면 그 해 소득은 빈칸이다.</li>
        </ul>
        <p className="text-xs text-slate-600 dark:text-slate-300">
          아파트 그해 전환율(%):{" "}
          {snap.residential_counts.apartment
            .map((row) => `${row.year} ${row.r_pct == null ? "—" : row.r_pct}`)
            .join(" · ")}
        </p>
      </section>
      <YearTable caption="소득. 국고채 3년은 수준이다." rows={rowsFrom(income, INCOME_ROWS)} />
      <YearTable caption="소득에서 국고채 3년을 뺀 차이." rows={rowsFrom(spread, SPREAD_ROWS)} />
      <YearTable
        caption="자본. 주거는 12월 지수 대비. 코스피는 연말 종가의 가격수익률이다."
        rows={capitalRows}
      />
      <YearTable
        caption="투자. 상업은 4분기 복리. 주거 줄 이름은 소득+자본. 코스피는 KODEX KOSPI TR이다."
        rows={rowsFrom(investment, INVEST_ROWS)}
      />
      <ul className="text-xs text-slate-500 space-y-1 list-disc pl-4">
        {snap.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  );
}
