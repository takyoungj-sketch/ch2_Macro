import { useState, type ReactNode } from "react";
import clsx from "clsx";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type {
  AssetType,
  ConclusionBullet,
  CoefficientNarrative,
  DiagnosticCheckItem,
  ModelCandidate,
  RecommendationConclusion,
  RecommendationPoolCandidate,
  RecommendationStage1,
  RecommendationStage2,
  RecommendedAction,
  RegressionRecommendResponse,
  RegressionVariableSpec,
  ResponseScale,
  TwinExperimentStep,
  TwinValidationVerdict,
} from "../types";
import { CvFitnessBadge, ScopeNLabels } from "../utils/recommendationLabels";
import RegressionEffectsTable from "./RegressionEffectsTable";
import RegressionEquation from "./RegressionEquation";

const BLOCK_LABELS: Record<string, string> = {
  gross_area: "연면적",
  land_area: "대지면적",
  building_age: "연식",
  road_width: "도로조건",
  zone_type: "용도지역",
  building_use: "건축물용도",
  structure: "구조",
  asset_type: "유형",
  region_leaf: "지역(읍·면·동/법정리)",
};

const BULLET_MARK: Record<ConclusionBullet["kind"], string> = {
  positive: "✔",
  negative: "✖",
  neutral: "·",
};

const VERDICT_BOX: Record<string, string> = {
  adopt_predictive:
    "border-slate-200 bg-slate-50/80 dark:border-slate-700 dark:bg-slate-800/50",
  caution: "border-amber-200 bg-amber-50/80 dark:border-amber-900/50 dark:bg-amber-950/20",
  no_predictive_model: "border-red-200 bg-red-50/80 dark:border-red-900/50 dark:bg-red-950/20",
  explanatory_only:
    "border-slate-200 bg-slate-50/80 dark:border-slate-700 dark:bg-slate-800/50",
};

const ERROR_BANNER: Record<string, string> = {
  accent:
    "border-slate-200 bg-slate-50 dark:border-slate-600 dark:bg-slate-800/40",
  elevated:
    "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30",
  high: "border-orange-300 bg-orange-50 dark:border-orange-800 dark:bg-orange-950/30",
  fail: "border-red-400 bg-red-50 dark:border-red-800 dark:bg-red-950/30",
  neutral:
    "border-slate-200 bg-slate-50 dark:border-slate-600 dark:bg-slate-800/40",
  positive:
    "border-slate-200 bg-slate-50 dark:border-slate-600 dark:bg-slate-800/40",
  warning:
    "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30",
  negative: "border-red-400 bg-red-50 dark:border-red-800 dark:bg-red-950/30",
};

const ACTION_MARK: Record<RecommendedAction["kind"], string> = {
  do: "✓",
  dont: "✗",
  optional: "○",
};

const CHECK_MARK: Record<DiagnosticCheckItem["status"], string> = {
  ok: "✓",
  warn: "△",
  fail: "✗",
};

const CHECK_CLASS: Record<DiagnosticCheckItem["status"], string> = {
  ok: "text-emerald-700 dark:text-emerald-300",
  warn: "text-amber-700 dark:text-amber-300",
  fail: "text-red-700 dark:text-red-300",
};

function DiagnosticChecklist({ items }: { items: DiagnosticCheckItem[] }) {
  if (!items.length) return null;
  return (
    <div className="rounded-md border border-slate-200 dark:border-slate-700 px-2.5 py-2 text-xs space-y-1.5">
      <p className="font-semibold text-slate-700 dark:text-slate-200">진단 체크리스트</p>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.check_id} className="flex gap-2">
            <span className={clsx("shrink-0 font-bold w-3", CHECK_CLASS[item.status])}>
              {CHECK_MARK[item.status]}
            </span>
            <div>
              <span className="font-medium">{item.label_ko}</span>
              <span className="text-slate-600 dark:text-slate-400"> — {item.summary_ko}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CoefficientInsights({ items }: { items: CoefficientNarrative[] }) {
  if (!items.length) return null;
  return (
    <details className="rounded-md border border-slate-200 dark:border-slate-700 px-2.5 py-2 text-xs">
      <summary className="cursor-pointer font-semibold text-slate-700 dark:text-slate-200">
        계수 해석
      </summary>
      <ul className="mt-2 space-y-1.5">
        {items.map((c) => (
          <li
            key={c.name}
            className={clsx(
              c.is_top_contributor && "font-medium text-indigo-800 dark:text-indigo-200",
              !c.significant && "text-slate-500",
            )}
          >
            {c.is_top_contributor ? "★ " : "· "}
            {c.text_ko}
          </li>
        ))}
      </ul>
    </details>
  );
}

function DiagnosisTable({
  conclusion,
  adj,
}: {
  conclusion: RecommendationConclusion;
  adj?: number | null;
}) {
  const d = conclusion.macro_diagnosis;
  if (!d) return null;
  const cv = conclusion.cv_mape;
  const mape = conclusion.mape;
  const adjShown = adj ?? conclusion.adj_r_squared;
  return (
    <div className="pt-1">
      <p className="text-[10px] font-semibold text-slate-500 mb-1">모형 진단</p>
      <table className="w-full text-[11px] text-left">
        <tbody className="text-slate-700 dark:text-slate-200">
          <tr>
            <th className="py-0.5 pr-2 font-normal text-slate-500">CV-MAPE</th>
            <td className="tabular-nums">{cv != null ? `${cv.toFixed(1)}%` : "—"}</td>
            <td className="font-medium">{d.error.label_ko}</td>
          </tr>
          <tr>
            <th className="py-0.5 pr-2 font-normal text-slate-500">Adj R²</th>
            <td className="tabular-nums">{adjShown != null ? adjShown.toFixed(3) : "—"}</td>
            <td>설명력 {d.explanation.label_ko}</td>
          </tr>
          <tr>
            <th className="py-0.5 pr-2 font-normal text-slate-500">MAPE → CV</th>
            <td className="tabular-nums">
              {mape != null && cv != null ? `${mape.toFixed(1)} → ${cv.toFixed(1)}%` : "—"}
            </td>
            <td>검증 안정성 {d.stability.label_ko}</td>
          </tr>
          <tr>
            <th className="py-0.5 pr-2 font-normal text-slate-500">분석 표본</th>
            <td className="text-slate-600 dark:text-slate-300" colSpan={2}>
              {d.sample.label_ko}
              {d.sample.detail_ko ? ` · ${d.sample.detail_ko}` : ""}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function FinalVerdictBanner({ conclusion }: { conclusion: RecommendationConclusion }) {
  const d = conclusion.macro_diagnosis;
  const tone = d?.composite.tone ?? conclusion.final_verdict_tone ?? "neutral";
  const intensity = d?.error.label_ko ?? conclusion.predictive_fit?.label_ko ?? conclusion.final_verdict_ko;
  const composite = d?.composite.label_ko;
  return (
    <div className={clsx("rounded-lg border-2 px-3 py-3 space-y-2", ERROR_BANNER[tone] ?? ERROR_BANNER.neutral)}>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        예측 오차
        {composite ? ` · Macro 해석 ${composite}` : ""}
      </p>
      <p className="text-xl font-bold leading-tight text-slate-900 dark:text-slate-100">
        {conclusion.cv_mape != null ? (
          <>
            CV-MAPE {conclusion.cv_mape.toFixed(1)}%
            <span className="ml-2 text-base font-semibold">· {intensity}</span>
          </>
        ) : (
          intensity
        )}
      </p>
      {(d?.error_one_liner_ko || conclusion.headline_ko) && (
        <p className="text-sm text-slate-700 dark:text-slate-300">
          {d?.error_one_liner_ko || conclusion.headline_ko}
        </p>
      )}
      <DiagnosisTable conclusion={conclusion} />
      {(d?.summary_ko || conclusion.summary_ko) && (
        <div className="pt-1 border-t border-black/10 dark:border-white/10">
          <p className="text-[10px] font-semibold text-slate-500 mb-0.5">
            Macro 해석
            {composite ? ` · ${composite}` : ""}
          </p>
          <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
            {d?.summary_ko || conclusion.summary_ko}
          </p>
        </div>
      )}
      {conclusion.recommended_actions.length > 0 && (
        <div className="pt-1 border-t border-black/10 dark:border-white/10">
          <p className="text-[10px] font-semibold text-slate-500 mb-1">권장 활용</p>
          <ul className="text-xs space-y-0.5">
            {conclusion.recommended_actions.map((a) => (
              <li
                key={a.action_id}
                className={clsx(
                  a.kind === "dont" && "text-red-800 dark:text-red-300",
                  a.kind === "do" && "text-slate-800 dark:text-slate-200",
                  a.kind === "optional" && "text-slate-700 dark:text-slate-300",
                )}
              >
                {ACTION_MARK[a.kind]} {a.label_ko}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const TWIN_VAL_BOX: Record<TwinValidationVerdict["verdict"], string> = {
  improved:
    "border-emerald-300 bg-emerald-50/70 text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-100",
  tie: "border-amber-300 bg-amber-50/70 text-amber-950 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100",
  worse:
    "border-rose-300 bg-rose-50/70 text-rose-950 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-100",
  skipped:
    "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-600 dark:bg-slate-900/40 dark:text-slate-300",
};

function TwinValidationBanner({ v }: { v: TwinValidationVerdict }) {
  const band = v.practical_band_pp ?? v.epsilon_pp;
  return (
    <div className={clsx("rounded-md border px-2.5 py-2 space-y-1", TWIN_VAL_BOX[v.verdict])}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wide opacity-70">
          Twin 검증
        </span>
        <span className="text-xs font-bold">{v.label_ko}</span>
        {v.cv_mape_delta != null && (
          <span className="text-[11px] tabular-nums opacity-90">
            탐색 Δ {v.cv_mape_delta > 0 ? "+" : ""}
            {v.cv_mape_delta.toFixed(2)}%p
            {v.local_cv_mape != null && v.compared_cv_mape != null
              ? ` (Local ${v.local_cv_mape.toFixed(2)} → Twin ${v.compared_cv_mape.toFixed(2)})`
              : ""}
          </span>
        )}
        <span
          className={clsx(
            "rounded border px-1.5 py-0.5 text-[10px] font-medium",
            v.twin_adopt_recommended
              ? "border-emerald-500/60 bg-white/70 dark:bg-black/20"
              : "border-current/30 bg-white/50 dark:bg-black/20",
          )}
        >
          {v.verdict === "skipped"
            ? "판정 보류"
            : v.twin_adopt_recommended
              ? "Twin 채택 권고"
              : "Local 유지 권고"}
        </span>
      </div>
      <p className="text-[11px] leading-relaxed opacity-90">{v.summary_ko}</p>
      {v.local_confirm_cv_mape != null && v.compared_confirm_cv_mape != null && (
        <p className="text-[11px] tabular-nums opacity-90">
          확인 CV Local {v.local_confirm_cv_mape.toFixed(2)}% → Twin {v.compared_confirm_cv_mape.toFixed(2)}%
        </p>
      )}
      {v.confirm_skipped_reason && (
        <p className="text-[10px] opacity-70">{v.confirm_skipped_reason}</p>
      )}
      <p className="text-[10px] leading-relaxed opacity-70">
        Twin은 가격이 비슷한 지역이 아니라 지역 구조(거래 구성·토지 이용·체급)가 닮아 표본을 보탤
        후보입니다. 구조 순위는 실험 순서일 뿐 유용함의 증명이 아닙니다. 탐색 CV로 접두를 고르고,
        확인 CV(마지막 연도)와 계수 안정으로 권고합니다. {band}%p는 채택 문턱이 아니라 무시할 흔들림(실질적
        개선 띠)입니다.
      </p>
    </div>
  );
}

function TwinExperimentTable({
  steps,
  regionNameByCode,
  adoptRecommended = false,
}: {
  steps: TwinExperimentStep[];
  regionNameByCode: Record<string, string>;
  adoptRecommended?: boolean;
}) {
  if (!steps.length) return null;
  const local = steps.find((s) => s.step_id === "local");
  const searchWinner = steps.find((s) => s.search_picked);
  const stabLabel = { ok: "양호", warn: "주의", fail: "불안정" } as const;
  const coeffKo: Record<string, string> = {
    gross_area: "연면적",
    land_area: "대지면적",
    building_age: "연식",
  };

  function coeffBits(step: TwinExperimentStep): string | null {
    const localC = local?.key_coefficients ?? {};
    const bits: string[] = [];
    for (const [key, ko] of Object.entries(coeffKo)) {
      const a = localC[key];
      const b = step.key_coefficients?.[key];
      if (a != null && b != null) bits.push(`${ko} ${a >= 0 ? "+" : ""}${Math.round(a)} → ${b >= 0 ? "+" : ""}${Math.round(b)}`);
    }
    return bits.length ? bits.join(" · ") : null;
  }

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[11px] border-collapse">
          <thead>
            <tr className="text-slate-500">
              <th className="py-1 pr-2 font-medium">실험</th>
              <th className="py-1 pr-2 font-medium">n</th>
              <th className="py-1 pr-2 font-medium">탐색 CV</th>
              <th className="py-1 pr-2 font-medium">Δ</th>
              <th className="py-1 pr-2 font-medium">확인 CV</th>
              <th className="py-1 pr-2 font-medium">안정</th>
              <th className="py-1 font-medium">판정</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((s) => (
              <tr
                key={s.step_id}
                className={clsx(
                  s.search_picked && "bg-violet-50 dark:bg-violet-950/40",
                  s.selected && !s.search_picked && "bg-slate-50 dark:bg-slate-800/60",
                )}
              >
                <td className="py-0.5 pr-2">
                  {s.label}
                  {s.search_picked ? " ←" : ""}
                  {s.region_codes.length > 0 && (
                    <span className="block text-[10px] font-normal text-slate-500">
                      {s.region_codes.map((c) => regionNameByCode[c] ?? c.slice(-8)).join(" + ")}
                    </span>
                  )}
                </td>
                <td className="py-0.5 pr-2 tabular-nums">{s.n}</td>
                <td className="py-0.5 pr-2 tabular-nums">
                  {s.search_cv_mape != null ? `${s.search_cv_mape.toFixed(1)}%` : "—"}
                </td>
                <td className="py-0.5 pr-2 tabular-nums">
                  {s.search_cv_delta != null ? `${s.search_cv_delta > 0 ? "+" : ""}${s.search_cv_delta.toFixed(1)}` : "—"}
                </td>
                <td className="py-0.5 pr-2 tabular-nums">
                  {s.confirm_cv_mape != null ? `${s.confirm_cv_mape.toFixed(1)}%` : "—"}
                </td>
                <td className="py-0.5 pr-2">{stabLabel[s.stability]}</td>
                <td className="py-0.5 text-slate-600 dark:text-slate-300">{s.verdict_ko}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {searchWinner && searchWinner.prefix_k > 0 && (
        <div className="rounded-md border border-slate-200 dark:border-slate-700 px-2.5 py-2 text-[11px] space-y-1">
          <p className="font-semibold text-slate-700 dark:text-slate-200">최종 검증</p>
          <p className="text-slate-600 dark:text-slate-300">
            탐색에서 고른 조합: {searchWinner.label}
            {searchWinner.region_codes.length > 0
              ? ` (${searchWinner.region_codes.map((c) => regionNameByCode[c] ?? c.slice(-8)).join(" + ")})`
              : ""}
          </p>
          <p className="tabular-nums">
            탐색 CV {searchWinner.search_cv_mape != null ? `${searchWinner.search_cv_mape.toFixed(1)}%` : "—"}
            {" · "}
            확인 CV {searchWinner.confirm_cv_mape != null ? `${searchWinner.confirm_cv_mape.toFixed(1)}%` : "—"}
          </p>
          {coeffBits(searchWinner) && (
            <p className="text-slate-500">핵심 계수 {coeffBits(searchWinner)}</p>
          )}
          {searchWinner.coeff_notes && searchWinner.coeff_notes.length > 0 && (
            <p className="text-slate-500">{searchWinner.coeff_notes.join(" · ")}</p>
          )}
          <p className="font-medium text-slate-800 dark:text-slate-100">
            권고: {adoptRecommended ? "Twin 채택" : "Local 유지"}
            <span className="ml-1 font-normal text-slate-500">
              (탐색 CV를 최종 성능으로 쓰지 않습니다)
            </span>
          </p>
        </div>
      )}
    </div>
  );
}

/** 인라인 Macro 카드 — 예측형·설명형 동일 골격 */
function MacroModeSummary({
  mode,
  conclusion,
  candidate,
}: {
  mode: "predictive" | "explanatory";
  conclusion: RecommendationConclusion;
  candidate: ModelCandidate;
}) {
  const isPredictive = mode === "predictive";
  const d = conclusion.macro_diagnosis;
  const cardTone = d?.composite.tone ?? d?.error.tone ?? conclusion.final_verdict_tone ?? "neutral";
  const errorLabel = d?.error.label_ko ?? conclusion.predictive_fit?.label_ko ?? conclusion.final_verdict_ko;
  const adj = conclusion.adj_r_squared ?? candidate.metrics.adj_r_squared;
  const cv = conclusion.cv_mape;

  return (
    <div className={clsx("rounded-lg border px-3 py-2.5 space-y-2", ERROR_BANNER[cardTone] ?? ERROR_BANNER.neutral)}>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        {isPredictive
          ? `예측 오차${d?.composite.label_ko ? ` · Macro 해석 ${d.composite.label_ko}` : ""}`
          : "설명형"}
      </p>
      {isPredictive ? (
        <p className="text-base font-bold leading-snug text-slate-900 dark:text-slate-100">
          {cv != null ? `CV-MAPE ${cv.toFixed(1)}%` : "CV 미산출"}
          <span className="ml-2 text-sm font-semibold">· {errorLabel}</span>
        </p>
      ) : (
        <p className="text-base font-bold leading-snug text-slate-900 dark:text-slate-100">
          AIC {candidate.aic?.toFixed(0) ?? "—"}
          <span className="ml-2 text-sm font-semibold text-slate-600 dark:text-slate-300">
            Adj.R² {adj != null ? adj.toFixed(3) : "—"}
          </span>
        </p>
      )}
      <p className="text-xs text-slate-600 dark:text-slate-400">
        {blockSummary(candidate.blocks)} · {candidate.response_scale}
      </p>
      {isPredictive && (d?.error_one_liner_ko || conclusion.headline_ko) && (
        <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
          {d?.error_one_liner_ko || conclusion.headline_ko}
        </p>
      )}
      {isPredictive && <DiagnosisTable conclusion={conclusion} adj={adj} />}
      {isPredictive && (d?.summary_ko || conclusion.summary_ko) && (
        <div className="pt-1 border-t border-black/5 dark:border-white/10">
          <p className="text-[10px] font-semibold text-slate-500 mb-0.5">
            Macro 해석
            {d?.composite.label_ko ? ` · ${d.composite.label_ko}` : ""}
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            {d?.summary_ko || conclusion.summary_ko}
          </p>
        </div>
      )}
    </div>
  );
}

function ConclusionBullets({ conclusion }: { conclusion: RecommendationConclusion }) {
  if (!conclusion.bullets.length) return null;
  return (
    <div
      className={clsx(
        "rounded-md border px-2.5 py-2 text-xs space-y-1",
        VERDICT_BOX[conclusion.verdict] ?? VERDICT_BOX.caution,
      )}
    >
      {conclusion.bullets.length > 0 && (
        <ul className="space-y-0.5">
          {conclusion.bullets.map((b) => (
            <li
              key={b.text}
              className={clsx(
                b.kind === "negative" && "text-red-800 dark:text-red-300",
                b.kind === "positive" && "text-indigo-800 dark:text-indigo-300",
                b.kind === "neutral" && "text-slate-700 dark:text-slate-300",
              )}
            >
              {BULLET_MARK[b.kind]} {b.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ScopeSummaryBox({
  analysis_scope,
  stage1,
  conclusion,
  showSatisfaction = true,
}: {
  analysis_scope: RegressionRecommendResponse["analysis_scope"];
  stage1: RegressionRecommendResponse["stage1"];
  conclusion: RecommendationConclusion;
  showSatisfaction?: boolean;
}) {
  const excluded = conclusion.sample_excluded_n ?? Math.max(0, analysis_scope.scope_n_tx - stage1.selection_n);
  const pfit = conclusion.predictive_fit;
  return (
    <div className="rounded-md bg-slate-50 dark:bg-slate-800/50 px-2.5 py-2 text-xs space-y-1">
      <p className="font-medium">{analysis_scope.scope_label || "분석 scope"}</p>
      {showSatisfaction && (
        <p className="text-slate-700 dark:text-slate-200">
          예측 오차{" "}
          <span className="font-semibold">{pfit?.label_ko ?? conclusion.final_verdict_ko}</span>
          {conclusion.cv_mape != null && (
            <span className="ml-1 tabular-nums text-slate-500">CV-MAPE {conclusion.cv_mape.toFixed(1)}%</span>
          )}
        </p>
      )}
      <p className="tabular-nums text-slate-700 dark:text-slate-200">
        거래 {analysis_scope.scope_n_tx}건 → 분석 {stage1.selection_n}건
        {excluded > 0 && <span className="text-slate-500"> (제외 {excluded}건)</span>}
        <span className="text-slate-500"> · 적합 {stage1.fit_n}건</span>
      </p>
      {excluded > 0 && conclusion.excluded_block_notes && conclusion.excluded_block_notes.length > 0 && (
        <details className="text-[11px] text-slate-500">
          <summary className="cursor-pointer">주요 제외 사유</summary>
          <ul className="mt-1 list-disc pl-4">
            {conclusion.excluded_block_notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      )}
      <ScopeNLabels
        counts={{
          scope_n_tx: analysis_scope.scope_n_tx,
          selection_n: stage1.selection_n,
          fit_n: stage1.fit_n,
          include_partial: analysis_scope.include_partial,
          partial_tx_count: analysis_scope.partial_tx_count,
        }}
      />
      <p className="text-slate-400 text-[11px]">
        SSOT 풀({stage1.candidate_pool.length}블록) — 왼쪽 변수 체크와 무관
        {analysis_scope.anchor_unit?.name && <> · anchor {analysis_scope.anchor_unit.name}</>}
      </p>
    </div>
  );
}

function RankingList({
  mode,
  list,
  collapsed = false,
}: {
  mode: "predictive" | "explanatory";
  list: ModelCandidate[];
  collapsed?: boolean;
}) {
  const isPredictive = mode === "predictive";
  const title = isPredictive ? "예측형 랭킹 (CV-MAPE)" : "설명형 랭킹 (AIC)";
  const inner = (
    <ul className="space-y-1 max-h-32 overflow-y-auto">
      {list.map((c) => (
        <li
          key={`${mode}-${c.rank}-${c.blocks.join(",")}`}
          className="text-xs flex gap-2 px-1 py-0.5 border-b border-slate-100 dark:border-slate-800"
        >
          <span className="text-indigo-600 w-5">#{c.rank}</span>
          <span className="flex-1 truncate">{blockSummary(c.blocks)}</span>
          <span className="text-slate-500 tabular-nums shrink-0">
            {c.response_scale}
            {isPredictive
              ? ` · CV ${c.metrics.cv_mape?.toFixed(1) ?? "—"}%`
              : ` · AIC ${c.aic?.toFixed(0) ?? "—"}`}
          </span>
        </li>
      ))}
    </ul>
  );
  if (collapsed) {
    return (
      <details className="rounded border border-slate-200 dark:border-slate-700 px-2.5 py-2">
        <summary className="cursor-pointer text-xs font-medium text-slate-600 dark:text-slate-300">
          {title}
        </summary>
        <div className="mt-1.5">{inner}</div>
      </details>
    );
  }
  return (
    <div>
      <p className="text-[11px] font-medium text-slate-600 dark:text-slate-300 mb-1.5">{title}</p>
      {inner}
    </div>
  );
}

function TerminationLog({
  termination,
  twinRan,
}: {
  termination: RegressionRecommendResponse["termination"];
  twinRan?: boolean;
}) {
  if (!termination.reasons.length) return null;
  return (
    <details className="rounded border border-slate-200 dark:border-slate-700 px-2.5 py-2 text-xs">
      <summary className="cursor-pointer font-medium text-slate-600 dark:text-slate-300">
        탐색 로그 ({termination.stage_reached}단계
        {termination.action === "proceed_twin" && !twinRan ? " · Twin 검토 가능" : ""})
      </summary>
      <ol className="list-decimal list-inside space-y-0.5 text-slate-600 dark:text-slate-400 mt-1">
        {termination.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ol>
      {termination.next_stage_hint && (
        <p className="mt-1 text-[11px] text-slate-500">{termination.next_stage_hint}</p>
      )}
    </details>
  );
}

function blockSummary(blocks: string[]) {
  if (!blocks.length) return "(절편만)";
  return blocks.map((b) => BLOCK_LABELS[b] ?? b).join(" · ");
}

function poolFormulaLine(pool: RecommendationPoolCandidate, stage2: RecommendationStage2) {
  const blocks =
    pool.blocks?.length ? pool.blocks : stage2.recommended_blocks?.length
      ? stage2.recommended_blocks
      : stage2.fixed_blocks;
  const scale = pool.response_scale ?? stage2.fixed_response_scale;
  return `${blockSummary(blocks)} · ${scale}`;
}

function poolAdoptVars(
  pool: RecommendationPoolCandidate,
  stage1: RecommendationStage1,
  stage2: RecommendationStage2,
) {
  return {
    vars: pool.variables ?? stage1.primary.variables,
    scale: pool.response_scale ?? stage2.fixed_response_scale ?? stage1.primary.response_scale,
  };
}

function adoptLabelForMode(mode: string) {
  if (mode === "review_only") return "구조 탐색용으로 적용";
  if (mode === "explanatory") return "설명형으로 적용";
  return "이 후보로 분석";
}

type RankTab = "explanatory" | "predictive";

function resolveRecommendAssetType(assetType: AssetType | undefined, slice: string): AssetType {
  if (assetType) return assetType;
  if (slice && slice !== "unified") return slice as AssetType;
  return "commercial";
}

function CandidateEquationBlock({
  candidate,
  assetType,
  narratives,
}: {
  candidate: ModelCandidate;
  assetType: AssetType;
  narratives?: CoefficientNarrative[];
}) {
  const coeffs = candidate.coefficients ?? [];
  if (!coeffs.length) return null;
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1 text-xs font-semibold text-slate-600 dark:text-slate-400">
        회귀식
        <StatsGlossaryHelp termId="coefficient" size="xs" />
      </div>
      <RegressionEquation
        coefficients={coeffs}
        responseScale={candidate.response_scale}
        assetType={assetType}
      />
      <details className="text-xs" open>
        <summary className="cursor-pointer text-slate-600 dark:text-slate-400 font-medium">
          계수 상세
        </summary>
        <RegressionEffectsTable
          coefficients={coeffs}
          responseScale={candidate.response_scale}
          assetType={assetType}
        />
        {narratives && narratives.length > 0 && (
          <div className="mt-2">
            <CoefficientInsights items={narratives} />
          </div>
        )}
      </details>
    </div>
  );
}

function TwinOfferCard({
  twinRunning,
  onRunTwin,
}: {
  twinRunning?: boolean;
  onRunTwin: () => void;
}) {
  return (
    <div className="rounded-md border border-violet-200 dark:border-violet-900/50 bg-violet-50/40 dark:bg-violet-950/20 p-2.5 space-y-1.5">
      <p className="text-xs font-medium text-violet-900 dark:text-violet-200">추가 검증 권고</p>
      <p className="text-[11px] text-violet-800/90 dark:text-violet-300/90">
        Local만으로 구조적 관계가 충분히 안정적으로 확인되지 않을 수 있습니다. 닮은 거래군을
        보태면 같은 변수 관계가 유지되는지 비교할 수 있습니다.
      </p>
      <button
        type="button"
        className="px-2.5 py-1 text-xs rounded bg-violet-600 text-white disabled:opacity-50"
        disabled={twinRunning}
        onClick={onRunTwin}
      >
        {twinRunning ? "Twin 실험 중…" : "Twin 실험"}
      </button>
    </div>
  );
}

function CandidateMini({
  c,
  role,
  adoptLabel,
  onAdopt,
  onPredict,
  adopting,
  predictActive,
  rankMode = "predictive",
}: {
  c: ModelCandidate;
  role: string;
  adoptLabel?: string;
  onAdopt?: () => void;
  onPredict?: () => void;
  adopting?: boolean;
  predictActive?: boolean;
  rankMode?: "predictive" | "explanatory";
}) {
  const metricsLine =
    rankMode === "explanatory"
      ? `${c.response_scale} · AIC ${c.aic?.toFixed(0) ?? "—"} · Adj.R² ${
          c.metrics.adj_r_squared != null ? c.metrics.adj_r_squared.toFixed(3) : "—"
        } · CV ${c.metrics.cv_mape != null ? `${c.metrics.cv_mape.toFixed(1)}%` : "—"}`
      : `${c.response_scale} · Adj.R² ${
          c.metrics.adj_r_squared != null ? c.metrics.adj_r_squared.toFixed(3) : "—"
        } · CV-MAPE ${c.metrics.cv_mape != null ? `${c.metrics.cv_mape.toFixed(1)}%` : "—"}`;

  return (
    <div className="border border-slate-200 dark:border-slate-600 rounded-md p-2 space-y-1.5">
      <div className="flex items-start gap-2">
        <span className="text-[10px] uppercase tracking-wide text-indigo-600 dark:text-indigo-400 shrink-0">
          {role}
        </span>
        <div className="flex-1 min-w-0 text-xs">
          <p className="font-medium truncate">{blockSummary(c.blocks)}</p>
          <p className="text-slate-500 tabular-nums">{metricsLine}</p>
        </div>
      </div>
      {(onAdopt || onPredict) && (
        <div className="flex flex-wrap gap-1.5">
          {onAdopt && (
            <button
              type="button"
              className="px-2 py-0.5 text-[11px] rounded bg-indigo-600 text-white disabled:opacity-50"
              disabled={adopting}
              onClick={onAdopt}
            >
              {adoptLabel ?? "1단계 모형 적용"}
            </button>
          )}
          {onPredict && (
            <button
              type="button"
              className={clsx(
                "px-2 py-0.5 text-[11px] rounded border",
                predictActive
                  ? "border-indigo-500 text-indigo-700 dark:text-indigo-300"
                  : "border-slate-300 dark:border-slate-600 text-slate-600",
              )}
              onClick={onPredict}
            >
              모형 적용 예시
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export type AdoptPoolPayload = {
  vars: RegressionVariableSpec;
  scale: ResponseScale;
  regionCodes: string[];
  label: string;
};

type Props = {
  data: RegressionRecommendResponse;
  onAdopt?: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  onAdoptPool?: (payload: AdoptPoolPayload) => void;
  adopting?: boolean;
  onPredict?: (vars: RegressionVariableSpec, scale: ResponseScale, label: string) => void;
  predictActiveLabel?: string | null;
  regionNameByCode?: Record<string, string>;
  onRunTwin?: () => void;
  twinRunning?: boolean;
  /** full=모달 호환 전체 · predictive/explanatory=인라인 단일 모드 카드 */
  mode?: "full" | "predictive" | "explanatory";
  /** 회귀실험과 같이 계수 아래에 두는 예측창 */
  predictPanel?: ReactNode;
  assetType?: AssetType;
};

export default function RecommendStagePanel({
  data,
  onAdopt,
  onAdoptPool,
  adopting,
  onPredict,
  predictActiveLabel,
  regionNameByCode = {},
  onRunTwin,
  twinRunning,
  mode = "full",
  predictPanel,
  assetType,
}: Props) {
  const isFull = mode === "full";
  const isPredictive = mode === "predictive";
  const isExplanatory = mode === "explanatory";
  const [tab, setTab] = useState<RankTab>(isExplanatory ? "explanatory" : "predictive");
  const [twinStep, setTwinStep] = useState(0);
  const { stage1, stage2, analysis_scope, termination, warnings, conclusion, diagnostics_checklist, coefficient_narratives } = data;
  const list =
    tab === "explanatory" || isExplanatory
      ? stage1.candidates_explanatory
      : stage1.candidates_predictive;
  const adoptLabel = adoptLabelForMode(conclusion.adopt_mode);
  const predictiveRole = "현재 최적 후보 (예측형)";
  const explanatoryRole = "현재 최적 후보 (설명형)";
  const explanatoryCandidate = stage1.alternate ?? stage1.primary;
  const resolvedAssetType = resolveRecommendAssetType(assetType, analysis_scope.asset_slice);

  const showTwinResults =
    stage2 && (stage2.ran ? stage2.pools.length > 0 : Boolean(stage2.skipped_reason));
  const visiblePool = stage2?.ran ? stage2.pools[twinStep] : undefined;
  const inlineMode = isPredictive ? "predictive" : isExplanatory ? "explanatory" : null;

  if (inlineMode) {
    const modeCandidate = inlineMode === "predictive" ? stage1.primary : explanatoryCandidate;
    const modeRole =
      inlineMode === "predictive" ? "최적 후보 (예측형)" : "최적 후보 (설명형)";
    const modeAdoptLabel =
      inlineMode === "predictive" ? adoptLabel : "설명형으로 적용";

    return (
      <div className="space-y-3 text-sm">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
          <span className="font-semibold text-slate-800 dark:text-slate-100">모형 추천</span>
          <span
            className="rounded border border-violet-300 bg-violet-50 dark:border-violet-800 dark:bg-violet-950/40 px-1.5 py-0.5 text-[10px] font-medium text-violet-800 dark:text-violet-200"
            title="복합: Stage1 목적별 후보 + 선택적 Twin pool (확장)"
          >
            깊이: 확장
          </span>
          <span className="text-[11px] text-slate-500">
            {inlineMode === "predictive"
              ? "CV-MAPE 1위 · Twin은 선택"
              : "AIC 1위 · 예측 판정은 예측형 카드"}
          </span>
        </div>
        <MacroModeSummary
          mode={inlineMode}
          conclusion={conclusion}
          candidate={modeCandidate}
        />
        {inlineMode === "predictive" && <ConclusionBullets conclusion={conclusion} />}
        {inlineMode === "predictive" &&
          conclusion.twin_recommended &&
          onRunTwin &&
          !conclusion.twin_ran && (
            <TwinOfferCard twinRunning={twinRunning} onRunTwin={onRunTwin} />
          )}
        {inlineMode === "explanatory" && (
          <p className="text-xs text-slate-600 dark:text-slate-400">
            AIC가 낮을수록 같은 표본에서 설명력과 간결성의 균형이 낫습니다. 예측에 쓸지는 예측형
            카드의 CV-MAPE 판정을 보세요.
          </p>
        )}
        <ScopeSummaryBox
          analysis_scope={analysis_scope}
          stage1={stage1}
          conclusion={conclusion}
          showSatisfaction={inlineMode === "predictive"}
        />

        {inlineMode === "explanatory" && !stage1.alternate && (
          <p className="text-xs text-slate-500">
            설명형 1위가 예측형과 동일합니다 — 아래 후보를 참고하세요.
          </p>
        )}

        <CandidateEquationBlock
          candidate={modeCandidate}
          assetType={resolvedAssetType}
          narratives={inlineMode === "predictive" ? (coefficient_narratives ?? []) : undefined}
        />

        {(onAdopt || (onPredict && !predictPanel)) && (
          <CandidateMini
            c={modeCandidate}
            role={modeRole}
            adoptLabel={modeAdoptLabel}
            rankMode={inlineMode}
            onAdopt={
              onAdopt
                ? () => onAdopt(modeCandidate.variables, modeCandidate.response_scale)
                : undefined
            }
            onPredict={
              onPredict && !predictPanel
                ? () =>
                    onPredict(
                      modeCandidate.variables,
                      modeCandidate.response_scale,
                      modeRole,
                    )
                : undefined
            }
            adopting={adopting}
            predictActive={predictActiveLabel === modeRole}
          />
        )}

        {predictPanel}

        {inlineMode === "predictive" && (
          <DiagnosticChecklist items={diagnostics_checklist ?? []} />
        )}

        {inlineMode === "predictive" && showTwinResults && stage2 && (
          <div className="border-t border-slate-200 dark:border-slate-700 pt-3 space-y-2">
            <p className="text-xs font-medium text-slate-700 dark:text-slate-200">
              Twin 접두 실험
            </p>
            {stage2.twin_validation && <TwinValidationBanner v={stage2.twin_validation} />}
            {stage2.region_effect && (
              <p className="text-[11px] text-slate-600 dark:text-slate-300">{stage2.region_effect}</p>
            )}
            {stage2.twin_experiments && stage2.twin_experiments.length > 0 && (
              <TwinExperimentTable
                steps={stage2.twin_experiments}
                regionNameByCode={regionNameByCode}
                adoptRecommended={Boolean(stage2.twin_validation?.twin_adopt_recommended)}
              />
            )}

            {!stage2.ran && stage2.skipped_reason && (
              <p className="text-xs text-slate-500">{stage2.skipped_reason}</p>
            )}

            {stage2.ran && stage2.pools.length > 0 && visiblePool && (
              <div className="rounded-md border border-violet-200 dark:border-violet-900/50 bg-violet-50/50 dark:bg-violet-950/20 p-2 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium">{visiblePool.label}</p>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      className="px-1.5 py-0.5 text-[10px] border rounded disabled:opacity-40"
                      disabled={twinStep <= 0}
                      onClick={() => setTwinStep((s) => Math.max(0, s - 1))}
                    >
                      ←
                    </button>
                    <span className="text-[10px] text-slate-500 tabular-nums self-center">
                      {twinStep + 1}/{stage2.pools.length}
                    </span>
                    <button
                      type="button"
                      className="px-1.5 py-0.5 text-[10px] border rounded disabled:opacity-40"
                      disabled={twinStep >= stage2.pools.length - 1}
                      onClick={() => setTwinStep((s) => Math.min(stage2.pools.length - 1, s + 1))}
                    >
                      →
                    </button>
                  </div>
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-400 tabular-nums flex flex-wrap items-center gap-2">
                  <span>적합 n={visiblePool.n}</span>
                  <CvFitnessBadge cvMape={visiblePool.cv_mape} />
                  <span className="text-slate-500">{poolFormulaLine(visiblePool, stage2)}</span>
                  {visiblePool.cv_mape_delta != null && visiblePool.cv_mape_delta > 0 && (
                    <span className="text-[10px] text-slate-400">
                      (Local 대비 △{visiblePool.cv_mape_delta.toFixed(1)}%p)
                    </span>
                  )}
                </p>
                {visiblePool.region_codes.length > 1 && (
                  <p className="text-[10px] text-slate-500">
                    pool:{" "}
                    {visiblePool.region_codes
                      .map((c) => regionNameByCode[c] ?? c.slice(-8))
                      .join(" + ")}
                  </p>
                )}
                {onAdoptPool && (
                  <button
                    type="button"
                    className={clsx(
                      "px-2 py-0.5 text-[11px] rounded disabled:opacity-50",
                      stage2.primary?.candidate_id === visiblePool.candidate_id
                        ? "bg-violet-600 text-white"
                        : "border border-violet-400 text-violet-700 dark:text-violet-300",
                    )}
                    disabled={adopting}
                    onClick={() => {
                      const { vars, scale } = poolAdoptVars(visiblePool, stage1, stage2);
                      onAdoptPool({
                        vars,
                        scale,
                        regionCodes: visiblePool.region_codes,
                        label: visiblePool.label,
                      });
                    }}
                  >
                    {stage2.primary?.candidate_id === visiblePool.candidate_id
                      ? "Twin pool 적용 (검토)"
                      : "이 pool로 분석 (검토)"}
                  </button>
                )}
              </div>
            )}

            {stage2.ran && stage2.decision_reason && (
              <p className="text-[11px] text-slate-500">{stage2.decision_reason}</p>
            )}
          </div>
        )}

        <TerminationLog termination={termination} twinRan={conclusion.twin_ran} />

        {warnings.length > 0 && (
          <ul className="text-[11px] text-amber-700 dark:text-amber-400 space-y-0.5">
            {warnings.map((w) => (
              <li key={w}>⚠ {w}</li>
            ))}
          </ul>
        )}

        <RankingList mode={inlineMode} list={list} collapsed />
      </div>
    );
  }

  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
        <span className="font-semibold text-slate-800 dark:text-slate-100">모형 추천</span>
        <span
          className="rounded border border-violet-300 bg-violet-50 dark:border-violet-800 dark:bg-violet-950/40 px-1.5 py-0.5 text-[10px] font-medium text-violet-800 dark:text-violet-200"
          title="복합: Stage1 목적별 후보 + 선택적 Twin pool (확장)"
        >
          깊이: 확장
        </span>
        <span className="text-[11px] text-slate-500">
          설명형/예측형 후보 · 이 창에서만 확인
        </span>
      </div>
      {(isFull || isPredictive) && <FinalVerdictBanner conclusion={conclusion} />}
      {(isFull || isPredictive) &&
        conclusion.twin_recommended &&
        onRunTwin &&
        !conclusion.twin_ran && (
          <TwinOfferCard twinRunning={twinRunning} onRunTwin={onRunTwin} />
        )}
      {(isFull || isPredictive) && <ConclusionBullets conclusion={conclusion} />}

      {isFull && (
      <div className="flex items-center gap-2 text-[11px]">
        <span
          className={clsx(
            "px-2 py-0.5 rounded-full border",
            termination.stage_reached >= 1
              ? "bg-indigo-100 border-indigo-300 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200"
              : "border-slate-300 text-slate-500",
          )}
        >
          ① Local
        </span>
        <span className="text-slate-300">→</span>
        <span
          className={clsx(
            "px-2 py-0.5 rounded-full border",
            termination.stage_reached >= 2
              ? "bg-indigo-100 border-indigo-300 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200"
              : "border-slate-300 text-slate-500",
          )}
        >
          ② Twin
        </span>
      </div>
      )}

      <ScopeSummaryBox
        analysis_scope={analysis_scope}
        stage1={stage1}
        conclusion={conclusion}
        showSatisfaction={isFull || isPredictive}
      />

      {(isFull || isPredictive) && <DiagnosticChecklist items={diagnostics_checklist ?? []} />}
      {(isFull || isExplanatory) && <CoefficientInsights items={coefficient_narratives ?? []} />}

      {isFull && (
      <div className="grid gap-2 sm:grid-cols-2">
        <CandidateMini
          c={stage1.primary}
          role={predictiveRole}
          adoptLabel={adoptLabel}
          onAdopt={
            onAdopt
              ? () => onAdopt(stage1.primary.variables, stage1.primary.response_scale)
              : undefined
          }
          onPredict={
            onPredict
              ? () =>
                  onPredict(
                    stage1.primary.variables,
                    stage1.primary.response_scale,
                    predictiveRole,
                  )
              : undefined
          }
          adopting={adopting}
          predictActive={predictActiveLabel === predictiveRole}
        />
        {stage1.alternate && (
          <CandidateMini
            c={stage1.alternate}
            role={explanatoryRole}
            adoptLabel="설명형으로 적용"
            onAdopt={
              onAdopt
                ? () => onAdopt(stage1.alternate!.variables, stage1.alternate!.response_scale)
                : undefined
            }
            onPredict={
              onPredict
                ? () =>
                    onPredict(
                      stage1.alternate!.variables,
                      stage1.alternate!.response_scale,
                      explanatoryRole,
                    )
                : undefined
            }
            adopting={adopting}
            predictActive={predictActiveLabel === explanatoryRole}
          />
        )}
      </div>
      )}

      {isPredictive && (
        <CandidateMini
          c={stage1.primary}
          role={predictiveRole}
          adoptLabel={adoptLabel}
          onAdopt={
            onAdopt
              ? () => onAdopt(stage1.primary.variables, stage1.primary.response_scale)
              : undefined
          }
          onPredict={
            onPredict
              ? () =>
                  onPredict(
                    stage1.primary.variables,
                    stage1.primary.response_scale,
                    predictiveRole,
                  )
              : undefined
          }
          adopting={adopting}
          predictActive={predictActiveLabel === predictiveRole}
        />
      )}

      {isExplanatory && (
        <>
          {!stage1.alternate && (
            <p className="text-xs text-slate-500">
              설명형 1위가 예측형과 동일합니다 — 아래 후보를 참고하세요.
            </p>
          )}
          <CandidateMini
            c={explanatoryCandidate}
            role={explanatoryRole}
            adoptLabel="설명형으로 적용"
            onAdopt={
              onAdopt
                ? () =>
                    onAdopt(explanatoryCandidate.variables, explanatoryCandidate.response_scale)
                : undefined
            }
            onPredict={
              onPredict
                ? () =>
                    onPredict(
                      explanatoryCandidate.variables,
                      explanatoryCandidate.response_scale,
                      explanatoryRole,
                    )
                : undefined
            }
            adopting={adopting}
            predictActive={predictActiveLabel === explanatoryRole}
          />
        </>
      )}

      <div>
        {isFull && (
        <div className="flex gap-1 mb-2">
          {(
            [
              ["predictive", "예측형 (CV-MAPE)"],
              ["explanatory", "설명형 (AIC)"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={clsx(
                "px-2 py-0.5 text-[11px] rounded border",
                tab === key
                  ? "bg-slate-800 text-white border-slate-800 dark:bg-slate-100 dark:text-slate-900"
                  : "border-slate-200 dark:border-slate-600 text-slate-600",
              )}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>
        )}
        {!isFull && (
          <p className="text-[11px] font-medium text-slate-600 dark:text-slate-300 mb-1.5">
            {isExplanatory ? "설명형 랭킹 (AIC)" : "예측형 랭킹 (CV-MAPE)"}
          </p>
        )}
        <ul className="space-y-1 max-h-32 overflow-y-auto">
          {list.map((c) => (
            <li
              key={`${mode}-${tab}-${c.rank}-${c.blocks.join(",")}`}
              className="text-xs flex gap-2 px-1 py-0.5 border-b border-slate-100 dark:border-slate-800"
            >
              <span className="text-indigo-600 w-5">#{c.rank}</span>
              <span className="flex-1 truncate">{blockSummary(c.blocks)}</span>
              <span className="text-slate-500 tabular-nums shrink-0">
                {c.response_scale}
                {(tab === "predictive" || isPredictive) && !isExplanatory
                  ? ` · CV ${c.metrics.cv_mape?.toFixed(1) ?? "—"}%`
                  : ` · AIC ${c.aic?.toFixed(0) ?? "—"}`}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {(isFull || isPredictive) && showTwinResults && stage2 && (
        <div className="border-t border-slate-200 dark:border-slate-700 pt-3 space-y-2">
          <p className="text-xs font-medium text-slate-700 dark:text-slate-200">
            Twin 접두 실험
          </p>
          {stage2.twin_validation && <TwinValidationBanner v={stage2.twin_validation} />}
          {stage2.region_effect && (
            <p className="text-[11px] text-slate-600 dark:text-slate-300">{stage2.region_effect}</p>
          )}
          {stage2.twin_experiments && stage2.twin_experiments.length > 0 && (
            <TwinExperimentTable
              steps={stage2.twin_experiments}
              regionNameByCode={regionNameByCode}
              adoptRecommended={Boolean(stage2.twin_validation?.twin_adopt_recommended)}
            />
          )}

          {!stage2.ran && stage2.skipped_reason && (
            <p className="text-xs text-slate-500">{stage2.skipped_reason}</p>
          )}

          {stage2.ran && stage2.pools.length > 0 && visiblePool && (
            <div className="rounded-md border border-violet-200 dark:border-violet-900/50 bg-violet-50/50 dark:bg-violet-950/20 p-2 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium">{visiblePool.label}</p>
                <div className="flex gap-1">
                  <button
                    type="button"
                    className="px-1.5 py-0.5 text-[10px] border rounded disabled:opacity-40"
                    disabled={twinStep <= 0}
                    onClick={() => setTwinStep((s) => Math.max(0, s - 1))}
                  >
                    ←
                  </button>
                  <span className="text-[10px] text-slate-500 tabular-nums self-center">
                    {twinStep + 1}/{stage2.pools.length}
                  </span>
                  <button
                    type="button"
                    className="px-1.5 py-0.5 text-[10px] border rounded disabled:opacity-40"
                    disabled={twinStep >= stage2.pools.length - 1}
                    onClick={() => setTwinStep((s) => Math.min(stage2.pools.length - 1, s + 1))}
                  >
                    →
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 tabular-nums flex flex-wrap items-center gap-2">
                <span>적합 n={visiblePool.n}</span>
                <CvFitnessBadge cvMape={visiblePool.cv_mape} />
                <span className="text-slate-500">{poolFormulaLine(visiblePool, stage2)}</span>
                {visiblePool.cv_mape_delta != null && visiblePool.cv_mape_delta > 0 && (
                  <span className="text-[10px] text-slate-400">
                    (Local 대비 △{visiblePool.cv_mape_delta.toFixed(1)}%p)
                  </span>
                )}
              </p>
              {visiblePool.region_codes.length > 1 && (
                <p className="text-[10px] text-slate-500">
                  pool:{" "}
                  {visiblePool.region_codes
                    .map((c) => regionNameByCode[c] ?? c.slice(-8))
                    .join(" + ")}
                </p>
              )}
              {onAdoptPool && (
                <button
                  type="button"
                  className={clsx(
                    "px-2 py-0.5 text-[11px] rounded disabled:opacity-50",
                    stage2.primary?.candidate_id === visiblePool.candidate_id
                      ? "bg-violet-600 text-white"
                      : "border border-violet-400 text-violet-700 dark:text-violet-300",
                  )}
                  disabled={adopting}
                  onClick={() => {
                    const { vars, scale } = poolAdoptVars(visiblePool, stage1, stage2);
                    onAdoptPool({
                      vars,
                      scale,
                      regionCodes: visiblePool.region_codes,
                      label: visiblePool.label,
                    });
                  }}
                >
                  {stage2.primary?.candidate_id === visiblePool.candidate_id
                    ? "2단계 pool 적용 (검토)"
                    : "이 pool로 분석 (검토)"}
                </button>
              )}
            </div>
          )}

          {stage2.ran && stage2.decision_reason && (
            <p className="text-[11px] text-slate-500">{stage2.decision_reason}</p>
          )}
        </div>
      )}

      {isExplanatory && conclusion.twin_ran && stage2?.ran && (
        <p className="text-[11px] text-violet-700 dark:text-violet-300">
          쌍둥이 지역 pool이 실행되었습니다 — 예측형 탭에서 pool별 CV-MAPE 비교를 확인하세요.
        </p>
      )}

      {(isFull || isPredictive) && termination.reasons.length > 0 && (
        <details className="rounded border border-slate-200 dark:border-slate-700 px-2.5 py-2 text-xs">
          <summary className="cursor-pointer font-medium text-slate-600 dark:text-slate-300">
            탐색 로그 ({termination.stage_reached}단계
            {termination.action === "proceed_twin" && !conclusion.twin_ran
              ? " · Twin 검토 가능"
              : ""}
            )
          </summary>
          <ol className="list-decimal list-inside space-y-0.5 text-slate-600 dark:text-slate-400 mt-1">
            {termination.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ol>
          {termination.next_stage_hint && (
            <p className="mt-1 text-[11px] text-slate-500">{termination.next_stage_hint}</p>
          )}
        </details>
      )}

      {warnings.length > 0 && (
        <ul className="text-[11px] text-amber-700 dark:text-amber-400 space-y-0.5">
          {warnings.map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
