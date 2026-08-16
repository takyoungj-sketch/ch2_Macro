import { Fragment } from "react";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { YearlyMix, YearlyMixType, YearlyTypeCell } from "../types";
import { YEARLY_MIX_TYPES } from "../types";
import { formatAmountManwon, formatInt, formatYoy } from "../utils/format";

interface Props {
  yearlyMix: YearlyMix;
}

function cellOf(yearlyMix: YearlyMix, year: number, type: YearlyMixType): YearlyTypeCell {
  const yearBucket = yearlyMix[String(year)] as Record<YearlyMixType, YearlyTypeCell> | undefined;
  return yearBucket?.[type] ?? { count: 0, amount: 0 };
}

function yoy(curr: number, prev: number): number | null {
  if (!prev) return null;
  return ((curr - prev) / prev) * 100;
}

/** 연도 그룹 교차 배경 — 홀수/짝수 연도 컬럼을 번갈아 구분 */
function yearTone(yearIndex: number): string {
  return yearIndex % 2 === 0
    ? "bg-slate-50/90 dark:bg-slate-900/35"
    : "bg-white dark:bg-slate-800/40";
}

export default function YearlyMixTable({ yearlyMix }: Props) {
  const years = yearlyMix.years;
  const totalCountByYear = years.map((y) =>
    YEARLY_MIX_TYPES.reduce((sum, t) => sum + cellOf(yearlyMix, y, t).count, 0),
  );
  const totalAmountByYear = years.map((y) =>
    YEARLY_MIX_TYPES.reduce((sum, t) => sum + cellOf(yearlyMix, y, t).amount, 0),
  );

  return (
    <div className="card p-5">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">3개년 부동산 거래 현황 (8대 시장유형)</h2>
        <StatsGlossaryHelp termId="yearly_mix" size="sm" />
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        상가 = 상업업무 + 집합상가, 공장 = 공장창고 + 집합공장 (Profile 집계 단계에서만 병합)
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
                  colSpan={2}
                  className={`yearly-mix-year-head text-center ${yearTone(yi)} ${
                    yi > 0 ? "yearly-mix-year-start" : ""
                  }`}
                >
                  {y}
                </th>
              ))}
              <th colSpan={2} className="yearly-mix-total-head yearly-mix-year-start text-center">
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
                  <th className={`yearly-mix-subhead ${yearTone(yi)}`}>금액</th>
                </Fragment>
              ))}
              <th className="yearly-mix-subhead yearly-mix-total-head yearly-mix-year-start">건수</th>
              <th className="yearly-mix-subhead yearly-mix-total-head">금액</th>
            </tr>
          </thead>
          <tbody>
            {YEARLY_MIX_TYPES.map((type) => {
              const totals = yearlyMix.totals_by_type[type];
              const isDominant = yearlyMix.dominant_type === type;
              return (
                <tr key={type} className={isDominant ? "bg-amber-50 dark:bg-amber-900/20" : undefined}>
                  <td className="yearly-mix-sticky font-medium">
                    {type}
                    {isDominant && <span className="ml-1 text-xs text-amber-600 dark:text-amber-400">★</span>}
                  </td>
                  {years.map((y, yi) => {
                    const cell = cellOf(yearlyMix, y, type);
                    return (
                      <Fragment key={y}>
                        <td
                          className={`${yearTone(yi)} ${yi > 0 ? "yearly-mix-year-start" : ""}`}
                        >
                          {formatInt(cell.count)}
                        </td>
                        <td className={yearTone(yi)}>{formatAmountManwon(cell.amount)}</td>
                      </Fragment>
                    );
                  })}
                  <td className="yearly-mix-total-cell yearly-mix-year-start font-semibold">
                    {formatInt(totals?.count)}
                  </td>
                  <td className="yearly-mix-total-cell font-semibold">
                    {formatAmountManwon(totals?.amount)}
                  </td>
                </tr>
              );
            })}
            <tr className="yearly-mix-sum-row font-semibold">
              <td className="yearly-mix-sticky">합계</td>
              {years.map((y, i) => (
                <Fragment key={y}>
                  <td className={`${yearTone(i)} ${i > 0 ? "yearly-mix-year-start" : ""}`}>
                    {formatInt(totalCountByYear[i])}
                  </td>
                  <td className={yearTone(i)}>{formatAmountManwon(totalAmountByYear[i])}</td>
                </Fragment>
              ))}
              <td className="yearly-mix-total-cell yearly-mix-year-start">
                {formatInt(yearlyMix.total_count_3y)}
              </td>
              <td className="yearly-mix-total-cell">{formatAmountManwon(yearlyMix.total_amount_3y)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <TrendMini
          title="총 거래건수 추세"
          years={years}
          values={totalCountByYear}
          formatValue={(v) => `${formatInt(v)}건`}
        />
        <TrendMini
          title="총 거래액 추세"
          years={years}
          values={totalAmountByYear}
          formatValue={(v) => formatAmountManwon(v)}
        />
      </div>
    </div>
  );
}

function TrendMini({
  title,
  years,
  values,
  formatValue,
}: {
  title: string;
  years: number[];
  values: number[];
  formatValue: (v: number) => string;
}) {
  const max = Math.max(...values, 1);
  return (
    <div className="rounded-md bg-slate-50 p-3 dark:bg-slate-900/40">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">{title}</div>
      <div className="mt-2 flex items-end gap-3">
        {years.map((y, i) => {
          const prev = i > 0 ? values[i - 1] : NaN;
          const change = i > 0 ? yoy(values[i], prev) : null;
          const heightPct = Math.max(6, Math.round((values[i] / max) * 100));
          return (
            <div key={y} className="flex flex-1 flex-col items-center gap-1">
              <div className="flex h-16 w-full items-end">
                <div
                  className="w-full rounded-sm bg-slate-400 dark:bg-slate-500"
                  style={{ height: `${heightPct}%` }}
                />
              </div>
              <div className="text-[11px] font-medium">{formatValue(values[i])}</div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400">
                {y}
                {change !== null && (
                  <span className={change >= 0 ? "text-rose-500" : "text-blue-500"}> {formatYoy(change)}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
