import clsx from "clsx";
import { shortType } from "../copy/insight02";

export function fmtSigned(r: number | null | undefined): string {
  if (r == null || Number.isNaN(r)) return "—";
  const sign = r > 0 ? "+" : "";
  return `${sign}${r.toFixed(2)}`;
}

function cellBg(r: number): string {
  const t = Math.max(-1, Math.min(1, r));
  if (t >= 0) {
    const a = 0.1 + 0.72 * t;
    return `rgba(217, 119, 6, ${a})`;
  }
  const a = 0.1 + 0.72 * -t;
  return `rgba(37, 99, 235, ${a})`;
}

export default function CorrHeatmap({
  types,
  getR,
  selected,
  onSelect,
  missingLabel,
}: {
  types: string[];
  getR: (a: string, b: string) => number | null;
  selected: { a: string; b: string } | null;
  onSelect: (a: string, b: string) => void;
  missingLabel?: string;
}) {
  const isSel = (a: string, b: string) =>
    !!selected && ((selected.a === a && selected.b === b) || (selected.a === b && selected.b === a));

  return (
    <div className="overflow-x-auto">
      <table className="text-[11px] border-collapse min-w-[36rem]">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-white dark:bg-slate-800 p-1 text-left font-medium text-slate-500 w-14">
              {" "}
            </th>
            {types.map((t) => (
              <th key={t} className="p-1 font-medium text-slate-600 dark:text-slate-300 text-center whitespace-nowrap">
                {shortType(t)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {types.map((row) => (
            <tr key={row}>
              <th className="sticky left-0 z-10 bg-white dark:bg-slate-800 p-1 text-left font-medium text-slate-700 dark:text-slate-200 whitespace-nowrap">
                {shortType(row)}
              </th>
              {types.map((col) => {
                if (row === col) {
                  return (
                    <td key={col} className="p-0">
                      <div className="m-0.5 h-9 flex items-center justify-center text-slate-300 dark:text-slate-600">
                        —
                      </div>
                    </td>
                  );
                }
                const r = getR(row, col);
                const active = isSel(row, col);
                const strong = r != null && Math.abs(r) >= 0.55;
                return (
                  <td key={col} className="p-0">
                    <button
                      type="button"
                      className={clsx(
                        "m-0.5 h-9 w-full min-w-[2.75rem] rounded text-[11px] tabular-nums",
                        active && "ring-2 ring-slate-800 dark:ring-slate-200",
                        r == null
                          ? "text-slate-400"
                          : strong
                            ? "text-white"
                            : "text-slate-800 dark:text-slate-100",
                      )}
                      style={r == null ? undefined : { backgroundColor: cellBg(r) }}
                      onClick={() => onSelect(row, col)}
                      aria-label={`${row} × ${col} ${fmtSigned(r)}`}
                      aria-pressed={active}
                    >
                      {r == null ? missingLabel || "—" : fmtSigned(r)}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 flex items-center gap-2 text-[11px] text-slate-500">
        <span>−1</span>
        <span
          className="h-2 flex-1 max-w-[12rem] rounded"
          style={{
            background: "linear-gradient(90deg, rgb(37,99,235), rgb(241,245,249), rgb(217,119,6))",
          }}
        />
        <span>+1</span>
      </p>
    </div>
  );
}
