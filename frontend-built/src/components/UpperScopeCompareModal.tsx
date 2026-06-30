import clsx from "clsx";
import type { AssetType, RegressionLevelResult, RegressionRunResponse, ResponseScale } from "../types";
import {
  ADMIN_LABELS,
  fmtDecimal,
  fmtNum,
  levelCardTitle,
} from "../utils/regressionFormat";
import DraggableModalShell from "./DraggableModalShell";
import RegressionEquation from "./RegressionEquation";
import RegressionEffectsTable from "./RegressionEffectsTable";

type Props = {
  open: boolean;
  onClose: () => void;
  regData: RegressionRunResponse;
  assetType: AssetType;
  responseScale: ResponseScale;
  focusLabel?: string | null;
};

function ComparisonLevelCard({
  result,
  assetType,
  responseScale,
  emphasized,
}: {
  result: RegressionLevelResult;
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
            {ADMIN_LABELS[result.admin_level] ?? result.admin_level}
            {emphasized && " · 직계 상위"}
          </p>
        </div>
        <span className="text-slate-500 shrink-0">n={fmtNum(result.n)}</span>
      </div>

      {result.warning && <p className="badge-warn">{result.warning}</p>}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div>R² {fmtDecimal(result.r_squared, 4)}</div>
        <div>Adj R² {fmtDecimal(result.adj_r_squared, 4)}</div>
        <div>MAPE {result.mape != null ? `${fmtDecimal(result.mape, 1)}%` : "—"}</div>
        <div>유의 {result.significant_count}개</div>
      </div>

      {(result.equation || result.coefficients.length > 0) && (
        <div className="space-y-1">
          <div className="font-medium text-slate-600">회귀식</div>
          <RegressionEquation
            coefficients={result.coefficients}
            responseScale={responseScale}
            assetType={assetType}
            equation={result.equation}
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
          />
        </details>
      )}
    </div>
  );
}

export default function UpperScopeCompareModal({
  open,
  onClose,
  regData,
  assetType,
  responseScale,
  focusLabel,
}: Props) {
  const comparisons = regData.comparisons ?? [];
  const immediate = comparisons[0];
  const wider = comparisons.slice(1);

  if (!open) return null;

  const focusTitle =
    focusLabel ??
    levelCardTitle(regData.primary.scope_label, regData.primary.admin_level);

  return (
    <DraggableModalShell
      open={open}
      onClose={onClose}
      titleId="upper-scope-title"
      title="상위 지역 분석"
      subtitle={
        <>
          분석 초점 <strong className="text-slate-700 dark:text-slate-200">{focusTitle}</strong> vs
          상위 행정 scope — 참고용입니다.
        </>
      }
      maxWidthClass="max-w-2xl"
    >
      <div className="space-y-3">
        <div className="rounded-md border border-emerald-200 bg-emerald-50/40 dark:bg-emerald-950/20 dark:border-emerald-800 p-2 text-xs">
          <span className="font-medium text-emerald-900 dark:text-emerald-100">분석 초점 · </span>
          n={fmtNum(regData.primary.n)} · Adj R² {fmtDecimal(regData.primary.adj_r_squared, 4)}
        </div>

        {!comparisons.length && (
          <p className="text-xs text-slate-400 text-center py-6">
            상위 scope 비교가 없습니다 (시·군 단일 선택).
          </p>
        )}

        {immediate && (
          <ComparisonLevelCard
            result={immediate}
            assetType={assetType}
            responseScale={responseScale}
            emphasized
          />
        )}

        {wider.length > 0 && (
          <details className="group">
            <summary className="cursor-pointer text-xs font-medium text-slate-600">
              더 넓은 scope ({wider.length}개)
            </summary>
            <div className="mt-2 space-y-2">
              {wider.map((c, i) => (
                <ComparisonLevelCard
                  key={`${c.admin_level}-${i}`}
                  result={c}
                  assetType={assetType}
                  responseScale={responseScale}
                />
              ))}
            </div>
          </details>
        )}
      </div>
    </DraggableModalShell>
  );
}
