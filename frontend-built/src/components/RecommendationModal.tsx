import { useEffect, useMemo, useRef, useState } from "react";
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
import { BUILT_RECOMMEND_HELP } from "../utils/builtAnalysisHelp";
import type { ProfileLinkTarget } from "../utils/profileLink";
import { mapProfileTwinNeighbors, resolveTwinAnchorFromRequest } from "../utils/profileLink";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import DraggableModalShell from "./DraggableModalShell";
import RecommendStagePanel from "./RecommendStagePanel";
import PredictPanel from "./PredictPanel";

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
  regData: RegressionRunResponse;
  recommendM: UseMutationResult<RegressionRecommendResponse, Error, RegressionSelectionRequest>;
  assetType: AssetType;
  regionLabel: string;
  profileTarget?: ProfileLinkTarget | null;
};

export default function RecommendationModal({
  open,
  onClose,
  regBody,
  regData,
  recommendM,
  assetType,
  regionLabel,
  profileTarget,
}: Props) {
  const [predictTarget, setPredictTarget] = useState<PredictTarget | null>(null);
  const [runStage2, setRunStage2] = useState(false);
  const launchedTwin = useRef(false);

  const predictFitM = useMutation({
    mutationFn: (body: RegressionRunRequest) => runRegression(body),
  });

  const twinAnchor = useMemo(
    () =>
      resolveTwinAnchorFromRequest({
        profileTarget,
        regionCodes: regBody.region_codes,
        regionCodeLevel: regBody.region_code_level,
      }),
    [profileTarget, regBody.region_codes, regBody.region_code_level],
  );

  const twinLevel =
    twinAnchor?.level === "eupmyeondong" || twinAnchor?.level === "beopjungri"
      ? twinAnchor.level
      : null;

  const twinProfile = twinProfileForBuiltAsset(assetType);

  const twinQ = useQuery({
    queryKey: ["built-profile-twin", twinLevel, twinAnchor?.code, twinProfile],
    queryFn: () =>
      fetchProfileTwinNeighbors(twinLevel!, twinAnchor!.code, { twinProfile }),
    enabled: open && Boolean(twinLevel && twinAnchor?.code),
    staleTime: 5 * 60 * 1000,
  });

  const twinNeighbors = useMemo(
    () => mapProfileTwinNeighbors(twinQ.data?.neighbors),
    [twinQ.data],
  );
  const twinEnabled = Boolean(twinLevel && twinAnchor?.code);
  const twinWaiting = twinEnabled && twinQ.isPending && !twinQ.data;
  const twinCandidateStatus: "loading" | "ready" | "none" = !twinEnabled
    ? "none"
    : twinWaiting
      ? "loading"
      : twinNeighbors.length > 0
        ? "ready"
        : "none";

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
    if (!twin || !twinNeighbors.length) return base;
    return {
      ...base,
      profile_version: twin.profile_version,
      profile_as_of_month: twin.as_of_month ?? undefined,
      profile_window_years: twin.window_years,
      profile_twin_neighbors: twinNeighbors,
    };
  }, [regBody, twinQ.data, twinNeighbors, runStage2]);

  useEffect(() => {
    if (!open) {
      setRunStage2(false);
      launchedTwin.current = false;
      setPredictTarget(null);
      return;
    }
    setPredictTarget(null);
    predictFitM.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 창을 열 때만 미리보기·탭 초기화
  }, [open]);

  useEffect(() => {
    if (!open || runStage2) return;
    if (twinWaiting) return;
    if (recommendM.data || recommendM.isPending || recommendM.isError) return;
    recommendM.mutate({ ...enrichedRegBody, run_stage2: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin 이웃이 잡힌 뒤 첫 탐색
  }, [open, runStage2, twinWaiting, twinNeighbors.length]);

  useEffect(() => {
    if (!open || !runStage2) {
      launchedTwin.current = false;
      return;
    }
    if (twinWaiting) return;
    if (!twinNeighbors.length) {
      setRunStage2(false);
      return;
    }
    if (launchedTwin.current) return;
    launchedTwin.current = true;
    recommendM.mutate({ ...enrichedRegBody, run_stage2: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin opt-in 후 재요청
  }, [open, runStage2, twinWaiting, twinNeighbors]);

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

  const runExplore = () => {
    setRunStage2(false);
    recommendM.mutate({ ...enrichedRegBody, run_stage2: false });
  };

  const resolveFitN = (label: string) => {
    const data = recommendM.data;
    if (!data) return undefined;
    if (label.includes("pool") && data.stage2?.pools.length) {
      const pool = data.stage2.pools.find((p) => label.includes(p.label));
      if (pool) return pool.n;
    }
    return data.stage1.fit_n;
  };

  if (!open) return null;

  const loading = recommendM.isPending && !recommendM.data;
  const explored = Boolean(recommendM.data);

  return (
    <DraggableModalShell
      open={open}
      onClose={onClose}
      titleId="recommendation-modal-title"
      title="Macro 모형 탐색"
      subtitle="탐색 → 결과 → Twin → 비교. 이 창에서만 확인하며 기본 통계 식은 바꾸지 않습니다."
      maxWidthClass="max-w-4xl"
      resizable
      allowFullscreen
      defaultWidth={Math.min(900, typeof window !== "undefined" ? window.innerWidth - 48 : 900)}
      defaultHeight={Math.min(780, typeof window !== "undefined" ? window.innerHeight - 48 : 780)}
      minWidth={520}
      minHeight={360}
      headerActions={
        <div className="flex items-center gap-1.5">
          <AnalysisHelpPanel explain={BUILT_RECOMMEND_HELP} />
          <PublishAiContext context={recommendM.data && aiRecommendContext ? aiRecommendContext : null} />
          <button
            type="button"
            className="btn btn-ghost text-xs"
            disabled={recommendM.isPending}
            onClick={runExplore}
          >
            {recommendM.isPending && !runStage2
              ? "탐색 중…"
              : explored
                ? "다시 탐색"
                : "Macro 탐색"}
          </button>
        </div>
      }
    >
      <div className="h-full min-h-0 space-y-3">
        {loading && (
          <p className="text-xs text-slate-400 text-center py-8">Macro 탐색 계산 중…</p>
        )}

        {recommendM.isError && (
          <p className="text-sm text-red-600">
            {(recommendM.error as Error).message ?? "모형 탐색 실패"}
          </p>
        )}

        {recommendM.data && (
          <RecommendStagePanel
            data={recommendM.data}
            assetType={assetType}
            minePrimary={regData.primary}
            mineScale={regBody.response_scale}
            onPredict={(vars, scale, label) =>
              setPredictTarget({
                vars,
                scale,
                label,
                fitN: resolveFitN(label),
              })
            }
            predictActiveLabel={predictTarget?.label ?? null}
            regionNameByCode={regionNameByCode}
            onRunTwin={twinCandidateStatus === "ready" ? () => setRunStage2(true) : undefined}
            twinRunning={Boolean(runStage2 && (recommendM.isPending || twinWaiting))}
            twinCandidateStatus={twinCandidateStatus}
            predictPanel={
              <div className="mt-2 space-y-2">
                {predictFitM.isPending && (
                  <p className="text-xs text-slate-400 text-center py-2">추정용 모형 적합 중…</p>
                )}
                {predictFitM.isError && (
                  <p className="text-sm text-red-600">
                    {(predictFitM.error as Error).message ?? "추정용 모형 적합 실패"}
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
                    fitN={predictTarget.fitN ?? recommendM.data.stage1.fit_n}
                    scopeNTx={recommendM.data.analysis_scope.scope_n_tx}
                  />
                )}
              </div>
            }
          />
        )}

        {!loading && !recommendM.data && !recommendM.isError && (
          <p className="text-xs text-slate-400 text-center py-6">
            「Macro 탐색」을 누르면 변수 조합과 척도를 CV-MAPE로 비교해 대표 예측모형을 찾습니다.
          </p>
        )}
      </div>
    </DraggableModalShell>
  );
}
