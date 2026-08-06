import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import AiAssistantPanel from "./AiAssistantPanel";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { buildBuiltPredictionContext } from "../api/aiClient";
import { predictRegression } from "../api/client";
import { isOnlyDetached } from "../utils/assetTypes";
import { BUILT_PREDICTION_HELP } from "../utils/builtAnalysisHelp";
import {
  assessmentForName,
  buildExtrapolationGuidance,
  extrapolationBadge,
  inputBorderClass,
  isTechnicalExtrapolationWarning,
  shouldHidePrediction,
} from "../utils/extrapolationPolicy";
import { ADMIN_LABELS, ASSET_TYPE_LABELS, formatCoefName } from "../utils/regressionFormat";
import type {
  AssetType,
  PredictOptions,
  RegressionPredictRequest,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionVariableSpec,
} from "../types";

function fmtNum(n?: number | null, digits = 0) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function defaultPredictInputs(opts?: PredictOptions | null): Record<string, string> {
  const out: Record<string, string> = {};
  for (const c of opts?.continuous ?? []) {
    out[c.name] = "";
  }
  if (opts?.zone_types?.length) {
    out.zone_type = opts.zone_reference ?? opts.zone_types[0];
  }
  if (opts?.building_uses?.length) {
    out.building_use = opts.building_use_reference ?? opts.building_uses[0];
  }
  if (opts?.road_width_labels?.length) {
    out.road_width_label = opts.road_width_reference ?? opts.road_width_labels[0];
  }
  if (opts?.asset_types?.length) {
    out.predict_asset_type = opts.asset_type_reference ?? opts.asset_types[0];
  }
  if (opts?.region_leaves?.length) {
    out.region_leaf = opts.region_reference ?? opts.region_leaves[0];
  }
  return out;
}

type Props = {
  regData: RegressionRunResponse;
  regBody: RegressionRunRequest;
  vars: RegressionVariableSpec;
  assetType: AssetType;
  regionLabel: string;
  /** 모달 안 컴팩트 레이아웃 */
  embedded?: boolean;
  /** 상단 안내 (예: 추천 모형 기준) */
  modelHint?: string | null;
  /** 추천 미리보기 — 채택 예정 식 fit_n */
  fitN?: number;
  /** 추천 scope 거래 건수 */
  scopeNTx?: number;
};

export default function PredictPanel({
  regData,
  regBody,
  vars,
  assetType,
  regionLabel,
  embedded = false,
  modelHint,
  fitN,
  scopeNTx,
}: Props) {
  const levels = useMemo(() => {
    const all = [regData.primary, ...regData.comparisons];
    return all.filter((l) => l.n >= 10 && l.coefficients.length > 0 && l.predict_options);
  }, [regData]);

  const [adminLevel, setAdminLevel] = useState<string>("sigungu");
  const selected = levels.find((l) => l.admin_level === adminLevel) ?? levels[0];
  const [inputs, setInputs] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!levels.length) return;
    const focus = regData.primary;
    const pick = levels.find((l) => l.admin_level === focus.admin_level) ?? focus;
    setAdminLevel(pick.admin_level);
    setInputs(defaultPredictInputs(pick.predict_options));
  }, [regData, levels]);

  useEffect(() => {
    if (!selected?.predict_options) return;
    setInputs(defaultPredictInputs(selected.predict_options));
  }, [adminLevel, selected?.predict_options]);

  const predictM = useMutation({ mutationFn: predictRegression });

  const aiPredictionContext = useMemo(() => {
    if (!predictM.data || !selected) return null;
    return buildBuiltPredictionContext(predictM.data, {
      regionLabel: selected.scope_label ?? regionLabel,
      assetType,
      regressionN: selected.n,
      adjR2: selected.adj_r_squared,
    });
  }, [predictM.data, selected, regionLabel, assetType]);

  if (!levels.length) {
    return embedded ? (
      <p className="text-xs text-slate-400 text-center py-3">
        예측 가능한 scope가 없습니다 (n≥10 · 계수 있는 모형 필요).
      </p>
    ) : null;
  }

  const opts = selected?.predict_options;

  const runPredict = () => {
    const body: RegressionPredictRequest = {
      ...regBody,
      admin_level: adminLevel as RegressionPredictRequest["admin_level"],
    };
    for (const c of opts?.continuous ?? []) {
      const raw = inputs[c.name];
      if (raw === "" || raw == null) return;
      body[c.name as keyof RegressionPredictRequest] = Number(raw) as never;
    }
    if (vars.zone_type_dummy && inputs.zone_type) body.zone_type = inputs.zone_type;
    if (vars.building_use_dummy && inputs.building_use) body.building_use = inputs.building_use;
    if (vars.road_width_dummy && inputs.road_width_label) body.road_width_label = inputs.road_width_label;
    if (vars.asset_type_dummy && inputs.predict_asset_type) body.predict_asset_type = inputs.predict_asset_type;
    if (
      vars.region_leaf_dummy &&
      (adminLevel === "eupmyeondong" || adminLevel === "beopjungri") &&
      inputs.region_leaf
    ) {
      body.region_leaf = inputs.region_leaf;
    }
    predictM.mutate(body);
  };

  return (
    <div
      className={clsx(
        embedded
          ? "rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50/60 dark:bg-slate-900/40 p-3 space-y-2"
          : "card space-y-3",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          {!embedded && (
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">예측</p>
          )}
          <h2 className={clsx("font-semibold", embedded ? "text-xs" : "text-sm")}>
            {embedded ? "예측값" : "다른 변수 고정 · 예측값"}
          </h2>
          {modelHint && <p className="text-[11px] text-slate-500 mt-0.5">{modelHint}</p>}
          {embedded && (fitN != null || scopeNTx != null) && (
            <p className="text-[10px] text-slate-400 mt-0.5 tabular-nums">
              {scopeNTx != null && <>거래 {scopeNTx}</>}
              {fitN != null && (
                <>
                  {scopeNTx != null ? " · " : ""}
                  적합 {fitN}
                </>
              )}
              <span className="text-slate-300"> — 채택 예정 식 기준</span>
            </p>
          )}
          {!embedded && (
            <p className="text-xs text-slate-500 mt-1">
              탐색(통제 전) → 분석(통제 후) → <strong className="text-slate-600">예측</strong> 순으로
              해석하세요. OLS 기준 95% 예측구간(PI) — n이 작으면 구간이 넓습니다.
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5 shrink-0">
          <AnalysisHelpPanel explain={predictM.data?.explain ?? BUILT_PREDICTION_HELP} />
          {aiPredictionContext && <AiAssistantPanel context={aiPredictionContext} />}
          <button
            type="button"
            className={clsx("btn btn-primary shrink-0", embedded && "text-xs py-1")}
            onClick={runPredict}
            disabled={predictM.isPending}
          >
            {predictM.isPending ? "계산 중…" : "예측"}
          </button>
        </div>
      </div>

      <div className="flex flex-nowrap items-end gap-2 text-xs overflow-x-auto pb-0.5">
        <label className="space-y-1 shrink-0">
          <span className="text-slate-500 block whitespace-nowrap">scope</span>
          <select
            className="input !w-[11rem] py-1 text-xs"
            value={adminLevel}
            onChange={(e) => setAdminLevel(e.target.value)}
          >
            {levels.map((l) => (
              <option key={l.admin_level} value={l.admin_level}>
                {ADMIN_LABELS[l.admin_level] ?? l.admin_level} (n={l.n})
              </option>
            ))}
          </select>
        </label>

        {(opts?.continuous ?? []).map((c) => {
          const assess = assessmentForName(predictM.data?.continuous_assessments, c.name);
          const level = assess?.level ?? 0;
          return (
          <label key={c.name} className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">
              {formatCoefName(c.name, assetType, regBody.response_scale)}
            </span>
            <input
              className={clsx(
                "input !w-[8.5rem] py-1 text-xs",
                predictM.data && inputBorderClass(level),
              )}
              type="number"
              value={inputs[c.name] ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, [c.name]: e.target.value }))}
            />
          </label>
          );
        })}

        {vars.zone_type_dummy && (opts?.zone_types?.length ?? 0) > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">용도지역</span>
            <select
              className="input !w-[11rem] py-1 text-xs"
              value={inputs.zone_type ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, zone_type: e.target.value }))}
            >
              {opts!.zone_types.map((z) => (
                <option key={z} value={z}>
                  {z}
                  {z === opts!.zone_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.building_use_dummy && (opts?.building_uses?.length ?? 0) > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">
              {isOnlyDetached(assetType) ? "주택유형" : "건축물용도"}
            </span>
            <select
              className="input !w-[11rem] py-1 text-xs"
              value={inputs.building_use ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, building_use: e.target.value }))}
            >
              {opts!.building_uses.map((u) => (
                <option key={u} value={u}>
                  {u}
                  {u === opts!.building_use_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.road_width_dummy && (opts?.road_width_labels?.length ?? 0) > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">도로조건</span>
            <select
              className="input !w-[11rem] py-1 text-xs"
              value={inputs.road_width_label ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, road_width_label: e.target.value }))}
            >
              {opts!.road_width_labels.map((u) => (
                <option key={u} value={u}>
                  {u}
                  {u === opts!.road_width_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.asset_type_dummy && (opts?.asset_types?.length ?? 0) > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">유형</span>
            <select
              className="input !w-[11rem] py-1 text-xs"
              value={inputs.predict_asset_type ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, predict_asset_type: e.target.value }))}
            >
              {opts!.asset_types.map((u) => (
                <option key={u} value={u}>
                  {ASSET_TYPE_LABELS[u] ?? u}
                  {u === opts!.asset_type_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.region_leaf_dummy &&
          (adminLevel === "eupmyeondong" || adminLevel === "beopjungri") &&
          (opts?.region_leaves?.length ?? 0) > 0 && (
            <label className="space-y-1 shrink-0">
              <span className="text-slate-500 block whitespace-nowrap">
                {adminLevel === "beopjungri" ? "법정리" : "지역"}
              </span>
              <select
                className="input !w-[11rem] py-1 text-xs"
                value={inputs.region_leaf ?? ""}
                onChange={(e) => setInputs((prev) => ({ ...prev, region_leaf: e.target.value }))}
              >
                {(opts?.region_leaves ?? []).map((u) => (
                  <option key={u} value={u}>
                    {u}
                    {u === opts?.region_reference ? " (기준)" : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
      </div>

      {selected?.scope_label && (
        <p className="text-xs text-slate-500">모형: {selected.scope_label}</p>
      )}

      {predictM.isError && (
        <p className="text-sm text-red-600">{(predictM.error as Error).message ?? "예측 실패"}</p>
      )}

      {predictM.data && (() => {
        const level = predictM.data.extrapolation_level ?? 0;
        const badge = extrapolationBadge(level);
        const hidden = predictM.data.y_hat_suppressed || shouldHidePrediction(level, predictM.data.response_scale);
        const extrapGuidance = buildExtrapolationGuidance(
          predictM.data.continuous_assessments,
          level,
        );
        const otherWarnings = predictM.data.warnings.filter(
          (w) => !isTechnicalExtrapolationWarning(w),
        );
        return (
        <div
          className={clsx(
            "rounded-lg border p-3 space-y-2",
            embedded
              ? "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-600 text-xs"
              : "bg-slate-50 border-slate-200 text-sm",
            level >= 3 && "border-red-300 dark:border-red-700",
            level === 2 && "border-amber-300 dark:border-amber-700",
          )}
        >
          {badge && (
            <span className={clsx("inline-block text-[10px] font-semibold px-2 py-0.5 rounded", badge.className)}>
              {badge.label}
            </span>
          )}
          <div>
            <span className="text-slate-500 text-xs">예상 금액</span>
            {hidden ? (
              <div className={clsx("font-medium text-slate-600 dark:text-slate-300", embedded ? "text-sm" : "text-base")}>
                semi-log 극단 외삽 — 숫자 표시 생략
                <p className="text-[11px] font-normal text-slate-500 mt-1 leading-snug">
                  log(금액) 모형은 학습 범위를 크게 벗어나면 exp(ŷ)가 비현실적으로 커질 수 있습니다.
                  선형·log-log 모형을 시도하거나 입력을 학습 범위 근처로 조정하세요.
                </p>
              </div>
            ) : (
              <div className={clsx("font-bold", embedded ? "text-lg" : "text-xl")}>
                {fmtNum(Math.round(predictM.data.y_hat))}만원
              </div>
            )}
          </div>
          {!hidden && (
            <div className="text-xs space-y-1">
              <div>
                <span className="font-medium">95% 예측구간 (개별 거래)</span>{" "}
                {fmtNum(Math.round(predictM.data.pi_lower))} ~ {fmtNum(Math.round(predictM.data.pi_upper))}
                만원
              </div>
              <div className="text-slate-500">
                95% 평균 신뢰구간 {fmtNum(Math.round(predictM.data.ci_lower))} ~{" "}
                {fmtNum(Math.round(predictM.data.ci_upper))}만원
              </div>
            </div>
          )}
          {extrapGuidance.length > 0 && (
            <div className="space-y-1.5">
              {extrapGuidance.map((line) => (
                <p
                  key={line}
                  className={clsx(
                    "text-xs leading-relaxed",
                    level >= 3 ? "text-red-700 dark:text-red-300" : "text-amber-800 dark:text-amber-300",
                  )}
                >
                  {line}
                </p>
              ))}
            </div>
          )}
          {otherWarnings.map((w: string) => (
            <p key={w} className="text-xs badge-warn">
              {w}
            </p>
          ))}
        </div>
        );
      })()}
    </div>
  );
}
