import { useMemo, useState } from "react";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { TypeCorrBlock, TypeCorrMatrix } from "../types";
import { formatCorr } from "../utils/corr";

const SHORT: Record<string, string> = {
  토지: "토지",
  상가: "상가",
  공장: "공장",
  단독다가구: "단독",
  아파트: "아파트",
  오피스텔: "오피",
  연립다세대: "연립",
  분양권: "분양",
};

function cellFill(r: number | null, dark: boolean): string {
  if (r == null || Number.isNaN(r)) return dark ? "transparent" : "transparent";
  const a = Math.min(1, Math.abs(r));
  if (r >= 0) {
    return dark ? `rgba(251, 191, 36, ${0.12 + 0.72 * a})` : `rgba(217, 119, 6, ${0.1 + 0.55 * a})`;
  }
  return dark ? `rgba(96, 165, 250, ${0.12 + 0.72 * a})` : `rgba(37, 99, 235, ${0.08 + 0.5 * a})`;
}

function offDiagonalPairs(block: TypeCorrMatrix): { a: string; b: string; r: number }[] {
  const types = block.types;
  const out: { a: string; b: string; r: number }[] = [];
  for (let i = 0; i < types.length; i++) {
    for (let j = i + 1; j < types.length; j++) {
      const r = block.matrix[i]?.[j];
      if (r == null || Number.isNaN(r)) continue;
      out.push({ a: types[i], b: types[j], r });
    }
  }
  return out;
}

interface Props {
  data?: TypeCorrBlock | null;
}

export default function TypeCorrCard({ data }: Props) {
  const [mode, setMode] = useState<"amount" | "count">("amount");
  const dark = typeof document !== "undefined" && document.documentElement.classList.contains("dark");
  const block = mode === "amount" ? data?.amount : data?.count;
  const pairs = useMemo(() => (block ? offDiagonalPairs(block) : []), [block]);
  const together = useMemo(() => [...pairs].sort((x, y) => y.r - x.r).slice(0, 2), [pairs]);
  const opposite = useMemo(() => [...pairs].sort((x, y) => x.r - y.r).slice(0, 2), [pairs]);

  if (!block || !block.types?.length) return null;

  const n = block.n;
  const types = block.types;

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">유형 동조</h2>
        <StatsGlossaryHelp termId="type_corr" size="sm" />
        <div className="ml-auto flex gap-0.5 rounded-md bg-slate-100 p-0.5 text-[11px] dark:bg-slate-900/50">
          <button
            type="button"
            className={
              mode === "amount"
                ? "rounded px-2 py-1 font-medium bg-white shadow-sm dark:bg-slate-700"
                : "rounded px-2 py-1 text-slate-500 hover:text-slate-800 dark:text-slate-400"
            }
            onClick={() => setMode("amount")}
          >
            금액 비중
          </button>
          <button
            type="button"
            className={
              mode === "count"
                ? "rounded px-2 py-1 font-medium bg-white shadow-sm dark:bg-slate-700"
                : "rounded px-2 py-1 text-slate-500 hover:text-slate-800 dark:text-slate-400"
            }
            onClick={() => setMode("count")}
          >
            건수 비중
          </button>
        </div>
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        같은 결 전국 {n.toLocaleString("ko-KR")}곳의 3년 유형 비중 Pearson r. 크기(총액)가 아니라 구성.
      </p>

      <div className="mt-3 overflow-x-auto">
        <table className="border-collapse text-[10px] leading-none">
          <thead>
            <tr>
              <th className="p-0.5" />
              {types.map((t) => (
                <th key={t} className="p-0.5 font-medium text-slate-500" title={t}>
                  {SHORT[t] ?? t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {types.map((rowType, i) => (
              <tr key={rowType}>
                <th className="pr-1 text-left font-medium text-slate-500" title={rowType}>
                  {SHORT[rowType] ?? rowType}
                </th>
                {types.map((colType, j) => {
                  const r = block.matrix[i]?.[j] ?? null;
                  const label = r == null ? "—" : formatCorr(r, n, 3);
                  return (
                    <td
                      key={colType}
                      title={`${rowType} · ${colType}  r = ${label}`}
                      className="h-7 w-7 p-0 text-center tabular-nums"
                      style={{ background: cellFill(r, dark) }}
                    >
                      {i === j ? "" : label.replace("+", "")}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <div className="text-[11px] font-medium text-slate-500">같이 움직임</div>
          {together.map((p) => (
            <div key={`${p.a}-${p.b}`} className="mt-0.5 tabular-nums">
              {p.a} · {p.b}{" "}
              <span className="text-amber-700 dark:text-amber-300">{formatCorr(p.r, n, 3)}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="text-[11px] font-medium text-slate-500">반대로</div>
          {opposite.map((p) => (
            <div key={`${p.a}-${p.b}`} className="mt-0.5 tabular-nums">
              {p.a} · {p.b}{" "}
              <span className="text-sky-700 dark:text-sky-300">{formatCorr(p.r, n, 3)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
