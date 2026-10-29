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
import { AnalysisHelpPanel } from "@ch2/analysis-help";
import {
  ESTIMATE_COPY,
  StatisticalEstimateCaption,
  StatisticalEstimateDisclaimer,
  StatisticalEstimateRangeRow,
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
    out[c.name] = "";
  }
  if (opts?.road_conditions?.length) {
    out.road_condition = opts.road_reference ?? opts.road_conditions[0];
  }
  if (opts?.deal_types?.length) {
    out.deal_type = opts.deal_reference ?? opts.deal_types[0];
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
  const [inputs, setInputs] = useState<Record<string, string>>(() => defaultPredictInputs(opts));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LandRegressionPredictResponse | null>(null);
  const [resultSignature, setResultSignature] = useState<string | null>(null);
  const modelSignature = contentSignature({ regBody, model: regResult.analysis?.model_signature ?? regResult.coefficients });
  const requestSignature = contentSignature({ modelSignature, inputs });
  const currentData = !disabled && resultSignature === requestSignature ? data : null;
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
      deal_type: opts?.deal_types ?? [],
      beopjungri_name: opts?.beopjungri_names ?? [],
    }));
    setData(null);
    setResultSignature(null);
    setError(null);
  }, [modelSignature]);

  const aiContext = useMemo(() => {
    if (!currentData) return null;
    return buildLandPredictionContext(currentData, {
      regionLabel,
      regressionN: regResult.n,
      adjR2: regResult.adj_r_squared,
    });
  }, [currentData, regionLabel, regResult.n, regResult.adj_r_squared]);

  if (!opts) return null;

  const runPredict = async () => {
    if (disabled) return;
    const ticket = requestGate.current.start();
    const signature = requestSignature;
    setData(null);
    setResultSignature(null);
    setLoading(true);
    setError(null);
    try {
      const body: LandRegressionPredictRequest = { ...regBody, expected_model_signature: regResult.analysis?.model_signature };
      for (const c of opts.continuous) {
        const raw = inputs[c.name];
        if (raw === "" || raw == null) {
          setError(`${c.label}을(를) 입력해 주세요.`);
          setLoading(false);
          return;
        }
        const num = Number(raw);
        if (c.name === "contract_year") {
          body.contract_year = Math.round(num);
        } else if (c.name === "area_sqm") {
          body.area_sqm = num;
        }
      }
      if (vars.road_condition && opts.road_conditions.length) {
        body.road_condition = inputs.road_condition || opts.road_reference || undefined;
      }
      if (vars.deal_type && opts.deal_types.length) {
        body.deal_type = inputs.deal_type || opts.deal_reference || undefined;
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
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 inline-flex items-center gap-1">
            조건별 추정 · 토지 단가
            <AnalysisHelpPanel explain={LAND_PREDICT_HELP} />
            <StatsGlossaryHelp termId="prediction_interval" size="xs" />
          </p>
          <h3 className="font-semibold text-sm text-slate-800">다른 변수 고정 · 통계적 추정</h3>
          <p className="text-xs text-slate-500 mt-1">
            입력한 조건에서 모형이 추정한 단가입니다. 개별 필지의 적정가격을 뜻하지는 않습니다.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 shrink-0">
          <PublishAiContext context={aiContext} />
          <button
            type="button"
            disabled={loading || disabled}
            onClick={() => void runPredict()}
            className="px-4 py-1.5 rounded bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "계산 중…" : "추정값 계산"}
          </button>
        </div>
      </div>

      <div className="flex flex-nowrap items-end gap-2 text-xs overflow-x-auto pb-0.5">
        {opts.continuous.map((c) => (
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

        {vars.deal_type && opts.deal_types.length > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">거래유형</span>
            <select
              className="w-[11rem] rounded border border-slate-300 px-2 py-1 text-xs"
              value={inputs.deal_type ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, deal_type: e.target.value }))}
            >
              {opts.deal_types.map((z) => (
                <option key={z} value={z}>
                  {z}
                  {z === opts.deal_reference ? " (기준)" : ""}
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
        <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 space-y-2 text-sm">
          <div>
            <span className="text-slate-500 text-xs">{ESTIMATE_COPY.valueLabel}</span>
            <div className="text-xl font-bold tabular-nums">{fmtNum(currentData.y_hat, 2)} 만원/㎡</div>
            <StatisticalEstimateCaption />
          </div>
          <div className="text-xs space-y-1.5">
            <StatisticalEstimateRangeRow kind="mean">
              <span className="tabular-nums">
                {fmtNum(currentData.ci_lower, 2)} ~ {fmtNum(currentData.ci_upper, 2)} 만원/㎡
              </span>
            </StatisticalEstimateRangeRow>
            <StatisticalEstimateRangeRow kind="individual">
              <span className="tabular-nums">
                {fmtNum(currentData.pi_lower, 2)} ~ {fmtNum(currentData.pi_upper, 2)} 만원/㎡
              </span>
            </StatisticalEstimateRangeRow>
          </div>
          {currentData.warnings.map((w) => (
            <p key={w} className="text-xs text-amber-700 bg-amber-50 dark:text-amber-300 dark:bg-amber-950/40 rounded px-2 py-1">
              {w}
            </p>
          ))}
          <StatisticalEstimateDisclaimer />
        </div>
      )}
    </div>
  );
}
