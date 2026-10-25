import { useMemo, useState } from "react";
import runJson from "../../../docs/lab/scale_effect_stage2.json";

type Score = { mape_unit?: number | null; mae_unit?: number | null; mae_total?: number | null };
type Fold = {
  fold: number;
  n_test?: number;
  turning_area?: number | null;
  extremum?: string | null;
  beta2?: number | null;
  turning_in_train_range?: boolean;
  quad_unit?: Score;
  loglog_unit?: Score;
  ridge?: { mape_unit?: number | null; alpha?: number | null; square_kept?: boolean | null };
  lasso?: { mape_unit?: number | null; alpha?: number | null };
  quad_ridge?: { mape_unit?: number | null; alpha?: number | null; square_coef?: number | null };
  quad_lasso?: { mape_unit?: number | null; alpha?: number | null; square_kept?: boolean | null };
};
type Cell = {
  id: string;
  name: string;
  domain: string;
  slice: string;
  size_label: string;
  controls: string;
  ask: string;
  sample_note?: string;
  year_from?: number;
  year_to?: number;
  status?: string;
  note?: string;
  fit?: {
    n?: number;
    p10?: number | null;
    p50?: number | null;
    p90?: number | null;
    reading?: { structure?: string; prediction?: string; y_compare?: string; penalty?: string };
    folds?: Fold[];
  };
};
type Payload = {
  title?: string;
  generated?: string;
  keeps?: string;
  method?: string;
  score_note?: string;
  cells?: Cell[];
};

const data = runJson as Payload;

function num(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export default function ScaleEffectStage2Lab() {
  const cells = data.cells ?? [];
  const [id, setId] = useState(cells[0]?.id ?? "");
  const cell = useMemo(() => cells.find((c) => c.id === id) ?? cells[0], [cells, id]);

  if (!cell) {
    return <p className="text-sm text-slate-600">2단계 기록이 없다.</p>;
  }
  const reading = cell.fit?.reading ?? {};
  return (
    <div className="space-y-4 text-sm">
      <p className="text-slate-700 dark:text-slate-200">
        {data.title}. {data.generated ? `기록 ${data.generated}. ` : ""}
        {data.keeps} <a className="underline" href="?tool=scale-effect">1단계</a>
      </p>
      <p className="text-slate-600 dark:text-slate-300">{data.method}</p>
      <p className="text-slate-600 dark:text-slate-300">{data.score_note}</p>
      <div className="flex flex-wrap gap-2">
        {cells.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => setId(c.id)}
            className={
              c.id === cell.id
                ? "px-3 py-1.5 rounded-md bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                : "px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-600"
            }
          >
            {c.name.split(" ").slice(-1)[0]}
          </button>
        ))}
      </div>
      <p className="text-slate-800 dark:text-slate-100">
        {cell.domain} · {cell.slice} · {cell.size_label} · {cell.controls}
        {cell.year_from && cell.year_to ? ` · ${cell.year_from}–${cell.year_to}` : ""}
        {cell.fit?.n ? ` · n ${cell.fit.n}` : ""}
        {cell.fit?.p10 != null ? ` · P10–P90 ${num(cell.fit.p10, 0)}–${num(cell.fit.p90, 0)}㎡` : ""}
      </p>
      <p className="text-slate-600 dark:text-slate-300">{cell.sample_note}</p>
      <p className="font-medium">묻는 점. {cell.ask}</p>
      {cell.status !== "ok" ? <p>{cell.note || cell.status}</p> : null}
      <section className="space-y-1">
        <h2 className="font-semibold">설명 구조</h2>
        <p>{reading.structure}</p>
      </section>
      <section className="space-y-1">
        <h2 className="font-semibold">예측</h2>
        <p>{reading.prediction}</p>
      </section>
      <section className="space-y-1">
        <h2 className="font-semibold">단가와 총액</h2>
        <p>{reading.y_compare}</p>
      </section>
      <section className="space-y-1">
        <h2 className="font-semibold">Ridge·Lasso</h2>
        <p>{reading.penalty}</p>
      </section>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs border-collapse">
          <thead>
            <tr className="text-left border-b border-slate-300 dark:border-slate-600">
              <th className="py-2 pr-3">겹</th>
              <th className="py-2 pr-3">전환면적</th>
              <th className="py-2 pr-3">극값</th>
              <th className="py-2 pr-3">학습범위</th>
              <th className="py-2 pr-3">log-log</th>
              <th className="py-2 pr-3">2차</th>
              <th className="py-2 pr-3">Ridge</th>
              <th className="py-2 pr-3">Lasso</th>
              <th className="py-2 pr-3">2차+Ridge</th>
              <th className="py-2 pr-3">2차+Lasso</th>
            </tr>
          </thead>
          <tbody>
            {(cell.fit?.folds ?? []).map((fold) => (
              <tr key={fold.fold} className="border-b border-slate-200 dark:border-slate-700">
                <td className="py-2 pr-3">{fold.fold}</td>
                <td className="py-2 pr-3">{num(fold.turning_area, 0)}</td>
                <td className="py-2 pr-3">{fold.extremum || "—"}</td>
                <td className="py-2 pr-3">{fold.turning_in_train_range ? "안" : "밖"}</td>
                <td className="py-2 pr-3">{num(fold.loglog_unit?.mape_unit)}</td>
                <td className="py-2 pr-3">{num(fold.quad_unit?.mape_unit)}</td>
                <td className="py-2 pr-3">{num(fold.ridge?.mape_unit)}</td>
                <td className="py-2 pr-3">{num(fold.lasso?.mape_unit)}</td>
                <td className="py-2 pr-3">{num(fold.quad_ridge?.mape_unit)}</td>
                <td className="py-2 pr-3">{num(fold.quad_lasso?.mape_unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
