import clsx from "clsx";
import { simpleTableHeadClass, simpleTableHeadStickyBgClass } from "../constants/displayUi";
import { useAppStore } from "../store";
import type { YearlyTradeStat } from "../types";

interface Props {
  title?: string;
  /** 제목 행 생략 (무료 패널 등) */
  hideTitle?: boolean;
  /** 미정의·구버전 API 대비 */
  rows?: YearlyTradeStat[] | null;
}

const fmtInt = (n: number) => n.toLocaleString("ko-KR", { maximumFractionDigits: 0 });

const fmtArea = (n: number) =>
  n.toLocaleString("ko-KR", { maximumFractionDigits: 1, minimumFractionDigits: 0 });

const num = (v: unknown, fallback = 0): number => {
  const x = Number(v);
  return Number.isFinite(x) ? x : fallback;
};

const fmtUnit = (n: number | null) =>
  n == null
    ? "-"
    : n.toLocaleString("ko-KR", { maximumFractionDigits: 1, minimumFractionDigits: 0 });

/** 연도별 전체 거래·총거래액·총면적·가중 단가(만원/㎡) */
export default function YearlyStatsTable({
  title = "연도별 전체 거래",
  hideTitle = false,
  rows,
}: Props) {
  const uiTableTone = useAppStore((s) => s.uiTableTone);
  const list = rows ?? [];
  if (list.length === 0) return null;

  const years = list.map((r) => r.year);

  return (
    <div className={hideTitle ? "space-y-0" : "space-y-1.5"}>
      {!hideTitle && title ? (
        <h3 className="text-sm font-semibold text-slate-600">{title}</h3>
      ) : null}
      <div className="overflow-x-auto border border-slate-200 rounded-lg">
        <table className="border-collapse bg-white text-[11px] leading-tight min-w-max">
          <thead>
            <tr className={simpleTableHeadClass(uiTableTone)}>
              <th
                className={clsx(
                  "border border-slate-200 px-2 py-1.5 text-left font-medium sticky left-0 z-10",
                  simpleTableHeadStickyBgClass(uiTableTone)
                )}
              >
                구분
              </th>
              {years.map((y) => (
                <th
                  key={y}
                  className="border border-slate-200 px-2 py-1.5 text-center font-medium tabular-nums min-w-[4.25rem]"
                >
                  {y}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-slate-800">
            <tr>
              <td className="border border-slate-200 px-2 py-1 text-slate-600 sticky left-0 bg-white z-10">
                개수
              </td>
              {list.map((r) => (
                <td key={`c-${r.year}`} className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                  {fmtInt(num(r.count))}
                </td>
              ))}
            </tr>
            <tr>
              <td className="border border-slate-200 px-2 py-1 text-slate-600 sticky left-0 bg-white z-10">
                총거래액(만원)
              </td>
              {list.map((r) => (
                <td key={`p-${r.year}`} className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                  {fmtInt(Math.round(num(r.total_price_10k_sum)))}
                </td>
              ))}
            </tr>
            <tr>
              <td className="border border-slate-200 px-2 py-1 text-slate-600 sticky left-0 bg-white z-10">
                총면적(㎡)
              </td>
              {list.map((r) => (
                <td key={`a-${r.year}`} className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                  {fmtArea(num(r.area_sqm_sum))}
                </td>
              ))}
            </tr>
            <tr>
              <td className="border border-slate-200 px-2 py-1 text-slate-600 sticky left-0 bg-white z-10">
                단가(만원/㎡)
              </td>
              {list.map((r) => (
                <td
                  key={`u-${r.year}`}
                  className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-bold"
                >
                  {fmtUnit(typeof r.unit_price_per_sqm === "number" ? r.unit_price_per_sqm : null)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
