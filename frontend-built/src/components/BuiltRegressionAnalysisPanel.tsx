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
import { fetchProfileTwinNeighbors, runRegression } from "../api/client";
import { buildBuiltRecommendContext } from "../api/aiClient";
import type { ProfileLinkTarget } from "../utils/profileLink";
import AiAssistantPanel from "./AiAssistantPanel";
import MacroModelExploreCard from "./MacroModelExploreCard";
import PredictPanel from "./PredictPanel";
import UpperScopeAnalysisCard from "./UpperScopeAnalysisCard";
import type { AdoptPoolPayload } from "./RecommendStagePanel";

type MacroMode = "predictive" | "explanatory";

type PredictTarget = {
  vars: RegressionVariableSpec;
  scale: ResponseScale;
  label: string;
  fitN?: number;
};

type Props = {
  regBody: RegressionRunRequest;
  regData: RegressionRunResponse;
  resultRegBody: RegressionRunRequest;
  vars: RegressionVariableSpec;
  recommendM: UseMutationResult<
    RegressionRecommendResponse,
    Error,
    RegressionSelectionRequest
  >;
  onAdopt: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  onAdoptPool: (payload: AdoptPoolPayload) => void;
  adopting?: boolean;
  assetType: AssetType;
  regionLabel: string;
  profileTarget?: ProfileLinkTarget | null;
};

export default function BuiltRegressionAnalysisPanel({
  regBody,
  regData,
  resultRegBody,
  vars,
  recommendM,
  onAdopt,
  onAdoptPool,
  adopting,
  assetType,
  regionLabel,
  profileTarget,
}: Props) {
  const [macroExplored, setMacroExplored] = useState<MacroMode | null>(null);
  const [upperOpened, setUpperOpened] = useState(false);
  const [runStage2, setRunStage2] = useState(false);
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
    enabled: Boolean(twinLevel && profileTarget?.code),
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

  const runRecommend = (mode: MacroMode) => {
    setMacroExplored(mode);
    setPredictTarget(null);
    predictFitM.reset();
    setRunStage2(false);
    recommendM.mutate({ ...enrichedRegBody, run_stage2: false });
  };

  const handleRunTwin = () => {
    setRunStage2(true);
  };

  useEffect(() => {
    setMacroExplored(null);
    setUpperOpened(false);
    setRunStage2(false);
    setPredictTarget(null);
    predictFitM.reset();
    recommendM.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 새 회귀 결과마다 Macro·상위지역 opt-in 리셋
  }, [regData]);

  useEffect(() => {
    if (!runStage2 || macroExplored !== "predictive") return;
    recommendM.mutate(enrichedRegBody);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin opt-in 후 재요청
  }, [runStage2, enrichedRegBody]);

  useEffect(() => {
    if (!predictTarget) return;
    predictFitM.mutate({
      ...regBody,
      variables: predictTarget.vars,
      response_scale: predictTarget.scale,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fit when target changes
  }, [predictTarget]);

  const aiRecommendContext = useMemo(() => {
    if (!recommendM.data || !macroExplored) return null;
    return buildBuiltRecommendContext(recommendM.data, {
      regionLabel,
      assetType: String(assetType),
      purpose: "statistics",
    });
  }, [recommendM.data, macroExplored, regionLabel, assetType]);

  const resolveFitN = (label: string) => {
    const data = recommendM.data;
    if (!data) return undefined;
    if (label.includes("pool") && data.stage2?.pools.length) {
      const pool = data.stage2.pools.find((p) => label.includes(p.label));
      if (pool) return pool.n;
    }
    return data.stage1.fit_n;
  };

  const handlePredict = (nextVars: RegressionVariableSpec, scale: ResponseScale, label: string) => {
    setPredictTarget({
      vars: nextVars,
      scale,
      label,
      fitN: resolveFitN(label),
    });
  };

  const predictRegBody = useMemo(() => {
    if (!predictTarget) return null;
    return {
      ...regBody,
      variables: predictTarget.vars,
      response_scale: predictTarget.scale,
    };
  }, [regBody, predictTarget]);

  const focusLabel = regData.focus_scope_label ?? regData.primary.scope_label;

  return (
    <div className="space-y-4">
      <div
        className="border-t-2 border-slate-200 dark:border-slate-700 pt-4 -mt-1"
        aria-labelledby="built-additional-analysis-heading"
      >
        <h2
          id="built-additional-analysis-heading"
          className="text-sm font-semibold text-slate-800 dark:text-slate-100"
        >
          추가분석
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          기본 회귀·예측과 별도 — Macro 모형 탐색·상위지역 비교
        </p>
      </div>

      {aiRecommendContext && (
        <div className="flex justify-end px-0">
          <AiAssistantPanel context={aiRecommendContext} />
        </div>
      )}

      <MacroModelExploreCard
        mode="predictive"
        sectionId="built-step-predictive"
        recommendM={recommendM}
        onRunRecommend={() => runRecommend("predictive")}
        onAdopt={onAdopt}
        onAdoptPool={onAdoptPool}
        adopting={adopting}
        onPredict={handlePredict}
        predictActiveLabel={predictTarget?.label ?? null}
        regionNameByCode={regionNameByCode}
        onRunTwin={handleRunTwin}
        twinRunning={recommendM.isPending && runStage2}
        showHelp={false}
        explored={macroExplored === "predictive"}
        exploring={macroExplored === "predictive"}
      />

      <MacroModelExploreCard
        mode="explanatory"
        sectionId="built-step-explanatory"
        recommendM={recommendM}
        onRunRecommend={() => runRecommend("explanatory")}
        onAdopt={onAdopt}
        onAdoptPool={onAdoptPool}
        adopting={adopting}
        onPredict={handlePredict}
        predictActiveLabel={predictTarget?.label ?? null}
        regionNameByCode={regionNameByCode}
        showHelp={false}
        explored={macroExplored === "explanatory"}
        exploring={macroExplored === "explanatory"}
      />

      {macroExplored &&
        (predictTarget || predictFitM.isPending || predictFitM.data) && (
          <div className="card space-y-2">
            <h3 className="font-semibold text-sm">Macro 후보 예측 미리보기</h3>
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
                regData={predictFitM.data}
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

      <UpperScopeAnalysisCard
        regData={regData}
        regBody={resultRegBody}
        vars={vars}
        assetType={assetType}
        responseScale={resultRegBody.response_scale ?? "linear"}
        regionLabel={regionLabel}
        focusLabel={focusLabel}
        opened={upperOpened}
        onOpen={() => setUpperOpened(true)}
      />
    </div>
  );
}
