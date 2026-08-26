import booleanDisjoint from "@turf/boolean-disjoint";
import booleanIntersects from "@turf/boolean-intersects";
import booleanTouches from "@turf/boolean-touches";
import bbox from "@turf/bbox";
import { feature as turfFeature, polygon as turfPolygon } from "@turf/helpers";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MapGL, {
  Layer,
  Marker,
  NavigationControl,
  Source,
  type MapLayerMouseEvent,
  type MapRef,
} from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

import { clampMapMenuPos } from "@ch2/macro-shell";
import {
  fetchCollectiveBuildingMapPoints,
  fetchCollectiveMapResolveCodes,
  fetchCommercialRoadLine,
  fetchCommercialRoadMapPoints,
  fetchMapBoundaries,
  fetchMapConfig,
  fetchMapNeighbors,
  geocodeCollectiveBuilding,
  geocodeCommercialRoad,
  vworldSatelliteTileUrl,
} from "../api/mapClient";
import { applySelectionFitBounds, boundsFromGeoJson } from "../utils/mapFitBounds";
import { canonAdminCode, featureAdminCode, type MapAdminLevel } from "../utils/mapRegionScope";
import {
  analysisUnitLabel,
  MAX_COLLECTIVE_ANALYSIS_UNITS,
  type CollectiveAnalysisUnit,
} from "../utils/collectiveAnalysisUnits";
import { resolveUnitAddr2 } from "../utils/flatSidoRegion";

export type MapPanelMode = "normal" | "expanded" | "collapsed";

export type CollectiveMapRiPick = { eup: string; ri: string };

/** 상업 지도 Road-B — 선택 cluster 라벨 */
export type CommercialRoadLabelInput = {
  clusterKey: string;
  roadName: string;
  label: string;
  addr1: string;
  addr2: string;
  addr3?: string | null;
  addr4?: string | null;
};

export type CommercialRoadMapInput = CommercialRoadLabelInput;

/** 주거 지도 — 선택 건물 지번 라벨 */
export type CollectiveBuildingLabelInput = {
  buildingKey: string;
  label: string;
  jibunAddress?: string | null;
  roadAddress?: string | null;
  addr1: string;
  addr2: string;
};

export type CollectiveBuildingMapInput = CollectiveBuildingLabelInput;

export type CollectiveMapScopeInput = {
  assetType: string;
  addr1: string;
  addr2: string;
  guList: string[];
  leafList: string[];
  /** eup|ri */
  riPick: string[];
};

type Props = {
  scope: CollectiveMapScopeInput;
  fillHeight?: boolean;
  mapPanelMode?: MapPanelMode;
  onExpand?: () => void;
  onCollapse?: () => void;
  onNormal?: () => void;
  /** 읍·면·동 칩 추가 (지도 인접 선택) */
  onAddLeaf?: (name: string) => void;
  /** 리 칩 추가 */
  onAddRi?: (pick: CollectiveMapRiPick) => void;
  /** 교차 시군구 포함 분석 단위 (복합과 동일) */
  analysisUnits?: CollectiveAnalysisUnit[];
  onAddUnit?: (unit: CollectiveAnalysisUnit) => void;
  /** 집합상가·공장 resolve API */
  commercial?: boolean;
  /** 상업: 선택 도로(cluster) 지오코딩 라벨 */
  selectedRoads?: CommercialRoadLabelInput[];
  /** 상업: 현재 목록의 도로명 cluster — 확대 시 대표점 라벨 */
  roadCandidates?: CommercialRoadMapInput[];
  /** 주거: 선택 건물 지번 지오코딩 라벨 */
  selectedBuildings?: CollectiveBuildingLabelInput[];
  /** 주거: 현재 목록 건물 — 확대 시 건물명 라벨 */
  buildingCandidates?: CollectiveBuildingMapInput[];
};

type ContextMenuState = {
  x: number;
  y: number;
  code: string;
  label: string;
  unit: CollectiveAnalysisUnit;
};

const VWORLD_KEY = (import.meta.env.VITE_VWORLD_API_KEY ?? "").trim();

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
    if (c != null && String(c).trim()) {
      const s = String(c).trim();
      const parts = s.split(/\s+/);
      return parts[parts.length - 1] || s;
    }
  }
  return "";
}

function sanitizeRing(ring: unknown): [number, number][] | null {
  if (!Array.isArray(ring) || ring.length < 3) return null;
  const out: [number, number][] = [];
  for (const pt of ring) {
    if (!Array.isArray(pt) || pt.length < 2) continue;
    const lng = Number(pt[0]);
    const lat = Number(pt[1]);
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue;
    out.push([lng, lat]);
  }
  return out.length >= 3 ? out : null;
}

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

function leafNameFromProps(props: Record<string, unknown>): string | null {
  const emd = String(props.emd_kor_nm ?? "").trim();
  if (emd) return emd;
  const short = shortRegionLabel(props);
  return short || null;
}

function riPickFromProps(props: Record<string, unknown>): CollectiveMapRiPick | null {
  const ri = String(props.li_kor_nm ?? "").trim();
  let eup = String(props.emd_kor_nm ?? "").trim();
  if (!eup) {
    const full = String(props.full_nm ?? "").trim();
    const parts = full.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) eup = parts[parts.length - 2]!;
  }
  if (ri && eup) return { eup, ri };
  return null;
}

function parentLabelsFromProps(props: Record<string, unknown>): { addr1: string; addr2: string } {
  let addr1 = String(props.ctp_kor_nm ?? "").trim();
  let addr2 = String(props.sig_kor_nm ?? "").trim();
  if (!addr1 || !addr2) {
    const full = String(props.full_nm ?? "").trim();
    const parts = full.split(/\s+/).filter(Boolean);
    if (!addr1 && parts[0]) addr1 = parts[0]!;
    if (!addr2 && parts.length >= 2) addr2 = parts[1]!;
  }
  return { addr1, addr2 };
}

function unitFromFeature(
  props: Record<string, unknown>,
  code: string,
  mapLevel: MapAdminLevel,
  fallbackAddr1: string,
): CollectiveAnalysisUnit | null {
  const parents = parentLabelsFromProps(props);
  const raw = String(code ?? "").trim();
  if (mapLevel === "eupmyeondong") {
    const name = leafNameFromProps(props);
    if (!name) return null;
    let emd = raw;
    if (emd.length >= 10 && emd.endsWith("00")) emd = emd.slice(0, 8);
    else if (emd.length > 8 && /^\d+$/.test(emd)) emd = emd.slice(0, 8);
    return {
      code: emd,
      level: "eupmyeondong",
      name,
      addr1: parents.addr1 || fallbackAddr1,
      addr2: parents.addr2,
    };
  }
  if (mapLevel === "beopjungri") {
    const pick = riPickFromProps(props);
    if (!pick) return null;
    return {
      code: raw,
      level: "beopjungri",
      name: pick.ri,
      eup: pick.eup,
      addr1: parents.addr1 || fallbackAddr1,
      addr2: parents.addr2,
    };
  }
  return null;
}

export default function CollectiveRegionMapHub({
  scope,
  fillHeight = false,
  mapPanelMode = "normal",
  onExpand,
  onCollapse,
  onNormal,
  onAddLeaf: _onAddLeaf,
  onAddRi: _onAddRi,
  analysisUnits = [],
  onAddUnit,
  commercial = false,
  selectedRoads = [],
  selectedBuildings = [],
  buildingCandidates = [],
  roadCandidates = [],
}: Props) {
  const mapRef = useRef<MapRef | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const labelLayerRef = useRef<HTMLDivElement | null>(null);
  const labelNodesRef = useRef<
    Map<string, { el: HTMLSpanElement; lng: number; lat: number; minZoom: number }>
  >(
    new Map(),
  );
  const lastFitKeyRef = useRef("");
  const [mapReady, setMapReady] = useState(false);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  const hasAddr = Boolean(scope.addr1.trim() && scope.addr2.trim());

  const configQ = useQuery({
    queryKey: ["built-map-config"],
    queryFn: fetchMapConfig,
    staleTime: 60_000,
  });

  const resolveQ = useQuery({
    queryKey: [
      "built-map-resolve",
      commercial ? "commercial" : "residential",
      scope.assetType,
      scope.addr1,
      scope.addr2,
      scope.guList.join(","),
      scope.leafList.join(","),
      scope.riPick.join(","),
    ],
    queryFn: () =>
      fetchCollectiveMapResolveCodes({
        assetType: scope.assetType,
        addr1: scope.addr1,
        addr2: scope.addr2,
        gu: scope.guList,
        leaf: scope.leafList,
        riPick: scope.riPick,
        commercial,
      }),
    enabled: hasAddr && Boolean(configQ.data?.vworld_configured),
    staleTime: 30_000,
  });

  const mapLevel = (resolveQ.data?.level ?? null) as MapAdminLevel | null;
  const resolveSelected = resolveQ.data?.selected_codes ?? [];
  const selectedCodes = useMemo(() => {
    const out: string[] = [];
    const seen = new Set<string>();
    for (const c of [...resolveSelected, ...analysisUnits.map((u) => u.code)]) {
      const t = String(c ?? "").trim();
      if (!t || seen.has(t)) continue;
      seen.add(t);
      out.push(t);
    }
    return out;
  }, [resolveSelected, analysisUnits]);
  const hasSelection = Boolean(
    (resolveQ.data?.has_selection || analysisUnits.length > 0) && mapLevel && selectedCodes.length,
  );

  const boundariesQ = useQuery({
    queryKey: [
      "built-map-boundaries",
      mapLevel,
      selectedCodes.join(","),
      resolveQ.data?.context_sido_code,
      resolveQ.data?.context_sigungu_code,
    ],
    queryFn: () =>
      fetchMapBoundaries({
        level: mapLevel!,
        selected: selectedCodes,
        contextSidoCode: resolveQ.data?.context_sido_code,
        contextSigunguCode: resolveQ.data?.context_sigungu_code,
      }),
    enabled: hasSelection,
    staleTime: 60_000,
  });

  const selectionKey = selectedCodes.join(",");

  const neighborsQ = useQuery({
    queryKey: ["collective-map-neighbors", commercial ? "commercial" : "residential", mapLevel, selectionKey],
    queryFn: () =>
      fetchMapNeighbors({
        level: mapLevel!,
        codes: selectedCodes,
      }),
    enabled: Boolean(
      hasSelection &&
        (mapLevel === "eupmyeondong" || mapLevel === "beopjungri") &&
        configQ.data?.vworld_configured,
    ),
    staleTime: 30_000,
  });

  const neighborSelectableSet = useMemo(() => {
    const set = new Set<string>();
    for (const c of neighborsQ.data?.neighbor_codes ?? []) {
      set.add(canonAdminCode(mapLevel, c));
      set.add(c);
    }
    return set;
  }, [neighborsQ.data?.neighbor_codes, mapLevel]);

  const neighborGraphReady = Boolean(
    neighborsQ.data?.graph_ready &&
      Object.values(neighborsQ.data?.neighbors_by_code ?? {}).some((arr) => (arr?.length ?? 0) > 0),
  );

  const geojson = boundariesQ.data?.feature_collection ?? null;
  const selectedSet = useMemo(() => new Set(selectedCodes), [selectedCodes]);
  const selectedCanonSet = useMemo(() => {
    const s = new Set<string>();
    for (const c of selectedCodes) {
      s.add(canonAdminCode(mapLevel, c));
      s.add(c);
    }
    return s;
  }, [selectedCodes, mapLevel]);
  const labels = resolveQ.data?.labels ?? {};

  const primaryRoad = selectedRoads[0] ?? null;
  const primaryBuilding = selectedBuildings[0] ?? null;

  const roadGeocodeQ = useQuery({
    queryKey: [
      "commercial-road-geocode",
      primaryRoad?.clusterKey,
      primaryRoad?.roadName,
      primaryRoad?.addr1,
      primaryRoad?.addr2,
      primaryRoad?.addr3,
      primaryRoad?.addr4,
    ],
    queryFn: () =>
      geocodeCommercialRoad({
        cluster_key: primaryRoad!.clusterKey,
        road_name: primaryRoad!.roadName,
        label: primaryRoad!.label,
        addr1: primaryRoad!.addr1,
        addr2: primaryRoad!.addr2,
        addr3: primaryRoad!.addr3,
        addr4: primaryRoad!.addr4,
      }),
    enabled: Boolean(commercial && primaryRoad?.roadName && primaryRoad.addr1 && primaryRoad.addr2),
    staleTime: 10 * 60_000,
    retry: 1,
  });

  const roadMapPointsQ = useQuery({
    queryKey: [
      "collective-commercial-road-map-points",
      roadCandidates.map((road) => road.clusterKey).join(","),
    ],
    queryFn: () =>
      fetchCommercialRoadMapPoints(
        roadCandidates.map((road) => ({
          cluster_key: road.clusterKey,
          label: road.label,
          addr1: road.addr1,
          addr2: road.addr2,
          road_name: road.roadName,
          addr3: road.addr3,
          addr4: road.addr4,
        })),
      ),
    enabled: commercial && roadCandidates.length > 0 && Boolean(configQ.data?.vworld_configured),
    staleTime: 30 * 60_000,
    retry: 1,
  });

  const buildingGeocodeQ = useQuery({
    queryKey: [
      "collective-building-geocode",
      primaryBuilding?.buildingKey,
      primaryBuilding?.jibunAddress,
      primaryBuilding?.roadAddress,
      primaryBuilding?.addr1,
      primaryBuilding?.addr2,
    ],
    queryFn: () =>
      geocodeCollectiveBuilding({
        building_key: primaryBuilding!.buildingKey,
        label: primaryBuilding!.label,
        jibun_address: primaryBuilding!.jibunAddress,
        road_address: primaryBuilding!.roadAddress,
        addr1: primaryBuilding!.addr1,
        addr2: primaryBuilding!.addr2,
      }),
    enabled: Boolean(
      !commercial &&
        primaryBuilding &&
        primaryBuilding.addr1 &&
        primaryBuilding.addr2 &&
        (primaryBuilding.jibunAddress || primaryBuilding.roadAddress),
    ),
    staleTime: 10 * 60_000,
    retry: 1,
  });

  const buildingMapPointsQ = useQuery({
    queryKey: [
      "collective-building-map-points",
      buildingCandidates.map((b) => b.buildingKey).join(","),
    ],
    queryFn: () =>
      fetchCollectiveBuildingMapPoints(
        buildingCandidates.map((b) => ({
          building_key: b.buildingKey,
          label: b.label,
          addr1: b.addr1,
          addr2: b.addr2,
          jibun_address: b.jibunAddress,
          road_address: b.roadAddress,
        })),
      ),
    enabled: !commercial && buildingCandidates.length > 0 && Boolean(configQ.data?.vworld_configured),
    staleTime: 30 * 60_000,
    retry: 1,
  });

  const placeGeocodeQ = commercial ? roadGeocodeQ : buildingGeocodeQ;
  const placeLabel = commercial
    ? primaryRoad?.label || primaryRoad?.roadName || "도로"
    : primaryBuilding?.label || primaryBuilding?.jibunAddress || "건물";
  const placePending = Boolean(
    commercial ? primaryRoad && roadGeocodeQ.isFetching : primaryBuilding && buildingGeocodeQ.isFetching,
  );
  const placeRequested = Boolean(commercial ? primaryRoad : primaryBuilding);

  const placeMarker =
    placeGeocodeQ.data?.ok &&
    placeGeocodeQ.data.longitude != null &&
    placeGeocodeQ.data.latitude != null
      ? {
          lng: placeGeocodeQ.data.longitude,
          lat: placeGeocodeQ.data.latitude,
          label: placeLabel,
        }
      : null;

  const selectedAdminBbox = useMemo(() => {
    if (!geojson?.features?.length) return null;
    const picked = geojson.features.filter(
      (f) => Number((f.properties as { ch2_selected?: number } | null)?.ch2_selected) === 1,
    );
    if (!picked.length) return null;
    const b = bbox({ type: "FeatureCollection", features: picked });
    if (!b.every(Number.isFinite)) return null;
    return { west: b[0], south: b[1], east: b[2], north: b[3] };
  }, [geojson]);

  const roadLineQ = useQuery({
    queryKey: [
      "commercial-road-line",
      primaryRoad?.clusterKey,
      primaryRoad?.roadName,
      placeMarker?.lng,
      placeMarker?.lat,
      selectedAdminBbox?.west,
      selectedAdminBbox?.south,
      selectedAdminBbox?.east,
      selectedAdminBbox?.north,
    ],
    queryFn: () =>
      fetchCommercialRoadLine({
        cluster_key: primaryRoad!.clusterKey,
        road_name: primaryRoad!.roadName,
        label: primaryRoad!.label,
        addr1: primaryRoad!.addr1,
        addr2: primaryRoad!.addr2,
        addr3: primaryRoad!.addr3,
        addr4: primaryRoad!.addr4,
        longitude: placeMarker?.lng,
        latitude: placeMarker?.lat,
        west: selectedAdminBbox?.west,
        south: selectedAdminBbox?.south,
        east: selectedAdminBbox?.east,
        north: selectedAdminBbox?.north,
      }),
    enabled: Boolean(
      commercial &&
        primaryRoad?.roadName &&
        primaryRoad.addr1 &&
        primaryRoad.addr2 &&
        (placeMarker || selectedAdminBbox) &&
        configQ.data?.vworld_configured,
    ),
    staleTime: 10 * 60_000,
    retry: 1,
  });

  const roadLineFc =
    commercial && roadLineQ.data?.ok && (roadLineQ.data.feature_collection?.features?.length ?? 0) > 0
      ? roadLineQ.data.feature_collection
      : null;

  useEffect(() => {
    if (!mapReady || mapPanelMode === "collapsed") return;
    const map = mapRef.current?.getMap();
    if (!map) return;
    if (roadLineFc) {
      const b = boundsFromGeoJson(roadLineFc);
      if (b) {
        const t = window.setTimeout(() => {
          map.fitBounds(b, { padding: 64, duration: 650, maxZoom: 16, essential: true });
        }, 120);
        return () => window.clearTimeout(t);
      }
    }
    if (!placeMarker) return;
    const t = window.setTimeout(() => {
      map.easeTo({
        center: [placeMarker.lng, placeMarker.lat],
        zoom: Math.max(map.getZoom(), 15),
        duration: 650,
        essential: true,
      });
    }, 120);
    return () => window.clearTimeout(t);
  }, [
    mapReady,
    mapPanelMode,
    roadLineFc,
    placeMarker?.lng,
    placeMarker?.lat,
    placeMarker?.label,
  ]);

  const isRiSelection = useMemo(
    () =>
      mapLevel === "beopjungri" &&
      selectedCodes.some((c) => c.length >= 10 && !c.endsWith("00")),
    [mapLevel, selectedCodes],
  );

  const { fillGeoJson, outlineGeoJson, labelGeoJson } = useMemo((): {
    fillGeoJson: GeoJSON.FeatureCollection | null;
    outlineGeoJson: GeoJSON.FeatureCollection | null;
    labelGeoJson: GeoJSON.FeatureCollection | null;
  } => {
    if (!geojson || !mapLevel) {
      return { fillGeoJson: null, outlineGeoJson: null, labelGeoJson: null };
    }
    const fillFeatures: GeoJSON.Feature[] = [];
    const outlineFeatures: GeoJSON.Feature[] = [];
    const labelFeatures: GeoJSON.Feature[] = [];

    for (const feat of geojson.features) {
      const props = (feat.properties ?? {}) as Record<string, unknown>;
      const code = featureAdminCode(props, mapLevel);
      const selected = Boolean(
        code &&
          (selectedSet.has(code) || selectedCanonSet.has(canonAdminCode(mapLevel, code))),
      );
      const selectable = Boolean(
        code &&
          !selected &&
          neighborGraphReady &&
          (neighborSelectableSet.has(code) ||
            neighborSelectableSet.has(canonAdminCode(mapLevel, code))),
      );
      const label =
        shortRegionLabel(props) ||
        (code && labels[code] ? labels[code].split(/\s+/).pop() : null) ||
        (code ? String(code) : "");
      const nextProps = {
        ...props,
        ch2_code: code ?? null,
        ch2_selected: selected ? 1 : 0,
        ch2_selectable: selectable ? 1 : 0,
        ch2_label: label,
      };
      const geom = sanitizePolygonGeometry(feat.geometry);
      if (!geom) continue;
      fillFeatures.push({ type: "Feature", geometry: geom, properties: nextProps });
      const outline = polygonGeometryToOutline(geom);
      if (outline) {
        outlineFeatures.push({ type: "Feature", geometry: outline, properties: nextProps });
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
  }, [geojson, mapLevel, selectedSet, selectedCanonSet, labels, neighborGraphReady, neighborSelectableSet]);

  const fitDataKey = useMemo(
    () =>
      [
        "fit-v2",
        mapLevel,
        ...selectedCodes,
        boundariesQ.dataUpdatedAt,
        geojson?.features.length ?? 0,
        fillHeight ? "exp" : "norm",
      ].join("|"),
    [mapLevel, selectedCodes, boundariesQ.dataUpdatedAt, geojson?.features.length, fillHeight],
  );

  const fitToSelection = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map || !mapReady || !geojson || !mapLevel) return;
    const selectedFeats = geojson.features.filter((f) => {
      const code = featureAdminCode(f.properties as Record<string, unknown>, mapLevel);
      return code && selectedSet.has(code);
    });
    const targetFc: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: selectedFeats.length > 0 ? selectedFeats : geojson.features,
    };
    const b = boundsFromGeoJson(targetFc);
    if (!b) return;
    map.resize();
    const width =
      map.getContainer()?.clientWidth || containerRef.current?.clientWidth || 640;
    applySelectionFitBounds(map, {
      bounds: b,
      containerWidthPx: width,
      level: mapLevel,
      selectedCodes,
      targetCm: 20,
      duration: 650,
    });
  }, [geojson, mapReady, mapLevel, selectedCodes, selectedSet]);

  useEffect(() => {
    if (!mapReady || !boundariesQ.isSuccess || !geojson) return;
    if (lastFitKeyRef.current === fitDataKey) return;
    lastFitKeyRef.current = fitDataKey;
    const t = window.setTimeout(() => {
      window.requestAnimationFrame(() => fitToSelection());
    }, 120);
    return () => window.clearTimeout(t);
  }, [fitDataKey, mapReady, boundariesQ.isSuccess, geojson, fitToSelection]);

  useEffect(() => {
    if (!mapReady || mapPanelMode === "collapsed") return;
    const map = mapRef.current?.getMap();
    if (!map) return;
    const t = window.setTimeout(() => {
      map.resize();
      lastFitKeyRef.current = "";
      fitToSelection();
    }, 100);
    return () => window.clearTimeout(t);
  }, [fillHeight, mapPanelMode, mapReady, fitToSelection]);

  useEffect(() => {
    if (!mapReady) return;
    const map = mapRef.current?.getMap();
    const layer = labelLayerRef.current;
    if (!map || !layer) return;

    const nodes = labelNodesRef.current;
    nodes.clear();
    layer.replaceChildren();

    for (const feat of labelGeoJson?.features ?? []) {
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
      el.className = selected
        ? "absolute left-0 top-0 whitespace-nowrap rounded bg-amber-300/95 px-1.5 py-0.5 text-[11px] font-bold leading-none text-slate-950 shadow-md ring-1 ring-amber-950/40"
        : "absolute left-0 top-0 whitespace-nowrap rounded bg-slate-950/80 px-1.5 py-0.5 text-[11px] font-bold leading-none text-white shadow-md ring-1 ring-white/70";
      el.style.textShadow =
        "0 1px 2px rgba(0,0,0,0.9)";
      el.style.willChange = "transform";
      layer.appendChild(el);
      nodes.set(key, { el, lng, lat, minZoom: 0 });
    }

    for (const point of buildingMapPointsQ.data?.points ?? []) {
      const el = document.createElement("span");
      el.textContent = point.label;
      el.className =
        "absolute left-0 top-0 z-10 whitespace-nowrap rounded bg-slate-950/85 px-1.5 py-0.5 text-[12px] font-bold leading-none text-white shadow-md ring-1 ring-white/80";
      el.style.textShadow = "0 1px 2px rgba(0,0,0,0.95)";
      el.style.willChange = "transform";
      layer.appendChild(el);
      nodes.set(`building:${point.building_key}`, {
        el,
        lng: point.longitude,
        lat: point.latitude,
        minZoom: 14.5,
      });
    }

    for (const point of roadMapPointsQ.data?.points ?? []) {
      const el = document.createElement("span");
      el.textContent = point.label;
      el.className =
        "absolute left-0 top-0 z-10 whitespace-nowrap rounded bg-slate-950/85 px-1.5 py-0.5 text-[12px] font-bold leading-none text-white shadow-md ring-1 ring-white/80";
      el.style.textShadow = "0 1px 2px rgba(0,0,0,0.95)";
      el.style.willChange = "transform";
      layer.appendChild(el);
      nodes.set(`road:${point.cluster_key}`, {
        el,
        lng: point.longitude,
        lat: point.latitude,
        minZoom: 14.5,
      });
    }

    const syncPositions = () => {
      const w = map.getCanvas().clientWidth;
      const h = map.getCanvas().clientHeight;
      const zoom = map.getZoom();
      for (const { el, lng, lat, minZoom } of nodes.values()) {
        if (zoom < minZoom) {
          el.style.display = "none";
          continue;
        }
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
  }, [buildingMapPointsQ.data?.points, labelGeoJson, mapReady, roadMapPointsQ.data?.points]);

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
      if (!mapLevel || !geojson) return;

      if (mapLevel === "sido" || mapLevel === "sigungu") {
        setMapError("시군구 이상 복수지역 선택 불가.");
        return;
      }

      const map = mapRef.current?.getMap();
      const hitPad = isRiSelection ? 18 : 12;
      const rawFeat =
        eventFeature ??
        (map ? pickFeatureAtPoint(map, point, ["region-fill", "region-outline"], hitPad) : null);

      if (!rawFeat) {
        setMapError("추가할 행정구역을 지도에서 클릭·우클릭해 주세요.");
        return;
      }
      const code = featureAdminCode(rawFeat.properties as Record<string, unknown>, mapLevel);
      if (!code) {
        setMapError("이 구역의 행정코드를 확인할 수 없습니다.");
        return;
      }
      const already =
        selectedSet.has(code) ||
        selectedCanonSet.has(canonAdminCode(mapLevel, code)) ||
        analysisUnits.some((u) => u.code === code || u.code === code.slice(0, 8));
      if (already) {
        setMapError("이미 선택된 지역입니다.");
        return;
      }
      if (analysisUnits.length >= MAX_COLLECTIVE_ANALYSIS_UNITS) {
        setMapError(`선택 지역은 최대 ${MAX_COLLECTIVE_ANALYSIS_UNITS}개까지입니다.`);
        return;
      }

      const polygonFeat =
        geojson.features.find((f) => {
          const c = featureAdminCode(f.properties as Record<string, unknown>, mapLevel);
          return c === code || (c && canonAdminCode(mapLevel, c) === canonAdminCode(mapLevel, code));
        }) ?? rawFeat;

      const selectedFeatures = geojson.features.filter((f) => {
        const c = featureAdminCode(f.properties as Record<string, unknown>, mapLevel);
        if (!c) return false;
        return selectedSet.has(c) || selectedCanonSet.has(canonAdminCode(mapLevel, c));
      });
      if (!selectedFeatures.length) {
        setMapError("먼저 왼쪽에서 읍·면·동(또는 리)을 선택해 주세요.");
        return;
      }
      const canon = canonAdminCode(mapLevel, code);
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
      const unit = unitFromFeature(props, code, mapLevel, scope.addr1);
      if (!unit) {
        setMapError("지역 이름을 확인할 수 없습니다.");
        return;
      }
      if (analysisUnits.length && analysisUnits[0]!.level !== unit.level) {
        setMapError("같은 행정 레벨만 함께 선택할 수 있습니다.");
        return;
      }

      setMapError(null);
      const pos = clampMapMenuPos(point.x, point.y, containerRef.current);
      setContextMenu({
        x: pos.x,
        y: pos.y,
        code: unit.code,
        label: analysisUnitLabel(unit),
        unit,
      });
    },
    [
      analysisUnits,
      geojson,
      isRiSelection,
      mapLevel,
      neighborGraphReady,
      neighborSelectableSet,
      scope.addr1,
      selectedCanonSet,
      selectedCodes,
      selectedSet,
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

  const confirmAddRegion = useCallback(() => {
    if (!contextMenu) return;
    const unit = contextMenu.unit;
    const anchorSig = (selectedCodes[0] || analysisUnits[0]?.code || "")
      .replace(/\D/g, "")
      .slice(0, 5);
    const unitSig = unit.code.replace(/\D/g, "").slice(0, 5);
    const crossParent =
      Boolean(anchorSig && unitSig && anchorSig !== unitSig) ||
      Boolean(unit.addr2 && scope.addr2 && unit.addr2 !== scope.addr2);
    onAddUnit?.({
      ...unit,
      crossParent,
      addr1: unit.addr1 || scope.addr1,
      addr2: resolveUnitAddr2(scope.addr1, scope.addr2, unit.addr1, unit.addr2, crossParent),
    });
    setContextMenu(null);
  }, [analysisUnits, contextMenu, onAddUnit, scope.addr1, scope.addr2, selectedCodes]);

  const showSetupHint = !VWORLD_KEY && !configQ.data?.vworld_configured;
  const upperOnly = mapLevel === "sido" || mapLevel === "sigungu";
  const canMultiAdd = mapLevel === "eupmyeondong" || mapLevel === "beopjungri";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2 shrink-0">
        <p className="text-xs font-semibold text-slate-600">지도</p>
        <div className="flex items-center gap-1.5">
          {mapPanelMode !== "expanded" && onExpand ? (
            <button
              type="button"
              onClick={onExpand}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50"
            >
              <span aria-hidden>⛶</span>
              지도 확대
            </button>
          ) : null}
          {mapPanelMode === "expanded" && onNormal ? (
            <button
              type="button"
              onClick={onNormal}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50"
            >
              보통
            </button>
          ) : null}
          {mapPanelMode !== "collapsed" && onCollapse ? (
            <button
              type="button"
              onClick={onCollapse}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50"
            >
              <span aria-hidden>⊟</span>
              지도 접기
            </button>
          ) : null}
          {mapPanelMode === "collapsed" && onNormal ? (
            <button
              type="button"
              onClick={onNormal}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50"
            >
              지도 펼치기
            </button>
          ) : null}
        </div>
      </div>

      <div
        ref={containerRef}
        className={`relative rounded-xl overflow-hidden border border-slate-200 bg-slate-200 ${
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
          <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-slate-600 bg-slate-100 z-10">
            <div className="space-y-2 max-w-md">
              <p className="font-semibold">VWorld API 키가 필요합니다</p>
              <p className="text-xs text-slate-500">
                `frontend-collective/.env` 에 <code className="text-[11px]">VITE_VWORLD_API_KEY</code> 를
                설정하세요.
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
            }}
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
                    "fill-color": "#64748b",
                    "fill-opacity": [
                      "case",
                      ["==", ["get", "ch2_selected"], 1],
                      isRiSelection ? 0.08 : 0.06,
                      isRiSelection ? 0.1 : 0.07,
                    ],
                    "fill-antialias": true,
                  } as never}
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
                  } as never}
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
                      0.9,
                    ],
                  } as never}
                />
              </Source>
            ) : null}
            {roadLineFc ? (
              <Source id="commercial-road-line" type="geojson" data={roadLineFc}>
                <Layer
                  id="commercial-road-line-halo"
                  type="line"
                  layout={{ "line-cap": "round", "line-join": "round" }}
                  paint={{
                    "line-color": "#0c4a6e",
                    "line-width": 8,
                    "line-opacity": 0.9,
                  }}
                />
                <Layer
                  id="commercial-road-line"
                  type="line"
                  layout={{ "line-cap": "round", "line-join": "round" }}
                  paint={{
                    "line-color": "#38bdf8",
                    "line-width": 5,
                    "line-opacity": 1,
                  }}
                />
              </Source>
            ) : null}
            {placeMarker ? (
              <Marker longitude={placeMarker.lng} latitude={placeMarker.lat} anchor="bottom">
                <div className="flex flex-col items-center pointer-events-none">
                  <div className="rounded-md bg-amber-500 text-white text-[11px] font-semibold px-2 py-1 shadow max-w-[12rem] truncate">
                    {placeMarker.label}
                  </div>
                  <div className="w-0 h-0 border-l-[6px] border-r-[6px] border-t-[8px] border-l-transparent border-r-transparent border-t-amber-500" />
                </div>
              </Marker>
            ) : null}
          </MapGL>
        )}

        <div
          ref={labelLayerRef}
          className="pointer-events-none absolute inset-0 z-[5] overflow-hidden"
          aria-hidden
        />

        {(resolveQ.isFetching || boundariesQ.isFetching) && hasAddr ? (
          <div className="absolute top-2 left-2 z-10 text-[11px] bg-white/90 px-2 py-1 rounded shadow">
            경계 불러오는 중…
          </div>
        ) : null}
        {placePending ? (
          <div className="absolute top-2 left-2 z-10 text-[11px] bg-white/90 px-2 py-1 rounded shadow">
            {commercial ? "도로 위치 찾는 중…" : "건물 위치 찾는 중…"}
          </div>
        ) : null}
        {commercial && roadLineQ.isFetching ? (
          <div className="absolute top-2 left-2 z-10 text-[11px] bg-white/90 px-2 py-1 rounded shadow">
            도로 구간 불러오는 중…
          </div>
        ) : null}
        {placeRequested && placeGeocodeQ.isSuccess && !placeMarker ? (
          <div className="absolute top-2 left-2 z-10 text-[11px] bg-amber-50 text-amber-800 px-2 py-1 rounded shadow">
            {commercial ? "도로 위치를 찾지 못했습니다." : "건물 위치를 찾지 못했습니다."}
          </div>
        ) : null}
        {commercial &&
        roadLineQ.isSuccess &&
        !roadLineFc &&
        (placeMarker || selectedAdminBbox) ? (
          <div className="absolute top-10 left-2 z-10 text-[11px] bg-amber-50 text-amber-800 px-2 py-1 rounded shadow">
            도로 선은 찾지 못해 위치로 표시합니다.
          </div>
        ) : null}
        {!boundariesQ.isFetching && geojson?.features.length ? (
          <div className="absolute bottom-2 left-2 z-10 text-[11px] bg-white/90 px-2 py-1 rounded shadow text-slate-600">
            행정구역 {geojson.features.length}곳
            {geojson.features.length > selectedCodes.length ? " · 인접 포함" : ""}
            {neighborGraphReady
              ? ` · 선택가능 ${neighborSelectableSet.size}`
              : " · 선택 turf폴백"}
          </div>
        ) : null}

        {contextMenu ? (
          <div
            className="absolute z-20 rounded-lg border border-slate-200 bg-white shadow-lg p-2 text-sm"
            style={{ left: contextMenu.x, top: contextMenu.y, maxWidth: "16rem" }}
          >
            <p className="text-xs text-slate-600 mb-2 leading-snug">분석 지역을 추가할까요?</p>
            <p className="text-[11px] font-medium text-slate-800 mb-2 truncate">{contextMenu.label}</p>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                className="text-xs px-2 py-1 rounded border border-slate-200"
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
      </div>

      {mapPanelMode !== "collapsed" && mapError ? (
        <p className="text-xs text-red-600" role="alert">
          {mapError}
        </p>
      ) : null}
      {mapPanelMode !== "collapsed" && hasAddr && hasSelection && upperOnly ? (
        <p className="text-[11px] text-slate-500">시군구 이상 복수지역 선택 불가.</p>
      ) : null}
      {mapPanelMode !== "collapsed" && hasAddr && hasSelection && canMultiAdd ? (
        <p className="text-[11px] text-slate-500">
          인접 구역 추가: 지도에서{" "}
          <strong className="font-semibold text-slate-700">클릭</strong> 또는{" "}
          <strong className="font-semibold text-slate-700">우클릭</strong> → 확인
        </p>
      ) : null}
      {mapPanelMode !== "collapsed" && hasAddr && resolveQ.isSuccess && !hasSelection ? (
        <p className="text-[11px] text-amber-700">
          이 범위에 매핑된 행정코드가 없습니다. (코드 미부착 거래일 수 있습니다)
        </p>
      ) : null}
      {mapPanelMode !== "collapsed" && boundariesQ.isError ? (
        <p className="text-xs text-red-600">
          행정 경계를 불러오지 못했습니다. VWorld 키·도메인 등록을 확인하세요.
        </p>
      ) : null}
    </div>
  );
}
