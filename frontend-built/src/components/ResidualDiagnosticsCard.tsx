import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import type { InfluentialTransaction, ResidualDiagnostics, ResidualGroupSet } from "../types";
import DraggableModalShell from "./DraggableModalShell";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { BUILT_RESIDUAL_HELP } from "../utils/builtAnalysisHelp";
import { formatAssetTypeLabel, formatCoefName, fmtNum } from "../utils/regressionFormat";

function groupLabel(set: ResidualGroupSet, label: string) {
  return set.key === "asset_type" ? formatAssetTypeLabel(label) : label;
}

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
  const h = 110;
  const left = 44;
  const right = w - 16;
  const top = 14;
  const bottom = h - 30;
  const xs = points.map((p) => p.x);
  // 오차%는 −400%까지 벌어질 수 있어 그대로 그리면 0선 부근이 짜부라진다. 표시 범위를
  // 분위로 자르고 잘린 점은 경계에 붙여 «바깥에 있다»는 사실만 남긴다.
  const ys = points.map((p) => p.y).sort((a, b) => a - b);
  const q = (r: number) => ys[Math.min(ys.length - 1, Math.max(0, Math.floor(ys.length * r)))];
  const bound = Math.max(10, Math.min(120, Math.max(Math.abs(q(0.02)), Math.abs(q(0.98)))));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const spanX = maxX - minX || 1;
  const sx = (x: number) => left + ((x - minX) / spanX) * (right - left);
  const sy = (y: number) => {
    const c = Math.max(-bound, Math.min(bound, y));
    return (top + bottom) / 2 - (c / bound) * (bottom - top) / 2;
  };
  const tickStep = bound >= 100 ? 100 : bound >= 50 ? 50 : bound >= 20 ? 20 : 10;
  const yTicks = [-tickStep, 0, tickStep];
  const xTicks = Array.from({ length: 5 }, (_, index) => minX + (maxX - minX) * index / 4);
  const clippedCount = points.filter(p => Math.abs(p.y) > bound).length;
  return (
    <div className="space-y-1">
    <p className="text-[11px] font-normal text-slate-500 dark:text-slate-400">오차율(%)</p>
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="w-full rounded border border-slate-200 bg-slate-50 dark:border-slate-600 dark:bg-slate-950/90"
      role="img"
      aria-label="예측금액 대비 오차율 산점도"
    >
      <line
        x1={left}
        y1={sy(0)}
        x2={right}
        y2={sy(0)}
        stroke="currentColor"
        className="text-slate-400 dark:text-slate-500"
        strokeWidth={1}
      />
      {yTicks.map(value => <g key={value}>
        {value !== 0 && <line x1={left} x2={right} y1={sy(value)} y2={sy(value)} stroke="currentColor" strokeDasharray="2 3" className="text-slate-300 dark:text-slate-700" strokeWidth={0.5} />}
        <text x={left - 5} y={sy(value) + 3} textAnchor="end" style={{ fontSize: 9 }} className="fill-slate-500 dark:fill-slate-400">{value > 0 ? "+" : ""}{value}%</text>
      </g>)}
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
          ><title>{`예측금액 ${fmtMoney(p.x)}원 · 오차율 ${signed(p.y)}%`}</title></circle>
        );
      })}
      {xTicks.map((value, index) => <g key={index}>
        <line x1={sx(value)} x2={sx(value)} y1={bottom + 2} y2={bottom + 5} stroke="currentColor" className="text-slate-400" strokeWidth={0.5} />
        <text x={sx(value)} y={bottom + 17} textAnchor="middle" style={{ fontSize: 9 }} className="fill-slate-500 dark:fill-slate-400">{fmtMoney(value)}</text>
      </g>)}
    </svg>
    <p className="text-center text-[11px] font-normal text-slate-500 dark:text-slate-400">예측금액</p>
    <p className="text-xs text-slate-500 dark:text-slate-400">
      표시범위 ±{bound.toFixed(0)}%
      {clippedCount > 0 && <span className="ml-2 text-rose-700 dark:text-rose-300">범위 밖 {fmtNum(clippedCount)}건은 붉은 점으로 경계에 표시했습니다.</span>}
    </p>
    </div>
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
            ? `오차 차이가 확인된 집단 ${flagged.length}개`
            : "통계적으로 확인된 차이가 없습니다"}
          {set.omitted_n > 0 && ` · 표에서 제외 ${fmtNum(set.omitted_n)}건`}
          {set.trimmed && " · 일부 집단만 표시"}
        </span>
      </div>
      <div className="overflow-x-auto"><table className="w-full text-xs tabular-nums">
        <thead className="text-slate-400 dark:text-slate-500">
          <tr className="text-left">
            <th className="font-normal py-0.5">집단</th>
            <th className="font-normal py-0.5 text-right">n</th>
            <th className="font-normal py-0.5 text-right" title="해당 집단의 오차 중앙값에서 그 집단을 제외한 다른 거래의 오차 중앙값을 뺀 값입니다. 비교 기준 도움말에서 자세히 확인할 수 있습니다.">오차율 차이(%p)</th>
            <th className="font-normal py-0.5 text-right">오차 중앙값</th>
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
              <td className="py-1.5 pr-2 break-words">
                {groupLabel(set, g.label)}
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
      </table></div>
    </div>
  );
}

export default function ResidualDiagnosticsCard({
  diagnostics,
  onOpenTransactions,
  scopeLabel,
}: {
  diagnostics: ResidualDiagnostics;
  onOpenTransactions?: () => void;
  scopeLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<InfluentialTransaction | null>(null);
  useEffect(() => setSelectedTrade(null), [diagnostics]);
  const d = diagnostics;
  const amountHelp = {
    ...BUILT_RESIDUAL_HELP, spec_id: "built_residual_amount_ui", title: "금액대별 오차 읽기",
    summary: "예측금액이 낮거나 높은 구간에서 오차의 크기가 어떻게 달라지는지 확인합니다.",
    interpretation: [
      "오차율이 양수이면 실제 금액이 예측보다 높고, 음수이면 예측보다 낮습니다.",
      "분위는 기존 예측금액 기준 구간입니다. 절대오차율 중앙값은 오차의 크기, 오차율 표준편차는 거래 사이의 퍼짐을 나타냅니다.",
      "산점도의 범위 밖 거래는 경계에 붉게 표시합니다. 점에 마우스를 올리면 표시범위로 자르기 전 오차율을 확인할 수 있습니다.",
      ...[d.residual_definition, d.bias_note, d.het_note].filter((note): note is string => Boolean(note)),
    ],
    limitations: ["적합에 사용한 표본 안의 오차입니다. 새로운 거래의 예측오차는 CV-MAPE를 함께 확인해 주세요."], presets: [],
  };
  const groupHelp = {
    ...BUILT_RESIDUAL_HELP, spec_id: "built_residual_groups_ui", title: "조건별 오차 비교 기준",
    summary: "같은 조건의 거래에서 오차가 어느 쪽으로 나타나는지 비교합니다.",
    formula: "오차율 차이(%p) = 해당 집단의 오차 중앙값 − 그 집단을 제외한 다른 거래의 오차 중앙값",
    interpretation: [
      "● 표시는 기존 Mann–Whitney 양측 검정에서 p<0.05인 집단입니다. 검정은 오차 분포의 차이를 확인하며, 중앙값 차이 자체를 검정한 결과는 아닙니다.",
      "표시가 없는 집단은 차이가 통계적으로 확인되지 않았습니다. 수치 차이만으로 특정 조건의 효과를 단정하지 마세요.",
      "10건 미만이거나 분류할 수 없는 거래는 집단 표에서 제외합니다. 집단이 많으면 기존 기준에 따른 일부 집단만 표시합니다.",
    ], limitations: ["집단별 차이는 인과관계를 뜻하지 않습니다. 거래 구성과 표본 수를 함께 확인해 주세요."], presets: [],
  };
  const influenceHelp = {
    ...BUILT_RESIDUAL_HELP, spec_id: "built_residual_influence_ui", title: "주요 영향 거래 선정 기준",
    summary: "회귀계수에 미치는 영향이 큰 거래를 Cook 거리 순으로 확인합니다.",
    formula: undefined,
    interpretation: [
      "오차율은 실제 금액과 예측금액의 차이입니다. Cook 거리는 오차와 설명변수 조건을 함께 고려한 계수 영향도여서 오차율 순위와 다를 수 있습니다.",
      "거래 위치를 누르면 적합 당시 상세 자료를 확인할 수 있습니다. 전체 거래목록 연결도 그대로 이용할 수 있습니다.",
      "계수 변화는 아래 표시된 거래를 제외한 기존 재적합 결과입니다. 바뀐 값과 표준오차 대비 변화량을 함께 확인해 주세요.",
      ...(d.refit_note ? [d.refit_note] : []),
    ], limitations: ["영향도가 크다는 이유만으로 오류 거래나 제외 대상으로 판단하지 않습니다."], presets: [],
  };

  // 접힌 상태에서도 «볼 이유가 있는지»는 알려야 한다. 없으면 아무도 펼치지 않는다.
  const headline = useMemo(() => {
    const flagged = d.groups.flatMap((s) =>
      s.groups.filter((g) => g.significant).map((g) => ({ ...g, axis: s.label, label: groupLabel(s, g.label) })),
    );
    if (!flagged.length) return "집단별 오차 차이가 통계적으로 확인되지 않았습니다.";
    const worst = flagged.reduce((a, b) =>
      Math.abs(b.excess_bias_pct) > Math.abs(a.excess_bias_pct) ? b : a,
    );
    return `오차 차이가 확인된 집단 ${flagged.length}개 · 가장 큰 중앙값 차이: ${worst.axis} ‘${worst.label}’ ${signed(worst.excess_bias_pct)}%p`;
  }, [d.groups]);

  return (
    <div className="card space-y-3" data-built-residual-diagnostics>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-sm text-slate-800 dark:text-slate-100">
            잔차 진단
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {scopeLabel ? `${scopeLabel} · ` : ""}적합 표본 {fmtNum(d.n)}건
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

      <dl className="grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-3 dark:bg-slate-900/60">
        <div><dt className="text-xs text-slate-500 dark:text-slate-400">오차 중앙값</dt><dd className="mt-1 text-lg font-semibold tabular-nums">{signed(d.bias_pct)}%</dd></div>
        <div><dt className="text-xs text-slate-500 dark:text-slate-400">평균 오차</dt><dd className="mt-1 text-lg font-semibold tabular-nums">{d.mean_bias_pct == null ? "—" : `${signed(d.mean_bias_pct)}%`}</dd></div>
      </dl>
      <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">음수는 실제 거래금액보다 높게 추정한 경우를 뜻합니다.</p>
      <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">{headline}</p>

      {open && (
        <div className="space-y-3 pt-1">
          <section className="space-y-2" aria-label="금액대별 오차">
            <h4 className="flex items-center gap-1 text-sm font-semibold text-slate-700 dark:text-slate-100">
              금액대별 오차 <AnalysisHelpPanel explain={amountHelp} title="금액대별 오차 설명" />
            </h4>
            <ResidualScatter points={d.points} />
            {d.scale_bins.length > 0 && (
              <div className="overflow-x-auto"><table className="w-full text-xs tabular-nums mt-1">
                <thead className="text-slate-400 dark:text-slate-500">
                  <tr className="text-left">
                    <th className="font-normal py-0.5">예측금액 분위</th>
                    <th className="font-normal py-0.5 text-right">n</th>
                    <th className="font-normal py-0.5 text-right">금액 중앙값</th>
                    <th className="font-normal py-0.5 text-right">절대오차율 중앙값</th>
                    <th className="font-normal py-0.5 text-right" title="해당 분위에 속한 거래 오차율의 표본 표준편차입니다 (ddof=1).">오차율 표준편차</th>
                  </tr>
                </thead>
                <tbody>
                  {d.scale_bins.map((b) => (
                    <tr key={b.label} className="border-t border-slate-100 dark:border-slate-700/60">
                      <td className="py-1.5">{b.label}</td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {fmtNum(b.n)}
                      </td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {fmtMoney(b.fitted_median)}
                      </td>
                      <td className="py-0.5 text-right font-semibold text-slate-800 dark:text-slate-100">
                        {b.abs_pct_median.toFixed(1)}%
                      </td>
                      <td className="py-0.5 text-right text-slate-500 dark:text-slate-400">
                        {b.spread_pct.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            )}
          </section>

          {d.groups.length > 0 && (
            <details className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
              <summary className="cursor-pointer text-sm font-semibold">조건별 오차 분석 · {d.groups.length}개 항목</summary>
              <div className="mt-3 space-y-4">
              <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">비교 기준 <AnalysisHelpPanel explain={groupHelp} title="조건별 오차 분석 설명" /></div>
              {d.groups.map((s) => (
                <GroupTable key={s.key} set={s} />
              ))}
              </div>
            </details>
          )}

          {d.influential.length > 0 && (
            <details className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
              <summary className="cursor-pointer text-sm font-semibold">주요 영향 거래 {d.influential.length}건</summary>
              <div className="mt-3 space-y-2">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-100">
                  선정 기준 <AnalysisHelpPanel explain={influenceHelp} title="주요 영향 거래 설명" />
                </h4>
                {onOpenTransactions && (
                  <button
                    type="button"
                    className="text-[11px] underline text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    onClick={onOpenTransactions}
                  >
                    전체 거래목록 열기
                  </button>
                )}
              </div>
              <div className="overflow-x-auto"><table className="w-full text-xs tabular-nums">
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
                      <td className="py-0.5 pr-1 max-w-[9rem]">
                        <button type="button" onClick={() => setSelectedTrade(t)}
                          className="text-left underline underline-offset-2 text-sky-800 dark:text-sky-300"
                          aria-label={`${t.label} 영향 거래 확인`}>{t.label}</button>
                      </td>
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
              </table></div>
              {d.refit_shifts.length > 0 && (
                <details className="text-[11px] text-slate-500 dark:text-slate-400">
                  <summary className="cursor-pointer">영향 거래 제외 시 계수 변화</summary>
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
              </div>
            </details>
          )}

          {d.warning && (
            <p className="text-[11px] badge-warn">{d.warning}</p>
          )}
        </div>
      )}
      <DraggableModalShell open={selectedTrade != null} onClose={() => setSelectedTrade(null)}
        titleId="built-influential-trade-title" title="영향 거래 확인" resizable defaultWidth={600} defaultHeight={460}
        minWidth={320} minHeight={280} zClassName="z-[110]">
        {selectedTrade && <div className="p-3 space-y-3 text-sm">
          <p className="text-slate-600 dark:text-slate-300">현재 잔차 진단에 사용한 거래의 적합 당시 자료입니다. 영향도가 크다는 이유만으로 오류 거래나 제외 대상으로 판단하지 않습니다.</p>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
            <dt>위치</dt><dd>{selectedTrade.label}</dd>
            <dt>거래 ID</dt><dd>{selectedTrade.transaction_id ?? "원자료 식별자 미제공"}</dd>
            <dt>계약연도</dt><dd>{selectedTrade.contract_year ?? "—"}</dd>
            <dt>용도지역</dt><dd>{selectedTrade.zone_type ?? "—"}</dd>
            <dt>실제 거래금액</dt><dd>{fmtMoney(selectedTrade.price)}원</dd>
            <dt>모형 추정금액</dt><dd>{fmtMoney(selectedTrade.predicted)}원</dd>
            <dt>오차율</dt><dd>{signed(selectedTrade.error_pct)}%</dd>
            <dt>연면적 / 대지면적</dt><dd>{selectedTrade.gross_area ?? "—"} / {selectedTrade.land_area ?? "—"}㎡</dd>
            <dt>Cook 거리</dt><dd>{selectedTrade.cooks_d}</dd>
            <dt>레버리지</dt><dd>{selectedTrade.leverage ?? "—"}</dd>
          </dl>
          <p className="text-xs text-slate-600 dark:text-slate-300">Cook 거리는 해당 거래가 계수에 미치는 영향을, 레버리지는 설명변수 조건이 다른 거래와 떨어진 정도를 나타냅니다. 값의 크기만으로 거래의 유효성을 결정하지 않습니다.</p>
        </div>}
      </DraggableModalShell>
    </div>
  );
}
