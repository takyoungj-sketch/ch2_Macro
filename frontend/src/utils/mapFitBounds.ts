import bbox from "@turf/bbox";
import { LngLatBounds } from "maplibre-gl";
import type { Map as MapLibreMap } from "maplibre-gl";

import type { MapAdminLevel } from "./mapRegionScope";

/** bbox 를 padDeg 만큼 확장 (이웃 고리 가시화용) */
export function padBounds(
  bounds: [number, number, number, number],
  padDeg: number,
): [number, number, number, number] {
  const [west, south, east, north] = bounds;
  return [west - padDeg, south - padDeg, east + padDeg, north + padDeg];
}

/** 아주 작은 폴리곤(리·좁은 동) — bbox 최소 span 보정 */
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

/** GeoJSON → [west, south, east, north] */
export function boundsFromGeoJson(fc: GeoJSON.FeatureCollection): [number, number, number, number] | null {
  if (!fc.features.length) return null;
  try {
    const [west, south, east, north] = bbox(fc);
    if (!Number.isFinite(west)) return null;
    if (west === east && south === north) {
      return expandTinyBounds([west, south, east, north]);
    }
    return expandTinyBounds([west, south, east, north]);
  } catch {
    return null;
  }
}

/** 법정리(10자리, …00 아님) 여부 */
export function isBeopjungriRiCode(code: string): boolean {
  const c = code.trim();
  return c.length >= 10 && !c.endsWith("00");
}

/** 선택 코드 기준 maxZoom — 리는 더 깊게 */
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

/** 행정 레벨별 fit 상한 — 동·리는 더 깊게 확대 */
export function maxZoomForMapLevel(level: MapAdminLevel | null): number {
  return maxZoomForSelection(level, []);
}

/**
 * 선택 지역이 지도 너비의 약 78%를 채우도록 padding 산출.
 * 넓은 패널에서는 cm 목표만으로 너무 작게 보이므로 비율 하한을 둠.
 */
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

/** 선택 지역 중심 ~15cm 클로즈업 */
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
  const [west, south, east, north] = expandTinyBounds(
    bounds,
    isRi ? 0.00035 : 0.00055,
  );
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

  // 리는 너무 멀리 나가지 않게만 상한 적용 (강제 최대줌은 이웃 가시성을 해침)
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
