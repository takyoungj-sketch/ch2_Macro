import bbox from "@turf/bbox";
import { LngLatBounds } from "maplibre-gl";
import type { Map as MapLibreMap } from "maplibre-gl";

import type { MapAdminLevel } from "./mapRegionScope";

export function expandTinyBounds(
  bounds: [number, number, number, number],
  minSpanDeg = 0.00055,
): [number, number, number, number] {
  let [west, south, east, north] = bounds;
  const lngMid = (west + east) / 2;
  const latMid = (south + north) / 2;
  if (east - west < minSpanDeg) {
    west = lngMid - minSpanDeg / 2;
    east = lngMid + minSpanDeg / 2;
  }
  if (north - south < minSpanDeg) {
    south = latMid - minSpanDeg / 2;
    north = latMid + minSpanDeg / 2;
  }
  return [west, south, east, north];
}

export function boundsFromGeoJson(
  fc: GeoJSON.FeatureCollection,
): [number, number, number, number] | null {
  if (!fc.features.length) return null;
  try {
    const [west, south, east, north] = bbox(fc);
    if (!Number.isFinite(west)) return null;
    return expandTinyBounds([west, south, east, north]);
  } catch {
    return null;
  }
}

export function isBeopjungriRiCode(code: string): boolean {
  const c = code.trim();
  return c.length >= 10 && !c.endsWith("00");
}

export function maxZoomForSelection(
  level: MapAdminLevel | null,
  selectedCodes: readonly string[],
): number {
  if (level === "beopjungri") {
    if (selectedCodes.some(isBeopjungriRiCode)) return 20;
    return 18;
  }
  switch (level) {
    case "eupmyeondong":
      return 17;
    case "sigungu":
      return 15;
    case "sido":
      return 11;
    default:
      return 15;
  }
}

/** 선택 지역이 지도 너비의 약 78%를 채우도록 (넓은 패널에서도 토지와 비슷한 클로즈업) */
export function paddingForTargetWidthCm(
  containerWidthPx: number,
  targetCm = 15,
): { top: number; bottom: number; left: number; right: number } {
  const width = Math.max(containerWidthPx, 1);
  const targetFromCm = (targetCm / 2.54) * 96;
  const targetFromRatio = width * 0.78;
  const targetPx = Math.max(targetFromCm, targetFromRatio);
  const fillRatio = Math.min(0.92, targetPx / width);
  const padX = Math.round((width * (1 - fillRatio)) / 2);
  const padY = Math.round(padX * 0.28);
  return { top: padY, bottom: padY, left: padX, right: padX };
}

export type FitMapOptions = {
  bounds: [number, number, number, number];
  containerWidthPx: number;
  level: MapAdminLevel | null;
  selectedCodes?: readonly string[];
  targetCm?: number;
  duration?: number;
};

export function applySelectionFitBounds(map: MapLibreMap, opts: FitMapOptions): boolean {
  const {
    bounds,
    containerWidthPx,
    level,
    selectedCodes = [],
    targetCm = 15,
    duration = 700,
  } = opts;
  const isRi = level === "beopjungri" && selectedCodes.some(isBeopjungriRiCode);
  const [west, south, east, north] = expandTinyBounds(bounds, isRi ? 0.00035 : 0.00055);
  const lngLatBounds = LngLatBounds.convert([
    [west, south],
    [east, north],
  ]);
  if (!lngLatBounds) return false;

  map.resize();
  const padding = paddingForTargetWidthCm(containerWidthPx, targetCm);
  const maxZoom = maxZoomForSelection(level, selectedCodes);
  const camera = map.cameraForBounds(lngLatBounds, { padding, maxZoom });
  if (!camera) return false;

  const zoom =
    typeof camera.zoom === "number" ? Math.min(camera.zoom, maxZoom) : camera.zoom;

  map.easeTo({
    center: camera.center,
    zoom,
    bearing: 0,
    pitch: 0,
    duration,
    essential: true,
  });
  return true;
}
