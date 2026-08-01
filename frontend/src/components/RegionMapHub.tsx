import booleanDisjoint from "@turf/boolean-disjoint";
import booleanIntersects from "@turf/boolean-intersects";
import booleanTouches from "@turf/boolean-touches";
import bbox from "@turf/bbox";
import { feature as turfFeature, polygon as turfPolygon } from "@turf/helpers";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MapGL, { Layer, NavigationControl, Source, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

import {
  boundsToBboxParam,
  fetchMapBoundaries,
  fetchMapConfig,
  fetchMapNeighbors,
  vworldSatelliteTileUrl,
} from "../api/mapClient";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { MAX_PAID_LEAF_BEOPJUNGRI_PICK } from "../constants/tierPickLimits";
import { fetchRegions } from "../api/client";
import { useAppStore } from "../store";
import {
  featureAdminCode,
  resolveMapSelectionState,
} from "../utils/mapRegionScope";
import { boundsFromGeoJson, applySelectionFitBounds } from "../utils/mapFitBounds";
import { paidSubSigunguSelectionsCount } from "../utils/regionTier";

export type MapPanelMode = "normal" | "expanded" | "collapsed";

type Props = {
  fillHeight?: boolean;
  mapPanelMode?: MapPanelMode;
  onExpand?: () => void;
  onCollapse?: () => void;
  onNormal?: () => void;
};

const VWORLD_KEY = (import.meta.env.VITE_VWORLD_API_KEY ?? "").trim();

type ContextMenuState = {
  x: number;
  y: number;
  code: string;
  label: string;
};

/** Selection 그래프 비교용 — 읍면동은 8자리. */
function canonAdminCode(level: string | null | undefined, code: string): string {
  const c = code.trim();
  if (!c) return c;
  if (level === "beopjungri" && c.length >= 10 && !c.endsWith("00")) return c;
  if (c.length >= 10 && c.endsWith("00")) return c.slice(0, 8);
  if (c.length >= 8) return c.slice(0, 8);
  return c;
}

/** 동일 레벨 행정구역 — 경계 접촉·미세 겹침을 인접으로 인정 */
function shortRegionLabel(props: Record<string, unknown> | null | undefined): string {
  if (!props) return "";
  const candidates = [
    props.li_kor_nm,
    props.emd_kor_nm,
    props.sig_kor_nm,
    props.ctp_kor_nm,
    props.full_nm,
  ];
  for (const c of candidates) {
    if (c == null) continue;
    const s = String(c).trim();
    if (!s) continue;
    // full_nm 은 "충청북도 청주시 … 가경동" → 마지막 토큰만
    if (c === props.full_nm && s.includes(" ")) {
      const parts = s.split(/\s+/);
      return parts[parts.length - 1] ?? s;
    }
    return s;
  }
  return "";
}

function asLonLat(pt: unknown): [number, number] | null {
  if (!Array.isArray(pt) || pt.length < 2) return null;
  const lon = Number(pt[0]);
  const lat = Number(pt[1]);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  return [lon, lat];
}

function sanitizeRing(ring: unknown): [number, number][] | null {
  if (!Array.isArray(ring) || ring.length < 4) return null;
  const out: [number, number][] = [];
  for (const pt of ring) {
    const ll = asLonLat(pt);
    if (!ll) return null;
    out.push(ll);
  }
  return out;
}

/** MapLibre line 레이어가 MultiPolygon 을 깨뜨리는 경우가 있어 좌표를 숫자로 재구성 */
function sanitizePolygonGeometry(
  geometry: GeoJSON.Geometry | null | undefined,
): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  if (!geometry) return null;
  if (geometry.type === "Polygon") {
    const rings: [number, number][][] = [];
    for (const ring of geometry.coordinates) {
      const s = sanitizeRing(ring);
      if (s) rings.push(s);
    }
    return rings.length ? { type: "Polygon", coordinates: rings } : null;
  }
  if (geometry.type === "MultiPolygon") {
    const polys: [number, number][][][] = [];
    for (const poly of geometry.coordinates) {
      if (!Array.isArray(poly)) continue;
      const rings: [number, number][][] = [];
      for (const ring of poly) {
        const s = sanitizeRing(ring);
        if (s) rings.push(s);
      }
      if (rings.length) polys.push(rings);
    }
    return polys.length ? { type: "MultiPolygon", coordinates: polys } : null;
  }
  return null;
}

function polygonGeometryToOutline(
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon,
): GeoJSON.LineString | GeoJSON.MultiLineString | null {
  const lines: [number, number][][] = [];
  if (geometry.type === "Polygon") {
    for (const ring of geometry.coordinates) lines.push(ring as [number, number][]);
  } else {
    for (const poly of geometry.coordinates) {
      for (const ring of poly) lines.push(ring as [number, number][]);
    }
  }
  if (lines.length === 0) return null;
  if (lines.length === 1) return { type: "LineString", coordinates: lines[0]! };
  return { type: "MultiLineString", coordinates: lines };
}

function ringBboxCenter(ring: [number, number][]): [number, number] | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of ring) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null;
  return [(minX + maxX) / 2, (minY + maxY) / 2];
}

/** 폴리곤 라벨용 앵커 — MultiPolygon 은 가장 큰 파트 중심 */
function polygonLabelPoint(
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon,
): [number, number] | null {
  if (geometry.type === "Polygon") {
    const ring = geometry.coordinates[0] as [number, number][] | undefined;
    return ring ? ringBboxCenter(ring) : null;
  }
  let best: [number, number] | null = null;
  let bestArea = -1;
  for (const poly of geometry.coordinates) {
    const ring = poly[0];
    if (!ring?.length) continue;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const [x, y] of ring) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
    const area = (maxX - minX) * (maxY - minY);
    if (area > bestArea) {
      bestArea = area;
      best = [(minX + maxX) / 2, (minY + maxY) / 2];
    }
  }
  return best;
}

/** 동일 레벨 행정구역 — 경계 접촉·미세 틈(~120m)까지 인접으로 인정 */
function isAdjacentToAnySelected(
  clicked: GeoJSON.Feature,
  selectedFeatures: GeoJSON.Feature[],
  padDeg = 0.0011,
): boolean {
  if (selectedFeatures.length === 0) return true;
  if (!clicked.geometry) return false;
  try {
    const clickedFeat = turfFeature(clicked.geometry);
    const [w, s, e, n] = bbox(clickedFeat);
    const clickedPad = turfPolygon([
      [
        [w - padDeg, s - padDeg],
        [e + padDeg, s - padDeg],
        [e + padDeg, n + padDeg],
        [w - padDeg, n + padDeg],
        [w - padDeg, s - padDeg],
      ],
    ]);
    for (const sel of selectedFeatures) {
      if (!sel.geometry) continue;
      const selFeat = turfFeature(sel.geometry);
      if (booleanTouches(selFeat, clickedFeat)) return true;
      if (!booleanDisjoint(selFeat, clickedFeat)) return true;
      // 법정리 등 VWorld 경계 틈 — bbox 버퍼 교차로 보완
      if (booleanIntersects(selFeat, clickedPad)) return true;
    }
  } catch {
    return false;
  }
  return false;
}

function pickFeatureAtPoint(
  map: ReturnType<NonNullable<MapRef["getMap"]>>,
  point: { x: number; y: number },
  layerIds: string[],
  pad = 10,
): GeoJSON.Feature | null {
  const layers = layerIds.filter((id) => Boolean(map.getLayer(id)));
  if (layers.length === 0) return null;
  const box: [[number, number], [number, number]] = [
    [point.x - pad, point.y - pad],
    [point.x + pad, point.y + pad],
  ];
  const hits = map.queryRenderedFeatures(box, { layers });
  const first = hits[0];
  if (!first) return null;
  return {
    type: "Feature",
    geometry: first.geometry as GeoJSON.Geometry,
    properties: (first.properties ?? {}) as Record<string, unknown>,
  };
}

export default function RegionMapHub({
  fillHeight = false,
  mapPanelMode = "normal",
  onExpand,
  onCollapse,
  onNormal,
}: Props) {
  const mapRef = useRef<MapRef | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewMode = useAppStore((s) => s.viewMode);
  const tierSelection = useAppStore((s) => s.tierSelection);
  const addPickedBeopjungri = useAppStore((s) => s.addPickedBeopjungri);
  const mergePickedEupmyeondongCodes = useAppStore((s) => s.mergePickedEupmyeondongCodes);
  const mergePickedSigunguCodes = useAppStore((s) => s.mergePickedSigunguCodes);
  const mergePickedSidoCodes = useAppStore((s) => s.mergePickedSidoCodes);

  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);
  /** Display SSOT — 현재 지도 viewport bbox (없으면 레거시 context 1회) */
  const [viewBbox, setViewBbox] = useState<string | null>(null);
  const viewBboxTimerRef = useRef<number | null>(null);
  const lastFitKeyRef = useRef("");
  const labelLayerRef = useRef<HTMLDivElement | null>(null);
  const labelNodesRef = useRef<Map<string, { el: HTMLSpanElement; lng: number; lat: number }>>(
    new Map(),
  );

  const { data: regions = [] } = useQuery({
    queryKey: REGIONS_CATALOG_QUERY_KEY,
    queryFn: () => fetchRegions(),
    staleTime: 6 * 60 * 60 * 1000,
  });

  const mapScope = useMemo(() => resolveMapSelectionState(tierSelection, regions), [tierSelection, regions]);

  const selectionKey = mapScope.selectedCodes.join(",");

  useEffect(() => {
    // 선택 바뀌면 fit용으로 context 1회 → fit 후 viewport 로 전환
    setViewBbox(null);
  }, [selectionKey, mapScope.level]);

  const configQ = useQuery({
    queryKey: ["map-config"],
    queryFn: fetchMapConfig,
    staleTime: 60_000,
  });

  const syncViewportBbox = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    try {
      setViewBbox(boundsToBboxParam(map.getBounds()));
    } catch {
      /* ignore */
    }
  }, []);

  const scheduleViewportBbox = useCallback(() => {
    if (viewBboxTimerRef.current != null) window.clearTimeout(viewBboxTimerRef.current);
    viewBboxTimerRef.current = window.setTimeout(() => {
      syncViewportBbox();
    }, 280);
  }, [syncViewportBbox]);

  const boundariesQ = useQuery({
    queryKey: [
      "map-boundaries",
      "v5-viewport-display",
      mapScope.level,
      selectionKey,
      mapScope.contextSidoCode,
      mapScope.contextSigunguCode,
      viewBbox ?? "context-bootstrap",
    ],
    queryFn: () =>
      fetchMapBoundaries({
        level: mapScope.level!,
        selected: mapScope.selectedCodes,
        contextSidoCode: mapScope.contextSidoCode,
        contextSigunguCode: mapScope.contextSigunguCode,
        bbox: viewBbox,
      }),
    enabled: Boolean(mapScope.level && mapScope.hasSelection && configQ.data?.vworld_configured),
    staleTime: 0,
    placeholderData: (prev, prevQuery) => {
      if (!prev || !prevQuery?.queryKey) return prev;
      const pk = prevQuery.queryKey;
      const sameScope =
        pk[2] === mapScope.level &&
        pk[3] === selectionKey &&
        pk[4] === mapScope.contextSidoCode &&
        pk[5] === mapScope.contextSigunguCode;
      return sameScope ? prev : undefined;
    },
  });

  const neighborsQ = useQuery({
    queryKey: ["map-neighbors", mapScope.level, selectionKey],
    queryFn: () =>
      fetchMapNeighbors({
        level: mapScope.level!,
        codes: mapScope.selectedCodes,
      }),
    enabled: Boolean(
      mapScope.hasSelection &&
        (mapScope.level === "eupmyeondong" || mapScope.level === "beopjungri") &&
        configQ.data?.vworld_configured,
    ),
    staleTime: 30_000,
  });

  const neighborSelectableSet = useMemo(() => {
    const set = new Set<string>();
    for (const c of neighborsQ.data?.neighbor_codes ?? []) {
      set.add(canonAdminCode(mapScope.level, c));
      set.add(c);
    }
    return set;
  }, [neighborsQ.data?.neighbor_codes, mapScope.level]);

  // 전역 edge 수가 아니라, 현재 선택 코드에 이웃 데이터가 있을 때만 그래프 강제
  const neighborGraphReady = Boolean(
    neighborsQ.data?.graph_ready &&
      Object.values(neighborsQ.data?.neighbors_by_code ?? {}).some((arr) => (arr?.length ?? 0) > 0),
  );

  const geojson = boundariesQ.data?.feature_collection ?? null;

  const selectedSet = useMemo(() => new Set(mapScope.selectedCodes), [mapScope.selectedCodes]);
  const selectedCanonSet = useMemo(() => {
    const s = new Set<string>();
    for (const c of mapScope.selectedCodes) {
      s.add(canonAdminCode(mapScope.level, c));
      s.add(c);
    }
    return s;
  }, [mapScope.selectedCodes, mapScope.level]);

  const { fillGeoJson, outlineGeoJson, labelGeoJson } = useMemo((): {
    fillGeoJson: GeoJSON.FeatureCollection | null;
    outlineGeoJson: GeoJSON.FeatureCollection | null;
    labelGeoJson: GeoJSON.FeatureCollection | null;
  } => {
    if (!geojson || !mapScope.level) {
      return { fillGeoJson: null, outlineGeoJson: null, labelGeoJson: null };
    }

    const fillFeatures: GeoJSON.Feature[] = [];
    const outlineFeatures: GeoJSON.Feature[] = [];
    const labelFeatures: GeoJSON.Feature[] = [];

    for (const feat of geojson.features) {
      const props = (feat.properties ?? {}) as Record<string, unknown>;
      const code = featureAdminCode(props, mapScope.level!);
      const selected = Boolean(
        code &&
          (selectedSet.has(code) || selectedCanonSet.has(canonAdminCode(mapScope.level, code))),
      );
      const selectable = Boolean(
        code &&
          !selected &&
          neighborGraphReady &&
          (neighborSelectableSet.has(code) ||
            neighborSelectableSet.has(canonAdminCode(mapScope.level, code))),
      );
      const label =
        shortRegionLabel(props) ||
        (code && mapScope.labels[code]
          ? mapScope.labels[code].split(/\s+/).pop()
          : null) ||
        (code ? String(code) : "");
      const nextProps = {
        ...props,
        ch2_code: code ?? props.ch2_code ?? props.li_cd ?? null,
        ch2_selected: selected ? 1 : 0,
        ch2_selectable: selectable ? 1 : 0,
        ch2_label: label,
      };

      const geom = sanitizePolygonGeometry(feat.geometry);
      if (!geom) continue;

      fillFeatures.push({
        type: "Feature",
        geometry: geom,
        properties: nextProps,
      });

      const outline = polygonGeometryToOutline(geom);
      if (outline) {
        outlineFeatures.push({
          type: "Feature",
          geometry: outline,
          properties: nextProps,
        });
      }

      const anchor = polygonLabelPoint(geom);
      if (anchor && label) {
        labelFeatures.push({
          type: "Feature",
          geometry: { type: "Point", coordinates: anchor },
          properties: nextProps,
        });
      }
    }

    return {
      fillGeoJson: { type: "FeatureCollection", features: fillFeatures },
      outlineGeoJson: { type: "FeatureCollection", features: outlineFeatures },
      labelGeoJson: { type: "FeatureCollection", features: labelFeatures },
    };
  }, [geojson, mapScope.level, mapScope.labels, selectedSet, selectedCanonSet, neighborGraphReady, neighborSelectableSet]);

  const isRiSelection = useMemo(
    () =>
      mapScope.level === "beopjungri" &&
      mapScope.selectedCodes.some((c) => c.length >= 10 && !c.endsWith("00")),
    [mapScope.level, mapScope.selectedCodes],
  );

  // 선택은 바뀔 때만 fit. viewport 경계 재조회(dataUpdatedAt)로는 카메라를 되돌리지 않음.
  const selectionFitKey = useMemo(
    () => [mapScope.level, ...mapScope.selectedCodes].join("|"),
    [mapScope.level, mapScope.selectedCodes],
  );

  const fitToSelection = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map || !mapReady || !geojson || !mapScope.level) return;

    const selectedFeats = geojson.features.filter((f) => {
      const code = featureAdminCode(f.properties as Record<string, unknown>, mapScope.level!);
      if (!code) return false;
      return selectedSet.has(code) || selectedCanonSet.has(canonAdminCode(mapScope.level, code));
    });
    const targetFc: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: selectedFeats.length > 0 ? selectedFeats : geojson.features,
    };
    const bounds = boundsFromGeoJson(targetFc);
    if (!bounds) return;

    const width = map.getContainer()?.clientWidth || containerRef.current?.clientWidth || 640;
    applySelectionFitBounds(map, {
      bounds,
      containerWidthPx: width,
      level: mapScope.level,
      selectedCodes: mapScope.selectedCodes,
      targetCm: 20,
      duration: 650,
    });
  }, [geojson, mapReady, mapScope.level, mapScope.selectedCodes, selectedSet, selectedCanonSet]);

  useEffect(() => {
    if (!mapReady || !boundariesQ.isSuccess || !geojson?.features.length) return;
    if (lastFitKeyRef.current === selectionFitKey) return;

    const hasSelectedGeom = geojson.features.some((f) => {
      const code = featureAdminCode(f.properties as Record<string, unknown>, mapScope.level!);
      if (!code) return false;
      return selectedSet.has(code) || selectedCanonSet.has(canonAdminCode(mapScope.level, code));
    });
    // 선택 polygon이 아직 없으면(뷰포트 응답만) fit 보류
    if (mapScope.selectedCodes.length > 0 && !hasSelectedGeom) return;

    lastFitKeyRef.current = selectionFitKey;

    const t = window.setTimeout(() => {
      window.requestAnimationFrame(() => {
        fitToSelection();
        window.setTimeout(() => syncViewportBbox(), 700);
      });
    }, 80);
    return () => window.clearTimeout(t);
  }, [
    selectionFitKey,
    mapReady,
    boundariesQ.isSuccess,
    geojson,
    fitToSelection,
    syncViewportBbox,
    mapScope.level,
    mapScope.selectedCodes.length,
    selectedSet,
    selectedCanonSet,
  ]);

  useEffect(() => {
    if (!mapReady || mapPanelMode === "collapsed") return;
    const map = mapRef.current?.getMap();
    if (!map) return;
    const t = window.setTimeout(() => map.resize(), 80);
    return () => window.clearTimeout(t);
  }, [fillHeight, mapPanelMode, mapReady]);

  // 라벨: React setState 없이 DOM 위치만 갱신 (move 시 경계 레이어 재렌더/깜빡임 방지)
  useEffect(() => {
    if (!mapReady) return;
    const map = mapRef.current?.getMap();
    const layer = labelLayerRef.current;
    if (!map || !layer) return;

    const nodes = labelNodesRef.current;
    nodes.clear();
    layer.replaceChildren();

    const features = labelGeoJson?.features ?? [];
    for (const feat of features) {
      if (feat.geometry?.type !== "Point") continue;
      const coords = feat.geometry.coordinates;
      if (!Array.isArray(coords) || coords.length < 2) continue;
      const lng = Number(coords[0]);
      const lat = Number(coords[1]);
      if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue;
      const props = (feat.properties ?? {}) as Record<string, unknown>;
      const text = String(props.ch2_label ?? "").trim();
      if (!text) continue;
      const key = String(props.ch2_code ?? `${text}-${lng.toFixed(5)}-${lat.toFixed(5)}`);
      const selected = Number(props.ch2_selected) === 1;
      const el = document.createElement("span");
      el.textContent = text;
      el.dataset.labelKey = key;
      el.className = selected
        ? "absolute left-0 top-0 whitespace-nowrap rounded bg-amber-300/95 px-1.5 py-0.5 text-[11px] font-bold leading-none text-slate-950 shadow-md ring-1 ring-amber-950/40"
        : "absolute left-0 top-0 whitespace-nowrap rounded bg-slate-950/80 px-1.5 py-0.5 text-[11px] font-bold leading-none text-white shadow-md ring-1 ring-white/70";
      el.style.textShadow = "0 1px 2px rgba(0,0,0,0.9)";
      el.style.willChange = "transform";
      layer.appendChild(el);
      nodes.set(key, { el, lng, lat });
    }

    const syncPositions = () => {
      const w = map.getCanvas().clientWidth;
      const h = map.getCanvas().clientHeight;
      for (const { el, lng, lat } of nodes.values()) {
        const p = map.project([lng, lat]);
        const visible = p.x >= -48 && p.y >= -24 && p.x <= w + 48 && p.y <= h + 24;
        el.style.display = visible ? "" : "none";
        if (!visible) continue;
        el.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -50%)`;
      }
    };

    syncPositions();
    map.on("move", syncPositions);
    map.on("zoom", syncPositions);
    map.on("resize", syncPositions);
    return () => {
      map.off("move", syncPositions);
      map.off("zoom", syncPositions);
      map.off("resize", syncPositions);
      nodes.clear();
      layer.replaceChildren();
    };
  }, [mapReady, labelGeoJson]);

  const tileUrl = useMemo(() => {
    if (VWORLD_KEY) return vworldSatelliteTileUrl(VWORLD_KEY);
    return undefined;
  }, []);

  const mapStyle = useMemo(
    () => ({
      version: 8 as const,
      sources: tileUrl
        ? {
            vworldSat: {
              type: "raster" as const,
              tiles: [tileUrl],
              tileSize: 256,
              attribution: "© VWorld",
            },
          }
        : {},
      layers: tileUrl
        ? [
            {
              id: "vworld-sat",
              type: "raster" as const,
              source: "vworldSat",
            },
          ]
        : [],
    }),
    [tileUrl],
  );

  const offerAddRegionAt = useCallback(
    (point: { x: number; y: number }, eventFeature?: GeoJSON.Feature | null) => {
      setContextMenu(null);

      if (viewMode === "free") {
        setMapError("인접 지역 추가는 유료 분석 탭에서만 가능합니다.");
        return;
      }
      if (!mapScope.level || !geojson) return;

      // 시·도·시군구는 복수 선택 불가 — 인접 추가 UX 차단
      if (mapScope.level === "sido" || mapScope.level === "sigungu") {
        setMapError("시군구 이상 복수지역 선택 불가.");
        return;
      }

      const map = mapRef.current?.getMap();
      const hitPad = isRiSelection ? 18 : 12;
      const rawFeat =
        eventFeature ??
        (map
          ? pickFeatureAtPoint(map, point, ["region-fill", "region-outline"], hitPad)
          : null);

      if (!rawFeat) {
        setMapError("추가할 행정구역을 지도에서 클릭·우클릭해 주세요.");
        return;
      }
      const code = featureAdminCode(rawFeat.properties as Record<string, unknown>, mapScope.level);
      if (!code) {
        setMapError("이 구역의 행정코드를 확인할 수 없습니다.");
        return;
      }
      if (selectedSet.has(code) || selectedCanonSet.has(canonAdminCode(mapScope.level, code))) {
        setMapError("이미 선택된 지역입니다.");
        return;
      }

      const polygonFeat =
        geojson.features.find((f) => {
          const c = featureAdminCode(f.properties as Record<string, unknown>, mapScope.level!);
          return c === code;
        }) ?? rawFeat;

      const selectedFeatures = geojson.features.filter((f) => {
        const c = featureAdminCode(f.properties as Record<string, unknown>, mapScope.level!);
        if (!c) return false;
        return selectedSet.has(c) || selectedCanonSet.has(canonAdminCode(mapScope.level, c));
      });

      // Selection SSOT: neighbor_codes 그래프 (없으면 turf 폴백)
      const canon = canonAdminCode(mapScope.level, code);
      const inNeighborGraph =
        neighborSelectableSet.has(code) || neighborSelectableSet.has(canon);
      if (neighborGraphReady) {
        if (!inNeighborGraph) {
          setMapError("인접한 지역만 추가할 수 있습니다. (위상 이웃만 선택 가능)");
          return;
        }
      } else if (
        !isAdjacentToAnySelected(polygonFeat, selectedFeatures, isRiSelection ? 0.002 : 0.0012)
      ) {
        setMapError("인접한 지역만 추가할 수 있습니다. (맞닿은 구역을 선택해 주세요)");
        return;
      }

      const props = (polygonFeat.properties ?? rawFeat.properties) as Record<string, unknown>;
      const label =
        shortRegionLabel(props) ||
        mapScope.labels[code] ||
        String(props.full_nm ?? props.li_kor_nm ?? props.emd_kor_nm ?? code);
      setMapError(null);
      setContextMenu({
        x: point.x,
        y: point.y,
        code,
        label,
      });
    },
    [
      geojson,
      isRiSelection,
      mapScope.labels,
      mapScope.level,
      neighborGraphReady,
      neighborSelectableSet,
      selectedCanonSet,
      selectedSet,
      viewMode,
    ],
  );

  const handleContextMenu = useCallback(
    (evt: MapLayerMouseEvent) => {
      evt.preventDefault();
      evt.originalEvent?.preventDefault?.();
      const fromEvent = evt.features?.[0]
        ? ({
            type: "Feature" as const,
            geometry: evt.features[0].geometry as GeoJSON.Geometry,
            properties: (evt.features[0].properties ?? {}) as Record<string, unknown>,
          } satisfies GeoJSON.Feature)
        : null;
      offerAddRegionAt(evt.point, fromEvent);
    },
    [offerAddRegionAt],
  );

  const handleMapClick = useCallback(
    (evt: MapLayerMouseEvent) => {
      if (viewMode !== "paid") return;
      // 좌클릭으로도 인접 추가 (우클릭을 모르는 경우 대비)
      const fromEvent = evt.features?.[0]
        ? ({
            type: "Feature" as const,
            geometry: evt.features[0].geometry as GeoJSON.Geometry,
            properties: (evt.features[0].properties ?? {}) as Record<string, unknown>,
          } satisfies GeoJSON.Feature)
        : null;
      offerAddRegionAt(evt.point, fromEvent);
    },
    [offerAddRegionAt, viewMode],
  );

  const confirmAddRegion = useCallback(() => {
    if (!contextMenu || !mapScope.level) return;
    const { code } = contextMenu;
    setContextMenu(null);

    if (mapScope.level === "beopjungri") {
      const subCount = paidSubSigunguSelectionsCount(tierSelection);
      if (subCount >= MAX_PAID_LEAF_BEOPJUNGRI_PICK) {
        setMapError(`시군구 미만 선택은 최대 ${MAX_PAID_LEAF_BEOPJUNGRI_PICK}곳까지입니다.`);
        return;
      }
      addPickedBeopjungri(code);
      return;
    }
    if (mapScope.level === "eupmyeondong") {
      const subCount = paidSubSigunguSelectionsCount(tierSelection);
      if (subCount >= MAX_PAID_LEAF_BEOPJUNGRI_PICK) {
        setMapError(`시군구 미만 선택은 최대 ${MAX_PAID_LEAF_BEOPJUNGRI_PICK}곳까지입니다.`);
        return;
      }
      mergePickedEupmyeondongCodes([code], regions);
      return;
    }
    if (mapScope.level === "sigungu") {
      const ok = mergePickedSigunguCodes([code], regions);
      if (!ok) setMapError("시·군·구는 한 번에 하나만 선택할 수 있습니다.");
      return;
    }
    if (mapScope.level === "sido") {
      const ok = mergePickedSidoCodes([code], regions);
      if (!ok) setMapError("추가하지 못했습니다. 시·도 칩 정책을 확인해 주세요.");
    }
  }, [
    addPickedBeopjungri,
    contextMenu,
    mapScope.level,
    mergePickedEupmyeondongCodes,
    mergePickedSigunguCodes,
    mergePickedSidoCodes,
    regions,
    tierSelection,
  ]);

  const showSetupHint = !VWORLD_KEY && !configQ.data?.vworld_configured;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 shrink-0">
        <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">지도</p>
        <div className="flex items-center gap-2">
          {mapPanelMode === "collapsed" ? (
            <button
              type="button"
              onClick={onNormal}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
              aria-label="지도 펼치기"
            >
              <span aria-hidden>🗺</span>
              지도 펼치기
            </button>
          ) : (
            <>
              {mapPanelMode === "normal" ? (
                <button
                  type="button"
                  onClick={onExpand}
                  className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
                  aria-label="지도 확대"
                >
                  <span aria-hidden>⛶</span>
                  지도 확대
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onNormal}
                  className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
                  aria-label="지도 기본 크기"
                >
                  기본 크기
                </button>
              )}
              <button
                type="button"
                onClick={onCollapse}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
                aria-label="지도 접기"
              >
                <span aria-hidden>⊟</span>
                지도 접기
              </button>
            </>
          )}
        </div>
      </div>

      <div
        ref={containerRef}
        className={`relative rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700 bg-slate-200 dark:bg-slate-950 ${
          mapPanelMode === "collapsed" ? "hidden" : ""
        }`}
        style={
          mapPanelMode === "collapsed"
            ? undefined
            : fillHeight
              ? { height: "min(82vh, 52rem)" }
              : { height: "min(52vh, 28rem)" }
        }
      >
        {showSetupHint ? (
          <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-900 z-10">
            <div className="space-y-2 max-w-md">
              <p className="font-semibold">VWorld API 키가 필요합니다</p>
              <p className="text-xs text-slate-500">
                `frontend/.env` 에 <code className="text-[11px]">VITE_VWORLD_API_KEY</code>, 백엔드
                `.env` 에 <code className="text-[11px]">VWORLD_API_KEY</code> 를 설정하세요.
              </p>
            </div>
          </div>
        ) : (
          <MapGL
            ref={mapRef}
            initialViewState={{ longitude: 127.8, latitude: 36.2, zoom: 6.8, pitch: 0, bearing: 0 }}
            style={{ width: "100%", height: "100%" }}
            mapStyle={mapStyle as never}
            dragPan
            dragRotate={false}
            touchPitch={false}
            pitchWithRotate={false}
            scrollZoom
            doubleClickZoom
            cooperativeGestures={false}
            maxPitch={0}
            onLoad={() => {
              const map = mapRef.current?.getMap();
              map?.dragRotate.disable();
              map?.touchPitch.disable();
              setMapReady(true);
              scheduleViewportBbox();
            }}
            onMoveEnd={() => scheduleViewportBbox()}
            onZoomEnd={() => scheduleViewportBbox()}
            onContextMenu={handleContextMenu}
            onClick={handleMapClick}
            interactiveLayerIds={fillGeoJson ? ["region-fill", "region-outline"] : []}
          >
            <NavigationControl position="top-right" showCompass={false} />
            {fillGeoJson ? (
              <Source id="regions-fill" type="geojson" data={fillGeoJson}>
                <Layer
                  id="region-fill"
                  type="fill"
                  paint={{
                    // 선택은 면 채움이 아니라 노란 외곽선으로 강조 (클릭 hit 용 연한 면만)
                    "fill-color": "#64748b",
                    "fill-opacity": [
                      "case",
                      ["==", ["get", "ch2_selected"], 1],
                      isRiSelection ? 0.06 : 0.04,
                      isRiSelection ? 0.08 : 0.05,
                    ],
                    "fill-antialias": true,
                  }}
                />
              </Source>
            ) : null}
            {outlineGeoJson ? (
              <Source id="regions-outline" type="geojson" data={outlineGeoJson}>
                <Layer
                  id="region-outline-halo"
                  type="line"
                  filter={["==", ["get", "ch2_selected"], 1]}
                  layout={{ "line-cap": "round", "line-join": "round" }}
                  paint={{
                    "line-color": "#422006",
                    "line-opacity": 0.9,
                    "line-width": isRiSelection ? 8 : 7,
                  }}
                />
                <Layer
                  id="region-outline"
                  type="line"
                  layout={{ "line-cap": "round", "line-join": "round" }}
                  paint={{
                    "line-color": [
                      "case",
                      ["==", ["get", "ch2_selected"], 1],
                      "#facc15",
                      ["==", ["get", "ch2_selectable"], 1],
                      "#f97316",
                      "#ea580c",
                    ],
                    "line-width": [
                      "case",
                      ["==", ["get", "ch2_selected"], 1],
                      isRiSelection ? 4.5 : 4,
                      ["==", ["get", "ch2_selectable"], 1],
                      isRiSelection ? 2.4 : 2,
                      isRiSelection ? 1.8 : 1.35,
                    ],
                    "line-opacity": [
                      "case",
                      ["==", ["get", "ch2_selected"], 1],
                      1,
                      ["==", ["get", "ch2_selectable"], 1],
                      0.95,
                      0.55,
                    ],
                  }}
                />
              </Source>
            ) : null}
          </MapGL>
        )}

        <div
          ref={labelLayerRef}
          className="pointer-events-none absolute inset-0 z-[5] overflow-hidden"
          aria-hidden
        />

        {contextMenu ? (
          <div
            className="absolute z-20 rounded-lg border border-slate-200 bg-white shadow-lg p-2 text-sm dark:bg-slate-800 dark:border-slate-600"
            style={{ left: contextMenu.x, top: contextMenu.y, maxWidth: "16rem" }}
          >
            <p className="text-xs text-slate-600 dark:text-slate-300 mb-2 leading-snug">
              분석 지역을 추가할까요?
            </p>
            <p className="text-[11px] font-medium text-slate-800 dark:text-slate-100 mb-2 truncate">
              {contextMenu.label}
            </p>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                className="text-xs px-2 py-1 rounded border border-slate-200 dark:border-slate-600"
                onClick={() => setContextMenu(null)}
              >
                취소
              </button>
              <button
                type="button"
                className="text-xs px-2 py-1 rounded bg-blue-600 text-white font-semibold"
                onClick={confirmAddRegion}
              >
                추가
              </button>
            </div>
          </div>
        ) : null}

        {boundariesQ.isFetching ? (
          <div className="absolute top-2 left-2 z-10 text-[11px] bg-white/90 dark:bg-slate-800/90 px-2 py-1 rounded shadow">
            경계 불러오는 중…
          </div>
        ) : null}
        {!boundariesQ.isFetching && geojson?.features.length ? (
          <div className="absolute bottom-2 left-2 z-10 text-[11px] bg-white/90 dark:bg-slate-800/90 px-2 py-1 rounded shadow text-slate-600 dark:text-slate-300">
            표시 {geojson.features.length}곳
            {boundariesQ.data?.mode === "viewport" ? " · viewport" : " · context"}
            {neighborGraphReady
              ? ` · 선택가능 ${neighborSelectableSet.size}`
              : " · 선택 turf폴백"}
          </div>
        ) : null}
      </div>

        {mapPanelMode !== "collapsed" && mapError ? (
        <p className="text-xs text-red-600 dark:text-red-400" role="alert">
          {mapError}
        </p>
      ) : null}
      {mapPanelMode !== "collapsed" && viewMode === "paid" && mapScope.hasSelection ? (
        mapScope.level === "sido" || mapScope.level === "sigungu" ? (
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            시군구 이상 복수지역 선택 불가.
          </p>
        ) : (
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            인접 구역 추가: 지도에서{" "}
            <strong className="font-semibold text-slate-700 dark:text-slate-200">클릭</strong> 또는{" "}
            <strong className="font-semibold text-slate-700 dark:text-slate-200">우클릭</strong> → 확인
          </p>
        )
      ) : null}
      {mapPanelMode !== "collapsed" && boundariesQ.isError ? (
        <p className="text-xs text-red-600 dark:text-red-400">
          행정 경계를 불러오지 못했습니다. VWorld 키·도메인 등록을 확인하세요.
        </p>
      ) : null}
    </div>
  );
}
