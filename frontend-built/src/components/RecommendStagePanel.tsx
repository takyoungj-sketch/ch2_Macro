import { useEffect, useState, type ReactNode } from "react";
import clsx from "clsx";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type {
  AssetType,
  CoefficientNarrative,
  DiagnosticCheckItem,
  CandidateCvReport,
  CvCoverage,
  ModelCandidate,
  RecommendationPoolCandidate,
  RecommendationStage1,
  RecommendationStage2,
  RegressionLevelResult,
  RegressionRecommendResponse,
  RegressionVariableSpec,
  ResponseScale,
  TwinExperimentStep,
} from "../types";
import { formatResponseScale, ScopeNLabels } from "../utils/recommendationLabels";
import { fmtDecimal, fmtNum } from "../utils/regressionFormat";
import RegressionEffectsTable from "./RegressionEffectsTable";
import RegressionEquation from "./RegressionEquation";
import ZoneCaution from "./ZoneCaution";

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

const KEY_COEF: Record<string, string> = {
  gross_area: "연면적",
  land_area: "대지면적",
  building_age: "연식",
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
  onPredict?: (
    vars: RegressionVariableSpec,
    scale: ResponseScale,
    label: string,
    opts?: { regionCodes?: string[]; fitN?: number; slot?: "twin1" | "twin2" },
  ) => void;
  predictActiveLabel?: string | null;
  twin1PredictActiveLabel?: string | null;
  researchPredictActiveLabel?: string | null;
  regionNameByCode?: Record<string, string>;
  onRunTwin?: () => void;
  twinChoices?: { code: string; rank: number; label: string }[];
  checkedTwinCodes?: string[];
  onToggleTwinCode?: (code: string) => void;
  twinRunning?: boolean;
  onRunTwinResearch?: () => void;
  twinResearchRunning?: boolean;
  /** Profile Twin 이웃 조회 상태. ready 일 때만 실험 요청을 보낸다. */
  twinCandidateStatus?: "loading" | "ready" | "none";
  /** @deprecated 4단계 스토리로 통합. 호출부 호환만 유지 */
  mode?: "full" | "predictive" | "explanatory";
  predictPanel?: ReactNode;
  twin1PredictPanel?: ReactNode;
  researchPredictPanel?: ReactNode;
  assetType?: AssetType;
  minePrimary?: RegressionLevelResult | null;
  mineScale?: ResponseScale | null;
};

function cvWhen(slice?: CvCoverage | null): string {
  if (!slice) return "";
  const years = slice.years?.length ? `${slice.years.join("·")}년` : "";
  const n = slice.n_trades != null ? `${slice.n_trades}건` : "";
  return [years, n].filter(Boolean).join(" · ");
}

function confirmGapPp(report?: CandidateCvReport | null): number | null {
  const search = report?.search?.mape;
  const confirm = report?.confirm?.mape;
  if (search == null || confirm == null) return null;
  return confirm - search;
}

function confirmIsWeaker(report?: CandidateCvReport | null): boolean {
  const gap = confirmGapPp(report);
  return gap != null && gap >= 10;
}

type WorkspaceTab = "predict" | "explain" | "twin";

const WORKSPACE_TABS: { id: WorkspaceTab; label: string }[] = [
  { id: "predict", label: "예측형" },
  { id: "explain", label: "설명형" },
  { id: "twin", label: "쌍둥이 확장" },
];

function WorkspaceTabs({
  value,
  onChange,
}: {
  value: WorkspaceTab;
  onChange: (next: WorkspaceTab) => void;
}) {
  return (
    <div
      className="inline-flex flex-wrap rounded-md border border-slate-200 bg-slate-50 p-0.5 text-sm dark:border-slate-600 dark:bg-slate-900/70"
      role="tablist"
      aria-label="모형 탐색 작업"
    >
      {WORKSPACE_TABS.map((tab) => {
        const selected = value === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            className={clsx(
              "px-3 py-1.5 rounded whitespace-nowrap transition-colors",
              selected && tab.id === "predict" && "bg-white shadow-sm font-medium text-indigo-800 dark:bg-slate-700 dark:text-indigo-200",
              selected && tab.id === "explain" && "bg-white shadow-sm font-medium text-teal-800 dark:bg-slate-700 dark:text-teal-200",
              selected && tab.id === "twin" && "bg-white shadow-sm font-medium text-violet-800 dark:bg-slate-700 dark:text-violet-200",
              !selected && "text-slate-500 dark:text-slate-400",
            )}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

function blockSummary(blocks: string[]) {
  if (!blocks.length) return "(절편만)";
  return blocks.map((b) => BLOCK_LABELS[b] ?? b).join(" · ");
}

function resolveRecommendAssetType(assetType: AssetType | undefined, slice: string): AssetType {
  if (assetType) return assetType;
  if (slice && slice !== "unified") return slice as AssetType;
  return "commercial";
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

function signBits(coefs?: Record<string, number> | null): string {
  if (!coefs) return "—";
  const bits: string[] = [];
  for (const [key, label] of Object.entries(KEY_COEF)) {
    const v = coefs[key];
    if (v == null || !Number.isFinite(v)) continue;
    bits.push(`${label} ${v >= 0 ? "+" : "−"}`);
  }
  return bits.length ? bits.join(" · ") : "—";
}

function signsHold(
  local?: Record<string, number> | null,
  twin?: Record<string, number> | null,
): boolean | null {
  if (!local || !twin) return null;
  let compared = 0;
  for (const key of Object.keys(KEY_COEF)) {
    const a = local[key];
    const b = twin[key];
    if (a == null || b == null || !Number.isFinite(a) || !Number.isFinite(b)) continue;
    compared += 1;
    if (Math.sign(a) !== Math.sign(b) && !(a === 0 && b === 0)) return false;
  }
  return compared > 0 ? true : null;
}

function StageSection({
  index,
  title,
  children,
}: {
  index: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-2.5 border-t border-slate-200 dark:border-slate-700 pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
        {index} {title}
      </h3>
      {children}
    </section>
  );
}

function CheckChips({ items }: { items: DiagnosticCheckItem[] }) {
  if (!items.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5 text-xs">
        {items.map((item) => (
        <li
          key={item.check_id}
          className={clsx("rounded border px-1.5 py-0.5", CHECK_CLASS[item.status])}
          title={item.summary_ko}
        >
          {CHECK_MARK[item.status]} {item.label_ko}
          </li>
        ))}
      </ul>
  );
}

function CoefficientInsights({ items }: { items: CoefficientNarrative[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-2 space-y-1.5">
      <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">계수 해석</p>
      <ul className="space-y-1.5 text-sm">
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
    </div>
  );
}

export default function RecommendStagePanel({
  data,
  onAdoptPool,
  adopting,
  onPredict,
  predictActiveLabel: _predictActiveLabel,
  twin1PredictActiveLabel,
  researchPredictActiveLabel,
  regionNameByCode = {},
  onRunTwin,
  twinChoices = [],
  checkedTwinCodes = [],
  onToggleTwinCode,
  twinRunning,
  onRunTwinResearch,
  twinResearchRunning,
  twinCandidateStatus = "none",
  predictPanel,
  twin1PredictPanel,
  researchPredictPanel,
  assetType,
  minePrimary,
  mineScale,
}: Props) {
  const [twinStep, setTwinStep] = useState(0);
  const [workspace, setWorkspace] = useState<WorkspaceTab>("predict");
  const {
    stage1,
    stage2,
    analysis_scope,
    termination,
    warnings,
    conclusion,
    diagnostics_checklist,
    coefficient_narratives,
  } = data;
  const primary = stage1.primary;
  const extremeRate = stage1.primary_cv_extreme_rate ?? 0;
  const ranking = stage1.candidates_predictive ?? [];
  const rankingKey = ranking
    .map((c) => `${c.rank}:${c.response_scale}:${c.blocks.join(",")}`)
    .join("|");
  const defaultRank = ranking[0]?.rank ?? 1;
  const [selectedRank, setSelectedRank] = useState(defaultRank);
  useEffect(() => {
    setSelectedRank(defaultRank);
  }, [rankingKey, defaultRank]);
  const judgmentByRank = new Map(
    (stage1.predictive_judgments ?? []).map((row) => [row.rank, row]),
  );
  const selected = ranking.find((c) => c.rank === selectedRank) ?? ranking[0] ?? primary;
  const selectedLabel =
    judgmentByRank.get(selected.rank)?.label ??
    (selected.rank === primary.rank ? "예측 최소" : "비교 후보");
  const selectedIsPrimary =
    selected.response_scale === primary.response_scale &&
    selected.blocks.join(",") === primary.blocks.join(",");
  const resolvedAssetType = resolveRecommendAssetType(assetType, analysis_scope.asset_slice);
  const checks = diagnostics_checklist ?? [];
  const sampleChecks = checks.filter((c) => c.check_id === "sample");
  const resultChecks = checks.filter((c) => c.check_id !== "sample" && c.check_id !== "regional");
  const twinChecks = checks.filter((c) => c.check_id === "regional");

  const emptyTwinSkip = Boolean(
    stage2?.skipped_reason?.includes("Profile Twin 후보가 전달되지"),
  );
  const twin1Done = Boolean(
    stage2 &&
      (stage2.ran ||
        stage2.inspect_pool ||
        (Boolean(stage2.skipped_reason) && !emptyTwinSkip)),
  );
  const showTwinResults = twin1Done;
  const canRunTwin =
    twinCandidateStatus === "ready" && Boolean(onRunTwin) && checkedTwinCodes.length > 0;
  const adminLevel = (analysis_scope.admin_level || "").toLowerCase();
  const twinBlockedAdmin = adminLevel === "sigungu" || adminLevel === "gu";
  const visiblePool = stage2?.ran
    ? (stage2.pools?.[twinStep] ?? stage2.inspect_pool ?? undefined)
    : undefined;
  const inspectPool = stage2?.inspect_pool ?? visiblePool;
  const twinSteps = stage2?.twin_experiments ?? [];
  const localStep = twinSteps.find((s) => s.step_id === "local");
  const twinStepPick =
    twinSteps.find((s) => s.search_picked && s.step_id !== "local") ??
    twinSteps.find((s) => s.selected && s.step_id !== "local");
  const hold = signsHold(localStep?.key_coefficients, twinStepPick?.key_coefficients);
  const explanatory = stage1.alternate;
  const explDiffers =
    Boolean(explanatory) &&
    (explanatory!.response_scale !== primary.response_scale ||
      explanatory!.blocks.join(",") !== primary.blocks.join(","));
  const representativeConfirmed = stage1.representative_confirmed !== false;
  const searchWhen = cvWhen(primary.cv_report?.search);
  const confirmWhen = cvWhen(primary.cv_report?.confirm);
  const primaryGap = confirmGapPp(primary.cv_report);
  const withholdReasons = (() => {
    if (representativeConfirmed) return [];
    const search = primary.cv_report?.search;
    const confirm = primary.cv_report?.confirm;
    const lines: string[] = [];
    if (search?.mape == null || (search.folds ?? 0) < 2) {
      lines.push("탐색 검증이 한 해입니다.");
    }
    if ((search?.n_trades ?? 0) < 10) {
      lines.push("탐색에 쓴 거래가 10건 미만입니다.");
    }
    if ((confirm?.years?.length ?? 0) > 0 && confirm?.mape == null) {
      lines.push("마지막 연도 확인을 계산하지 못했습니다.");
    }
    if (primaryGap != null && primaryGap >= 10) {
      lines.push(`확인 오차가 탐색보다 ${primaryGap.toFixed(1)}%p 큽니다.`);
    }
    if (!lines.length && stage1.representative_note) lines.push(stage1.representative_note);
    return lines;
  })();

  return (
    <div className="space-y-1.5 text-base">
      <ScopeNLabels
        counts={{
          scope_n_tx: analysis_scope.scope_n_tx,
          selection_n: stage1.selection_n,
          fit_n: stage1.fit_n,
          include_partial: analysis_scope.include_partial,
          partial_tx_count: analysis_scope.partial_tx_count,
        }}
        compact
        className="text-xs text-slate-500 mb-2"
      />
      {(stage1.sample_drop_notes?.length ?? 0) > 0 && (
        <p className="text-xs text-slate-500 mb-2">
          {stage1.sample_drop_notes!.join(" · ")}
        </p>
      )}

      <WorkspaceTabs value={workspace} onChange={setWorkspace} />

      {workspace === "predict" && (
      <div role="tabpanel" className="space-y-2.5">
        <p className="text-xs text-slate-500">
          거래가격을 가장 잘 예측하는 식입니다. 순위는 탐색 CV이고, 확인 CV로 대표모형 확정을 가릅니다.
        </p>
        <div
          className={clsx(
            "rounded-lg border-2 px-3 py-3 space-y-2",
            representativeConfirmed
              ? "border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-950/20"
              : "border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30",
          )}
        >
          <p
            className={clsx(
              "text-sm font-semibold",
              representativeConfirmed
                ? "text-indigo-800 dark:text-indigo-200"
                : "text-amber-900 dark:text-amber-200",
            )}
          >
            {representativeConfirmed ? "예측 최소" : "탐색 1위 · 대표모형 미확정"}
          </p>
          <p className="text-sm text-slate-800 dark:text-slate-100">
            {formatResponseScale(primary.response_scale)} · {blockSummary(primary.blocks)}
          </p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded border border-slate-200/80 dark:border-slate-600 bg-white/70 dark:bg-slate-900/40 px-2 py-1.5">
              <p className="text-xs text-slate-500">탐색 CV-MAPE</p>
              <p className="text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                {primary.metrics.cv_mape != null ? `${primary.metrics.cv_mape.toFixed(2)}%` : "—"}
              </p>
              {searchWhen && <p className="text-xs text-slate-500">{searchWhen}</p>}
            </div>
            <div
              className={clsx(
                "rounded border px-2 py-1.5",
                representativeConfirmed
                  ? "border-slate-200/80 dark:border-slate-600 bg-white/70 dark:bg-slate-900/40"
                  : "border-amber-300 dark:border-amber-700 bg-white/80 dark:bg-slate-900/50",
              )}
            >
              <p className="text-xs text-slate-500">확인 CV-MAPE</p>
              <p
                className={clsx(
                  "text-lg font-semibold tabular-nums",
                  representativeConfirmed
                    ? "text-slate-900 dark:text-slate-100"
                    : "text-amber-900 dark:text-amber-200",
                )}
              >
                {primary.cv_report?.confirm?.mape != null
                  ? `${primary.cv_report.confirm.mape.toFixed(2)}%`
                  : "—"}
              </p>
              <p className="text-xs text-slate-500">
                {confirmWhen || stage1.primary_confirm_note || "확인 없음"}
              </p>
            </div>
          </div>
          {representativeConfirmed ? (
            <p className="text-sm text-slate-700 dark:text-slate-200">
              이 식을 이 지역 거래의 예측 기준선으로 둡니다. 왼쪽 기본 통계 식은 바꾸지 않습니다.
            </p>
          ) : (
            <div className="text-sm text-amber-950 dark:text-amber-100 space-y-0.5">
              {withholdReasons.map((line) => (
                <p key={line}>{line}</p>
              ))}
              <p>이 식을 지역 대표 예측모형으로 확정하지 않았습니다.</p>
              <p>왼쪽 기본 통계 식은 바꾸지 않습니다. 쌍둥이 확장은 이 탐색 1위를 출발점으로 씁니다.</p>
            </div>
          )}
          {stage1.satisfaction.label_ko && (
            <p className="text-xs text-slate-500">
              등급 {stage1.satisfaction.label_ko}
              {stage1.satisfaction.stars > 0 && ` ${"★".repeat(stage1.satisfaction.stars)}`}
              {stage1.satisfaction.grade_basis === "confirm" && " · 확인 CV 기준"}
            </p>
          )}
        </div>

        <CheckChips items={sampleChecks} />
        {warnings.length > 0 && (
          <ul className="text-xs text-amber-700 dark:text-amber-400 space-y-0.5">
            {warnings.map((w) => (
              <li key={w}>⚠ {w}</li>
            ))}
          </ul>
        )}

        <div className="overflow-x-auto rounded-md border border-slate-200 dark:border-slate-700">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="text-slate-500 border-b border-slate-200 dark:border-slate-700">
                <th className="py-1.5 px-2 font-medium">순위</th>
                <th className="py-1.5 pr-2 font-medium">척도</th>
                <th className="py-1.5 pr-2 font-medium">변수</th>
                <th className="py-1.5 pr-2 font-medium">탐색 CV</th>
                <th className="py-1.5 pr-2 font-medium">확인 CV</th>
                <th className="py-1.5 pr-2 font-medium">차이(%p)</th>
                <th className="py-1.5 pr-2 font-medium">상태</th>
              </tr>
            </thead>
            <tbody>
              {ranking.map((c) => {
                const judged = judgmentByRank.get(c.rank);
                const gap = judged?.cv_gap_pp;
                const label = judged?.label ?? (c.rank === 1 ? "예측 최소" : "비교 후보");
                const interpretive = label.includes("해석 후보");
                const status = label.replace(" · 해석 후보", "");
                const rowUnconfirmed = c.rank === primary.rank && !representativeConfirmed;
                const confirmWeak = confirmIsWeaker(c.cv_report);
                return (
                <tr
                  key={`${c.rank}-${c.response_scale}-${c.blocks.join(",")}`}
                  role="button"
                  tabIndex={0}
                  aria-pressed={c.rank === selected.rank}
                  onClick={() => setSelectedRank(c.rank)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedRank(c.rank);
                    }
                  }}
                className={clsx(
                    "cursor-pointer border-b border-slate-100 dark:border-slate-800 last:border-0",
                    c.rank === selected.rank && "bg-indigo-50/70 dark:bg-indigo-950/30",
                  )}
                >
                  <td className="py-1.5 px-2 tabular-nums font-semibold text-indigo-700 dark:text-indigo-300">
                    #{c.rank}
                  </td>
                  <td className="py-1.5 pr-2">{formatResponseScale(c.response_scale)}</td>
                  <td className="py-1.5 pr-2">{blockSummary(c.blocks)}</td>
                  <td className="py-1.5 pr-2 tabular-nums">
                    {c.metrics.cv_mape != null ? `${c.metrics.cv_mape.toFixed(2)}%` : "—"}
                    {cvWhen(c.cv_report?.search) && (
                      <div className="text-[10px] leading-snug text-slate-500">{cvWhen(c.cv_report?.search)}</div>
                    )}
                  </td>
                  <td
                    className={clsx(
                      "py-1.5 pr-2 tabular-nums",
                      confirmWeak && "text-amber-800 dark:text-amber-300 font-medium",
                    )}
                  >
                    {c.cv_report?.confirm?.mape != null
                      ? `${c.cv_report.confirm.mape.toFixed(2)}%`
                      : c.cv_report?.confirm?.years?.length
                        ? "계산 없음"
                        : "—"}
                    {cvWhen(c.cv_report?.confirm) && (
                      <div className="text-[10px] leading-snug font-normal text-slate-500">
                        {cvWhen(c.cv_report?.confirm)}
                      </div>
                    )}
                  </td>
                  <td className="py-1.5 pr-2 tabular-nums">
                    {gap == null ? "—" : gap === 0 ? "0.00" : `+${gap.toFixed(2)}`}
                  </td>
                  <td className="py-1.5 pr-2 text-slate-600 dark:text-slate-300">
                    <div>{status}</div>
                    {rowUnconfirmed && (
                      <div className="mt-0.5 inline-block rounded bg-amber-200/80 px-1.5 py-0.5 text-[10px] font-semibold text-amber-950 dark:bg-amber-900/60 dark:text-amber-100">
                        미확정
                      </div>
                    )}
                    {interpretive && <div className="text-[10px] text-slate-500">해석 후보</div>}
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <p className="text-xs text-slate-500">
          순위를 누르면 그 식과 계수를 봅니다. Local 기준선과 Twin은 예측 최소 식입니다.
        </p>

        <div className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-3 space-y-2">
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            #{selected.rank} · {selectedLabel}
            <span className="ml-2 text-xs font-medium text-slate-500">
              {formatResponseScale(selected.response_scale)} · {blockSummary(selected.blocks)}
            </span>
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <div className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5">
              <p className="text-slate-500">탐색 CV</p>
              <p className="font-medium tabular-nums">
                {selected.metrics.cv_mape != null ? `${selected.metrics.cv_mape.toFixed(2)}%` : "—"}
              </p>
              {cvWhen(selected.cv_report?.search) && (
                <p className="text-[10px] text-slate-500">{cvWhen(selected.cv_report?.search)}</p>
              )}
            </div>
            <div className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5">
              <p className="text-slate-500">확인 CV</p>
              <p
                className={clsx(
                  "font-medium tabular-nums",
                  confirmIsWeaker(selected.cv_report) && "text-amber-800 dark:text-amber-300",
                )}
              >
                {selected.cv_report?.confirm?.mape != null
                  ? `${selected.cv_report.confirm.mape.toFixed(2)}%`
                  : "—"}
              </p>
              {cvWhen(selected.cv_report?.confirm) && (
                <p className="text-[10px] text-slate-500">{cvWhen(selected.cv_report?.confirm)}</p>
              )}
            </div>
            <div className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5">
              <p className="text-slate-500">Adj R²</p>
              <p className="font-medium tabular-nums">
                {selected.metrics.adj_r_squared != null
                  ? selected.metrics.adj_r_squared.toFixed(3)
                  : "—"}
              </p>
            </div>
            <div className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5">
              <p className="text-slate-500">학습 MAPE</p>
              <p className="font-medium tabular-nums">
                {selected.metrics.mape != null ? `${selected.metrics.mape.toFixed(2)}%` : "—"}
              </p>
            </div>
          </div>
          <CandidateEquationBlock
            candidate={selected}
            assetType={resolvedAssetType}
            narratives={selectedIsPrimary ? (coefficient_narratives ?? []) : []}
          />
          <p className="text-xs text-slate-500 leading-relaxed">
            이 식과 계수는 탐색에 쓴 같은 표본입니다. 값 계산은 이 식의 열만 보고 다시 적합하므로,
            순위표에서 뺀 숫자 결측이 이 식에 없으면 건수가 달라질 수 있습니다.
          </p>
          {onPredict && (
            <details
              key={`${selected.rank}-${selected.response_scale}-${selected.blocks.join(",")}`}
              className="rounded-md border border-slate-200 dark:border-slate-700 px-2.5 py-2"
              onToggle={(e) => {
                if ((e.target as HTMLDetailsElement).open) {
                  onPredict(
                    selected.variables,
                    selected.response_scale,
                    `#${selected.rank} ${selectedLabel}`,
                  );
                }
              }}
            >
              <summary className="cursor-pointer text-sm font-semibold text-slate-700 dark:text-slate-200">
                이 순위로 값 계산해 보기
              </summary>
              <p className="mt-2 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                통계적 추정값입니다. 지역 거래자료에서 관찰된 변수 간 관계를 이용해 산출한 참고값이며,
                개별 대상물건의 감정평가액이나 AVM 가격이 아닙니다.
              </p>
              {predictPanel}
            </details>
          )}
        </div>

        {(stage1.parity_notes?.length ?? 0) > 0 && (
          <div className="space-y-1">
            {stage1.parity_notes!.map((note) => (
              <p key={note} className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {note}
              </p>
            ))}
          </div>
        )}

        {stage1.assessed_side?.note && (
          <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
            {stage1.assessed_side.note}
          </p>
        )}

        {(stage1.primary_cv_median_ape != null || stage1.primary_cv_extreme_rate != null) && (
          <p className="text-xs text-slate-600 dark:text-slate-300">
            {stage1.primary_cv_median_ape != null && (
              <>중위 오차 {stage1.primary_cv_median_ape.toFixed(1)}%</>
            )}
            {stage1.primary_cv_extreme_rate != null && (
              <span className={extremeRate > 0.05 ? "text-amber-700 dark:text-amber-400" : ""}>
                {stage1.primary_cv_median_ape != null ? " · " : ""}
                범위 밖 예측 {(extremeRate * 100).toFixed(1)}%
              </span>
            )}
          </p>
        )}
        {extremeRate > 0.05 && (
          <p className="text-sm text-amber-800 dark:text-amber-300 leading-relaxed">
            예측 {(extremeRate * 100).toFixed(0)}%가 학습 거래 가격 범위를 한 자릿수 이상 벗어났습니다.
            평균 오차가 낮아도 개별 예측이 불안정할 수 있습니다.
          </p>
        )}
        <details className="text-xs text-slate-500">
          <summary className="cursor-pointer">CV를 읽는 법</summary>
          <p className="mt-1 leading-relaxed">
            순위는 마지막 연도를 뺀 탐색 CV가 낮은 순입니다. 최저보다 1.0%p 이내이고 표본이 같으면
            성능 유사입니다. 이 폭은 화면 규칙이며 통계적 동률이 아닙니다. 확인 CV는 고르는 데 쓰지
            않은 마지막 연도입니다. 탐색 CV만으로 이 지역 전체의 기대오차라고 읽지 않습니다.
          </p>
        </details>
      </div>
      )}

      {workspace === "explain" && (
        <div role="tabpanel" className="space-y-2.5">
          <p className="text-xs text-slate-500">
            가격 차이를 설명하는 식입니다. log·log-log 중에서 AIC가 가장 낮은 식을 보여 줍니다.
            예측형 순위와 별개이며, 특정 변수를 우선해 고르지 않습니다.
          </p>
          {explanatory ? (
            <div className="rounded-lg border border-teal-200 dark:border-teal-800 bg-teal-50/40 dark:bg-teal-950/20 px-3 py-3 space-y-2">
              <p className="text-sm font-semibold text-teal-900 dark:text-teal-100">AIC 1위</p>
              <p className="text-sm text-slate-800 dark:text-slate-100">
                {formatResponseScale(explanatory.response_scale)} · {blockSummary(explanatory.blocks)}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="rounded border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/40 px-2 py-1.5">
                  <p className="text-slate-500">AIC</p>
                  <p className="font-medium tabular-nums">
                    {explanatory.aic != null ? explanatory.aic.toFixed(1) : "—"}
                  </p>
                </div>
                <div className="rounded border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/40 px-2 py-1.5">
                  <p className="text-slate-500">Adj R²</p>
                  <p className="font-medium tabular-nums">
                    {explanatory.metrics.adj_r_squared != null
                      ? explanatory.metrics.adj_r_squared.toFixed(3)
                      : "—"}
                  </p>
                </div>
                <div className="rounded border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/40 px-2 py-1.5">
                  <p className="text-slate-500">학습 MAPE</p>
                  <p className="font-medium tabular-nums">
                    {explanatory.metrics.mape != null ? `${explanatory.metrics.mape.toFixed(2)}%` : "—"}
                  </p>
                </div>
                <div className="rounded border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/40 px-2 py-1.5">
                  <p className="text-slate-500">탐색 CV</p>
                  <p className="font-medium tabular-nums">
                    {explanatory.metrics.cv_mape != null ? `${explanatory.metrics.cv_mape.toFixed(2)}%` : "—"}
                  </p>
                </div>
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-200">
                {explDiffers
                  ? `예측형 탐색 1위는 ${formatResponseScale(primary.response_scale)} · ${blockSummary(primary.blocks)} 입니다. 이 AIC 1위는 그 순위를 바꾸지 않습니다.`
                  : "예측형 탐색 1위와 같은 식입니다."}
              </p>
              <CandidateEquationBlock
                candidate={explanatory}
                assetType={resolvedAssetType}
                narratives={[]}
              />
            </div>
          ) : (
            <p className="text-sm text-slate-500">설명형으로 고를 수 있는 식이 없습니다.</p>
          )}
        </div>
      )}

      {workspace === "twin" && (
      <div role="tabpanel" className="space-y-1.5">
        <p className="text-xs text-slate-500">
          출발점은 예측형 탐색 1위입니다. 대표모형 확정과는 별개이며, 기본 통계 식은 바꾸지 않습니다.
          {!representativeConfirmed && " 지금은 탐색 1위를 대표모형으로 확정하지 않은 상태입니다."}
        </p>

      <StageSection index="②" title="Local 기준선">
        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          선택 지역 거래만으로 본 예측 최소 식입니다. Twin 실험1을 눌러도 이 식은 바뀌지 않습니다.
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
          <div className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5">
            <p className="text-slate-500">척도</p>
            <p className="font-medium">{formatResponseScale(primary.response_scale)}</p>
          </div>
          <div className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5">
            <p className="text-slate-500">적합 표본</p>
            <p className="font-medium tabular-nums">{stage1.fit_n}</p>
          </div>
          <div className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5">
            <p className="text-slate-500">Adj R²</p>
            <p className="font-medium tabular-nums">
              {primary.metrics.adj_r_squared != null
                ? primary.metrics.adj_r_squared.toFixed(3)
                : "—"}
      </p>
    </div>
          <div className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5">
            <p className="text-slate-500">CV-MAPE</p>
            <p className="font-medium tabular-nums">
              {primary.metrics.cv_mape != null ? `${primary.metrics.cv_mape.toFixed(1)}%` : "—"}
            </p>
    </div>
        </div>

        {(conclusion.macro_diagnosis?.summary_ko || conclusion.summary_ko) && (
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            {conclusion.macro_diagnosis?.summary_ko || conclusion.summary_ko}
          </p>
        )}
        <CheckChips items={resultChecks} />
        <p className="text-xs text-slate-500 leading-relaxed">
          식과 값 계산은 예측형 탭에서 고른 순위입니다. 이 절의 숫자는 예측 최소 식입니다.
        </p>

        {(stage1.provision_notes?.length ?? 0) > 0 && (
          <div className="space-y-1">
            {stage1.provision_notes!.map((note) => (
              <p key={note} className="text-[11px] leading-snug text-slate-600 dark:text-slate-300">
                {note}
              </p>
            ))}
          </div>
        )}
      </StageSection>

      <StageSection index="③" title="추가 지역">
        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          위의 Local 식은 그대로 둡니다. 목록에서 지역을 고르면 그 거래를 지금 지역과 한 표본으로
          합치고, 지역 더미를 넣어 다시 적합합니다. 예측오차와 계수 방향으로 적용 여부를 판단합니다.
        </p>
        <CheckChips items={twinChecks} />

        {twinCandidateStatus === "loading" && (
          <p className="text-sm text-slate-500">유사 지역 후보를 불러오는 중…</p>
        )}

        {twinCandidateStatus === "none" && (
          <p className="text-sm text-slate-500">
            {twinBlockedAdmin
              ? "시군구·구 초점에는 쌍둥이 확장을 붙이지 않습니다."
              : "이 지역의 쌍둥이 후보가 없어 실험을 돌릴 수 없습니다."}
          </p>
        )}

        {twinChoices.length > 0 && (
          <div className="modal-table-wrap">
            <table className="w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left w-8">선택</th>
                  <th className="text-right">순위</th>
                  <th className="text-left">지역</th>
                </tr>
              </thead>
              <tbody>
                {twinChoices.map((row) => (
                  <tr key={row.code}>
                    <td>
                      <input
                        type="checkbox"
                        checked={checkedTwinCodes.includes(row.code)}
                        onChange={() => onToggleTwinCode?.(row.code)}
                        aria-label={`${row.rank}위 ${row.label}`}
                      />
                    </td>
                    <td className="text-right tabular-nums">{row.rank}</td>
                    <td>{row.label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {twinCandidateStatus === "ready" && checkedTwinCodes.length === 0 && (
          <p className="text-sm text-slate-500">추가할 지역을 하나 이상 고르면 통합회귀를 실행할 수 있습니다.</p>
        )}

        {conclusion.twin_recommended && twinCandidateStatus === "ready" && (
          <p className="text-sm text-violet-900 dark:text-violet-100">
            Local 표본만으로는 예측 기준선이 얇을 수 있어, 유사 지역 거래를 보탠 검증을 권합니다.
          </p>
        )}

        {twinCandidateStatus === "ready" && (
          <button
            type="button"
            className="px-2.5 py-1 text-sm rounded bg-violet-600 text-white disabled:opacity-50"
            disabled={!canRunTwin || twinRunning}
            onClick={onRunTwin}
          >
            {twinRunning ? "적합 중…" : "통합회귀 실행"}
          </button>
        )}

        {showTwinResults && stage2 && (
          <TwinStructureResult
            stage2={stage2}
            localStep={localStep}
            twinStepPick={twinStepPick}
            hold={hold}
            regionNameByCode={regionNameByCode}
            visiblePool={visiblePool}
            twinStepIndex={twinStep}
            setTwinStep={setTwinStep}
            onAdoptPool={onAdoptPool}
            inspectPool={inspectPool}
            onPredict={onPredict}
            twin1PredictPanel={twin1PredictPanel}
            twin1PredictActiveLabel={twin1PredictActiveLabel}
            stage1={stage1}
            adopting={adopting}
          />
        )}
      </StageSection>

      <StageSection index="④" title="Twin 실험2">
        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          선택한 지역을 보탠 표본에서 예측형 식을 다시 고릅니다. 출시 전 확인용이며 기본 통계 식은 바꾸지
          않습니다.
        </p>

        {!twin1Done && (
          <p className="text-sm text-slate-500">
            통합회귀를 실행하면 그 표본으로 식을 다시 고를 수 있습니다.
                  </p>
                )}

        {twinResearchRunning && !stage2?.research_ran && (
          <p className="text-sm text-amber-800 dark:text-amber-200">Twin 실험2를 계산 중…</p>
        )}

        {twin1Done && onRunTwinResearch && !stage2?.research_ran && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 px-2.5 py-2">
            <p className="text-sm text-amber-950 dark:text-amber-100">
              Twin1과 같은 1위 표본에서 CV-MAPE로 식을 다시 고릅니다. Local 식과 Twin1 식은 그대로 둡니다.
            </p>
                  <button
                    type="button"
              className="px-2.5 py-1 text-sm rounded bg-amber-600 text-white disabled:opacity-50"
              disabled={twinResearchRunning || !stage2?.ran}
              onClick={onRunTwinResearch}
            >
              {twinResearchRunning ? "Twin 실험2 중…" : "Twin 실험2"}
                  </button>
              </div>
            )}

        {stage2?.research_ran && (
          <TwinResearchResult
            stage2={stage2}
            stage1={stage1}
            inspectPool={inspectPool}
            researchPredictPanel={researchPredictPanel}
            onPredict={onPredict}
            researchPredictActiveLabel={researchPredictActiveLabel}
          />
        )}
      </StageSection>

      <StageSection index="⑤" title="모형 비교">
        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          기본 회귀실험 · Local · Twin1 · Twin2를 나란히 봅니다. 아직 돌리지 않은 열은 비워 둡니다. 기본
          통계 식은 바꾸지 않습니다.
        </p>
        <ModelCompareTable
          mine={minePrimary ?? null}
          mineScale={mineScale ?? null}
          primary={primary}
          fitN={stage1.fit_n}
          twinRan={Boolean(stage2?.ran)}
          twinPool={stage2?.inspect_pool ?? stage2?.primary ?? visiblePool ?? null}
          hold={hold}
          twinAdopted={Boolean(stage2?.twin_validation?.twin_adopt_recommended)}
          twin2Ran={Boolean(stage2?.research_ran)}
          twin2Pool={stage2?.research ?? null}
        />
      </StageSection>
      </div>
      )}

      {termination.reasons.length > 0 && (
        <details className="rounded border border-slate-200 dark:border-slate-700 px-2.5 py-2 text-sm">
          <summary className="cursor-pointer font-medium text-slate-600 dark:text-slate-300">
            탐색 로그
          </summary>
          <ol className="list-decimal list-inside space-y-0.5 text-slate-600 dark:text-slate-400 mt-1">
            {termination.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ol>
        </details>
        )}
      </div>
    );
  }

function CandidateEquationBlock({
  candidate,
  assetType,
  narratives,
}: {
  candidate: ModelCandidate;
  assetType: AssetType;
  narratives: CoefficientNarrative[];
}) {
  const coeffs = candidate.coefficients ?? [];
  if (!coeffs.length) return null;
  return (
    <div className="space-y-1">
      <details className="text-sm">
        <summary className="cursor-pointer text-slate-600 dark:text-slate-400 font-medium inline-flex items-center gap-1">
          회귀식 · 계수
          <StatsGlossaryHelp termId="coefficient" size="xs" />
        </summary>
        <div className="mt-2 space-y-1">
          <RegressionEquation
            coefficients={coeffs}
            responseScale={candidate.response_scale}
            assetType={assetType}
          />
          <RegressionEffectsTable
            coefficients={coeffs}
            responseScale={candidate.response_scale}
            assetType={assetType}
          />
          <CoefficientInsights items={narratives} />
        </div>
      </details>
      <ZoneCaution />
    </div>
  );
}

function TwinStructureResult({
  stage2,
  localStep,
  twinStepPick,
  hold,
  regionNameByCode,
  visiblePool,
  twinStepIndex,
  setTwinStep,
  onAdoptPool,
  inspectPool,
  onPredict,
  twin1PredictPanel,
  twin1PredictActiveLabel,
  stage1,
  adopting,
}: {
  stage2: RecommendationStage2;
  localStep?: TwinExperimentStep;
  twinStepPick?: TwinExperimentStep;
  hold: boolean | null;
  regionNameByCode: Record<string, string>;
  visiblePool?: RecommendationPoolCandidate;
  twinStepIndex: number;
  setTwinStep: (fn: (s: number) => number) => void;
  onAdoptPool?: (payload: AdoptPoolPayload) => void;
  inspectPool?: RecommendationPoolCandidate;
  onPredict?: (
    vars: RegressionVariableSpec,
    scale: ResponseScale,
    label: string,
    opts?: { regionCodes?: string[]; fitN?: number; slot?: "twin1" | "twin2" },
  ) => void;
  twin1PredictPanel?: ReactNode;
  twin1PredictActiveLabel?: string | null;
  stage1: RecommendationStage1;
  adopting?: boolean;
}) {
  if (!stage2.ran && stage2.skipped_reason) {
    return <p className="text-sm text-slate-500">{stage2.skipped_reason}</p>;
  }

  const twinLabel =
    twinStepPick?.region_codes
      .map((c) => regionNameByCode[c] ?? c.slice(-8))
      .join(" + ") || twinStepPick?.label;
  const adopted = Boolean(stage2.twin_validation?.twin_adopt_recommended);
  const predictPool = inspectPool ?? visiblePool;
  const twin1PredictActive = Boolean(twin1PredictActiveLabel?.startsWith("Twin 재적합"));
  const twinCv = twinStepPick?.search_cv_mape ?? visiblePool?.cv_mape ?? inspectPool?.cv_mape;
  const localCv = localStep?.search_cv_mape ?? stage2.local_cv_mape;
  const twinConfirm =
    twinStepPick?.confirm_cv_mape ?? visiblePool?.confirm_cv_mape ?? inspectPool?.confirm_cv_mape;
  const localConfirm = localStep?.confirm_cv_mape ?? stage2.local_confirm_cv_mape;

  return (
    <div className="space-y-2 rounded-md border border-violet-200 dark:border-violet-900/50 bg-violet-50/40 dark:bg-violet-950/15 p-2.5">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="text-slate-500">
              <th className="py-1 pr-2 font-medium"> </th>
              <th className="py-1 pr-2 font-medium">Local</th>
              <th className="py-1 font-medium">Twin{twinLabel ? ` · ${twinLabel}` : ""}</th>
            </tr>
          </thead>
          <tbody className="text-slate-800 dark:text-slate-100">
            <tr>
              <td className="py-0.5 pr-2 text-slate-500">탐색 CV</td>
              <td className="py-0.5 pr-2 tabular-nums">
                {localCv != null ? `${localCv.toFixed(1)}%` : "—"}
              </td>
              <td className="py-0.5 tabular-nums">{twinCv != null ? `${twinCv.toFixed(1)}%` : "—"}</td>
            </tr>
            <tr>
              <td className="py-0.5 pr-2 text-slate-500">확인 CV</td>
              <td className="py-0.5 pr-2 tabular-nums">
                {localConfirm != null ? `${localConfirm.toFixed(1)}%` : "—"}
              </td>
              <td className="py-0.5 tabular-nums">
                {twinConfirm != null ? `${twinConfirm.toFixed(1)}%` : "—"}
              </td>
            </tr>
            <tr>
              <td className="py-0.5 pr-2 text-slate-500">표본 n</td>
              <td className="py-0.5 pr-2 tabular-nums">{localStep?.n ?? stage1.fit_n}</td>
              <td className="py-0.5 tabular-nums">{twinStepPick?.n ?? visiblePool?.n ?? inspectPool?.n ?? "—"}</td>
            </tr>
            <tr>
              <td className="py-0.5 pr-2 text-slate-500">판단</td>
              <td className="py-0.5 pr-2">기준선</td>
              <td className="py-0.5 font-medium">
                {adopted ? "예측력 개선 — 재적합 권고" : "Local 유지"}
              </td>
            </tr>
          </tbody>
        </table>
        </div>

      <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">
        {adopted
          ? "확인 CV가 Local보다 나아지고 주요 계수 방향이 유지되어, 같은 식을 Twin 표본에 다시 적합하는 것을 권고합니다. 변수 구성은 바뀌지 않습니다."
          : stage2.decision_reason ||
            "예측력 개선과 계수 안정을 함께 만족하지 않아 Local 기준선을 유지합니다. Twin이 반드시 식을 좋게 만들지는 않습니다."}
      </p>
      <p className="text-[11px] text-slate-500 leading-relaxed">
        후보 지역은 거래 구성·토지 이용·체급으로 고릅니다. 거래가격으로 고르지 않습니다. 판단 순서는
        예측력 → 계수 안정 → 표본 규모입니다. 아래 예측은 채택과 별개로, 쌍둥이 1위 표본에 Local 식 +
        지역 더미를 다시 적합한 값입니다. Local 식은 위에 그대로 있습니다.
      </p>

      {predictPool && (
        <div className="rounded-md border border-violet-300 dark:border-violet-800 bg-white/70 dark:bg-slate-900/40 px-2.5 py-2 space-y-2">
          <p className="text-sm font-semibold text-violet-900 dark:text-violet-100">
            Twin 실험1 재적합 식 · 예측
          </p>
          <p className="text-xs font-medium text-slate-800 dark:text-slate-100">
            {formatResponseScale(
              predictPool.response_scale ?? stage2.fixed_response_scale,
            )}{" "}
            · {blockSummary(predictPool.blocks ?? stage1.primary.blocks)} · n=
            {predictPool.n}
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
            쌍둥이 1위만 보태고 지역 더미를 넣었습니다. CV 채택 여부와 관계없이 이 표본의 추정값·범위를
            볼 수 있습니다. Local 최적식은 위에서 그대로입니다.
          </p>
          {onPredict && !twin1PredictActive && (
          <button
            type="button"
              className="px-2 py-0.5 text-xs rounded border border-violet-400 text-violet-700 dark:text-violet-300"
              onClick={() => {
                const { vars, scale } = poolAdoptVars(predictPool, stage1, stage2);
                onPredict(vars, scale, `Twin 재적합 · ${predictPool.label}`, {
                  regionCodes: predictPool.region_codes,
                  fitN: predictPool.n,
                  slot: "twin1",
                });
              }}
            >
              Twin1 표본으로 값 계산해 보기
          </button>
          )}
          {twin1PredictActive && twin1PredictPanel}
        </div>
      )}

      {stage2.twin_experiments && stage2.twin_experiments.length > 0 && (
        <details className="text-xs" open>
          <summary className="cursor-pointer text-slate-500">접두 실험 상세 · 계수 안정</summary>
          <TwinExperimentTable
            steps={stage2.twin_experiments}
            regionNameByCode={regionNameByCode}
          />
          <p className="mt-1.5 text-[11px] text-slate-500 leading-relaxed">
            계수 방향{" "}
            {hold == null ? "비교 부족" : hold ? "유지" : "일부 다름"}
            . 부호가 뒤집히면 채택하지 않습니다.
          </p>
        </details>
          )}

          {stage2.ran && stage2.pools.length > 0 && visiblePool && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
          <span>{visiblePool.label}</span>
          {stage2.pools.length > 1 && (
            <span className="flex gap-1">
                  <button
                    type="button"
                className="px-1.5 py-0.5 border rounded disabled:opacity-40"
                disabled={twinStepIndex <= 0}
                    onClick={() => setTwinStep((s) => Math.max(0, s - 1))}
                  >
                    ←
                  </button>
              <span className="tabular-nums self-center">
                {twinStepIndex + 1}/{stage2.pools.length}
                  </span>
                  <button
                    type="button"
                className="px-1.5 py-0.5 border rounded disabled:opacity-40"
                disabled={twinStepIndex >= stage2.pools.length - 1}
                    onClick={() => setTwinStep((s) => Math.min(stage2.pools.length - 1, s + 1))}
                  >
                    →
                  </button>
                  </span>
              )}
              {onAdoptPool && (
                <button
                  type="button"
              className="px-2 py-0.5 rounded border border-violet-400 text-violet-700 dark:text-violet-300 disabled:opacity-50"
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
              Twin 식을 기본 통계에 적용 (선택)
                </button>
              )}
            </div>
          )}
    </div>
  );
}

function TwinResearchResult({
  stage2,
  stage1,
  inspectPool,
  researchPredictPanel,
  onPredict,
  researchPredictActiveLabel,
}: {
  stage2: RecommendationStage2;
  stage1: RecommendationStage1;
  inspectPool?: RecommendationPoolCandidate;
  researchPredictPanel?: ReactNode;
  onPredict?: (
    vars: RegressionVariableSpec,
    scale: ResponseScale,
    label: string,
    opts?: { regionCodes?: string[]; fitN?: number; slot?: "twin1" | "twin2" },
  ) => void;
  researchPredictActiveLabel?: string | null;
}) {
  const research = stage2.research;
  const active = Boolean(researchPredictActiveLabel?.startsWith("Twin 실험2"));
  const localCv = stage2.local_search_cv_mape ?? stage2.local_cv_mape;
  return (
    <div className="space-y-2 rounded-md border border-amber-200 dark:border-amber-900/50 bg-amber-50/40 dark:bg-amber-950/15 p-2.5">
      <p className="text-sm font-semibold text-amber-950 dark:text-amber-100">
        Twin 실험2 · Twin 1위 재탐색
      </p>
      <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
        Local 식을 버리고, Twin 1위 지역 거래만 보탠 표본에서 예측형 식을 다시 고른 결과입니다.
        Twin1과 표본은 같고(1위), Twin1은 지역 더미를 넣습니다. 확인용이며 기본 통계 식은 바꾸지
        않습니다. 값 입력은 Twin1 예측과 같습니다.
      </p>
      {stage2.research_skipped_reason && !research && (
        <p className="text-sm text-slate-500">{stage2.research_skipped_reason}</p>
      )}
      {research && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="text-slate-500">
                  <th className="py-1 pr-2 font-medium"> </th>
                  <th className="py-1 pr-2 font-medium">Twin1 식 고정</th>
                  <th className="py-1 font-medium">Twin2 재탐색</th>
                </tr>
              </thead>
              <tbody className="text-slate-800 dark:text-slate-100">
                <tr>
                  <td className="py-0.5 pr-2 text-slate-500">변수</td>
                  <td className="py-0.5 pr-2">
                    {blockSummary(inspectPool?.blocks ?? stage1.primary.blocks)}
                  </td>
                  <td className="py-0.5">{blockSummary(research.blocks ?? [])}</td>
                </tr>
                <tr>
                  <td className="py-0.5 pr-2 text-slate-500">척도</td>
                  <td className="py-0.5 pr-2">
                    {formatResponseScale(
                      inspectPool?.response_scale ?? stage2.fixed_response_scale,
                    )}
                  </td>
                  <td className="py-0.5">{formatResponseScale(research.response_scale)}</td>
                </tr>
                <tr>
                  <td className="py-0.5 pr-2 text-slate-500">n</td>
                  <td className="py-0.5 pr-2 tabular-nums">{inspectPool?.n ?? "—"}</td>
                  <td className="py-0.5 tabular-nums">{research.n}</td>
                </tr>
                <tr>
                  <td className="py-0.5 pr-2 text-slate-500">탐색 CV</td>
                  <td className="py-0.5 pr-2 tabular-nums">
                    {inspectPool?.cv_mape != null
                      ? `${inspectPool.cv_mape.toFixed(1)}%`
                      : localCv != null
                        ? `${localCv.toFixed(1)}%`
                        : "—"}
                  </td>
                  <td className="py-0.5 tabular-nums">
                    {research.cv_mape != null ? `${research.cv_mape.toFixed(1)}%` : "—"}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="rounded-md border border-amber-300 dark:border-amber-800 bg-white/70 dark:bg-slate-900/40 px-2.5 py-2 space-y-2">
            <p className="text-sm font-semibold text-amber-950 dark:text-amber-100">
              Twin 실험2 식 · 예측
            </p>
            <p className="text-xs font-medium text-slate-800 dark:text-slate-100">
              {formatResponseScale(research.response_scale)} · {blockSummary(research.blocks ?? [])}{" "}
              · n={research.n}
            </p>
            {onPredict && !active && (
              <button
                type="button"
                className="px-2 py-0.5 text-xs rounded border border-amber-400 text-amber-800 dark:text-amber-200"
                onClick={() => {
                  const { vars, scale } = poolAdoptVars(research, stage1, stage2);
                  onPredict(vars, scale, `Twin 실험2 · ${research.label}`, {
                    regionCodes: research.region_codes,
                    fitN: research.n,
                    slot: "twin2",
                  });
                }}
              >
                Twin 실험2 표본으로 값 계산해 보기
              </button>
            )}
            {active && researchPredictPanel}
          </div>
        </>
      )}
    </div>
  );
}

function TwinExperimentTable({
  steps,
  regionNameByCode,
}: {
  steps: TwinExperimentStep[];
  regionNameByCode: Record<string, string>;
}) {
  const stabLabel = { ok: "양호", warn: "주의", fail: "불안정" } as const;
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full text-left text-xs border-collapse">
        <thead>
          <tr className="text-slate-500">
            <th className="py-1 pr-2 font-medium">실험</th>
            <th className="py-1 pr-2 font-medium">n</th>
            <th className="py-1 pr-2 font-medium">탐색 CV</th>
            <th className="py-1 pr-2 font-medium">확인 CV</th>
            <th className="py-1 font-medium">안정</th>
            <th className="py-1 font-medium">계수 방향</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((s) => (
            <tr key={s.step_id} className={s.search_picked ? "bg-violet-50 dark:bg-violet-950/40" : undefined}>
              <td className="py-0.5 pr-2">
                {s.label}
                {s.region_codes.length > 0 && (
                  <span className="block text-[11px] text-slate-500">
                    {s.region_codes.map((c) => regionNameByCode[c] ?? c.slice(-8)).join(" + ")}
                  </span>
                )}
              </td>
              <td className="py-0.5 pr-2 tabular-nums">{s.n}</td>
              <td className="py-0.5 pr-2 tabular-nums">
                {s.search_cv_mape != null ? `${s.search_cv_mape.toFixed(1)}%` : "—"}
              </td>
              <td className="py-0.5 pr-2 tabular-nums">
                {s.confirm_cv_mape != null ? `${s.confirm_cv_mape.toFixed(1)}%` : "—"}
              </td>
              <td className="py-0.5">{stabLabel[s.stability]}</td>
              <td className="py-0.5">{signBits(s.key_coefficients)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ModelCompareTable({
  mine,
  mineScale,
  primary,
  fitN,
  twinRan,
  twinPool,
  hold,
  twinAdopted,
  twin2Ran,
  twin2Pool,
}: {
  mine: RegressionLevelResult | null;
  mineScale: ResponseScale | null;
  primary: ModelCandidate;
  fitN: number;
  twinRan: boolean;
  twinPool: RecommendationPoolCandidate | null;
  hold: boolean | null;
  twinAdopted?: boolean;
  twin2Ran?: boolean;
  twin2Pool?: RecommendationPoolCandidate | null;
}) {
  const twinCv = twinPool?.cv_mape;
  const macroCv = primary.metrics.cv_mape;
  const twin2Cv = twin2Pool?.cv_mape;
  const showTwin2 = true;

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-md border border-slate-200 dark:border-slate-700">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="text-slate-500 border-b border-slate-200 dark:border-slate-700">
              <th className="py-1.5 px-2 font-medium"> </th>
              <th className="py-1.5 pr-2 font-medium">기본 회귀실험</th>
              <th className="py-1.5 pr-2 font-medium">Macro #1</th>
              <th className="py-1.5 pr-2 font-medium">Twin1</th>
              <th className="py-1.5 pr-2 font-medium">Twin2</th>
            </tr>
          </thead>
          <tbody className="text-slate-800 dark:text-slate-100">
            <tr className="border-b border-slate-100 dark:border-slate-800">
              <td className="py-1 px-2 text-slate-500">목적</td>
              <td className="py-1 pr-2">사용자 가설</td>
              <td className="py-1 pr-2">Local 기준선</td>
              <td className="py-1 pr-2">{twinRan ? "예측력 확장" : "실험 전"}</td>
              <td className="py-1 pr-2">
                {twin2Ran ? (twin2Pool ? "예측형 재탐색" : "산출 불가") : "실험 전"}
              </td>
            </tr>
            <tr className="border-b border-slate-100 dark:border-slate-800">
              <td className="py-1 px-2 text-slate-500">변수</td>
              <td className="py-1 pr-2">사용자 선택</td>
              <td className="py-1 pr-2">{blockSummary(primary.blocks)}</td>
              <td className="py-1 pr-2">{twinRan ? "Local 식 고정 · Twin 표본" : "실험 전"}</td>
              {showTwin2 && (
                <td className="py-1 pr-2">
                  {twin2Pool ? blockSummary(twin2Pool.blocks ?? []) : "—"}
                </td>
              )}
            </tr>
            <tr className="border-b border-slate-100 dark:border-slate-800">
              <td className="py-1 px-2 text-slate-500">척도</td>
              <td className="py-1 pr-2">{formatResponseScale(mineScale)}</td>
              <td className="py-1 pr-2">{formatResponseScale(primary.response_scale)}</td>
              <td className="py-1 pr-2">
                {twinRan
                  ? formatResponseScale(twinPool?.response_scale ?? primary.response_scale)
                  : "—"}
              </td>
              {showTwin2 && (
                <td className="py-1 pr-2">
                  {twin2Pool ? formatResponseScale(twin2Pool.response_scale) : "—"}
                </td>
              )}
            </tr>
            <tr className="border-b border-slate-100 dark:border-slate-800">
              <td className="py-1 px-2 text-slate-500">n</td>
              <td className="py-1 pr-2 tabular-nums">{mine ? fmtNum(mine.n) : "—"}</td>
              <td className="py-1 pr-2 tabular-nums">{fmtNum(fitN)}</td>
              <td className="py-1 pr-2 tabular-nums">
                {twinRan && twinPool ? fmtNum(twinPool.n) : "—"}
              </td>
              {showTwin2 && (
                <td className="py-1 pr-2 tabular-nums">
                  {twin2Pool ? fmtNum(twin2Pool.n) : "—"}
                </td>
              )}
            </tr>
            <tr className="border-b border-slate-100 dark:border-slate-800">
              <td className="py-1 px-2 text-slate-500">Adj R²</td>
              <td className="py-1 pr-2 tabular-nums">
                {mine ? fmtDecimal(mine.adj_r_squared, 3) : "—"}
              </td>
              <td className="py-1 pr-2 tabular-nums">
                {fmtDecimal(primary.metrics.adj_r_squared, 3)}
              </td>
              <td className="py-1 pr-2 tabular-nums">
                {twinRan ? fmtDecimal(twinPool?.adj_r_squared, 3) : "—"}
              </td>
              {showTwin2 && (
                <td className="py-1 pr-2 tabular-nums">
                  {fmtDecimal(twin2Pool?.adj_r_squared, 3)}
                </td>
              )}
            </tr>
            <tr className="border-b border-slate-100 dark:border-slate-800">
              <td className="py-1 px-2 text-slate-500">MAPE</td>
              <td className="py-1 pr-2 tabular-nums">
                {mine?.mape != null ? `${fmtDecimal(mine.mape, 1)}%` : "—"}
              </td>
              <td className="py-1 pr-2">—</td>
              <td className="py-1 pr-2">—</td>
              {showTwin2 && <td className="py-1 pr-2">—</td>}
            </tr>
            <tr>
              <td className="py-1 px-2 text-slate-500">CV-MAPE</td>
              <td className="py-1 pr-2">—</td>
              <td className="py-1 pr-2 tabular-nums">
                {macroCv != null ? `${fmtDecimal(macroCv, 1)}%` : "—"}
              </td>
              <td className="py-1 pr-2 tabular-nums">
                {twinRan && twinCv != null ? `${fmtDecimal(twinCv, 1)}%` : "—"}
              </td>
              {showTwin2 && (
                <td className="py-1 pr-2 tabular-nums">
                  {twin2Cv != null ? `${fmtDecimal(twin2Cv, 1)}%` : "—"}
                </td>
              )}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
        기본 통계는 표본 내 적합, Macro #1은 교차검증입니다. 숫자를 한 줄로 우열 가리지 않습니다.
        {twinRan
          ? twinAdopted
            ? " Twin1 재적합이 확인 CV에서 Local을 이겼습니다. 같은 식·다른 표본입니다."
            : hold === false
              ? " Twin1에서 주요 계수 방향이 갈리면 Local을 유지하는 편이 안전합니다."
              : " Twin1이 Local보다 예측을 좋게 만들지 못하면 Local 기준선이 결론입니다."
          : " Twin은 같은 식에 유사 지역 거래를 보태 예측력이 나아지는지 보는 실험입니다."}
        {twin2Ran
          ? twin2Pool
            ? " Twin2는 Local + Twin 1위 표본에서 예측형 식을 다시 고른 확인용입니다. Twin1과 표본은 같고 Twin1은 지역 더미를 넣습니다. 기본 통계 식은 바꾸지 않습니다."
            : " Twin2 식을 다시 고를 수 없었습니다."
          : ""}
      </p>
    </div>
  );
}
