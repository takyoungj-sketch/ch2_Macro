import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runBuildingRegression } from "../api/client";
import type { AssetType, CollectiveRegressionResponse } from "../types";

export type FloorMode = "linear" | "dummy" | "grouped" | "relative";

export function RegressionTable({ data }: { data: CollectiveRegressionResponse }) {
  return (
    <div className="text-xs space-y-2">
      {data.warnings.map((w) => (
        <p key={w} className="text-amber-700">
          {w}
        </p>
      ))}
      <p>
        n={data.n}, R²={data.r_squared?.toFixed(3) ?? "—"}, adj R²={data.adj_r_squared?.toFixed(3) ?? "—"}
      </p>
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-slate-50 text-slate-600">
            <th className="border border-slate-200 px-2 py-1 text-left">변수</th>
            <th className="border border-slate-200 px-2 py-1 text-right">계수</th>
            <th className="border border-slate-200 px-2 py-1 text-right">SE</th>
            <th className="border border-slate-200 px-2 py-1 text-right">t</th>
            <th className="border border-slate-200 px-2 py-1 text-right">p</th>
          </tr>
        </thead>
        <tbody>
          {data.coefficients.map((c) => (
            <tr key={c.name}>
              <td className="border border-slate-200 px-2 py-1">{c.label}</td>
              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{c.coef.toFixed(2)}</td>
              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{c.se?.toFixed(2) ?? "—"}</td>
              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{c.t?.toFixed(2) ?? "—"}</td>
              <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">{c.p?.toFixed(3) ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BuildingRegressionPanel({
  buildingKey,
  assetType,
  yearFrom,
  yearTo,
  experiment = false,
  gateTip,
  regressionEligible = true,
}: {
  buildingKey: string;
  assetType: AssetType;
  yearFrom?: number;
  yearTo?: number;
  experiment?: boolean;
  gateTip?: string;
  regressionEligible?: boolean;
}) {
  const [excludeOutliers, setExcludeOutliers] = useState(false);
  const [floorMode, setFloorMode] = useState<FloorMode>("relative");
  const [vars, setVars] = useState({
    exclusive_area: true,
    building_age: assetType !== "presale",
    floor: true,
    dong: assetType === "apartment" || assetType === "rowhouse",
    housing_subtype: assetType === "presale",
  });

  const regM = useMutation({
    mutationFn: () =>
      runBuildingRegression(buildingKey, {
        asset_type: assetType,
        contract_year_from: yearFrom,
        contract_year_to: yearTo,
        exclude_outliers_iqr: excludeOutliers,
        experiment,
        variables: { ...vars, floor_mode: floorMode },
      }),
  });

  return (
    <div className="space-y-3">
      {!regressionEligible && (
        <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
          {gateTip ?? "권장 표본 기준 미달"} — 실험 단계에서는 아래 옵션으로 실행할 수 있습니다.
        </p>
      )}

      <p className="text-[10px] text-slate-500">
        {assetType === "presale"
          ? "금액 ~ 전용면적·층·권리 (OLS). 층 변수 형식은 실험용으로 선택하세요."
          : "금액 ~ 전용면적·연식·층·동 (OLS). 층 변수 형식은 실험용으로 선택하세요."}
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        {(
          [
            ["exclusive_area", "전용면적"],
            ...(assetType !== "presale" ? ([["building_age", "연식"]] as const) : []),
            ["floor", "층"],
            ...(assetType === "apartment" || assetType === "rowhouse"
              ? ([["dong", "동"]] as const)
              : []),
            ...(assetType === "presale" ? ([["housing_subtype", "권리"]] as const) : []),
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={vars[key as keyof typeof vars]}
              onChange={(e) => setVars((v) => ({ ...v, [key]: e.target.checked }))}
            />
            {label}
          </label>
        ))}
      </div>

      {vars.floor && (
        <div className="text-xs space-y-1">
          <span className="text-slate-600 font-medium">층 변수 형식</span>
          <select
            className="border border-slate-200 rounded px-2 py-1 bg-white w-full max-w-md"
            value={floorMode}
            onChange={(e) => setFloorMode(e.target.value as FloorMode)}
          >
            <option value="relative">상대 층 (1·최상·저·중·고 / max층)</option>
            <option value="dummy">층별 더미 (개별 층)</option>
            <option value="grouped">절대 구간 (1–5 / 6–15 / 16+)</option>
            <option value="linear">층 선형</option>
          </select>
        </div>
      )}

      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={excludeOutliers} onChange={(e) => setExcludeOutliers(e.target.checked)} />
        IQR 이상치 제외
      </label>

      <button type="button" className="btn btn-primary text-xs" disabled={regM.isPending} onClick={() => regM.mutate()}>
        {regM.isPending ? "실행 중…" : "회귀 실행"}
      </button>

      {regM.isError && (
        <p className="text-xs text-red-600">
          {(regM.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            "회귀 실패"}
        </p>
      )}
      {regM.data && <RegressionTable data={regM.data} />}
    </div>
  );
}
