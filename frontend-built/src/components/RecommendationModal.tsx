import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, type UseMutationResult } from "@tanstack/react-query";
import type {
  AssetType,
  RegressionRecommendResponse,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionSelectionRequest,
  RegressionVariableSpec,
  ResponseScale,
} from "../types";
import { fetchProfileTwinNeighbors, runRegression, twinProfileForBuiltAsset } from "../api/client";
import { buildBuiltRecommendContext } from "../api/aiClient";
import type { ProfileLinkTarget } from "../utils/profileLink";
import { BUILT_RECOMMEND_HELP } from "../utils/builtAnalysisHelp";
import AiAssistantPanel from "./AiAssistantPanel";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import DraggableModalShell from "./DraggableModalShell";
import RecommendStagePanel, { type AdoptPoolPayload } from "./RecommendStagePanel";
import PredictPanel from "./PredictPanel";

const PREDICTIVE_ROLE = "현재 최적 후보 (예측형)";

type PredictTarget = {
  vars: RegressionVariableSpec;
  scale: ResponseScale;
  label: string;
  fitN?: number;
};

type Props = {
  open: boolean;
  onClose: () => void;
  regBody: RegressionRunRequest;
  recommendM: UseMutationResult<RegressionRecommendResponse, Error, RegressionSelectionRequest>;
  onAdopt: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  onAdoptPool?: (payload: AdoptPoolPayload) => void;
  adopting?: boolean;
  assetType: AssetType;
  regionLabel: string;
  profileTarget?: ProfileLinkTarget | null;
};

export default function RecommendationModal({
  open,
  onClose,
  regBody,
  recommendM,
  onAdopt,
  onAdoptPool,
  adopting,
  assetType,
  regionLabel,
  profileTarget,
}: Props) {
  const [predictTarget, setPredictTarget] = useState<PredictTarget | null>(null);
  const [runStage2, setRunStage2] = useState(false);

  const predictFitM = useMutation({
    mutationFn: (body: RegressionRunRequest) => runRegression(body),
  });

  const twinLevel =
    profileTarget?.level === "eupmyeondong" || profileTarget?.level === "beopjungri"
      ? profileTarget.level
      : null;

  const twinProfile = twinProfileForBuiltAsset(assetType);

  const twinQ = useQuery({
    queryKey: ["built-profile-twin", twinLevel, profileTarget?.code, twinProfile],
    queryFn: () =>
      fetchProfileTwinNeighbors(twinLevel!, profileTarget!.code, { twinProfile }),
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
    const base: RegressionSelectionRequest = {
      ...regBody,
      run_stage2: runStage2,
    };
    if (!twin || !twin.neighbors.length) return base;
    return {
      ...base,
      profile_version: twin.profile_version,
      profile_as_of_month: twin.as_of_month,
      profile_window_years: twin.window_years,
      profile_twin_neighbors: twin.neighbors
        .map((n) => ({
          region_code: (n.twin_beopjungri_code || n.twin_eupmyeondong_code || "").trim(),
          similarity_score: n.similarity_score,
        }))
        .filter((n) => n.region_code),
    };
  }, [regBody, twinQ.data, runStage2]);

  useEffect(() => {
    if (!open) return;
    setRunStage2(false);
    setPredictTarget(null);
    predictFitM.reset();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    recommendM.mutate(enrichedRegBody);
    if (!runStage2) {
      setPredictTarget(null);
      predictFitM.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin 로딩·2단계 opt-in 후 재요청
  }, [open, enrichedRegBody]);

  useEffect(() => {
    if (!open || !recommendM.data || predictTarget) return;
    setPredictTarget({
      vars: recommendM.data.stage1.primary.variables,
      scale: recommendM.data.stage1.primary.response_scale,
      label: PREDICTIVE_ROLE,
      fitN: recommendM.data.stage1.fit_n,
    });
  }, [open, recommendM.data, predictTarget]);

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

  const aiRecommendContext = useMemo(() => {
    if (!recommendM.data) return null;
    return buildBuiltRecommendContext(recommendM.data, {
      regionLabel,
      assetType: String(assetType),
      purpose: "statistics",
    });
  }, [recommendM.data, regionLabel, assetType]);

  if (!open) return null;

  const loading = recommendM.isPending && !recommendM.data;

  const resolveFitN = (label: string, vars: RegressionVariableSpec, scale: ResponseScale) => {
    void vars;
    void scale;
    const data = recommendM.data;
    if (!data) return undefined;
    if (label.includes("pool") && data.stage2?.pools.length) {
      const pool = data.stage2.pools.find((p) => label.includes(p.label));
      if (pool) return pool.n;
    }
    return data.stage1.fit_n;
  };

  return (
    <DraggableModalShell
      open={open}
      onClose={onClose}
      titleId="recommendation-modal-title"
      title="모형 탐색"
      subtitle="① Local SSOT 탐색 → ② (선택) Twin pool — 채택은 사용자가 결정합니다."
      maxWidthClass="max-w-4xl"
      resizable
      defaultWidth={Math.min(900, typeof window !== "undefined" ? window.innerWidth - 48 : 900)}
      defaultHeight={Math.min(780, typeof window !== "undefined" ? window.innerHeight - 48 : 780)}
      minWidth={520}
      minHeight={360}
    >
      <div className="h-full min-h-0 space-y-3">
        <div className="flex items-center justify-end gap-1.5 shrink-0">
          <AnalysisHelpPanel explain={BUILT_RECOMMEND_HELP} />
          {recommendM.data && aiRecommendContext && (
            <AiAssistantPanel context={aiRecommendContext} />
          )}
        </div>

        {loading && (
          <p className="text-xs text-slate-400 text-center py-8">모형 탐색 계산 중…</p>
        )}

        {recommendM.isError && (
          <p className="text-sm text-red-600">
            {(recommendM.error as Error).message ?? "모형 탐색 실패"}
          </p>
        )}

        {recommendM.data && (
          <RecommendStagePanel
            data={recommendM.data}
            onAdopt={onAdopt}
            onAdoptPool={onAdoptPool}
            adopting={adopting}
            onPredict={(vars, scale, label) =>
              setPredictTarget({
                vars,
                scale,
                label,
                fitN: resolveFitN(label, vars, scale),
              })
            }
            predictActiveLabel={predictTarget?.label ?? null}
            regionNameByCode={regionNameByCode}
            onRunTwin={() => setRunStage2(true)}
            twinRunning={recommendM.isPending && runStage2}
          />
        )}

        {!loading && !recommendM.data && !recommendM.isError && (
          <p className="text-xs text-slate-400 text-center py-6">탐색 결과가 없습니다.</p>
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
                fitN={predictTarget.fitN ?? recommendM.data?.stage1.fit_n}
                scopeNTx={recommendM.data?.analysis_scope.scope_n_tx}
              />
            )}
          </div>
        )}
      </div>
    </DraggableModalShell>
  );
}
