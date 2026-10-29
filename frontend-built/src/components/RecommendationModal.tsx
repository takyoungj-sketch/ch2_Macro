import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, type UseMutationResult } from "@tanstack/react-query";
import type {
  AssetType,
  RegressionRecommendResponse,
  RegressionLevelResult,
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
import { BasicRegressionCoefficients, BasicRegressionEquation } from "./BasicRegressionDetails";
import { contentSignature } from "../../../shared/regression-ui/signature";
import { analysisPhase, phaseLabels } from "../../../shared/regression-ui/phase";

type PredictTarget = {
  vars: RegressionVariableSpec;
  scale: ResponseScale;
  label: string;
  fitN?: number;
  regionCodes?: string[];
};

type Props = {
  open: boolean;
  onClose: () => void;
  regBody: RegressionRunRequest;
  regData: RegressionRunResponse;
  baselineRegBody?: RegressionRunRequest;
  recommendM: UseMutationResult<RegressionRecommendResponse, Error, RegressionSelectionRequest>;
  assetType: AssetType;
  regionLabel: string;
  profileTarget?: ProfileLinkTarget | null;
  /** 대표 예측모형의 변수·척도만 기본 통계에 옮긴다. 통계분석은 호출하지 않는다. */
  onAdopt?: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
};

export default function RecommendationModal({
  open,
  onClose,
  regBody,
  regData,
  baselineRegBody = regBody,
  recommendM,
  assetType,
  regionLabel,
  profileTarget,
  onAdopt,
}: Props) {
  const [predictTarget, setPredictTarget] = useState<PredictTarget | null>(null);
  const [twin1Target, setTwin1Target] = useState<PredictTarget | null>(null);
  const [researchTarget, setResearchTarget] = useState<PredictTarget | null>(null);
  const [runStage2, setRunStage2] = useState(false);
  const [checkedTwinCodes, setCheckedTwinCodes] = useState<string[]>([]);
  const [twinRunId, setTwinRunId] = useState(0);
  const [researchRunId, setResearchRunId] = useState(0);
  const [runTwinResearch, setRunTwinResearch] = useState(false);
  const [heldData, setHeldData] = useState<RegressionRecommendResponse | null>(null);
  const [localBaseline, setLocalBaseline] = useState<RegressionRecommendResponse | null>(null);
  const [resultTwinCodes, setResultTwinCodes] = useState<string[]>([]);
  const launchedStage1 = useRef(false);
  const launchedTwin = useRef(false);
  const launchedResearch = useRef(false);
  const autoResearchPredictKey = useRef<string | null>(null);

  const predictFitM = useMutation({
    mutationFn: (body: RegressionRunRequest) => runRegression(body),
  });
  const twin1FitM = useMutation({
    mutationFn: (body: RegressionRunRequest) => runRegression(body),
  });
  const researchFitM = useMutation({
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

  const twinChoices = useMemo(
    () =>
      (twinQ.data?.neighbors ?? [])
        .map((n) => {
          const code = (n.twin_beopjungri_code || n.twin_eupmyeondong_code || "").trim();
          const name = n.twin_beopjungri_name || n.twin_eupmyeondong_name || n.twin_sigungu_name || code;
          return { code, rank: n.rank, label: name };
        })
        .filter((row) => row.code),
    [twinQ.data],
  );

  useEffect(() => {
    setCheckedTwinCodes([]);
  }, [twinChoices]);

  const enrichedRegBody: RegressionSelectionRequest = useMemo(() => {
    const twin = twinQ.data;
    const base: RegressionSelectionRequest = {
      ...regBody,
      run_stage2: runStage2,
      run_stage2_research: runTwinResearch,
    };
    if (!twin || !twinNeighbors.length) return base;
    return {
      ...base,
      profile_version: twin.profile_version,
      profile_as_of_month: twin.as_of_month ?? undefined,
      profile_window_years: twin.window_years,
      profile_twin_neighbors: twinNeighbors,
      selected_twin_codes: checkedTwinCodes,
    };
  }, [regBody, twinQ.data, twinNeighbors, checkedTwinCodes, runStage2, runTwinResearch]);

  useEffect(() => {
    if (!open) {
      setRunStage2(false);
      setRunTwinResearch(false);
      launchedStage1.current = false;
      launchedTwin.current = false;
      launchedResearch.current = false;
      autoResearchPredictKey.current = null;
      setPredictTarget(null);
      setTwin1Target(null);
      setResearchTarget(null);
      setHeldData(null);
      setLocalBaseline(null);
      return;
    }
    setPredictTarget(null);
    setTwin1Target(null);
    setResearchTarget(null);
    autoResearchPredictKey.current = null;
    predictFitM.reset();
    twin1FitM.reset();
    researchFitM.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 창을 열 때만 미리보기·탭 초기화
  }, [open]);

  useEffect(() => {
    if (!open || runStage2) return;
    if (twinWaiting) return;
    // 실패·취소 상태를 게이트로 쓰면 창을 다시 열어도 영구히 막힌다. 열린 세션마다 한 번.
    if (launchedStage1.current || recommendM.data || recommendM.isPending) return;
    launchedStage1.current = true;
    recommendM.mutate({ ...enrichedRegBody, run_stage2: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin 이웃이 잡힌 뒤 첫 탐색
  }, [open, runStage2, twinWaiting, twinNeighbors.length]);

  useEffect(() => {
    if (!open || !runStage2) {
      launchedTwin.current = false;
      return;
    }
    if (twinWaiting) return;
    if (!twinNeighbors.length || !checkedTwinCodes.length) {
      setRunStage2(false);
      return;
    }
    if (launchedTwin.current) return;
    launchedTwin.current = true;
    recommendM.mutate({ ...enrichedRegBody, run_stage2: true, run_stage2_research: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin opt-in 후 재요청
  }, [open, runStage2, twinRunId, twinWaiting, twinNeighbors, checkedTwinCodes]);

  useEffect(() => {
    if (!open || !runTwinResearch) {
      launchedResearch.current = false;
      return;
    }
    if (twinWaiting) return;
    if (!twinNeighbors.length || !checkedTwinCodes.length) {
      setRunTwinResearch(false);
      return;
    }
    if (launchedResearch.current) return;
    launchedResearch.current = true;
    recommendM.mutate({
      ...enrichedRegBody,
      run_stage2: true,
      run_stage2_research: true,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin 실험2 opt-in 후 재요청
  }, [open, runTwinResearch, researchRunId, twinWaiting, twinNeighbors, checkedTwinCodes]);

  useEffect(() => {
    if (!open) return;
    const d = recommendM.data;
    if (!d) return;
    setHeldData(d);
    setResultTwinCodes(recommendM.variables?.selected_twin_codes ?? []);
    if (!d.stage2?.ran) setLocalBaseline(d);
  }, [open, recommendM.data]);

  useEffect(() => {
    if (!open || !predictTarget) return;
    predictFitM.mutate({
      ...regBody,
      variables: predictTarget.vars,
      response_scale: predictTarget.scale,
      ...(predictTarget.regionCodes?.length
        ? { region_codes: predictTarget.regionCodes }
        : {}),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fit when target changes
  }, [open, predictTarget]);

  useEffect(() => {
    if (!open || !twin1Target) return;
    twin1FitM.mutate({
      ...regBody,
      variables: twin1Target.vars,
      response_scale: twin1Target.scale,
      ...(twin1Target.regionCodes?.length
        ? { region_codes: twin1Target.regionCodes }
        : {}),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin1 fit when target changes
  }, [open, twin1Target]);

  useEffect(() => {
    if (!open || !researchTarget) return;
    researchFitM.mutate({
      ...regBody,
      variables: researchTarget.vars,
      response_scale: researchTarget.scale,
      ...(researchTarget.regionCodes?.length
        ? { region_codes: researchTarget.regionCodes }
        : {}),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Twin2 fit when target changes
  }, [open, researchTarget]);

  useEffect(() => {
    if (!open) return;
    const data = recommendM.data;
    const research = data?.stage2?.research;
    if (!data?.stage2?.research_ran || !research) return;
    const key = `${research.candidate_id}:${research.n}:${(research.region_codes ?? []).join(",")}`;
    if (autoResearchPredictKey.current === key) return;
    autoResearchPredictKey.current = key;
    setResearchTarget({
      vars: research.variables ?? data.stage1.primary.variables,
      scale: research.response_scale ?? data.stage1.primary.response_scale,
      label: `Twin 실험2 · ${research.label}`,
      fitN: research.n,
      regionCodes: research.region_codes,
    });
  }, [open, recommendM.data]);

  const predictRegBody = useMemo(() => {
    if (!predictTarget) return null;
    return {
      ...regBody,
      variables: predictTarget.vars,
      response_scale: predictTarget.scale,
      ...(predictTarget.regionCodes?.length
        ? { region_codes: predictTarget.regionCodes }
        : {}),
    };
  }, [regBody, predictTarget]);

  const twin1RegBody = useMemo(() => {
    if (!twin1Target) return null;
    return {
      ...regBody,
      variables: twin1Target.vars,
      response_scale: twin1Target.scale,
      ...(twin1Target.regionCodes?.length
        ? { region_codes: twin1Target.regionCodes }
        : {}),
    };
  }, [regBody, twin1Target]);

  const researchRegBody = useMemo(() => {
    if (!researchTarget) return null;
    return {
      ...regBody,
      variables: researchTarget.vars,
      response_scale: researchTarget.scale,
      ...(researchTarget.regionCodes?.length
        ? { region_codes: researchTarget.regionCodes }
        : {}),
    };
  }, [regBody, researchTarget]);

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
    setRunTwinResearch(false);
    launchedStage1.current = true;
    launchedTwin.current = false;
    launchedResearch.current = false;
    autoResearchPredictKey.current = null;
    setPredictTarget(null);
    setTwin1Target(null);
    setResearchTarget(null);
    recommendM.mutate({ ...enrichedRegBody, run_stage2: false, run_stage2_research: false });
  };

  const resolveFitN = (label: string, optsFitN?: number) => {
    if (optsFitN != null) return optsFitN;
    const data = recommendM.data;
    if (!data) return undefined;
    if (label.startsWith("Twin 실험2") && data.stage2?.research?.n) {
      return data.stage2.research.n;
    }
    if (label.startsWith("Twin") && data.stage2?.inspect_pool?.n) {
      return data.stage2.inspect_pool.n;
    }
    if (label.startsWith("Twin") && data.stage2?.primary?.n) {
      return data.stage2.primary.n;
    }
    if (label.includes("pool") && data.stage2?.pools.length) {
      const pool = data.stage2.pools.find((p) => label.includes(p.label));
      if (pool) return pool.n;
    }
    return data.stage1.fit_n;
  };

  if (!open) return null;

  const sourceData = recommendM.data ?? heldData;
  const panelData =
    sourceData && localBaseline && sourceData.stage2?.ran
      ? {
          ...sourceData,
          stage1: localBaseline.stage1,
          coefficient_narratives: localBaseline.coefficient_narratives,
          warnings: localBaseline.warnings,
          termination: localBaseline.termination,
          analysis_scope: localBaseline.analysis_scope,
          diagnostics_checklist: localBaseline.diagnostics_checklist,
        }
      : sourceData;
  const loading =
    recommendM.isPending && !panelData && !runStage2 && !runTwinResearch;
  const explored = Boolean(panelData);
  const twin1Pending = Boolean(
    runStage2 && !runTwinResearch && (recommendM.isPending || twinWaiting),
  );
  const twinSelectionChanged = Boolean(panelData?.stage2?.ran &&
    contentSignature([...checkedTwinCodes].sort()) !== contentSignature([...resultTwinCodes].sort()));
  const requestStage = recommendM.variables?.run_stage2_research ? "twin2"
    : recommendM.variables?.run_stage2 ? "twin1" : "local";
  const localPhase = analysisPhase({ pending: recommendM.isPending && requestStage === "local",
    failed: recommendM.isError && requestStage === "local", hasResult: !!panelData });
  const twinPhase = analysisPhase({ pending: recommendM.isPending && requestStage === "twin1",
    failed: recommendM.isError && requestStage === "twin1", hasResult: !!panelData?.stage2?.ran,
    changed: twinSelectionChanged, unavailable: !twinEnabled || twinQ.isError });
  const researchPhase = analysisPhase({ pending: recommendM.isPending && requestStage === "twin2",
    failed: recommendM.isError && requestStage === "twin2", hasResult: !!panelData?.stage2?.research_ran,
    changed: twinSelectionChanged, unavailable: !twinEnabled || twinQ.isError });

  return (
    <DraggableModalShell
      open={open}
      onClose={onClose}
      titleId="recommendation-modal-title"
      title="Macro 모형 탐색"
      subtitle="예측형 · 설명형 · 쌍둥이 확장. 이 창에서 후보를 비교하며 기본 회귀 설정은 유지합니다."
      maxWidthClass="max-w-6xl"
      resizable
      allowFullscreen
      defaultWidth={Math.min(
        Math.round((typeof window !== "undefined" ? window.innerWidth : 1200) * 0.9),
        typeof window !== "undefined" ? window.innerWidth - 32 : 1100,
      )}
      defaultHeight={Math.min(
        Math.round((typeof window !== "undefined" ? window.innerHeight : 900) * 0.88),
        typeof window !== "undefined" ? window.innerHeight - 32 : 820,
      )}
      minWidth={520}
      minHeight={360}
      headerActions={
        <div className="flex items-center gap-1.5">
          <AnalysisHelpPanel explain={BUILT_RECOMMEND_HELP} />
          <PublishAiContext context={!recommendM.isPending && !twinSelectionChanged && recommendM.data && aiRecommendContext ? aiRecommendContext : null} />
          <button
            type="button"
            className="btn btn-ghost text-sm"
            disabled={recommendM.isPending}
            onClick={runExplore}
          >
            {recommendM.isPending && !runStage2 && !runTwinResearch
              ? "탐색 중…"
              : explored
                ? "다시 탐색"
                : "Macro 탐색"}
          </button>
        </div>
      }
    >
      <div className="h-full min-h-0 space-y-3">
        <section className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 space-y-2 text-sm" aria-label="탐색 범위와 진행 상태">
          <p><strong>현재 탐색 범위</strong> · {regionLabel} · {regBody.window_years ? `최근 ${regBody.window_years}년` : `${regBody.contract_year_from ?? "시작연도 제한 없음"} ~ ${regBody.contract_year_to ?? "종료연도 제한 없음"}`}
            {regBody.as_of_month && ` · 기준월 ${regBody.as_of_month}`}</p>
          <ol className="flex flex-wrap gap-x-5 gap-y-1" aria-live="polite">
            <li>1. 지역 내 탐색 · {phaseLabels[localPhase]}</li>
            <li>2. Twin1 · {phaseLabels[twinPhase]}</li>
            <li>3. Twin2 · {phaseLabels[researchPhase]}</li>
          </ol>
          {panelData && <p>조회 {panelData.analysis_scope.scope_n_tx.toLocaleString("ko-KR")}건 · 탐색 {panelData.stage1.selection_n.toLocaleString("ko-KR")}건 · 적합 {panelData.stage1.fit_n.toLocaleString("ko-KR")}건{!panelData.analysis_scope.include_partial && Boolean(panelData.analysis_scope.partial_tx_count) && ` · 지분 ${panelData.analysis_scope.partial_tx_count}건 제외`} </p>}
          {recommendM.isPending && panelData && <p role="status">새 결과를 계산 중입니다. 아래에는 이전 계산 결과가 남아 있습니다.</p>}
          {recommendM.isError && panelData && <p role="status">이번 계산은 실패했습니다. 아래 이전 성공 결과가 이번 요청의 완료를 뜻하지 않습니다.</p>}
          {twinQ.isError && <p role="alert">쌍둥이 지역 후보를 불러오지 못했습니다. 지역 내 탐색 결과와 구분해서 확인하세요.</p>}
          {contentSignature(baselineRegBody) !== contentSignature(regBody) && <p>기본 회귀와 현재 탐색의 설정이 다릅니다. 기본 회귀 비교 열은 마지막 통계분석 조건입니다.</p>}
        </section>
        {loading && (
          <p className="text-sm text-slate-400 text-center py-8">Macro 탐색 계산 중…</p>
        )}

        {recommendM.isError && (
          <p className="text-sm text-red-600">
            {(recommendM.error as Error).message ?? "모형 탐색 실패"}
          </p>
        )}

        {panelData && (
          <RecommendStagePanel
            data={panelData}
            assetType={assetType}
            minePrimary={regData.primary}
            mineScale={baselineRegBody.response_scale}
            onAdopt={recommendM.isPending ? undefined : onAdopt}
            onPredict={recommendM.isPending || twinSelectionChanged ? undefined : (vars, scale, label, opts) => {
              if (recommendM.isPending || (opts?.slot && twinSelectionChanged)) return;
              const target = {
                vars,
                scale,
                label,
                fitN: resolveFitN(label, opts?.fitN),
                regionCodes: opts?.regionCodes,
              };
              if (opts?.slot === "twin2" || label.startsWith("Twin 실험2")) {
                setResearchTarget(target);
              } else if (opts?.slot === "twin1" || label.startsWith("Twin 재적합")) {
                setTwin1Target(target);
              } else {
                setPredictTarget(target);
              }
            }}
            predictActiveLabel={predictTarget?.label ?? null}
            predictOptions={!predictFitM.isPending && !predictFitM.isError ? predictFitM.data?.primary.predict_options : null}
            twin1PredictActiveLabel={twin1Target?.label ?? null}
            twin1PredictIdentity={twin1Target ? contentSignature({ vars: twin1Target.vars, scale: twin1Target.scale, fitN: twin1Target.fitN, regionCodes: twin1Target.regionCodes }) : null}
            researchPredictIdentity={researchTarget ? contentSignature({ vars: researchTarget.vars, scale: researchTarget.scale, fitN: researchTarget.fitN, regionCodes: researchTarget.regionCodes }) : null}
            researchPredictActiveLabel={researchTarget?.label ?? null}
            regionNameByCode={regionNameByCode}
            onRunTwin={
              twinCandidateStatus === "ready" && !recommendM.isPending
                ? () => {
                    setRunTwinResearch(false);
                    launchedResearch.current = false;
                    setResearchTarget(null);
                    autoResearchPredictKey.current = null;
                    launchedTwin.current = false;
                    setTwinRunId((n) => n + 1);
                    setRunStage2(true);
                  }
                : undefined
            }
            twinChoices={twinChoices}
            checkedTwinCodes={checkedTwinCodes}
            resultTwinCodes={resultTwinCodes}
            twinSelectionChanged={twinSelectionChanged}
            twinStatus={phaseLabels[twinPhase]}
            researchStatus={phaseLabels[researchPhase]}
            onToggleTwinCode={(code) =>
              setCheckedTwinCodes((cur) =>
                cur.includes(code) ? cur.filter((item) => item !== code) : [...cur, code],
              )
            }
            twinRunning={twin1Pending}
            onRunTwinResearch={
              twinCandidateStatus === "ready" && !recommendM.isPending ? () => {
                launchedResearch.current = false;
                setResearchRunId(n => n + 1);
                setRunTwinResearch(true);
              } : undefined
            }
            twinResearchRunning={Boolean(
              runTwinResearch && (recommendM.isPending || twinWaiting),
            )}
            twinCandidateStatus={twinCandidateStatus}
            busy={recommendM.isPending}
            predictPanel={
              <div className="mt-2 space-y-2">
                {predictFitM.isPending && (
                  <p className="text-sm text-slate-400 text-center py-2">추정용 모형 적합 중…</p>
                )}
                {predictFitM.isError && (
                  <p className="text-sm text-red-600">
                    {(predictFitM.error as Error).message ?? "추정용 모형 적합 실패"}
                  </p>
                )}
                {!predictFitM.isPending && !predictFitM.isError && predictFitM.data && predictRegBody && predictTarget && (
                  <PredictPanel
                    embedded
                    basicPresentation
                    regData={predictFitM.data as RegressionRunResponse}
                    regBody={predictRegBody}
                    vars={predictTarget.vars}
                    assetType={assetType}
                    regionLabel={regionLabel}
                    modelHint={predictTarget.label}
                    fitN={predictFitM.data.primary.n}
                    scopeNTx={panelData.analysis_scope.scope_n_tx}
                  />
                )}
              </div>
            }
            twin1PredictPanel={
              <div className="mt-2 space-y-2">
                {twin1FitM.isPending && (
                  <p className="text-sm text-slate-400 text-center py-2">추정용 모형 적합 중…</p>
                )}
                {twin1FitM.isError && (
                  <p className="text-sm text-red-600">
                    {(twin1FitM.error as Error).message ?? "추정용 모형 적합 실패"}
                  </p>
                )}
                {!twinSelectionChanged && !twin1FitM.isPending && !twin1FitM.isError && twin1FitM.data && twin1RegBody && twin1Target && (
                  <>
                  <TwinFitDetails result={twin1FitM.data.primary} scale={twin1Target.scale} assetType={assetType} />
                  <PredictPanel
                    embedded
                    basicPresentation
                    regData={twin1FitM.data as RegressionRunResponse}
                    regBody={twin1RegBody}
                    vars={twin1Target.vars}
                    assetType={assetType}
                    regionLabel={regionLabel}
                    modelHint="Twin1 · 기존 식 재적합"
                    fitN={twin1FitM.data.primary.n}
                    scopeNTx={panelData.analysis_scope.scope_n_tx}
                  />
                  </>
                )}
              </div>
            }
            researchPredictPanel={
              <div className="mt-2 space-y-2">
                {researchFitM.isPending && (
                  <p className="text-sm text-slate-400 text-center py-2">추정용 모형 적합 중…</p>
                )}
                {researchFitM.isError && (
                  <p className="text-sm text-red-600">
                    {(researchFitM.error as Error).message ?? "추정용 모형 적합 실패"}
                  </p>
                )}
                {!twinSelectionChanged && !researchFitM.isPending && !researchFitM.isError && researchFitM.data && researchRegBody && researchTarget && (
                  <>
                  <TwinFitDetails result={researchFitM.data.primary} scale={researchTarget.scale} assetType={assetType} />
                  <PredictPanel
                    embedded
                    basicPresentation
                    regData={researchFitM.data as RegressionRunResponse}
                    regBody={researchRegBody}
                    vars={researchTarget.vars}
                    assetType={assetType}
                    regionLabel={regionLabel}
                    modelHint="Twin2 · 확장 표본 재탐색"
                    fitN={researchFitM.data.primary.n}
                    scopeNTx={panelData.analysis_scope.scope_n_tx}
                  />
                  </>
                )}
              </div>
            }
          />
        )}

        {!loading && !panelData && !recommendM.isError && !runStage2 && !runTwinResearch && (
          <p className="text-sm text-slate-400 text-center py-6">
            {twinWaiting
              ? "쌍둥이 지역 후보를 불러온 뒤 탐색을 시작합니다…"
              : "변수 조합과 척도를 CV-MAPE로 비교해 탐색 1위를 고릅니다. 검증이 얇으면 대표모형으로 확정하지 않습니다. 결과는 예측형·설명형·쌍둥이 확장으로 나뉩니다. 기본 통계 식은 바꾸지 않습니다."}
          </p>
        )}
        {twin1Pending && !panelData && (
          <p className="text-sm text-violet-800 dark:text-violet-200 text-center py-6">
            Local 최적식은 그대로입니다. Twin 실험1을 계산 중…
          </p>
        )}
      </div>
    </DraggableModalShell>
  );
}

function TwinFitDetails({ result, scale, assetType }: { result: RegressionLevelResult; scale: ResponseScale; assetType: AssetType }) {
  return <details className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700">
    <summary className="cursor-pointer font-semibold">회귀식·계수 상세</summary>
    <div className="mt-3 space-y-3">
      <BasicRegressionEquation coefficients={result.coefficients} responseScale={scale} assetType={assetType} predictOptions={result.predict_options} equation={result.equation} />
      <BasicRegressionCoefficients coefficients={result.coefficients} responseScale={scale} assetType={assetType} predictOptions={result.predict_options} />
    </div>
  </details>;
}
