import { useEffect, useState } from "react";
import clsx from "clsx";
import type { UseMutationResult } from "@tanstack/react-query";
import type { AiContextPayload } from "@ch2/ai-assistant/aiClient";
import type {
  RegressionCompareResponse,
  RegressionRunRequest,
  RegressionSuggestResponse,
  RegressionVariableSpec,
  ResponseScale,
} from "../types";
import DraggableModalShell from "./DraggableModalShell";
import { ModelComparePanel } from "./ModelComparePanel";
import { ModelSelectionPanel } from "./ModelSelectionPanel";

type Tab = "suggest" | "compare";

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
}: Props) {
  const [tab, setTab] = useState<Tab>("suggest");

  useEffect(() => {
    if (!open) return;
    suggestM.mutate(regBody);
    compareM.mutate(regBody);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetch on open only
  }, [open]);

  if (!open) return null;

  const loading = suggestM.isPending || compareM.isPending;
  const hasSuggest = !!suggestM.data;
  const hasCompare = !!compareM.data;

  return (
    <DraggableModalShell
      open={open}
      onClose={onClose}
      titleId="model-explore-title"
      title="모형 추천"
      subtitle="Group Forward 추천 · Best Subset 비교 — 채택은 사용자가 결정합니다."
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
      <div className="space-y-2">
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
              />
            )}
            {!loading && !compareM.data && !compareM.isError && (
              <p className="text-xs text-slate-400 text-center py-6">비교 결과가 없습니다.</p>
            )}
          </>
        )}
      </div>
    </DraggableModalShell>
  );
}
