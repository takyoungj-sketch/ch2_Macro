import axios from "axios";

import type { MapAdminLevel } from "../utils/mapRegionScope";

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();

/** /api/map — built client 와 base 분리 */
const mapApi = axios.create({
  baseURL: "/api",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

const builtApi = axios.create({
  baseURL: "/api/built",
  headers: _API_TOKEN ? { "X-Api-Token": _API_TOKEN } : undefined,
});

export type MapConfigResponse = {
  vworld_configured: boolean;
  tile_base: string;
  neighbor_graph_ready?: boolean;
  neighbor_edge_count?: number;
};

export type MapNeighborsResponse = {
  level: string;
  codes: string[];
  neighbors_by_code: Record<string, string[]>;
  neighbor_codes: string[];
  graph_ready: boolean;
  edge_count: number;
};

export type MapBoundariesResponse = {
  level: MapAdminLevel;
  selected: string[];
  feature_collection: GeoJSON.FeatureCollection;
};

export type BuiltMapResolveCodesResponse = {
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

export async function fetchMapNeighbors(opts: {
  level: MapAdminLevel;
  codes: string[];
}): Promise<MapNeighborsResponse> {
  const params = new URLSearchParams();
  params.set("level", opts.level === "beopjungri" ? "beopjungri" : "eupmyeondong");
  for (const code of opts.codes) {
    const c = String(code ?? "").trim();
    if (c) params.append("codes", c);
  }
  const { data } = await mapApi.get<MapNeighborsResponse>("/map/neighbors", { params });
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

export async function fetchBuiltMapResolveCodes(opts: {
  assetType?: string;
  addr1?: string;
  addr2?: string;
  gu?: string[];
  leaf?: string[];
  riPick?: string[];
}): Promise<BuiltMapResolveCodesResponse> {
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
  const { data } = await builtApi.get<BuiltMapResolveCodesResponse>(
    `/regions/resolve-codes?${params.toString()}`,
  );
  return data;
}

export function vworldSatelliteTileUrl(apiKey: string): string {
  return `https://api.vworld.kr/req/wmts/1.0.0/${encodeURIComponent(apiKey)}/Satellite/{z}/{y}/{x}.jpeg`;
}
