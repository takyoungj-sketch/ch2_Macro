import { useEffect, useMemo, useRef, useState } from "react";
import { createRequestGate } from "../../../shared/regression-ui/requestGate";
import { contentSignature } from "../../../shared/regression-ui/signature";
import { reconcileListedInputs } from "../../../shared/regression-ui/inputs";
import { fetchLandRegressionPredict } from "../api/client";
import { buildLandPredictionContext } from "../api/aiContext";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import type {
  LandPredictOptions,
  LandRegressionPredictRequest,
  LandRegressionPredictResponse,
  LandRegressionRequest,
  LandRegressionResponse,
  LandRegressionVariables,
} from "../types";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import {
  StatsGlossaryHelp,
} from "@ch2/stats-glossary";
import { LAND_PREDICT_HELP } from "../constants/landStatsExplain";
import { parseApiError } from "../utils/apiError";

function fmtNum(n?: number | null, digits = 2) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function defaultPredictInputs(opts?: LandPredictOptions | null): Record<string, string> {
  const out: Record<string, string> = {};
  for (const c of opts?.continuous ?? []) {
    if (c.name !== "contract_year") out[c.name] = "";
  }
  if (opts?.road_conditions?.length) {
    out.road_condition = opts.road_reference ?? opts.road_conditions[0];
  }
  if (opts?.beopjungri_names?.length) {
    out.beopjungri_name = opts.beopjungri_reference ?? opts.beopjungri_names[0];
  }
  out.partial_ownership = "0";
  return out;
}

export default function LandPredictPanel({
  regResult,
  regBody,
  vars,
  regionLabel,
  disabled = false,
}: {
  regResult: LandRegressionResponse;
  regBody: LandRegressionRequest;
  vars: LandRegressionVariables;
  regionLabel: string;
  disabled?: boolean;
}) {
  const opts = regResult.predict_options;
  const currentYear = new Date().getFullYear();
  const yearOption = opts?.continuous.find(c => c.name === "contract_year");
  const usesYear = Boolean(yearOption);
  const hasDealEffect = Boolean(opts?.deal_types.length);
  const usesBroker = Boolean(opts?.deal_types.includes("중개거래"));
  const brokerUnavailable = hasDealEffect && !usesBroker;
  const yearOutside = usesYear && ((yearOption?.min != null && currentYear < yearOption.min) || (yearOption?.max != null && currentYear > yearOption.max));
  const [inputs, setInputs] = useState<Record<string, string>>(() => defaultPredictInputs(opts));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LandRegressionPredictResponse | null>(null);
  const [resultSignature, setResultSignature] = useState<string | null>(null);
  const modelSignature = contentSignature({ regBody, model: regResult.analysis?.model_signature ?? regResult.coefficients });
  const requestSignature = contentSignature({ modelSignature, inputs, contractYear: usesYear ? currentYear : null, dealType: usesBroker ? "중개거래" : null });
  const currentData = !disabled && resultSignature === requestSignature ? data : null;
  // 결과 요약에 표시된 표본 제외 등 동일 안내는 반복하지 않는다.
  const predictionWarnings = [...new Set(currentData?.warnings ?? [])].filter(w =>
    !regResult.warnings.includes(w) && w !== regResult.missing_treatment_label);

  const requestGate = useRef(createRequestGate());
  useEffect(() => {
    requestGate.current.invalidate();
    setLoading(false);
    setError(null);
    return () => requestGate.current.invalidate();
  }, [requestSignature, disabled]);

  useEffect(() => {
    setInputs(current => reconcileListedInputs(defaultPredictInputs(opts), current, {
      road_condition: opts?.road_conditions ?? [],
      beopjungri_name: opts?.beopjungri_names ?? [],
    }));
    setData(null);
    setResultSignature(null);
    setError(null);
  }, [modelSignature]);

  const aiContext = useMemo(() => {
    if (!currentData) return null;
    const context = buildLandPredictionContext(currentData, {
      regionLabel,
      regressionN: regResult.n,
      adjR2: regResult.adj_r_squared,
    });
    context.facts = { ...context.facts, estimate_contract_year: usesYear ? currentYear : null,
      estimate_deal_type: usesBroker ? "중개거래" : null, time_adjustment_applied: usesYear,
      deal_adjustment_applied: hasDealEffect };
    return context;
  }, [currentData, regionLabel, regResult.n, regResult.adj_r_squared, usesYear, currentYear, usesBroker, hasDealEffect]);

  if (!opts) return null;

  const runPredict = async () => {
    if (disabled || brokerUnavailable) return;
    const ticket = requestGate.current.start();
    const signature = requestSignature;
    setData(null);
    setResultSignature(null);
    setLoading(true);
    setError(null);
    try {
      const body: LandRegressionPredictRequest = { ...regBody, expected_model_signature: regResult.analysis?.model_signature,
        contract_year: usesYear ? currentYear : undefined, deal_type: usesBroker ? "중개거래" : undefined };
      for (const c of opts.continuous.filter(c => c.name !== "contract_year")) {
        const raw = inputs[c.name];
        if (raw === "" || raw == null) {
          setError(`${c.label}을(를) 입력해 주세요.`);
          setLoading(false);
          return;
        }
        const num = Number(raw);
        if (c.name === "area_sqm") {
          body.area_sqm = num;
        }
      }
      if (vars.road_condition && opts.road_conditions.length) {
        body.road_condition = inputs.road_condition || opts.road_reference || undefined;
      }
      if (vars.beopjungri_fe && opts.beopjungri_names.length) {
        body.beopjungri_name =
          inputs.beopjungri_name || opts.beopjungri_reference || undefined;
      }
      if (opts.partial_ownership_enabled) {
        body.partial_ownership = inputs.partial_ownership === "1";
      }
      if (vars.assessed_land_price) {
        const raw = inputs.assessed_land_price;
        const num = Number(raw);
        if (raw === "" || raw == null || !Number.isFinite(num) || num <= 0) {
          setError("개별공시지가(원/㎡)를 입력해 주세요.");
          setLoading(false);
          return;
        }
        body.assessed_land_price = num;
      }
      const res = await fetchLandRegressionPredict(body);
      if (!requestGate.current.isCurrent(ticket)) return;
      setData(res);
      setResultSignature(signature);
    } catch (e) {
      if (!requestGate.current.isCurrent(ticket)) return;
      setError(parseApiError(e).message);
      setData(null);
    } finally {
      if (requestGate.current.isCurrent(ticket)) setLoading(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-3 dark:border-slate-700 dark:bg-slate-800/50">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 inline-flex items-center gap-1">
            조건별 추정 · 토지 단가
            <AnalysisHelpPanel explain={LAND_PREDICT_HELP} />
            <StatsGlossaryHelp termId="prediction_interval" size="xs" />
          </p>
          
          <p className="text-xs text-slate-500 mt-1">
            입력한 조건에서 모형이 추정한 단가입니다. 개별 필지의 적정가격을 뜻하지는 않습니다.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 shrink-0">
          <PublishAiContext context={aiContext} />
          <button
            type="button"
            disabled={loading || disabled || brokerUnavailable}
            onClick={() => void runPredict()}
            className="px-4 py-1.5 rounded bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "계산 중…" : "추정값 계산"}
          </button>
        </div>
      </div>

      <div className="space-y-1 text-xs text-slate-600 dark:text-slate-300" aria-label="추정 기준">
        <p>추정 기준: {usesYear ? `${currentYear}년` : "선택 기간의 거래 수준"} · {usesBroker ? "중개거래" : hasDealEffect ? "중개거래 적용 불가" : "거래유형 구분 미적용"}</p>
        {!usesYear && <p>연도추세가 회귀식에 없어 현재 시점으로 보정하지 않습니다.</p>}
        {!hasDealEffect && <p>거래유형 효과가 회귀식에 없어 선택 표본의 거래유형을 기준으로 추정합니다.</p>}
        {yearOutside && <p className="text-amber-700 dark:text-amber-300">학습 기간 밖으로 연도추세를 연장해 적용합니다. 현재 시세를 직접 확인한 값은 아닙니다.</p>}
        {brokerUnavailable && <p role="alert" className="text-amber-700 dark:text-amber-300">이 모형에는 중개거래 범주가 없어 추정할 수 없습니다. 중개거래가 포함된 자료로 회귀를 다시 실행해 주세요.</p>}
      </div>
      <div className="flex flex-nowrap items-end gap-2 text-xs overflow-x-auto pb-0.5">
        {opts.continuous.filter(c => c.name !== "contract_year").map((c) => (
          <label key={c.name} className="space-y-1 shrink-0">
            <span
              className="text-slate-500 block whitespace-nowrap"
              title={c.min != null && c.max != null ? `${c.min}~${c.max}` : undefined}
            >
              {c.label}
            </span>
            <input
              className="w-[8.5rem] rounded border border-slate-300 px-2 py-1 text-xs"
              type="number"
              title={
                c.min != null && c.max != null
                  ? `${fmtNum(c.min, 0)}~${fmtNum(c.max, 0)}`
                  : undefined
              }
              value={inputs[c.name] ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, [c.name]: e.target.value }))}
            />
          </label>
        ))}

        {vars.road_condition && opts.road_conditions.length > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">도로조건</span>
            <select
              className="w-[11rem] rounded border border-slate-300 px-2 py-1 text-xs"
              value={inputs.road_condition ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, road_condition: e.target.value }))}
            >
              {opts.road_conditions.map((z) => (
                <option key={z} value={z}>
                  {z}
                  {z === opts.road_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.beopjungri_fe && opts.beopjungri_names.length > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">법정동</span>
            <select
              className="w-[11rem] rounded border border-slate-300 px-2 py-1 text-xs"
              value={inputs.beopjungri_name ?? ""}
              onChange={(e) =>
                setInputs((prev) => ({ ...prev, beopjungri_name: e.target.value }))
              }
            >
              {opts.beopjungri_names.map((z) => (
                <option key={z} value={z}>
                  {z}
                  {z === opts.beopjungri_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.assessed_land_price && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">개별공시지가(원/㎡)</span>
            <input
              className="w-[8.5rem] rounded border border-slate-300 px-2 py-1 text-xs"
              type="number"
              min={1}
              value={inputs.assessed_land_price ?? ""}
              onChange={(e) =>
                setInputs((prev) => ({ ...prev, assessed_land_price: e.target.value }))
              }
            />
          </label>
        )}

        {opts.partial_ownership_enabled && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">지분거래</span>
            <select
              className="w-[8rem] rounded border border-slate-300 px-2 py-1 text-xs"
              value={inputs.partial_ownership ?? "0"}
              onChange={(e) =>
                setInputs((prev) => ({ ...prev, partial_ownership: e.target.value }))
              }
            >
              <option value="0">전체(기준)</option>
              <option value="1">지분</option>
            </select>
          </label>
        )}
      </div>

      {error && <p className="text-xs text-red-500 bg-red-50 rounded p-2">{error}</p>}

      {currentData && (
        <div className="space-y-4 rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 dark:border-indigo-500/30 dark:bg-slate-900/60">
          <div>
            <p className="text-sm text-slate-600 dark:text-slate-300">통계적 추정단가</p>
            <p className="mt-2 break-words text-3xl font-bold leading-tight tabular-nums text-indigo-700 dark:text-indigo-200 sm:text-4xl">{fmtNum(currentData.y_hat, 2)} 만원/㎡</p>
          </div>
          <div className="rounded-lg bg-white/70 px-3 py-3 dark:bg-slate-800/70">
            <p className="flex items-center gap-1 text-sm text-slate-600 dark:text-slate-300">95% 평균 추정범위 <StatsGlossaryHelp termId="confidence_interval" size="xs" /></p>
            <p className="mt-1 text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-100">{fmtNum(currentData.ci_lower, 2)} ~ {fmtNum(currentData.ci_upper, 2)} 만원/㎡</p>
          </div>
          {regResult.analysis?.provision?.identification_limited && <p role="status" className="text-xs leading-relaxed text-amber-800 dark:text-amber-200">일부 변수의 효과를 따로 구분하기 어려운 모형입니다. 추정값 해석에 주의해 주세요.</p>}
          <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">이 결과는 AVM에 의한 가격평가가 아닌, 회귀모형의 통계적 참고값입니다.</p>
          <details className="border-t border-slate-200 pt-3 text-xs text-slate-600 dark:border-slate-700 dark:text-slate-300">
            <summary className="cursor-pointer font-medium">예측범위와 상세 안내{predictionWarnings.length > 0 ? ` · 주의사항 ${predictionWarnings.length}개` : ""}</summary>
            <div className="mt-3 space-y-3 leading-relaxed">
              <div>
                <p className="flex items-center gap-1 font-medium">95% 개별 거래 예측범위 <StatsGlossaryHelp termId="prediction_interval" size="xs" /></p>
                <p className="mt-1 tabular-nums">{fmtNum(currentData.pi_lower, 2)} ~ {fmtNum(currentData.pi_upper, 2)} 만원/㎡</p>
                <p className="mt-1">개별 거래의 변동까지 고려한 범위여서 평균 추정범위보다 넓을 수 있습니다.</p>
              </div>
              <p>모형에 포함되지 않은 특성과 거래 조건에 따라 실제 단가는 달라질 수 있습니다. 표시한 범위가 실제 거래단가를 보장하지는 않습니다.</p>
              {predictionWarnings.map(w => <p key={w}>{w}</p>)}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
