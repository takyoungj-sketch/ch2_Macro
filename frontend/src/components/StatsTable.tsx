import clsx from "clsx";
import { simpleTableHeadClass } from "../constants/displayUi";
import type { StatsResult } from "../types";

const fmt = (v: number | null) =>
  v == null ? "-" : v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });

interface Props {
  title?: string;
  rows: Array<{ label: string; stats: StatsResult }>;
}

export default function StatsTable({ title, rows }: Props) {
  if (rows.length === 0) return null;

  const headRow = clsx(simpleTableHeadClass("neutral"), "uppercase tracking-wide");

  return (
    <div className="overflow-x-auto">
      {title && (
        <h3 className="text-sm font-semibold text-slate-600 mb-2">{title}</h3>
      )}
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className={headRow}>
            <th className="px-3 py-2 text-left">구분</th>
            <th className="px-3 py-2 text-right">건수</th>
            <th className="px-3 py-2 text-right text-blue-700 font-bold">평균단가</th>
            <th className="px-3 py-2 text-right">95% CI 하한</th>
            <th className="px-3 py-2 text-right">95% CI 상한</th>
            <th className="px-3 py-2 text-right">최솟값</th>
            <th className="px-3 py-2 text-right">25%</th>
            <th className="px-3 py-2 text-right">중위값</th>
            <th className="px-3 py-2 text-right">75%</th>
            <th className="px-3 py-2 text-right">최댓값</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ label, stats }) => (
            <tr
              key={label}
              className={clsx(
                "border-b border-slate-100 hover:bg-slate-50 transition-colors",
                stats.is_reliable && "font-medium"
              )}
            >
              <td className="px-3 py-2 text-slate-700">{label}</td>
              <td
                className={clsx(
                  "px-3 py-2 text-right tabular-nums",
                  stats.is_reliable
                    ? "text-amber-600 font-semibold"
                    : "text-slate-500"
                )}
              >
                {stats.count}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-blue-600 font-bold">
                {fmt(stats.mean)}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-500">
                {fmt(stats.ci_lower)}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-500">
                {fmt(stats.ci_upper)}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(stats.min)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(stats.p25)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(stats.median)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(stats.p75)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmt(stats.max)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-slate-400 mt-1">
        * 단위: 만원/㎡ &nbsp;|&nbsp; 건수 15건 이상 시 노란색 강조 &nbsp;|&nbsp; 95% 신뢰구간
      </p>
    </div>
  );
}
