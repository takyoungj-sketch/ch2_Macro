import { useState } from "react";
import clsx from "clsx";
import type {
  ConclusionBullet,
  CoefficientNarrative,
  DiagnosticCheckItem,
  ModelCandidate,
  RecommendationConclusion,
  RecommendedAction,
  RegressionRecommendResponse,
  RegressionVariableSpec,
  ResponseScale,
} from "../types";
import { CvFitnessBadge, ScopeNLabels } from "../utils/recommendationLabels";

const BLOCK_LABELS: Record<string, string> = {
  gross_area: "연면적",
  land_area: "대지면적",
  building_age: "연식",
  road_width: "도로조건",
  zone_type: "용도지역",
  building_use: "건축물용도",
  asset_type: "유형",
  region_leaf: "지역(읍·면·동/법정리)",
};

const GRADE_LABEL: Record<string, string> = {
  excellent: "매우 양호",
  good: "양호",
  fair: "보통",
  poor: "미흡",
  insufficient_cv: "CV 미산출",
  pending: "평가 중",
};

const BULLET_MARK: Record<ConclusionBullet["kind"], string> = {
  positive: "✔",
  negative: "✖",
  neutral: "·",
};

const VERDICT_BOX: Record<string, string> = {
  adopt_predictive:
    "border-emerald-200 bg-emerald-50/80 dark:border-emerald-900/50 dark:bg-emerald-950/20",
  caution: "border-amber-200 bg-amber-50/80 dark:border-amber-900/50 dark:bg-amber-950/20",
  no_predictive_model: "border-red-200 bg-red-50/80 dark:border-red-900/50 dark:bg-red-950/20",
  explanatory_only:
    "border-slate-200 bg-slate-50/80 dark:border-slate-700 dark:bg-slate-800/50",
};

const VERDICT_BANNER: Record<string, string> = {
  positive:
    "border-emerald-400 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30",
  warning: "border-amber-400 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30",
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
        계수 해석 (설명형 참고)
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

function FinalVerdictBanner({ conclusion }: { conclusion: RecommendationConclusion }) {
  const tone = conclusion.final_verdict_tone ?? "warning";
  return (
    <div className={clsx("rounded-lg border-2 px-3 py-3 space-y-2", VERDICT_BANNER[tone])}>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        최종 판정
      </p>
      <p className="text-xl font-bold leading-tight text-slate-900 dark:text-slate-100">
        {conclusion.final_verdict_emoji} {conclusion.final_verdict_ko}
        {conclusion.cv_mape != null && (
          <span className="ml-2 align-middle">
            <CvFitnessBadge cvMape={conclusion.cv_mape} fitness={conclusion.cv_fitness} />
          </span>
        )}
      </p>
      {conclusion.final_verdict_sublines.length > 0 && (
        <ul className="text-sm text-slate-700 dark:text-slate-300 space-y-0.5">
          {conclusion.final_verdict_sublines.map((line) => (
            <li key={line}>· {line}</li>
          ))}
        </ul>
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
                  a.kind === "do" && "text-emerald-800 dark:text-emerald-300",
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

function blockSummary(blocks: string[]) {
  if (!blocks.length) return "(절편만)";
  return blocks.map((b) => BLOCK_LABELS[b] ?? b).join(" · ");
}

function stars(n: number) {
  return "★".repeat(Math.max(0, Math.min(5, n))) + "☆".repeat(Math.max(0, 5 - Math.min(5, n)));
}

function adoptLabelForMode(mode: string) {
  if (mode === "review_only") return "검토용으로 적용";
  if (mode === "explanatory") return "설명형으로 적용";
  return "이 후보로 분석";
}

type RankTab = "explanatory" | "predictive";

function CandidateMini({
  c,
  role,
  adoptLabel,
  onAdopt,
  onPredict,
  adopting,
  predictActive,
}: {
  c: ModelCandidate;
  role: string;
  adoptLabel?: string;
  onAdopt: () => void;
  onPredict?: () => void;
  adopting?: boolean;
  predictActive?: boolean;
}) {
  return (
    <div className="border border-slate-200 dark:border-slate-600 rounded-md p-2 space-y-1.5">
      <div className="flex items-start gap-2">
        <span className="text-[10px] uppercase tracking-wide text-indigo-600 dark:text-indigo-400 shrink-0">
          {role}
        </span>
        <div className="flex-1 min-w-0 text-xs">
          <p className="font-medium truncate">{blockSummary(c.blocks)}</p>
          <p className="text-slate-500 tabular-nums">
            {c.response_scale} · Adj.R²{" "}
            {c.metrics.adj_r_squared != null ? c.metrics.adj_r_squared.toFixed(3) : "—"} · CV-MAPE{" "}
            {c.metrics.cv_mape != null ? `${c.metrics.cv_mape.toFixed(1)}%` : "—"}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          className="px-2 py-0.5 text-[11px] rounded bg-indigo-600 text-white disabled:opacity-50"
          disabled={adopting}
          onClick={onAdopt}
        >
          {adoptLabel ?? "1단계 모형 적용"}
        </button>
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
            예측 미리보기
          </button>
        )}
      </div>
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
  onAdopt: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  onAdoptPool?: (payload: AdoptPoolPayload) => void;
  adopting?: boolean;
  onPredict?: (vars: RegressionVariableSpec, scale: ResponseScale, label: string) => void;
  predictActiveLabel?: string | null;
  regionNameByCode?: Record<string, string>;
  onRunTwin?: () => void;
  twinRunning?: boolean;
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
}: Props) {
  const [tab, setTab] = useState<RankTab>("predictive");
  const [twinStep, setTwinStep] = useState(0);
  const { stage1, stage2, analysis_scope, termination, warnings, conclusion, diagnostics_checklist, coefficient_narratives } = data;
  const list =
    tab === "explanatory" ? stage1.candidates_explanatory : stage1.candidates_predictive;
  const sat = stage1.satisfaction;
  const gradeLabel = GRADE_LABEL[sat.grade] ?? sat.grade;
  const adoptLabel = adoptLabelForMode(conclusion.adopt_mode);
  const predictiveRole = "현재 최적 후보 (예측형)";
  const explanatoryRole = "현재 최적 후보 (설명형)";

  const showTwinResults =
    stage2 && (stage2.ran ? stage2.pools.length > 0 : Boolean(stage2.skipped_reason));
  const visiblePool = stage2?.ran ? stage2.pools[twinStep] : undefined;

  return (
    <div className="space-y-3 text-sm">
      <FinalVerdictBanner conclusion={conclusion} />

      {conclusion.bullets.length > 0 && (
        <div
          className={clsx(
            "rounded-md border px-2.5 py-2 text-xs space-y-1",
            VERDICT_BOX[conclusion.verdict] ?? VERDICT_BOX.caution,
          )}
        >
          <p className="font-medium text-slate-700 dark:text-slate-200">{conclusion.headline_ko}</p>
          <ul className="space-y-0.5">
            {conclusion.bullets.map((b) => (
              <li
                key={b.text}
                className={clsx(
                  b.kind === "negative" && "text-red-800 dark:text-red-300",
                  b.kind === "positive" && "text-emerald-800 dark:text-emerald-300",
                  b.kind === "neutral" && "text-slate-700 dark:text-slate-300",
                )}
              >
                {BULLET_MARK[b.kind]} {b.text}
              </li>
            ))}
          </ul>
          {conclusion.summary_ko && (
            <p className="text-[11px] leading-relaxed text-slate-600 dark:text-slate-400 pt-1 border-t border-black/5 dark:border-white/10">
              {conclusion.summary_ko}
            </p>
          )}
        </div>
      )}

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

      <div className="rounded-md bg-slate-50 dark:bg-slate-800/50 px-2.5 py-2 text-xs space-y-1">
        <p className="font-medium">{analysis_scope.scope_label || "분석 scope"}</p>
        <ScopeNLabels
          counts={{
            scope_n_tx: analysis_scope.scope_n_tx,
            selection_n: stage1.selection_n,
            fit_n: stage1.fit_n,
          }}
        />
        <p className="text-slate-600 dark:text-slate-300">
          만족 등급{" "}
          <span className="font-medium">
            {gradeLabel} {stars(sat.stars)}
          </span>
        </p>
        <p className="text-slate-400 text-[11px]">
          SSOT 풀({stage1.candidate_pool.length}블록) — 왼쪽 변수 체크와 무관
          {analysis_scope.anchor_unit?.name && <> · anchor {analysis_scope.anchor_unit.name}</>}
        </p>
      </div>

      <DiagnosticChecklist items={diagnostics_checklist ?? []} />
      <CoefficientInsights items={coefficient_narratives ?? []} />

      <div className="grid gap-2 sm:grid-cols-2">
        <CandidateMini
          c={stage1.primary}
          role={predictiveRole}
          adoptLabel={adoptLabel}
          onAdopt={() => onAdopt(stage1.primary.variables, stage1.primary.response_scale)}
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
            onAdopt={() => onAdopt(stage1.alternate!.variables, stage1.alternate!.response_scale)}
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

      <div>
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
        <ul className="space-y-1 max-h-32 overflow-y-auto">
          {list.map((c) => (
            <li
              key={`${tab}-${c.rank}-${c.blocks.join(",")}`}
              className="text-xs flex gap-2 px-1 py-0.5 border-b border-slate-100 dark:border-slate-800"
            >
              <span className="text-indigo-600 w-5">#{c.rank}</span>
              <span className="flex-1 truncate">{blockSummary(c.blocks)}</span>
              <span className="text-slate-500 tabular-nums shrink-0">
                {c.response_scale}
                {tab === "predictive"
                  ? ` · CV ${c.metrics.cv_mape?.toFixed(1) ?? "—"}%`
                  : ` · AIC ${c.aic?.toFixed(0) ?? "—"}`}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {conclusion.twin_recommended && onRunTwin && !conclusion.twin_ran && (
        <div className="rounded-md border border-violet-200 dark:border-violet-900/50 bg-violet-50/40 dark:bg-violet-950/20 p-2.5 space-y-1.5">
          <p className="text-xs font-medium text-violet-900 dark:text-violet-200">
            ② Profile Twin pool 추가 검토
          </p>
          <p className="text-[11px] text-violet-800/90 dark:text-violet-300/90">
            1단계 결과가 충분히 만족스럽지 않을 때, 쌍둥이 지역을 pool에 넣어 표본을 확장합니다.
            식·스케일은 1단계와 동일하게 고정합니다.
          </p>
          <button
            type="button"
            className="px-2.5 py-1 text-xs rounded bg-violet-600 text-white disabled:opacity-50"
            disabled={twinRunning}
            onClick={onRunTwin}
          >
            {twinRunning ? "Twin pool 계산 중…" : "② Twin pool 검토 실행"}
          </button>
        </div>
      )}

      {showTwinResults && stage2 && (
        <div className="border-t border-slate-200 dark:border-slate-700 pt-3 space-y-2">
          <p className="text-xs font-medium text-slate-700 dark:text-slate-200">
            ② Twin pool 결과
            <span className="ml-1 font-normal text-slate-500">
              — {blockSummary(stage2.fixed_blocks)} · {stage2.fixed_response_scale} 고정
            </span>
          </p>

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
                {visiblePool.cv_mape_delta != null && visiblePool.cv_mape_delta > 0 && (
                  <span className="text-emerald-600">
                    △{visiblePool.cv_mape_delta.toFixed(1)}%p vs Local
                  </span>
                )}
                {stage2.local_cv_mape != null &&
                  visiblePool.cv_mape != null &&
                  visiblePool.cv_mape > stage2.local_cv_mape + 0.5 && (
                    <span className="text-red-600">
                      Local {stage2.local_cv_mape.toFixed(1)}%보다 나쁨
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
                  onClick={() =>
                    onAdoptPool({
                      vars: stage1.primary.variables,
                      scale: stage2.fixed_response_scale,
                      regionCodes: visiblePool.region_codes,
                      label: visiblePool.label,
                    })
                  }
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

      {termination.reasons.length > 0 && (
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
