import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useMutation, useQuery, type UseMutationResult } from "@tanstack/react-query";
import type { AiContextPayload } from "@ch2/ai-assistant/aiClient";
import type {
  AssetType,
  RegressionCompareResponse,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionSelectionRequest,
  RegressionSuggestResponse,
  RegressionVariableSpec,
  ResponseScale,
} from "../types";
import { fetchProfileTwinNeighbors, runRegression } from "../api/client";
import type { ProfileLinkTarget } from "../utils/profileLink";
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
  /** 단일 anchor(읍·면·동/법정리)일 때만 존재 — Profile Twin 후보 조회용. */
  profileTarget?: ProfileLinkTarget | null;
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
  profileTarget,
}: Props) {
  const [tab, setTab] = useState<Tab>("suggest");
  const [predictTarget, setPredictTarget] = useState<PredictTarget | null>(null);

  const predictFitM = useMutation({
    mutationFn: (body: RegressionRunRequest) => runRegression(body),
  });

  const twinLevel =
    profileTarget?.level === "eupmyeondong" || profileTarget?.level === "beopjungri"
      ? profileTarget.level
      : null;

  const twinQ = useQuery({
    queryKey: ["built-profile-twin", twinLevel, profileTarget?.code],
    queryFn: () => fetchProfileTwinNeighbors(twinLevel!, profileTarget!.code),
    enabled: open && Boolean(twinLevel && profileTarget?.code),
    staleTime: 5 * 60 * 1000,
  });

  const regionNameByCode = useMemo(() => {
    const map: Record<string, string> = {};
    for (const n of twinQ.data?.neighbors ?? []) {
      const code = (n.twin_beopjungri_code || n.twin_eupmyeondong_code || "").trim();
      const name = n.twin_beopjungri_name || n.twin_eupmyeondong_name || n.twin_sigungu_name;
      if (code && name) map[code] = name;
    }
    return map;
  }, [twinQ.data]);

  const enrichedRegBody: RegressionSelectionRequest = useMemo(() => {
    const twin = twinQ.data;
    if (!twin || !twin.neighbors.length) return regBody;
    return {
      ...regBody,
      profile_version: twin.profile_version,
      profile_as_of_month: twin.as_of_month,
      profile_window_years: twin.window_years,
      profile_twin_neighbors: twin.neighbors.map((n) => ({
        region_code: (n.twin_beopjungri_code || n.twin_eupmyeondong_code || "").trim(),
        similarity_score: n.similarity_score,
      })).filter((n) => n.region_code),
    };
  }, [regBody, twinQ.data]);

  useEffect(() => {
    if (!open) return;
    suggestM.mutate(enrichedRegBody);
    compareM.mutate(enrichedRegBody);
    setPredictTarget(null);
    predictFitM.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin 로딩 완료 후 재요청
  }, [open, enrichedRegBody]);

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
                regionNameByCode={regionNameByCode}
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
                regionNameByCode={regionNameByCode}
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
