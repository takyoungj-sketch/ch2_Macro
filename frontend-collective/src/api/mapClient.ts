import axios from "axios";

import type { MapAdminLevel } from "../utils/mapRegionScope";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();

/** /api/map — collective client 와 base 분리 */
const mapApi = axios.create({
  baseURL: "/api",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

const collectiveApi = axios.create({
  baseURL: "/api/collective",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

const commercialApi = axios.create({
  baseURL: "/api/collective/commercial",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type MapConfigResponse = {
  vworld_configured: boolean;
  tile_base: string;
};

export type MapBoundariesResponse = {
  level: MapAdminLevel;
  selected: string[];
  feature_collection: GeoJSON.FeatureCollection;
};

export type CollectiveMapResolveCodesResponse = {
  level: MapAdminLevel | null;
  selected_codes: string[];
  context_sido_code: string | null;
  context_sigungu_code: string | null;
  labels: Record<string, string>;
  has_selection: boolean;
};

export async function fetchMapConfig(): Promise<MapConfigResponse> {
  const { data } = await mapApi.get<MapConfigResponse>("/map/config");
  return data;
}

export async function fetchMapBoundaries(opts: {
  level: MapAdminLevel;
  selected: string[];
  contextSidoCode?: string | null;
  contextSigunguCode?: string | null;
}): Promise<MapBoundariesResponse> {
  const params = new URLSearchParams();
  params.set("level", opts.level);
  for (const code of opts.selected) {
    const c = String(code ?? "").trim();
    if (c) params.append("selected", c);
  }
  if (opts.contextSidoCode) params.set("context_sido_code", opts.contextSidoCode);
  if (opts.contextSigunguCode) params.set("context_sigungu_code", opts.contextSigunguCode);
  const { data } = await mapApi.get<MapBoundariesResponse>("/map/boundaries", { params });
  return data;
}

export async function fetchCollectiveMapResolveCodes(opts: {
  assetType?: string;
  addr1?: string;
  addr2?: string;
  gu?: string[];
  leaf?: string[];
  riPick?: string[];
  /** 집합상가·공장 — /api/collective/commercial/regions/resolve-codes */
  commercial?: boolean;
}): Promise<CollectiveMapResolveCodesResponse> {
  const params = new URLSearchParams();
  if (opts.assetType) params.set("asset_type", opts.assetType);
  if (opts.addr1) params.set("addr1", opts.addr1);
  if (opts.addr2) params.set("addr2", opts.addr2);
  for (const g of opts.gu ?? []) {
    if (g.trim()) params.append("gu", g.trim());
  }
  for (const l of opts.leaf ?? []) {
    if (l.trim()) params.append("leaf", l.trim());
  }
  for (const r of opts.riPick ?? []) {
    if (r.trim()) params.append("ri_pick", r.trim());
  }
  const api = opts.commercial ? commercialApi : collectiveApi;
  const { data } = await api.get<CollectiveMapResolveCodesResponse>(
    `/regions/resolve-codes?${params.toString()}`,
  );
  return data;
}

export function vworldSatelliteTileUrl(apiKey: string): string {
  return `https://api.vworld.kr/req/wmts/1.0.0/${encodeURIComponent(apiKey)}/Satellite/{z}/{y}/{x}.jpeg`;
}

export type CommercialRoadGeocodeRequest = {
  addr1: string;
  addr2: string;
  road_name: string;
  addr3?: string | null;
  addr4?: string | null;
  cluster_key?: string | null;
  label?: string | null;
};

export type CommercialRoadGeocodeResponse = {
  ok: boolean;
  query: string;
  longitude: number | null;
  latitude: number | null;
  matched_name: string | null;
  category: string | null;
  label: string | null;
  cluster_key: string | null;
  error: string | null;
};

export async function geocodeCommercialRoad(
  body: CommercialRoadGeocodeRequest,
): Promise<CommercialRoadGeocodeResponse> {
  const { data } = await commercialApi.post<CommercialRoadGeocodeResponse>(
    "/roads/geocode",
    {
      addr1: body.addr1,
      addr2: body.addr2,
      road_name: body.road_name,
      addr3: body.addr3 || undefined,
      addr4: body.addr4 || undefined,
      cluster_key: body.cluster_key || undefined,
      label: body.label || undefined,
    },
  );
  return data;
}

export type CommercialRoadMapPointInput = {
  cluster_key: string;
  label: string;
  addr1: string;
  addr2: string;
  road_name: string;
  addr3?: string | null;
  addr4?: string | null;
};

export type CommercialRoadMapPointsResponse = {
  points: Array<{
    cluster_key: string;
    label: string;
    longitude: number;
    latitude: number;
  }>;
  unresolved: string[];
};

export async function fetchCommercialRoadMapPoints(
  roads: CommercialRoadMapPointInput[],
): Promise<CommercialRoadMapPointsResponse> {
  const { data } = await commercialApi.post<CommercialRoadMapPointsResponse>(
    "/roads/map-points",
    { roads: roads.slice(0, 100) },
  );
  return data;
}

export type CollectiveBuildingGeocodeRequest = {
  addr1: string;
  addr2: string;
  jibun_address?: string | null;
  road_address?: string | null;
  building_key?: string | null;
  label?: string | null;
};

export type CollectiveBuildingGeocodeResponse = {
  ok: boolean;
  query: string;
  longitude: number | null;
  latitude: number | null;
  matched_name: string | null;
  category: string | null;
  label: string | null;
  building_key: string | null;
  error: string | null;
};

export type CollectiveBuildingMapPointInput = {
  building_key: string;
  label: string;
  addr1: string;
  addr2: string;
  jibun_address?: string | null;
  road_address?: string | null;
};

export type CollectiveBuildingMapPointsResponse = {
  points: Array<{
    building_key: string;
    label: string;
    longitude: number;
    latitude: number;
  }>;
  unresolved: string[];
};

export async function fetchCollectiveBuildingMapPoints(
  buildings: CollectiveBuildingMapPointInput[],
): Promise<CollectiveBuildingMapPointsResponse> {
  const { data } = await collectiveApi.post<CollectiveBuildingMapPointsResponse>(
    "/buildings/map-points",
    { buildings: buildings.slice(0, 100) },
  );
  return data;
}

export async function geocodeCollectiveBuilding(
  body: CollectiveBuildingGeocodeRequest,
): Promise<CollectiveBuildingGeocodeResponse> {
  const { data } = await collectiveApi.post<CollectiveBuildingGeocodeResponse>(
    "/buildings/geocode",
    {
      addr1: body.addr1,
      addr2: body.addr2,
      jibun_address: body.jibun_address || undefined,
      road_address: body.road_address || undefined,
      building_key: body.building_key || undefined,
      label: body.label || undefined,
    },
  );
  return data;
}
