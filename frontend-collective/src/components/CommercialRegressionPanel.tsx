import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runCommercialRegression } from "../api/commercialClient";
import type { CommercialRegressionResponse } from "../types";
import type { CommercialModalScope } from "./CommercialClusterDetailModal";
import { RegressionTable, type FloorMode } from "./BuildingRegressionPanel";
import AnalysisHelpPanel from "./AnalysisHelpPanel";

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

function toRegressionTableData(data: CommercialRegressionResponse) {
  return {
    building_key: data.cluster_key,
    display_name: data.display_label,
    n: data.n,
    r_squared: data.r_squared,
    adj_r_squared: data.adj_r_squared,
    coefficients: data.coefficients,
    warnings: data.warnings,
  };
}

export default function CommercialRegressionPanel({
  clusterKey,
  scope,
  isShop,
  count,
}: {
  clusterKey: string;
  scope: CommercialModalScope;
  isShop: boolean;
  count: number;
}) {
  const [excludeOutliers, setExcludeOutliers] = useState(false);
  const [floorMode, setFloorMode] = useState<FloorMode>("relative");
  const [vars, setVars] = useState({
    gross_area: true,
    land_area: !isShop,
    building_age: true,
    floor: isShop,
    zone_type: true,
    building_use: true,
    road_width: isShop,
    road_code: !isShop,
    addr4: false,
  });

  const regressionEligible = count >= 30;
  const gateTip =
    `회귀 분석: 선택 구간 거래 ${count}건 (최소 30건 필요)` +
    (count >= 15 ? "" : " · 최근 3년 15건 이상도 권장");

  const regM = useMutation({
    mutationFn: () =>
      runCommercialRegression(clusterKey, {
        ...regionParams(scope),
        contract_year_from: scope.yearFrom === "" ? undefined : scope.yearFrom,
        contract_year_to: scope.yearTo === "" ? undefined : scope.yearTo,
        exclude_outliers_iqr: excludeOutliers,
        experiment: !regressionEligible,
        variables: { ...vars, floor_mode: floorMode },
      }),
  });

  const varOptions = (
    [
      ["gross_area", "연면적"],
      ["land_area", "대지면적"],
      ["building_age", "연식"],
      ["floor", "층"],
      ["zone_type", "용도지역"],
      ["building_use", "건축물용도"],
      ...(isShop ? ([["road_width", "도로폭"]] as const) : ([["road_code", "도로폭(m)"]] as const)),
      ["addr4", "동(addr4)"],
    ] as const
  );

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium text-slate-700">회귀 분석 (탐색용)</p>
        {regM.data?.explain && <AnalysisHelpPanel explain={regM.data.explain} />}
      </div>

      {!regressionEligible && (
        <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
          {gateTip} — 표본이 적어도 참고용으로 실행할 수 있습니다.
        </p>
      )}

      <p className="text-[10px] text-slate-500">
        금액(만원) ~ 연면적·{isShop ? "연식·층·용도 등" : "대지면적·연식·용도 등"} (OLS).{" "}
        도로(cluster) 내 거래만 사용합니다.
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        {varOptions.map(([key, label]) => (
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
          {(regM.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "회귀 실패"}
        </p>
      )}
      {regM.data && <RegressionTable data={toRegressionTableData(regM.data)} />}
    </div>
  );
}
