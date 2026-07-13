import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useMutation, type UseMutationResult } from "@tanstack/react-query";
import type { AiContextPayload } from "@ch2/ai-assistant/aiClient";
import type {
  AssetType,
  RegressionCompareResponse,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionSuggestResponse,
  RegressionVariableSpec,
  ResponseScale,
} from "../types";
import { runRegression } from "../api/client";
import DraggableModalShell from "./DraggableModalShell";
import { ModelComparePanel } from "./ModelComparePanel";
import { ModelSelectionPanel } from "./ModelSelectionPanel";
import PredictPanel from "./PredictPanel";

type Tab = "suggest" | "compare";

type PredictTarget = {
  vars: RegressionVariableSpec;
  scale: ResponseScale;
  label: string;
};

type Props = {
  open: boolean;
  onClose: () => void;
  regBody: RegressionRunRequest;
  suggestM: UseMutationResult<RegressionSuggestResponse, Error, RegressionRunRequest>;
  compareM: UseMutationResult<RegressionCompareResponse, Error, RegressionRunRequest>;
  onAdopt: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  adopting?: boolean;
  aiSuggestContext?: AiContextPayload | null;
  aiCompareContext?: AiContextPayload | null;
  assetType: AssetType;
  regionLabel: string;
};

export default function ModelExploreModal({
  open,
  onClose,
  regBody,
  suggestM,
  compareM,
  onAdopt,
  adopting,
  aiSuggestContext,
  aiCompareContext,
  assetType,
  regionLabel,
}: Props) {
  const [tab, setTab] = useState<Tab>("suggest");
  const [predictTarget, setPredictTarget] = useState<PredictTarget | null>(null);

  const predictFitM = useMutation({
    mutationFn: (body: RegressionRunRequest) => runRegression(body),
  });

  useEffect(() => {
    if (!open) return;
    suggestM.mutate(regBody);
    compareM.mutate(regBody);
    setPredictTarget(null);
    predictFitM.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetch on open only
  }, [open]);

  useEffect(() => {
    if (!open || !suggestM.data || predictTarget) return;
    setPredictTarget({
      vars: suggestM.data.recommended_variables,
      scale: suggestM.data.response_scale,
      label: "추천 모형 (Group Forward)",
    });
  }, [open, suggestM.data, predictTarget]);

  useEffect(() => {
    if (!open || !predictTarget) return;
    predictFitM.mutate({
      ...regBody,
      variables: predictTarget.vars,
      response_scale: predictTarget.scale,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fit when target changes
  }, [open, predictTarget]);

  const predictRegBody = useMemo(() => {
    if (!predictTarget) return null;
    return {
      ...regBody,
      variables: predictTarget.vars,
      response_scale: predictTarget.scale,
    };
  }, [regBody, predictTarget]);

  if (!open) return null;

  const loading = suggestM.isPending || compareM.isPending;
  const hasSuggest = !!suggestM.data;
  const hasCompare = !!compareM.data;

  const onPredictCandidate = (vars: RegressionVariableSpec, scale: ResponseScale, label: string) => {
    setPredictTarget({ vars, scale, label });
  };

  return (
    <DraggableModalShell
      open={open}
      onClose={onClose}
      titleId="model-explore-title"
      title="모형 추천"
      subtitle="Group Forward 추천 · Best Subset 비교 — 채택은 사용자가 결정합니다."
      maxWidthClass="max-w-4xl"
      resizable
      defaultWidth={Math.min(900, typeof window !== "undefined" ? window.innerWidth - 48 : 900)}
      defaultHeight={Math.min(780, typeof window !== "undefined" ? window.innerHeight - 48 : 780)}
      minWidth={520}
      minHeight={360}
      headerExtra={
        <div className="flex gap-1">
          {(
            [
              ["suggest", "추천"],
              ["compare", "비교"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={clsx(
                "px-2.5 py-1 rounded text-xs border",
                tab === key
                  ? "bg-slate-800 text-white border-slate-800 dark:bg-slate-100 dark:text-slate-900"
                  : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-600 text-slate-600",
              )}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>
      }
    >
      <div className="h-full min-h-0 space-y-3">
        {loading && !hasSuggest && !hasCompare && (
          <p className="text-xs text-slate-400 text-center py-8">모형 추천 계산 중…</p>
        )}

        {tab === "suggest" && (
          <>
            {suggestM.isError && (
              <p className="text-sm text-red-600">{(suggestM.error as Error).message ?? "추천 실패"}</p>
            )}
            {suggestM.data && (
              <ModelSelectionPanel
                data={suggestM.data}
                onAdopt={onAdopt}
                adopting={adopting}
                aiContext={aiSuggestContext}
                embedded
                onPredict={(vars, scale, label) => setPredictTarget({ vars, scale, label })}
                predictActive={predictTarget?.label === "추천 모형 (Group Forward)"}
              />
            )}
            {!loading && !suggestM.data && !suggestM.isError && (
              <p className="text-xs text-slate-400 text-center py-6">추천 결과가 없습니다.</p>
            )}
          </>
        )}

        {tab === "compare" && (
          <>
            {compareM.isError && (
              <p className="text-sm text-red-600">{(compareM.error as Error).message ?? "비교 실패"}</p>
            )}
            {compareM.data && (
              <ModelComparePanel
                data={compareM.data}
                onAdopt={onAdopt}
                adopting={adopting}
                aiContext={aiCompareContext}
                embedded
                onPredict={(vars, scale, label) => onPredictCandidate(vars, scale, label)}
                predictActiveLabel={predictTarget?.label}
              />
            )}
            {!loading && !compareM.data && !compareM.isError && (
              <p className="text-xs text-slate-400 text-center py-6">비교 결과가 없습니다.</p>
            )}
          </>
        )}

        {(predictTarget || predictFitM.isPending || predictFitM.data) && (
          <div className="border-t border-slate-200 dark:border-slate-700 pt-3 space-y-2">
            {predictFitM.isPending && (
              <p className="text-xs text-slate-400 text-center py-2">예측용 모형 적합 중…</p>
            )}
            {predictFitM.isError && (
              <p className="text-sm text-red-600">
                {(predictFitM.error as Error).message ?? "예측용 모형 적합 실패"}
              </p>
            )}
            {predictFitM.data && predictRegBody && predictTarget && (
              <PredictPanel
                embedded
                regData={predictFitM.data as RegressionRunResponse}
                regBody={predictRegBody}
                vars={predictTarget.vars}
                assetType={assetType}
                regionLabel={regionLabel}
                modelHint={`${predictTarget.label} · ${predictTarget.scale}`}
              />
            )}
          </div>
        )}
      </div>
    </DraggableModalShell>
  );
}
