import type { ModelComparison, ResponseScale } from "../types";

function stars(n: number) {
  return "★".repeat(Math.max(0, Math.min(5, n))) + "☆".repeat(Math.max(0, 5 - n));
}

export function ModelComparisonCard({
  cmp,
  selected,
}: {
  cmp: ModelComparison;
  selected: ResponseScale;
}) {
  const rows: { type: ResponseScale; label: string; m: ModelComparison["log"] }[] = [
    { type: "log", label: "로그회귀", m: cmp.log },
    { type: "linear", label: "선형회귀", m: cmp.linear },
  ];
  const basis = cmp.metric_basis === "cv" ? "교차검증" : "표본내";
  return (
    <div className="rounded-md border border-slate-200 dark:border-slate-600 p-2 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium text-slate-700 dark:text-slate-200">
          모델 비교 ({basis})
        </span>
        <span className="text-[11px] text-amber-600 dark:text-amber-400" title={cmp.confidence_label ?? ""}>
          신뢰 {stars(cmp.confidence_stars)} {cmp.confidence_label ?? ""}
        </span>
      </div>
      <table className="w-full border-collapse text-[11px]">
        <thead>
          <tr className="text-slate-500 dark:text-slate-400">
            <th className="text-left font-normal py-0.5">모델</th>
            <th className="text-right font-normal">조정 R²</th>
            <th className="text-right font-normal">MAPE</th>
            <th className="text-right font-normal">RMSE(만원)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ type, label, m }) => {
            const isRec = cmp.recommended === type;
            const isSel = selected === type;
            return (
              <tr
                key={type}
                className={isSel ? "bg-indigo-50 dark:bg-indigo-950/40 font-medium" : undefined}
              >
                <td className="py-0.5 text-slate-700 dark:text-slate-200">
                  {label}
                  {isRec && (
                    <span className="ml-1 text-[10px] text-emerald-600 dark:text-emerald-400">권장</span>
                  )}
                </td>
                <td className="text-right tabular-nums">{m?.adj_r_squared?.toFixed(3) ?? "—"}</td>
                <td className="text-right tabular-nums">{m?.mape != null ? `${m.mape}%` : "—"}</td>
                <td className="text-right tabular-nums">
                  {m?.rmse != null ? Math.round(m.rmse).toLocaleString("ko-KR") : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
