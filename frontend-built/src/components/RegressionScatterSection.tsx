import { useMemo, useState } from "react";
import clsx from "clsx";
import type {
  CorrelationSeries,
  PartialRegressionSeries,
  RegressionRunResponse,
} from "../types";
import { buildBuiltScatterContext } from "../api/aiContext";
import AiAssistantPanel from "./AiAssistantPanel";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import {
  BUILT_SCATTER_PARTIAL_HELP,
  BUILT_SCATTER_RAW_HELP,
} from "../utils/builtAnalysisHelp";

const ADMIN_LABELS: Record<string, string> = {
  sigungu: "시군구",
  gu: "구",
  eupmyeondong: "읍·면·동",
  beopjungri: "법정리",
};

type ScatterTab = "raw" | "partial";

function fmtNum(n?: number | null, digits = 0) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtDecimal(n?: number | null, digits = 5) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

function fmtCoefInt(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return Math.round(n).toLocaleString("ko-KR");
}

function fmtP(p?: number | null) {
  if (p == null || Number.isNaN(p)) return "—";
  if (p < 0.001) return "p<0.001";
  return `p=${p.toFixed(3)}`;
}

function ScatterMini({
  points,
  label,
  mode,
  pearsonR,
  beta,
  pValue,
  partialR2,
}: {
  points: { x: number; y: number }[];
  label: string;
  mode: ScatterTab;
  pearsonR?: number | null;
  beta?: number | null;
  pValue?: number | null;
  partialR2?: number | null;
}) {
  if (!points.length) return null;

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = mode === "partial" ? Math.min(0, ...xs) : Math.min(...xs);
  const maxX = mode === "partial" ? Math.max(0, ...xs) : Math.max(...xs);
  const minY = mode === "partial" ? Math.min(0, ...ys) : Math.min(...ys);
  const maxY = mode === "partial" ? Math.max(0, ...ys) : Math.max(...ys);
  const pad = 8;
  const w = 240;
  const h = 130;
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const sx = (x: number) => pad + ((x - minX) / spanX) * (w - pad * 2);
  const sy = (y: number) => h - pad - ((y - minY) / spanY) * (h - pad * 2);

  const showLine = mode === "partial" && beta != null && Number.isFinite(beta);
  const lineX1 = minX;
  const lineX2 = maxX;
  const lineY1 = (beta ?? 0) * lineX1;
  const lineY2 = (beta ?? 0) * lineX2;

  return (
    <div className="card">
      <div className="text-xs font-semibold mb-0.5">
        {label}
        {mode === "raw" ? " vs 금액" : " (통제 후)"}
      </div>
      <div className="text-[10px] text-slate-500 mb-1 min-h-[2rem]">
        {mode === "raw" ? (
          <>
            <span className="font-medium text-slate-600">r={fmtDecimal(pearsonR, 3)}</span>
            <span className="block text-slate-400">실제 거래 분포</span>
          </>
        ) : (
          <>
            <span className="font-medium text-slate-600">
              β={fmtCoefInt(beta)} · {fmtP(pValue)}
            </span>
            {partialR2 != null && (
              <span className="ml-1 text-slate-400">· 부분 R²={fmtDecimal(partialR2, 3)}</span>
            )}
            <span className="block text-slate-400">다른 변수 통제 후 잔차</span>
          </>
        )}
      </div>
      <svg width={w} height={h} className="bg-slate-50 rounded border border-slate-100">
        {mode === "partial" && (
          <>
            <line
              x1={sx(0)}
              y1={pad}
              x2={sx(0)}
              y2={h - pad}
              stroke="#cbd5e1"
              strokeWidth={1}
              strokeDasharray="3 2"
            />
            <line
              x1={pad}
              y1={sy(0)}
              x2={w - pad}
              y2={sy(0)}
              stroke="#cbd5e1"
              strokeWidth={1}
              strokeDasharray="3 2"
            />
          </>
        )}
        {showLine && (
          <line
            x1={sx(lineX1)}
            y1={sy(lineY1)}
            x2={sx(lineX2)}
            y2={sy(lineY2)}
            stroke="#2563eb"
            strokeWidth={1.5}
            opacity={0.85}
          />
        )}
        {points.map((p, i) => (
          <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r={2.2} fill="#64748b" opacity={0.55} />
        ))}
      </svg>
    </div>
  );
}

export default function RegressionScatterSection({
  data,
  regionLabel,
  assetType,
  responseScale = "linear",
}: {
  data: RegressionRunResponse;
  regionLabel: string;
  assetType: string;
  responseScale?: "linear" | "log";
}) {
  const [tab, setTab] = useState<ScatterTab>("raw");
  const hasRaw = data.correlations.length > 0;
  const hasPartial = (data.partial_regressions?.length ?? 0) > 0;

  const aiContext = useMemo(
    () =>
      buildBuiltScatterContext(data, {
        regionLabel,
        assetType,
        responseScale,
        activeTab: tab,
      }),
    [data, regionLabel, assetType, responseScale, tab],
  );

  if (!hasRaw && !hasPartial) return null;

  const tabHelp = tab === "raw" ? BUILT_SCATTER_RAW_HELP : BUILT_SCATTER_PARTIAL_HELP;
  const tabHints = useMemo(() => {
    if (tab !== "partial" || !data.explain?.interpretation_hints?.length) return [];
    return data.explain.interpretation_hints;
  }, [tab, data.explain?.interpretation_hints]);

  const explain = useMemo(
    () =>
      tabHints.length
        ? { ...tabHelp, interpretation_hints: tabHints }
        : tabHelp,
    [tabHelp, tabHints],
  );

  const scopeBits = [
    ADMIN_LABELS[data.correlation_admin_level ?? "sigungu"],
    data.correlation_scope_label,
    data.correlation_n != null ? `n=${fmtNum(data.correlation_n)}` : null,
  ].filter(Boolean);

  const activeSeries =
    tab === "raw" ? data.correlations : (data.partial_regressions ?? []);

  return (
    <div className="space-y-2 rounded-lg border border-slate-200 bg-white/60 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-slate-700">
            {tab === "raw" ? "탐색" : "분석"} — 변수별 산점도
          </p>
          <p className="text-[11px] text-slate-500 mt-0.5">{scopeBits.join(" · ")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 shrink-0">
          {aiContext && <AiAssistantPanel context={aiContext} />}
          <AnalysisHelpPanel explain={explain} />
          <div
            className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5 text-[11px]"
            role="tablist"
            aria-label="산점도 모드"
          >
            <button
              type="button"
              role="tab"
              aria-selected={tab === "raw"}
              disabled={!hasRaw}
              className={clsx(
                "px-2.5 py-1 rounded whitespace-nowrap",
                tab === "raw" ? "bg-white shadow-sm font-medium text-slate-800" : "text-slate-500",
                !hasRaw && "opacity-40 cursor-not-allowed",
              )}
              onClick={() => setTab("raw")}
            >
              상관관계 (통제 전)
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "partial"}
              disabled={!hasPartial}
              className={clsx(
                "px-2.5 py-1 rounded whitespace-nowrap",
                tab === "partial"
                  ? "bg-white shadow-sm font-medium text-slate-800"
                  : "text-slate-500",
                !hasPartial && "opacity-40 cursor-not-allowed",
              )}
              onClick={() => setTab("partial")}
            >
              부분회귀도 (통제 후)
            </button>
          </div>
        </div>
      </div>

      <p className="text-[11px] text-slate-500">
        {tab === "raw" ? (
          <>
            <strong className="text-slate-600">통제 전</strong> — 현실에서 거래가 어떻게 퍼져 있는지
            봅니다 (Pearson r).{" "}
            <span className="text-slate-400">탭을 바꿔 r과 β를 비교해 보세요.</span>
          </>
        ) : (
          <>
            <strong className="text-slate-600">통제 후</strong> — 회귀 모형에 포함된 다른 변수·더미
            영향을 제거한 뒤, 계수 β와 같은 의미의 순수 관계를 봅니다.
          </>
        )}
      </p>

      {activeSeries.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
          {tab === "raw"
            ? (activeSeries as CorrelationSeries[]).map((s) => (
                <ScatterMini
                  key={s.variable}
                  points={s.points}
                  label={s.label}
                  mode="raw"
                  pearsonR={s.pearson_r}
                />
              ))
            : (activeSeries as PartialRegressionSeries[]).map((s) => (
                <ScatterMini
                  key={s.variable}
                  points={s.points}
                  label={s.label}
                  mode="partial"
                  beta={s.beta}
                  pValue={s.p_value}
                  partialR2={s.partial_r_squared}
                />
              ))}
        </div>
      ) : (
        <p className="text-xs text-slate-400 text-center py-4">
          {tab === "partial"
            ? "표본이 부족하거나 연속 변수가 없어 부분회귀도를 만들 수 없습니다."
            : "표시할 산점도가 없습니다."}
        </p>
      )}
    </div>
  );
}
