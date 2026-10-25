import { useMemo, useState } from "react";
import runJson from "../../../docs/lab/scale_effect_lab.json";

type FitModel = { mape?: number | null; mae?: number | null; folds?: number };
type Coef = { beta?: number | null; p?: number | null };
type Fit = {
  n?: number;
  status?: string;
  loglog_beta?: Coef;
  quad_beta2?: Coef;
  turning_area?: number | null;
  turning_in_range?: boolean;
  explain_gain?: boolean;
  models?: Record<string, FitModel>;
};
type Cell = {
  role: string;
  role_label: string;
  status?: string;
  thin?: boolean;
  name?: string;
  slice?: string;
  n?: number;
  n_used?: number;
  spread?: number;
  controls?: string;
  fit?: Fit;
};
type Domain = {
  id: string;
  label: string;
  size_label?: string;
  y_label?: string;
  year_from?: number;
  year_to?: number;
  note?: string;
  questions?: { explain?: string; predict?: string; recommend?: string };
  cells?: Cell[];
};
type Payload = {
  title?: string;
  term?: string;
  generated?: string;
  window?: string;
  models?: string[];
  score?: string;
  hold?: string;
  domains?: Domain[];
};

const data = runJson as Payload;
const MODEL_KEYS = [
  ["linear", "선형"],
  ["loglog", "log-log"],
  ["quad", "2차"],
  ["ridge", "Ridge"],
  ["lasso", "Lasso"],
  ["quad_ridge", "2차+Ridge"],
  ["quad_lasso", "2차+Lasso"],
] as const;

function num(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export default function ScaleEffectLab() {
  const domains = data.domains ?? [];
  const [id, setId] = useState(domains[0]?.id ?? "");
  const domain = useMemo(() => domains.find((d) => d.id === id) ?? domains[0], [domains, id]);

  if (!domain) {
    return <p className="text-sm text-slate-600">기록이 아직 없다. backend에서 실험을 다시 돌리면 이 창이 채워진다.</p>;
  }

  const q = domain.questions ?? {};
  return (
    <div className="space-y-4 text-sm">
      <p className="text-slate-700 dark:text-slate-200">
        <a className="underline" href="?tool=scale-effect-2">2단계(네 지역)</a>
        {" · "}
        {data.term}. {data.window}
        {data.generated ? ` · 기록 ${data.generated}` : ""}. {domain.year_from && domain.year_to ? `${domain.year_from}–${domain.year_to}. ` : ""}
        규모는 {domain.size_label}, 결과는 {domain.y_label}.
      </p>
      <p className="text-slate-600 dark:text-slate-300">{data.score}</p>
      <p className="text-slate-600 dark:text-slate-300">{data.hold}</p>
      {domain.note ? <p className="text-slate-600 dark:text-slate-300">{domain.note}</p> : null}

      <div className="flex flex-wrap gap-2">
        {domains.map((d) => (
          <button
            key={d.id}
            type="button"
            onClick={() => setId(d.id)}
            className={
              d.id === domain.id
                ? "px-3 py-1.5 rounded-md bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                : "px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-600"
            }
          >
            {d.label}
          </button>
        ))}
      </div>

      <ol className="space-y-2 list-decimal pl-5">
        <li>{q.explain || "설명 비교가 없다."}</li>
        <li>{q.predict || "예측 비교가 없다."}</li>
        <li>{q.recommend || "추천 규칙이 없다."}</li>
      </ol>

      <div className="overflow-x-auto">
        <table className="min-w-full text-xs border-collapse">
          <thead>
            <tr className="text-left border-b border-slate-300 dark:border-slate-600">
              <th className="py-2 pr-3">칸</th>
              <th className="py-2 pr-3">지역</th>
              <th className="py-2 pr-3">n</th>
              <th className="py-2 pr-3">P90/P50</th>
              <th className="py-2 pr-3">log-log β</th>
              <th className="py-2 pr-3">전환 면적</th>
              {MODEL_KEYS.map(([key, label]) => (
                <th key={key} className="py-2 pr-3">
                  {label} MAPE
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(domain.cells ?? []).map((cell) => {
              const fit = cell.fit;
              const beta = fit?.loglog_beta?.beta;
              return (
                <tr key={cell.role} className="border-b border-slate-200 dark:border-slate-700 align-top">
                  <td className="py-2 pr-3 whitespace-nowrap">{cell.role_label}</td>
                  <td className="py-2 pr-3">
                    {cell.name || cell.status || "—"}
                    {cell.slice ? <div className="text-slate-500">{cell.slice}</div> : null}
                    {cell.controls ? <div className="text-slate-500">{cell.controls}</div> : null}
                  </td>
                  <td className="py-2 pr-3 whitespace-nowrap">
                    {cell.n_used ?? fit?.n ?? cell.n ?? "—"}
                    {cell.n && cell.n_used && cell.n !== cell.n_used ? <div className="text-slate-500">모집단 {cell.n}</div> : null}
                  </td>
                  <td className="py-2 pr-3">{num(cell.spread, 2)}</td>
                  <td className="py-2 pr-3">{beta == null ? "—" : num(beta, 3)}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">
                    {fit?.turning_area == null ? "—" : `${num(fit.turning_area, 0)}㎡`}
                    {fit?.turning_in_range ? <div>범위 안</div> : fit?.status === "ok" ? <div className="text-slate-500">범위 밖</div> : null}
                    {fit?.explain_gain ? <div>설명 우세</div> : null}
                  </td>
                  {MODEL_KEYS.map(([key]) => (
                    <td key={key} className="py-2 pr-3">
                      {num(fit?.models?.[key]?.mape, 2)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
