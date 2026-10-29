import clsx from "clsx";
import type {
  AssetType,
  RegressionLevelResult,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionVariableSpec,
  ResponseScale,
} from "../types";
import {
  ADMIN_LABELS,
  fmtDecimal,
  fmtNum,
  levelCardTitle,
} from "../utils/regressionFormat";
import PredictPanel from "./PredictPanel";
import RegressionEquation from "./RegressionEquation";
import ZoneCaution from "./ZoneCaution";
import RegressionEffectsTable from "./RegressionEffectsTable";
import SampleFunnel from "./SampleFunnel";
import UpperScopeModelDiff from "./UpperScopeModelDiff";
import AnalysisSummary, { primaryCaution } from "../../../shared/regression-ui/AnalysisSummary";
import { DetailAnalysis, SummaryHeading } from "../../../shared/regression-ui/ReadingLayout";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { BUILT_UPPER_SCOPE_HELP } from "../utils/builtAnalysisHelp";

type Props = {
  regData: RegressionRunResponse;
  regBody: RegressionRunRequest;
  vars: RegressionVariableSpec;
  assetType: AssetType;
  responseScale: ResponseScale;
  regionLabel: string;
  focusLabel?: string | null;
  opened: boolean;
  onOpen: () => void;
};

function ComparisonLevelCard({
  result,
  focus,
  focusTitle,
  assetType,
  responseScale,
  emphasized,
}: {
  result: RegressionLevelResult;
  focus: RegressionLevelResult;
  focusTitle: string;
  assetType: AssetType;
  responseScale: ResponseScale;
  emphasized?: boolean;
}) {
  return (
    <div
      className={clsx(
        "rounded-md border p-3 space-y-2 text-xs",
        emphasized
          ? "border-slate-300 bg-slate-50 dark:bg-slate-800/40 dark:border-slate-600"
          : "border-slate-200 dark:border-slate-700",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold text-sm">
            {levelCardTitle(result.scope_label, result.admin_level)}
          </h3>
          <p className="text-slate-500 mt-0.5">
            {ADMIN_LABELS[result.admin_level] ?? result.admin_level} 재적합
            {emphasized && " · 직계 상위"}
          </p>
        </div>
        <span className="text-slate-500 shrink-0">n={fmtNum(result.n)}</span>
      </div>

      <section className="space-y-2" aria-label="결과 요약">
        <SummaryHeading />
        {result.warning && <p className="badge-warn">{result.warning}</p>}
        {primaryCaution(result.analysis) && (
          <p className="text-amber-800 dark:text-amber-300">{primaryCaution(result.analysis)}</p>
        )}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div>R² {fmtDecimal(result.r_squared, 4)}</div>
        <div>Adj R² {fmtDecimal(result.adj_r_squared, 4)}</div>
        <div>학습 MAPE {result.mape != null ? `${fmtDecimal(result.mape, 1)}%` : "—"}</div>
        <div>유의 계수 {result.significant_count}개 (p&lt;0.05)</div>
      </div>
      <p className="text-slate-500">
        위 지표는 이 단계 표본 안에서만 유효합니다. 초점 수치와 나란히 두고 우열을 가리지 마세요.
      </p>
      </section>

      <DetailAnalysis>
      {result.sample && <SampleFunnel sample={result.sample} />}
      <AnalysisSummary analysis={result.analysis} />
      <UpperScopeModelDiff
        focus={focus}
        upper={result}
        assetType={assetType}
        focusTitle={focusTitle}
      />

      {(result.equation || result.coefficients.length > 0) && (
        <div className="space-y-1">
          <div className="font-medium text-slate-600">회귀식과 계수</div>
          <RegressionEquation
            coefficients={result.coefficients}
            responseScale={responseScale}
            assetType={assetType}
            equation={result.equation}
            predictOptions={result.predict_options}
          />
        </div>
      )}

      {result.coefficients.length > 0 && (
        <details>
          <summary className="cursor-pointer text-slate-500">계수 상세</summary>
          <RegressionEffectsTable
            coefficients={result.coefficients}
            responseScale={responseScale}
            assetType={assetType}
            predictOptions={result.predict_options}
          />
        </details>
      )}
      <ZoneCaution />
      </DetailAnalysis>
    </div>
  );
}

export default function UpperScopeAnalysisCard({
  regData,
  regBody,
  vars,
  assetType,
  responseScale,
  regionLabel,
  focusLabel,
  opened,
  onOpen,
}: Props) {
  const comparisons = regData.comparisons ?? [];
  const immediate = comparisons[0];
  const wider = comparisons.slice(1);

  const focusTitle =
    focusLabel ?? levelCardTitle(regData.primary.scope_label, regData.primary.admin_level);

  return (
    <section id="built-step-upper" className="card scroll-mt-16 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-semibold text-sm inline-flex items-center gap-1">상위지역 재적합 <AnalysisHelpPanel explain={BUILT_UPPER_SCOPE_HELP} title="상위지역 재적합 설명" /></h2>
          <p className="text-xs text-slate-500 mt-1">
            통계분석 때 상위 행정 단위 표본에 따로 적합한 결과입니다. 실제 반영 변수와 기준 범주를 확인한 뒤 초점 결과와 비교하세요.
          </p>
        </div>
        <button
          type="button"
          className={clsx("btn text-xs shrink-0", opened ? "btn-ghost" : "btn-primary")}
          onClick={onOpen}
        >
          {opened ? "접기" : "결과 보기"}
        </button>
      </div>

      {!opened && (
        <p className="text-xs text-slate-400 py-2">
          「결과 보기」를 누르면 이미 계산된 상위지역 결과를 펼칩니다. 새 계산은 기본 통계분석을 다시 실행하세요.
        </p>
      )}

      {opened && (
        <>
          <p className="text-xs text-slate-500">
            분석 초점{" "}
            <strong className="text-slate-700 dark:text-slate-200">{focusTitle}</strong>
          </p>

          <div className="rounded-md border border-emerald-200 bg-emerald-50/40 dark:bg-emerald-950/20 dark:border-emerald-800 p-2 text-xs">
            <span className="font-medium text-emerald-900 dark:text-emerald-100">분석 초점 · </span>
            n={fmtNum(regData.primary.n)} · Adj R² {fmtDecimal(regData.primary.adj_r_squared, 4)}
          </div>

          {!comparisons.length && (
            <p className="text-xs text-slate-400 text-center py-4">
              재적합할 상위 단위가 없습니다 (시·군을 초점으로 고른 경우 등).
            </p>
          )}

          {immediate && (
            <ComparisonLevelCard
              result={immediate}
              focus={regData.primary}
              focusTitle={focusTitle}
              assetType={assetType}
              responseScale={responseScale}
              emphasized
            />
          )}

          {wider.length > 0 && (
            <details className="group">
              <summary className="cursor-pointer text-xs font-medium text-slate-600">
                더 넓은 단위 재적합 ({wider.length}개)
              </summary>
              <div className="mt-2 space-y-2">
                {wider.map((c, i) => (
                  <ComparisonLevelCard
                    key={`${c.admin_level}-${i}`}
                    result={c}
                    focus={regData.primary}
                    focusTitle={focusTitle}
                    assetType={assetType}
                    responseScale={responseScale}
                  />
                ))}
              </div>
            </details>
          )}

          {comparisons.length > 0 && (
            <div className="border-t border-slate-200 dark:border-slate-700 pt-3">
              <PredictPanel
                embedded
                regData={regData}
                regBody={regBody}
                vars={vars}
                assetType={assetType}
                regionLabel={regionLabel}
                modelHint={`${ADMIN_LABELS[immediate.admin_level] ?? immediate.admin_level} 재적합 모형 · 기본통계 변수 중 이 단계에서 추정 가능한 것만 씁니다`}
                lockAdminLevel={immediate.admin_level}
              />
            </div>
          )}
        </>
      )}
    </section>
  );
}
