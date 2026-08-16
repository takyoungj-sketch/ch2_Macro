import { Fragment } from "react";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { RentProfileYearlyResponse } from "../types";
import { deepLinkTo } from "../utils/deepLinks";
import { formatAmountManwon, formatInt } from "../utils/format";

function yearTone(yearIndex: number): string {
  return yearIndex % 2 === 0
    ? "bg-slate-50/90 dark:bg-slate-900/35"
    : "bg-white dark:bg-slate-800/40";
}

function cellOf(row: RentProfileYearlyResponse["types"][number], year: number) {
  return row.years[String(year)] ?? { count: 0, deposit_sum: 0, monthly_sum: 0 };
}

function moneyOrDash(n: number, monthly = false): string {
  if (!n) return "-";
  const s = formatAmountManwon(n);
  return monthly ? `${s}/월` : s;
}

export default function RentYearlyTable({
  data,
  regionLevel,
  regionCode,
}: {
  data: RentProfileYearlyResponse;
  regionLevel: string;
  regionCode: string;
}) {
  const years = data.years;
  const href = deepLinkTo("rent", { regionLevel, regionCode });

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">주거 전월세 3개년 (4유형)</h2>
          <StatsGlossaryHelp termId="rent_yearly" size="sm" />
        </div>
        <a href={href} className="btn btn-primary text-xs">
          임대 상세분석 →
        </a>
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        매매가 아닙니다. 보증금 합과 월세 합은 더하지 마세요. 월세는 계약의 월 금액 합(만/월)이며 연환산하지
        않습니다. 전세전환·월세전환은 넣지 않았습니다.
      </p>

      <div className="mt-4 overflow-x-auto">
        <table className="data yearly-mix-table w-full">
          <thead>
            <tr>
              <th rowSpan={2} className="yearly-mix-sticky align-bottom">
                유형
              </th>
              {years.map((y, yi) => (
                <th
                  key={y}
                  colSpan={3}
                  className={`yearly-mix-year-head text-center ${yearTone(yi)} ${
                    yi > 0 ? "yearly-mix-year-start" : ""
                  }`}
                >
                  {y}
                </th>
              ))}
              <th colSpan={3} className="yearly-mix-total-head yearly-mix-year-start text-center">
                3개년 합계
              </th>
            </tr>
            <tr>
              {years.map((y, yi) => (
                <Fragment key={y}>
                  <th
                    className={`yearly-mix-subhead ${yearTone(yi)} ${
                      yi > 0 ? "yearly-mix-year-start" : ""
                    }`}
                  >
                    건수
                  </th>
                  <th className={`yearly-mix-subhead ${yearTone(yi)}`}>보증금</th>
                  <th className={`yearly-mix-subhead ${yearTone(yi)}`}>월세(만/월)</th>
                </Fragment>
              ))}
              <th className="yearly-mix-subhead yearly-mix-total-head yearly-mix-year-start">건수</th>
              <th className="yearly-mix-subhead yearly-mix-total-head">보증금</th>
              <th className="yearly-mix-subhead yearly-mix-total-head">월세(만/월)</th>
            </tr>
          </thead>
          <tbody>
            {data.types.map((row) => (
              <tr key={row.asset_type}>
                <td className="yearly-mix-sticky font-medium">{row.label}</td>
                {years.map((y, yi) => {
                  const cell = cellOf(row, y);
                  return (
                    <Fragment key={y}>
                      <td className={`${yearTone(yi)} ${yi > 0 ? "yearly-mix-year-start" : ""}`}>
                        {cell.count ? formatInt(cell.count) : "-"}
                      </td>
                      <td className={yearTone(yi)}>{moneyOrDash(cell.deposit_sum)}</td>
                      <td className={yearTone(yi)}>{moneyOrDash(cell.monthly_sum, true)}</td>
                    </Fragment>
                  );
                })}
                <td className="yearly-mix-total-cell yearly-mix-year-start font-semibold">
                  {row.total_count ? formatInt(row.total_count) : "-"}
                </td>
                <td className="yearly-mix-total-cell font-semibold">
                  {moneyOrDash(row.total_deposit_sum)}
                </td>
                <td className="yearly-mix-total-cell font-semibold">
                  {moneyOrDash(row.total_monthly_sum, true)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
