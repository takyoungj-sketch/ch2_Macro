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
};

export type MapBoundariesResponse = {
  level: MapAdminLevel;
  selected: string[];
  feature_collection: GeoJSON.FeatureCollection;
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
  const { data } = await api.get<MapBoundariesResponse>("/map/boundaries", { params });
  return data;
}

export function vworldSatelliteTileUrl(apiKey: string): string {
  return `https://api.vworld.kr/req/wmts/1.0.0/${encodeURIComponent(apiKey)}/Satellite/{z}/{y}/{x}.jpeg`;
}
