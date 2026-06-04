import { useMemo } from "react";
import BuildingRegressionPanel from "../components/BuildingRegressionPanel";
import { COLLECTIVE_EXPERIMENT_MODE } from "../api/client";
import type { AssetType } from "../types";
import { ASSET_LABELS } from "../types";

function parseSearchParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    buildingKey: p.get("building_key") ?? "",
    displayName: p.get("display_name") ?? "",
    assetType: (p.get("asset_type") ?? "apartment") as AssetType,
    yearFrom: p.get("year_from") ? Number(p.get("year_from")) : undefined,
    yearTo: p.get("year_to") ? Number(p.get("year_to")) : undefined,
  };
}

export default function BuildingRegressionPage() {
  const params = useMemo(() => parseSearchParams(), []);

  if (!params.buildingKey) {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">
        building_key가 필요합니다.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 p-4 md:p-6">
      <div className="max-w-3xl mx-auto card space-y-4">
        <div>
          <h1 className="text-lg font-bold text-slate-800">{params.displayName || "건물 회귀"}</h1>
          <p className="text-xs text-slate-500 mt-1">{ASSET_LABELS[params.assetType]} · 별도 창 (레거시)</p>
        </div>
        <BuildingRegressionPanel
          buildingKey={params.buildingKey}
          assetType={params.assetType}
          yearFrom={params.yearFrom}
          yearTo={params.yearTo}
          experiment={COLLECTIVE_EXPERIMENT_MODE}
        />
      </div>
    </div>
  );
}
