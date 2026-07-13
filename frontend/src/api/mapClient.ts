import axios from "axios";

import type { MapAdminLevel } from "../utils/mapRegionScope";

const api = axios.create({ baseURL: "/api" });

const _API_TOKEN = (import.meta.env.VITE_API_TOKEN ?? "").trim();
if (_API_TOKEN) {
  api.defaults.headers.common["X-Api-Token"] = _API_TOKEN;
}

export type MapConfigResponse = {
  vworld_configured: boolean;
  tile_base: string;
  neighbor_graph_ready?: boolean;
  neighbor_edge_count?: number;
};

export type MapBoundariesResponse = {
  level: MapAdminLevel;
  selected: string[];
  mode?: "viewport" | "context";
  feature_collection: GeoJSON.FeatureCollection;
};

export type MapNeighborsResponse = {
  level: string;
  codes: string[];
  neighbors_by_code: Record<string, string[]>;
  neighbor_codes: string[];
  graph_ready: boolean;
  edge_count: number;
};

export async function fetchMapConfig(): Promise<MapConfigResponse> {
  const { data } = await api.get<MapConfigResponse>("/map/config");
  return data;
}

export async function fetchMapBoundaries(opts: {
  level: MapAdminLevel;
  selected: string[];
  contextSidoCode?: string | null;
  contextSigunguCode?: string | null;
  /** Display SSOT — west,south,east,north */
  bbox?: string | null;
}): Promise<MapBoundariesResponse> {
  // FastAPI Query(list) 는 selected=a&selected=b 형식만 인식 (axios 기본 selected[]= 는 무시됨)
  const params = new URLSearchParams();
  params.set("level", opts.level);
  for (const code of opts.selected) {
    const c = String(code ?? "").trim();
    if (c) params.append("selected", c);
  }
  if (opts.contextSidoCode) params.set("context_sido_code", opts.contextSidoCode);
  if (opts.contextSigunguCode) params.set("context_sigungu_code", opts.contextSigunguCode);
  if (opts.bbox) params.set("bbox", opts.bbox);
  const { data } = await api.get<MapBoundariesResponse>("/map/boundaries", { params });
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
  const { data } = await api.get<MapNeighborsResponse>("/map/neighbors", { params });
  return data;
}

export function vworldSatelliteTileUrl(apiKey: string): string {
  return `https://api.vworld.kr/req/wmts/1.0.0/${encodeURIComponent(apiKey)}/Satellite/{z}/{y}/{x}.jpeg`;
}

/** MapLibre LngLatBounds → API bbox string */
export function boundsToBboxParam(b: {
  getWest(): number;
  getSouth(): number;
  getEast(): number;
  getNorth(): number;
}): string {
  return `${b.getWest()},${b.getSouth()},${b.getEast()},${b.getNorth()}`;
}
