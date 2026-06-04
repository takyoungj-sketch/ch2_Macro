import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchBuildingFloorIndex } from "../api/client";
import type { AssetType } from "../types";

function fmt(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

type Dimension = "floor" | "dong" | "area";

const DIMENSION_OPTIONS: { id: Dimension; label: string; show?: (assetType: AssetType) => boolean }[] = [
  { id: "floor", label: "층별" },
  { id: "dong", label: "동별", show: (t) => t === "apartment" || t === "rowhouse" },
  { id: "area", label: "면적형별" },
];

function dimensionColumnLabel(dim: string) {
  if (dim === "dong") return "동";
  if (dim === "area") return "면적형";
  return "층";
}

function dimensionHelpText(dim: string) {
  if (dim === "dong") return "동별 평균 ㎡당가를 단지 중앙값 대비 지수(%)로 표시합니다.";
  if (dim === "area") {
    return "면적형별 평균 ㎡당가를 단지 중앙값 대비 지수(%)로 표시합니다. 면적형은 전용면적을 30㎡ 구간으로 묶은 값입니다.";
  }
  return "층별 평균 ㎡당가를 단지 중앙값 대비 지수(%)로 표시합니다.";
}

export default function FloorIndexPanel({
  buildingKey,
  assetType,
  yearFrom,
  yearTo,
  experiment = false,
  floorIndexEligible = true,
  gateTip,
}: {
  buildingKey: string;
  assetType: AssetType;
  yearFrom?: number;
  yearTo?: number;
  experiment?: boolean;
  floorIndexEligible?: boolean;
  gateTip?: string;
}) {
  const [dimension, setDimension] = useState<Dimension>("floor");
  const toggles = DIMENSION_OPTIONS.filter((o) => !o.show || o.show(assetType));

  const q = useQuery({
    queryKey: ["b-floor-index", buildingKey, dimension, yearFrom, yearTo, experiment],
    queryFn: () =>
      fetchBuildingFloorIndex(buildingKey, {
        dimension,
        contract_year_from: yearFrom,
        contract_year_to: yearTo,
        experiment,
      }),
  });

  if (!floorIndexEligible && !experiment) {
    return (
      <p className="text-xs text-amber-700 text-center py-6">{gateTip ?? "효용지수 분석 최소 표본 미달"}</p>
    );
  }

  if (q.isLoading) return <p className="text-xs text-slate-400 text-center py-6">효용지수 계산 중…</p>;
  if (q.isError) {
    const msg =
      (q.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      "효용지수를 불러오지 못했습니다.";
    return <p className="text-xs text-amber-700 text-center py-6">{String(msg)}</p>;
  }
  if (!q.data) return null;

  const { cells, baseline_median, n_total, dimension: dim } = q.data;

  return (
    <div className="space-y-3">
      {!floorIndexEligible && (
        <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
          {gateTip ?? "권장 표본 기준 미달"} — 실험 모드로 조회 중입니다.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="text-slate-500">기준</span>
        <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5">
          {toggles.map(({ id, label }) => (
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
        <span className="text-slate-500">
          단지 중앙값 <strong className="text-slate-700">{fmt(baseline_median)}</strong> 만원/㎡ = 100 · n=
          {n_total.toLocaleString("ko-KR")}
        </span>
      </div>

      <p className="text-[10px] text-slate-500">
        {dimensionHelpText(dim)} 셀 n&lt;15는 참고용입니다.
      </p>

      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <table className="w-full text-[11px] border-collapse min-w-[360px]">
          <thead>
            <tr className="bg-slate-50 text-slate-600">
              <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">
                {dimensionColumnLabel(dim)}
              </th>
              <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">건수</th>
              <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">평균(만원/㎡)</th>
              <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-indigo-700">지수</th>
            </tr>
          </thead>
          <tbody className="text-slate-800">
            {cells.map((c) => (
              <tr key={c.label} className={clsx(!c.is_reliable && "bg-amber-50/40")}>
                <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                  {c.label}
                  {!c.is_reliable && <span className="ml-1 text-[9px] text-amber-600">n&lt;15</span>}
                </td>
                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{c.count}</td>
                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{fmt(c.mean_unit_price)}</td>
                <td className="border border-slate-200 px-2 py-1 text-right tabular-nums font-semibold text-indigo-600">
                  {c.index != null ? `${c.index}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
