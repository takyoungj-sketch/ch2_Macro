import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchCommercialFloorIndex } from "../api/commercialClient";
import type { CommercialModalScope } from "./CommercialClusterDetailModal";
import AnalysisHelpPanel from "./AnalysisHelpPanel";

function fmt(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtP(v: number | null | undefined) {
  if (v == null) return "—";
  if (v < 0.001) return "<0.001";
  return v.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

type Dimension = "floor" | "area";

const CONTROL_LABELS: Record<string, string> = {
  ln_gross_area: "ln(연면적)",
  building_age: "연식",
  building_use: "건축물용도",
};

function regionParams(scope: CommercialModalScope) {
  return scope.hasIntermediate
    ? {
        addr1: scope.addr1,
        addr2: scope.addr2,
        addr3_list: scope.guList.length ? scope.guList : undefined,
        addr4_list: scope.leafList.length ? scope.leafList : undefined,
      }
    : {
        addr1: scope.addr1,
        addr2: scope.addr2,
        addr3_list: scope.leafList.length ? scope.leafList : undefined,
      };
}

function dimensionHelpText(dim: string, isRegression: boolean, isFactory: boolean) {
  if (dim === "area") {
    if (isFactory) {
      return "연면적을 100/300/1000㎡ 구간으로 묶어, 도로(cluster) 중앙값 대비 지수(%)를 표시합니다.";
    }
    return "연면적을 30㎡ 구간으로 묶어, 도로(cluster) 중앙값 대비 지수(%)를 표시합니다.";
  }
  if (isRegression) {
    return "반로그 OLS로 ln(㎡당단가)를 추정합니다. 1층=100% 기준, 연면적·연식·건축물용도를 통제한 뒤 exp(γ)로 지수를 산출합니다.";
  }
  if (isFactory) {
    return "층별 평균 ㎡당가를 cluster 중앙값 대비 지수(%)로 표시합니다. 층 정보 sparse — 참고용, 면적대 탭을 우선하세요.";
  }
  return "층별 평균 ㎡당가를 도로(cluster) 중앙값 대비 지수(%)로 표시합니다.";
}

export default function CommercialFloorIndexPanel({
  clusterKey,
  scope,
  count,
  isFactory = false,
}: {
  clusterKey: string;
  scope: CommercialModalScope;
  count: number;
  isFactory?: boolean;
}) {
  const [dimension, setDimension] = useState<Dimension>(isFactory ? "area" : "floor");
  const floorIndexEligible = count >= 50;
  const experiment = !floorIndexEligible;
  const gateTip = `${isFactory ? "면적대·층" : "층·면적"} 효용지수: 선택 구간 거래 ${count}건 (최소 50건 권장)`;

  const dimensionOptions: { id: Dimension; label: string }[] = isFactory
    ? [
        { id: "area", label: "면적대별" },
        { id: "floor", label: "층별(참고)" },
      ]
    : [
        { id: "floor", label: "층별" },
        { id: "area", label: "면적형별" },
      ];

  const q = useQuery({
    queryKey: ["comm-floor-index", clusterKey, scope, dimension, experiment, isFactory],
    queryFn: () =>
      fetchCommercialFloorIndex(clusterKey, {
        ...regionParams(scope),
        contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
        contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
        dimension,
        experiment,
      }),
  });

  if (q.isLoading) return <p className="text-xs text-slate-400 text-center py-6">효용지수 계산 중…</p>;
  if (q.isError) {
    const msg =
      (q.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      "효용지수를 불러오지 못했습니다.";
    return <p className="text-xs text-amber-700 text-center py-6">{String(msg)}</p>;
  }
  if (!q.data) return null;

  const {
    cells,
    baseline_median,
    n_total,
    n_regression,
    dimension: dim,
    method,
    reference_floor,
    controls,
    r_squared,
    warnings,
    explain,
  } = q.data;

  const isRegression = method === "regression_semilog" && dim === "floor";
  const baselineLabel = isFactory ? "cluster 중앙값" : "도로 중앙값";

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium text-slate-700">
          {isFactory ? "면적대·층 효용지수" : "층·면적 효용지수"}
        </p>
        <AnalysisHelpPanel explain={explain} />
      </div>

      {!floorIndexEligible && (
        <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
          {gateTip} — 참고용으로 조회 중입니다.
        </p>
      )}

      {warnings && warnings.length > 0 && (
        <ul className="text-[10px] text-amber-800 bg-amber-50 border border-amber-100 rounded px-2 py-1.5 space-y-0.5 list-disc list-inside">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="text-slate-500">기준</span>
        <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5">
          {dimensionOptions.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={clsx(
                "px-2 py-0.5 rounded text-[11px] font-medium",
                dimension === id ? "bg-white shadow-sm text-slate-800" : "text-slate-500",
              )}
              onClick={() => setDimension(id)}
            >
              {label}
            </button>
          ))}
        </div>
        {isRegression ? (
          <span className="text-slate-500">
            {reference_floor ?? "1층"} = <strong className="text-slate-700">100</strong>
            {r_squared != null && (
              <>
                {" "}
                · R² <strong className="text-slate-700">{fmt(r_squared)}</strong>
              </>
            )}
            {n_regression != null && <> · 회귀 n={n_regression.toLocaleString("ko-KR")}</>}
            {" · "}전체 n={n_total.toLocaleString("ko-KR")}
          </span>
        ) : (
          <span className="text-slate-500">
            {baselineLabel} <strong className="text-slate-700">{fmt(baseline_median)}</strong> 만원/㎡ = 100 · n=
            {n_total.toLocaleString("ko-KR")}
          </span>
        )}
      </div>

      {isRegression && controls && controls.length > 0 && (
        <p className="text-[10px] text-slate-500">
          통제변수: {controls.map((c) => CONTROL_LABELS[c] ?? c).join(", ")}
        </p>
      )}

      <p className="text-[10px] text-slate-500">
        {dimensionHelpText(dim, isRegression, isFactory)} 셀 n&lt;15는 참고용입니다.
      </p>

      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <table className="w-full text-[11px] border-collapse min-w-[480px]">
          <thead>
            <tr className="bg-slate-50 text-slate-600">
              <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">
                {dim === "area" ? (isFactory ? "면적대" : "면적형") : "층 구간"}
              </th>
              <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">건수</th>
              <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">평균(만원/㎡)</th>
              <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-indigo-700">지수</th>
              {isRegression && (
                <>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">95% CI</th>
                  <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">p</th>
                </>
              )}
            </tr>
          </thead>
          <tbody className="text-slate-800">
            {cells.length === 0 && (
              <tr>
                <td
                  colSpan={isRegression ? 6 : 4}
                  className="border border-slate-200 px-2 py-4 text-center text-slate-400"
                >
                  표시할 데이터가 없습니다.
                </td>
              </tr>
            )}
            {cells.map((c) => (
              <tr key={c.label} className={clsx(!c.is_reliable && "bg-amber-50/40")}>
                <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                  {c.label}
                  {c.is_reference && (
                    <span className="ml-1 text-[9px] text-indigo-600 font-medium">기준</span>
                  )}
                  {!c.is_reliable && <span className="ml-1 text-[9px] text-amber-600">n&lt;15</span>}
                </td>
                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{c.count}</td>
                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{fmt(c.mean_unit_price)}</td>
                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums font-semibold text-indigo-600">
                  {c.index != null ? `${c.index}%` : "—"}
                </td>
                {isRegression && (
                  <>
                    <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-slate-600">
                      {c.index_lo != null && c.index_hi != null ? `${c.index_lo}–${c.index_hi}%` : "—"}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-slate-600">
                      {fmtP(c.p_value)}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
