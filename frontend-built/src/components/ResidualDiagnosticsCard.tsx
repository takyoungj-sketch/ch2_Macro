import { useMemo, useState } from "react";
import clsx from "clsx";
import type { ResidualDiagnostics, ResidualGroupSet } from "../types";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { BUILT_RESIDUAL_HELP } from "../utils/builtAnalysisHelp";
import { formatCoefName, fmtNum } from "../utils/regressionFormat";

/** 오차%는 부호가 뜻을 가진다 — 양수면 모형이 싸게 봤다는 것. */
function signed(v?: number | null, digits = 1) {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;
}

function fmtMoney(v?: number | null) {
  if (v == null || Number.isNaN(v)) return "—";
  if (Math.abs(v) >= 10000) return `${(v / 10000).toFixed(1)}억`;
  return `${Math.round(v).toLocaleString("ko-KR")}만`;
}

/** 잔차 대 예측금액. 0선을 기준으로 위아래 쏠림과 금액대별 폭을 본다. */
function ResidualScatter({ points }: { points: { x: number; y: number }[] }) {
  if (points.length < 5) return null;
  const w = 460;
  const h = 170;
  const pad = 26;
  const xs = points.map((p) => p.x);
  // 오차%는 −400%까지 벌어질 수 있어 그대로 그리면 0선 부근이 짜부라진다. 표시 범위를
  // 분위로 자르고 잘린 점은 경계에 붙여 «바깥에 있다»는 사실만 남긴다.
  const ys = points.map((p) => p.y).sort((a, b) => a - b);
  const q = (r: number) => ys[Math.min(ys.length - 1, Math.max(0, Math.floor(ys.length * r)))];
  const bound = Math.max(10, Math.min(120, Math.max(Math.abs(q(0.02)), Math.abs(q(0.98)))));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const spanX = maxX - minX || 1;
  const sx = (x: number) => pad + ((x - minX) / spanX) * (w - pad * 2);
  const sy = (y: number) => {
    const c = Math.max(-bound, Math.min(bound, y));
    return h / 2 - (c / bound) * (h / 2 - pad);
  };
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="w-full rounded border border-slate-200 bg-slate-50 dark:border-slate-600 dark:bg-slate-950/90"
      role="img"
      aria-label="예측금액 대비 오차율 산점도"
    >
      <line
        x1={pad}
        y1={sy(0)}
        x2={w - pad}
        y2={sy(0)}
        stroke="currentColor"
        className="text-slate-400 dark:text-slate-500"
        strokeWidth={1}
      />
      {points.map((p, i) => {
        const clipped = Math.abs(p.y) > bound;
        return (
          <circle
            key={i}
            cx={sx(p.x)}
            cy={sy(p.y)}
            r={clipped ? 1.6 : 2.2}
            className={clsx(
              clipped
                ? "fill-rose-500/70 dark:fill-rose-400/80"
                : "fill-slate-500/60 dark:fill-sky-400/75",
            )}
          />
        );
      })}
      <text x={pad} y={12} className="fill-slate-400 text-[9px]">
        오차% (위=과소평가) · 표시범위 ±{bound.toFixed(0)}%
      </text>
      <text x={pad} y={h - 6} className="fill-slate-400 text-[9px]">
        예측금액 {fmtMoney(minX)}
      </text>
      <text x={w - pad} y={h - 6} textAnchor="end" className="fill-slate-400 text-[9px]">
        {fmtMoney(maxX)}
      </text>
    </svg>
  );
}

function GroupTable({ set }: { set: ResidualGroupSet }) {
  const flagged = set.groups.filter((g) => g.significant);
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-100">
          {set.label}
        </span>
        <span className="text-[11px] text-slate-400 dark:text-slate-500">
          {flagged.length > 0
            ? `${flagged.length}개 집단이 나머지와 다르게 틀립니다`
            : "나머지와 다르게 틀리는 집단이 없습니다"}
          {set.omitted_n > 0 && ` · 표에서 뺀 ${fmtNum(set.omitted_n)}건 (10건 미만·분류 불가)`}
          {set.trimmed && " · 상위만"}
        </span>
      </div>
      <table className="w-full text-[11px] tabular-nums">
        <thead className="text-slate-400 dark:text-slate-500">
          <tr className="text-left">
            <th className="font-normal py-0.5">집단</th>
            <th className="font-normal py-0.5 text-right">n</th>
            <th className="font-normal py-0.5 text-right">전체 대비</th>
            <th className="font-normal py-0.5 text-right">중위 오차</th>
            <th className="font-normal py-0.5 text-right">MAPE</th>
          </tr>
        </thead>
        <tbody>
          {set.groups.map((g) => (
            <tr
              key={g.label}
              className={clsx(
                "border-t border-slate-100 dark:border-slate-700/60",
                g.significant && "bg-amber-50/70 dark:bg-amber-500/10",
              )}
            >
              <td className="py-0.5 pr-1 truncate max-w-[9rem]">
                {g.label}
                {g.significant && (
                  <span className="ml-1 text-amber-600 dark:text-amber-400" title="나머지 표본과 다름 (p<0.05)">
                    ●
                  </span>
                )}
              </td>
              <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">{fmtNum(g.n)}</td>
              <td
                className={clsx(
                  "py-0.5 text-right font-medium",
                  g.significant
                    ? g.excess_bias_pct > 0
                      ? "text-emerald-700 dark:text-emerald-400"
                      : "text-rose-700 dark:text-rose-400"
                    : "text-slate-400 dark:text-slate-500",
                )}
              >
                {signed(g.excess_bias_pct)}%p
              </td>
              <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                {signed(g.bias_pct)}%
              </td>
              <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                {g.mape_pct.toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ResidualDiagnosticsCard({
  diagnostics,
  onOpenTransactions,
}: {
  diagnostics: ResidualDiagnostics;
  onOpenTransactions?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const d = diagnostics;

  // 접힌 상태에서도 «볼 이유가 있는지»는 알려야 한다. 없으면 아무도 펼치지 않는다.
  const headline = useMemo(() => {
    const flagged = d.groups.flatMap((s) =>
      s.groups.filter((g) => g.significant).map((g) => ({ axis: s.label, ...g })),
    );
    if (!flagged.length) return "구조적으로 치우친 집단이 발견되지 않았습니다.";
    const worst = flagged.reduce((a, b) =>
      Math.abs(b.excess_bias_pct) > Math.abs(a.excess_bias_pct) ? b : a,
    );
    const axes = Array.from(new Set(flagged.map((f) => f.axis)));
    return `${axes.join("·")}에서 ${flagged.length}개 집단이 치우쳐 있습니다 — 가장 큰 곳은 ${worst.axis} «${worst.label}» ${signed(worst.excess_bias_pct)}%p.`;
  }, [d.groups]);

  return (
    <div className="card space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-sm text-slate-800 dark:text-slate-100">
            잔차 진단 — 이 식이 어디서 틀리나
          </h3>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
            n={fmtNum(d.n)} · 중위 오차 {signed(d.bias_pct)}%
            {d.mean_bias_pct != null && ` · 평균 ${signed(d.mean_bias_pct)}%`}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <AnalysisHelpPanel explain={BUILT_RESIDUAL_HELP} />
          <button
            type="button"
            className="px-3 py-1.5 text-sm rounded-md border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-900/70 dark:text-slate-300 dark:hover:bg-slate-700"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
          >
            {open ? "접기" : "펼치기"}
          </button>
        </div>
      </div>

      <p className="text-xs text-slate-600 dark:text-slate-300">{headline}</p>

      {!open && d.het_note && (
        <p className="text-[11px] text-slate-500 dark:text-slate-400">{d.het_note}</p>
      )}

      {open && (
        <div className="space-y-3 pt-1">
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            {d.residual_definition}
          </p>
          {d.bias_note && (
            <p className="text-[11px] text-slate-500 dark:text-slate-400 border-l-2 border-slate-200 pl-2 dark:border-slate-600">
              {d.bias_note}
            </p>
          )}

          <section className="space-y-1">
            <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-100">
              금액대별 오차
            </h4>
            {d.het_note && (
              <p className="text-[11px] text-slate-500 dark:text-slate-400">{d.het_note}</p>
            )}
            <ResidualScatter points={d.points} />
            {d.scale_bins.length > 0 && (
              <table className="w-full text-[11px] tabular-nums mt-1">
                <thead className="text-slate-400 dark:text-slate-500">
                  <tr className="text-left">
                    <th className="font-normal py-0.5">예측금액 분위</th>
                    <th className="font-normal py-0.5 text-right">n</th>
                    <th className="font-normal py-0.5 text-right">중위 금액</th>
                    <th className="font-normal py-0.5 text-right">중위 절대오차</th>
                    <th className="font-normal py-0.5 text-right">오차 산포</th>
                  </tr>
                </thead>
                <tbody>
                  {d.scale_bins.map((b) => (
                    <tr key={b.label} className="border-t border-slate-100 dark:border-slate-700/60">
                      <td className="py-0.5">{b.label}</td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {fmtNum(b.n)}
                      </td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {fmtMoney(b.fitted_median)}
                      </td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {b.abs_pct_median.toFixed(1)}%
                      </td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {b.spread_pct.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {d.groups.length > 0 && (
            <section className="space-y-2.5">
              <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-100">
                집단별 치우침
              </h4>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                <strong className="text-slate-600 dark:text-slate-200">전체 대비</strong>가 읽을
                숫자입니다. 표본 전체가 공통으로 가진 치우침을 뺀 값이라, 그 집단만 다르게 틀리는
                정도를 나타냅니다. ● 표시는 나머지 표본과 다르다는 뜻(p&lt;0.05)입니다.
              </p>
              {d.groups.map((s) => (
                <GroupTable key={s.key} set={s} />
              ))}
            </section>
          )}

          {d.influential.length > 0 && (
            <section className="space-y-1">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-100">
                  결과를 끌고 있는 거래
                </h4>
                {onOpenTransactions && (
                  <button
                    type="button"
                    className="text-[11px] underline text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    onClick={onOpenTransactions}
                  >
                    거래목록 열기
                  </button>
                )}
              </div>
              {d.refit_note && (
                <p className="text-[11px] text-slate-500 dark:text-slate-400">{d.refit_note}</p>
              )}
              <table className="w-full text-[11px] tabular-nums">
                <thead className="text-slate-400 dark:text-slate-500">
                  <tr className="text-left">
                    <th className="font-normal py-0.5">위치</th>
                    <th className="font-normal py-0.5 text-right">연도</th>
                    <th className="font-normal py-0.5 text-right">실제</th>
                    <th className="font-normal py-0.5 text-right">예측</th>
                    <th className="font-normal py-0.5 text-right">오차</th>
                    <th className="font-normal py-0.5 text-right">연면적</th>
                  </tr>
                </thead>
                <tbody>
                  {d.influential.map((t) => (
                    <tr key={t.rank} className="border-t border-slate-100 dark:border-slate-700/60">
                      <td className="py-0.5 pr-1 truncate max-w-[9rem]">{t.label}</td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {t.contract_year ?? "—"}
                      </td>
                      <td className="py-0.5 text-right">{fmtMoney(t.price)}</td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {fmtMoney(t.predicted)}
                      </td>
                      <td
                        className={clsx(
                          "py-0.5 text-right font-medium",
                          (t.error_pct ?? 0) > 0
                            ? "text-emerald-700 dark:text-emerald-400"
                            : "text-rose-700 dark:text-rose-400",
                        )}
                      >
                        {signed(t.error_pct)}%
                      </td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {t.gross_area != null ? `${fmtNum(t.gross_area)}㎡` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {d.refit_shifts.length > 0 && (
                <details className="text-[11px] text-slate-500 dark:text-slate-400">
                  <summary className="cursor-pointer">이 거래를 뺐을 때 계수 변화</summary>
                  <table className="w-full tabular-nums mt-1">
                    <tbody>
                      {d.refit_shifts.map((c) => (
                        <tr key={c.name} className="border-t border-slate-100 dark:border-slate-700/60">
                          <td className="py-0.5 pr-1">{formatCoefName(c.name)}</td>
                          <td className="py-0.5 text-right">{c.before.toFixed(4)}</td>
                          <td className="py-0.5 text-center text-slate-400">→</td>
                          <td className="py-0.5 text-right">{c.after.toFixed(4)}</td>
                          <td className="py-0.5 text-right">
                            {c.shift_se != null ? `${c.shift_se.toFixed(1)} SE` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              )}
            </section>
          )}

          {d.warning && (
            <p className="text-[11px] badge-warn">{d.warning}</p>
          )}
        </div>
      )}
    </div>
  );
}
