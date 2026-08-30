import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useMutation, useQuery, type UseMutationResult } from "@tanstack/react-query";
import type {
  AssetType,
  RegressionLevelResult,
  RegressionRecommendResponse,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionSelectionRequest,
  RegressionVariableSpec,
  ResponseScale,
} from "../types";
import { fetchProfileTwinNeighbors, runRegression, twinProfileForBuiltAsset } from "../api/client";
import { buildBuiltRecommendContext } from "../api/aiClient";
import { fmtDecimal, fmtNum } from "../utils/regressionFormat";
import { BUILT_RECOMMEND_HELP } from "../utils/builtAnalysisHelp";
import type { ProfileLinkTarget } from "../utils/profileLink";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import DraggableModalShell from "./DraggableModalShell";
import RecommendStagePanel from "./RecommendStagePanel";
import PredictPanel from "./PredictPanel";

type MacroTab = "predictive" | "explanatory";

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
  const [tab, setTab] = useState<MacroTab>("predictive");
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
    if (!open) {
      setRunStage2(false);
      setPredictTarget(null);
      return;
    }
    setTab("predictive");
    setPredictTarget(null);
    predictFitM.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 창을 열 때만 미리보기·탭 초기화
  }, [open]);

  useEffect(() => {
    if (!open || runStage2) return;
    if (recommendM.data || recommendM.isPending || recommendM.isError) return;
    recommendM.mutate({ ...enrichedRegBody, run_stage2: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 결과 없을 때만 첫 탐색
  }, [open]);

  useEffect(() => {
    if (!open || !runStage2) return;
    recommendM.mutate(enrichedRegBody);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin opt-in 후 재요청
  }, [open, runStage2, enrichedRegBody]);

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
    setPredictTarget(null);
    predictFitM.reset();
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
      subtitle="한 번 탐색하면 예측형·설명형이 함께 나옵니다. 이 창에서만 확인하며 기본 통계 식은 바꾸지 않습니다."
      maxWidthClass="max-w-4xl"
      resizable
      allowFullscreen
      defaultWidth={Math.min(900, typeof window !== "undefined" ? window.innerWidth - 48 : 900)}
      defaultHeight={Math.min(780, typeof window !== "undefined" ? window.innerHeight - 48 : 780)}
      minWidth={520}
      minHeight={360}
      headerExtra={
        explored ? (
          <div className="flex gap-1">
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
                    : "border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300",
                )}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
          </div>
        ) : null
      }
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
          <>
            <MacroVsMineCompare mine={regData.primary} recommend={recommendM.data} />
            <RecommendStagePanel
              data={recommendM.data}
              mode={tab}
              onPredict={
                tab === "predictive"
                  ? (vars, scale, label) =>
                      setPredictTarget({
                        vars,
                        scale,
                        label,
                        fitN: resolveFitN(label),
                      })
                  : undefined
              }
              predictActiveLabel={predictTarget?.label ?? null}
              regionNameByCode={regionNameByCode}
              onRunTwin={tab === "predictive" ? () => setRunStage2(true) : undefined}
              twinRunning={recommendM.isPending && runStage2}
            />
          </>
        )}

        {!loading && !recommendM.data && !recommendM.isError && (
          <p className="text-xs text-slate-400 text-center py-6">
            「Macro 탐색」을 누르면 SSOT 변수 풀에서 예측형(CV-MAPE)과 설명형(AIC) 후보를 함께
            찾습니다.
          </p>
        )}

        {tab === "predictive" &&
          recommendM.data &&
          (predictTarget || predictFitM.isPending || predictFitM.data) && (
            <div className="border-t border-slate-200 dark:border-slate-700 pt-3 space-y-2">
              <h3 className="font-semibold text-sm">이 창의 예측 미리보기</h3>
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

function cell(v: string) {
  return <span className="tabular-nums">{v}</span>;
}

function MacroVsMineCompare({
  mine,
  recommend,
}: {
  mine: RegressionLevelResult;
  recommend: RegressionRecommendResponse;
}) {
  const pred = recommend.stage1.primary;
  const expl = recommend.stage1.alternate ?? recommend.stage1.primary;
  const predCv = pred.metrics.cv_mape;
  const predAdj = pred.metrics.adj_r_squared;
  const explAdj = expl.metrics.adj_r_squared;

  return (
    <div className="rounded-md border border-slate-200 dark:border-slate-700 px-3 py-2 text-xs space-y-1.5">
      <p className="font-medium text-slate-700 dark:text-slate-200">내 식 vs Macro</p>
      <p className="text-[11px] text-slate-500">
        참고만. 기본 통계는 그대로입니다. 내 실험 MAPE는 표본 내, 예측형은 CV-MAPE, 설명형은 AIC.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="text-slate-500">
              <th className="py-1 pr-2 font-medium"> </th>
              <th className="py-1 pr-2 font-medium">내 실험</th>
              <th className="py-1 pr-2 font-medium">예측형</th>
              <th className="py-1 font-medium">설명형</th>
            </tr>
          </thead>
          <tbody className="text-slate-800 dark:text-slate-100">
            <tr>
              <td className="py-0.5 pr-2 text-slate-500">n</td>
              <td className="py-0.5 pr-2">{cell(fmtNum(mine.n))}</td>
              <td className="py-0.5 pr-2">{cell(fmtNum(recommend.stage1.fit_n))}</td>
              <td className="py-0.5">{cell("—")}</td>
            </tr>
            <tr>
              <td className="py-0.5 pr-2 text-slate-500">Adj R²</td>
              <td className="py-0.5 pr-2">{cell(fmtDecimal(mine.adj_r_squared, 3))}</td>
              <td className="py-0.5 pr-2">{cell(fmtDecimal(predAdj, 3))}</td>
              <td className="py-0.5">{cell(fmtDecimal(explAdj, 3))}</td>
            </tr>
            <tr>
              <td className="py-0.5 pr-2 text-slate-500">지표</td>
              <td className="py-0.5 pr-2">
                MAPE {mine.mape != null ? `${fmtDecimal(mine.mape, 1)}%` : "—"}
              </td>
              <td className="py-0.5 pr-2">
                CV-MAPE {predCv != null ? `${fmtDecimal(predCv, 1)}%` : "—"}
              </td>
              <td className="py-0.5">AIC {expl.aic != null ? fmtNum(Math.round(expl.aic)) : "—"}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
