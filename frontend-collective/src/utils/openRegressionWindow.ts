import type { AssetType } from "../types";

export function openBuildingRegressionWindow(params: {
  buildingKey: string;
  displayName: string;
  assetType: AssetType;
  yearFrom?: number;
  yearTo?: number;
}) {
  const base = import.meta.env.BASE_URL.replace(/\/?$/, "/");
  const u = new URL(`${window.location.origin}${base}residential/`);
  u.searchParams.set("view", "regression");
  u.searchParams.set("building_key", params.buildingKey);
  u.searchParams.set("display_name", params.displayName);
  u.searchParams.set("asset_type", params.assetType);
  if (params.yearFrom != null) u.searchParams.set("year_from", String(params.yearFrom));
  if (params.yearTo != null) u.searchParams.set("year_to", String(params.yearTo));
  window.open(u.toString(), "_blank", "noopener,noreferrer,width=980,height=780");
}
