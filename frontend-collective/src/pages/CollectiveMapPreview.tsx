import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import MapGL, { Marker, NavigationControl, type MapRef } from "react-map-gl/maplibre";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { fetchAddr2, fetchBuildings } from "../api/client";
import { fetchCommercialAddr2, fetchCommercialClusters } from "../api/commercialClient";
import { fetchCollectiveBuildingMapPoints, fetchCommercialRoadMapPoints, vworldSatelliteTileUrl } from "../api/mapClient";
import { buildingDisplayName } from "../utils/buildingName";
import "./CollectiveMapPreview.css";

const SEOUL = "서울특별시";
const START = { longitude: 127.035, latitude: 37.525, zoom: 12.1 };
const LIST_LIMIT = 30;
const FORMAT = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });

type Kind = "apartment" | "shop";
type Position = { longitude: number; latitude: number };
type Place = { id: string; kind: Kind; name: string; mean: number | null; count: number; note?: string; position?: Position };
const NAMES = { apartment: "아파트 단지", shop: "집합상가 도로" };
const DEMO: Place[] = [
  ["apartment", "예시 아파트 A", 2410, 43, -0.017, 0.012],
  ["apartment", "예시 아파트 B", 1915, 31, 0.018, 0.004],
  ["apartment", "예시 아파트 C", 2240, 27, 0.005, -0.014],
  ["shop", "예시 상가길 A", 3150, 26, -0.006, 0.005],
  ["shop", "예시 상가길 B", 1830, 18, 0.015, -0.008],
  ["shop", "예시 상가길 C", 2460, 12, -0.016, -0.009],
].map(([kind, name, mean, count, dx, dy], index) => ({
  id: String(index), kind: kind as Kind, name: String(name), mean: Number(mean), count: Number(count),
  position: { longitude: START.longitude + Number(dx), latitude: START.latitude + Number(dy) },
}));

function price(value: number | null) {
  return value == null ? "—" : FORMAT.format(value);
}

function createMapStyle(): StyleSpecification {
  const key = (import.meta.env.VITE_VWORLD_API_KEY ?? "").trim();
  const tiles = key ? [vworldSatelliteTileUrl(key)] : [];
  return {
    version: 8,
    sources: tiles.length ? {
      vworld: { type: "raster", tiles, tileSize: 256, attribution: "© VWorld" },
    } : {},
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#e8edf0" } },
      ...(tiles.length ? [{ id: "vworld", type: "raster" as const, source: "vworld" }] : []),
    ],
  };
}

const MAP_STYLE = createMapStyle();

export default function CollectiveMapPreview() {
  const [demo, setDemo] = useState(() => new URLSearchParams(window.location.search).get("data") !== "live");
  const [district, setDistrict] = useState("");
  const [years, setYears] = useState(5);
  const [visible, setVisible] = useState<Record<Kind, boolean>>({ apartment: true, shop: true });
  const [selected, setSelected] = useState<Place | null>(null);
  const map = useRef<MapRef>(null);

  const districts = useQuery({
    queryKey: ["collective-map-preview", "seoul-districts"],
    queryFn: async () => {
      const results = await Promise.allSettled([
        fetchAddr2(SEOUL, "apartment"), fetchCommercialAddr2(SEOUL, "collective_shop"),
      ]);
      const list = results.flatMap((result) => result.status === "fulfilled" ? result.value : []);
      if (!list.length && results.some((result) => result.status === "rejected")) throw new Error("지역 조회 실패");
      return [...new Set(list)].sort((a, b) => a.localeCompare(b, "ko"));
    },
    enabled: !demo,
    retry: false,
  });
  const effectiveDistrict = district || (districts.data?.includes("강남구") ? "강남구" : districts.data?.[0]) || "";
  const scope = { addr1: SEOUL, addr2: effectiveDistrict, window_years: years, page_size: LIST_LIMIT, sort: "count" };
  const enabled = !demo && Boolean(effectiveDistrict);
  const buildings = useQuery({
    queryKey: ["collective-map-preview", "apartment", effectiveDistrict, years],
    queryFn: () => fetchBuildings({ ...scope, asset_type: "apartment" }),
    enabled,
    retry: false,
  });
  const roads = useQuery({
    queryKey: ["collective-map-preview", "shop", effectiveDistrict, years],
    queryFn: () => fetchCommercialClusters({ ...scope, asset_type: "collective_shop" }),
    enabled,
    retry: false,
  });
  const buildingsOnMap = useQuery({
    queryKey: ["collective-map-preview", "building-points", effectiveDistrict, buildings.data?.items.map((row) => row.building_key)],
    queryFn: () => fetchCollectiveBuildingMapPoints((buildings.data?.items ?? []).map((row) => ({
      building_key: row.building_key, label: buildingDisplayName(row), addr1: SEOUL, addr2: effectiveDistrict,
      jibun_address: row.jibun_address || row.address || null, road_address: row.road_address || null,
    })), true),
    enabled: enabled && !!buildings.data?.items.length,
    retry: false,
  });
  const roadsOnMap = useQuery({
    queryKey: ["collective-map-preview", "road-points", effectiveDistrict, roads.data?.items.map((row) => row.cluster_key)],
    queryFn: () => fetchCommercialRoadMapPoints((roads.data?.items ?? []).flatMap((row) => row.road_name ? [{
      cluster_key: row.cluster_key, label: row.display_label, addr1: SEOUL, addr2: effectiveDistrict,
      road_name: row.road_name, addr3: row.addr3, addr4: row.addr4,
    }] : []), true),
    enabled: enabled && !!roads.data?.items.some((row) => row.road_name),
    retry: false,
  });

  const places = useMemo<Place[]>(() => {
    if (demo) return DEMO;
    const aptPositions = new Map((buildingsOnMap.data?.points ?? []).map((p) => [p.building_key, p]));
    const shopPositions = new Map((roadsOnMap.data?.points ?? []).map((p) => [p.cluster_key, p]));
    return [
      ...(buildings.data?.items ?? []).map((row): Place => ({
        id: row.building_key, kind: "apartment", name: buildingDisplayName(row),
        mean: row.mean ?? null, count: row.count, position: aptPositions.get(row.building_key),
      })),
      ...(roads.data?.items ?? []).map((row): Place => ({
        id: row.cluster_key, kind: "shop", name: row.road_name || row.display_label,
        mean: row.mean ?? null, count: row.count, note: [row.addr3, row.addr4].filter(Boolean).join(" · "),
        position: shopPositions.get(row.cluster_key),
      })),
    ];
  }, [demo, buildings.data, roads.data, buildingsOnMap.data, roadsOnMap.data]);

  useEffect(() => {
    const positions = places.flatMap((place) => place.position ? [place.position] : []);
    if (positions.length === 0) return;
    const longitude = positions.map((p) => p.longitude);
    const latitude = positions.map((p) => p.latitude);
    map.current?.fitBounds(
      [[Math.min(...longitude), Math.min(...latitude)], [Math.max(...longitude), Math.max(...latitude)]],
      { padding: 64, maxZoom: 14, duration: 0 },
    );
  }, [places]);

  function select(place: Place) {
    setSelected(place);
    if (place.position) map.current?.easeTo({ center: [place.position.longitude, place.position.latitude], duration: 400 });
  }

  const base = import.meta.env.BASE_URL;
  const regionsPending = !demo && districts.isFetching;
  const pending = enabled && (buildings.isFetching || roads.isFetching);
  const mapped = places.filter((place) => place.position && visible[place.kind]);
  const selectedPlace = selected && visible[selected.kind]
    ? places.find((place) => place.id === selected.id && place.kind === selected.kind)
    : undefined;
  const periods = [buildings.data, roads.data].map((response) =>
    response?.period_start && response.period_end ? response.period_start + " ~ " + response.period_end : null);
  const periodsDiffer = Boolean(periods[0] && periods[1] && periods[0] !== periods[1]);

  return (
    <main className="cmp">
      <header className="cmp-header">
        <div>
          <p className="cmp-brand">CH2 MACRO · 시험 페이지</p>
          <h1>집합부동산 가격 지도</h1>
          <p>아파트 단지와 집합상가 도로의 평균 거래단가를 한 지도에서 확인합니다.</p>
        </div>
        <nav aria-label="기존 집합 화면">
          <a href={base + "residential/"}>주거용 집합</a>
          <a href={base + "commercial/"}>비주거용 집합</a>
        </nav>
      </header>

      <section className="cmp-controls" aria-label="지도 조회 조건">
        <div className="cmp-switch" aria-label="데이터 모드">
          <button type="button" aria-pressed={demo} onClick={() => { setDemo(true); setSelected(null); }}>예시 데이터</button>
          <button type="button" aria-pressed={!demo} onClick={() => { setDemo(false); setSelected(null); }}>실거래 조회</button>
        </div>
        {demo ? <p>서울을 배경으로 배치한 예시 가격과 위치입니다.</p> : (
          <>
            <label>서울 자치구
              <select value={effectiveDistrict} onChange={(e) => { setDistrict(e.target.value); setSelected(null); }}>
                {!districts.data?.length && <option value="">자치구</option>}
                {districts.data?.map((value) => <option key={value}>{value}</option>)}
              </select>
            </label>
            <label>거래기간
              <select value={years} onChange={(e) => { setYears(Number(e.target.value)); setSelected(null); }}>
                <option value={5}>최근 5년</option><option value={3}>최근 3년</option>
              </select>
            </label>
            <p>유형별 거래 건수 상위 {LIST_LIMIT}개</p>
          </>
        )}
      </section>

      {regionsPending && <p role="status" className="cmp-status">서울 자치구를 불러오는 중입니다.</p>}
      {!demo && districts.isError && <p role="alert" className="cmp-status">지역을 불러오지 못했습니다. Macro API 연결을 확인하거나 예시 데이터를 볼 수 있습니다.</p>}
      {periodsDiffer && <p role="status" className="cmp-status">유형별 실제 집계기간이 다릅니다. 각 목록의 기간을 확인하세요.</p>}

      <div className="cmp-content">
        <section className="cmp-map" aria-label="집합부동산 가격 지도">
          <MapGL ref={map} initialViewState={START} mapStyle={MAP_STYLE} style={{ width: "100%", height: "100%" }} dragRotate={false} pitchWithRotate={false}>
            <NavigationControl position="bottom-right" showCompass={false} />
            {mapped.map((place) => place.position && (
              <Marker key={place.kind + place.id} {...place.position} anchor="bottom">
                <button className={"cmp-pin " + place.kind} type="button" onClick={() => select(place)} title={place.name} aria-label={place.name + " " + price(place.mean) + " 만원/㎡"} aria-pressed={selectedPlace?.id === place.id && selectedPlace.kind === place.kind}>
                  {price(place.mean)}
                </button>
              </Marker>
            ))}
          </MapGL>
          <div className="cmp-legend">
            {(["apartment", "shop"] as const).map((kind) => (
              <label key={kind}>
                <input type="checkbox" checked={visible[kind]} onChange={(e) => setVisible({ ...visible, [kind]: e.target.checked })} />
                <span className={"cmp-dot " + kind} />{NAMES[kind]}
              </label>
            ))}
            <small>평균 · 만원/㎡</small>
          </div>
          {selectedPlace && (
            <aside className="cmp-selection" aria-label="선택한 거래 통계">
              <button type="button" onClick={() => setSelected(null)} aria-label="선택 닫기">×</button>
              <small>{NAMES[selectedPlace.kind]}{selectedPlace.note ? " · " + selectedPlace.note : ""}</small>
              <strong>{selectedPlace.name}</strong>
              <span>평균 {price(selectedPlace.mean)}만원/㎡ · {FORMAT.format(selectedPlace.count)}건</span>
              {!selectedPlace.position && <small>표시할 지도 위치를 찾지 못했습니다.</small>}
            </aside>
          )}
        </section>

        <aside className="cmp-results" aria-label="유형별 결과">
          {pending && <p role="status">가격을 불러오는 중입니다.</p>}
          {(["apartment", "shop"] as const).filter((kind) => visible[kind]).map((kind) => {
            const rows = places.filter((place) => place.kind === kind);
            const response = kind === "apartment" ? buildings : roads;
            const positionQuery = kind === "apartment" ? buildingsOnMap : roadsOnMap;
            const period = periods[kind === "apartment" ? 0 : 1];
            const mappedCount = rows.filter((row) => row.position).length;
            return (
              <section key={kind}>
                <h2><span className={"cmp-dot " + kind} />{NAMES[kind]}</h2>
                {period && !demo && <p className="cmp-period">{period}</p>}
                {!demo && enabled && response.isError && <p role="alert">통계를 불러오지 못했습니다.</p>}
                {!demo && positionQuery.isError && <p role="alert">저장된 위치를 불러오지 못했습니다.</p>}
                {!demo && enabled && response.isSuccess && !rows.length && <p>거래가 없습니다.</p>}
                {rows.length > 0 && (
                  <>
                    <p className="cmp-period">{rows.length}개 표시 · 지도 {mappedCount}개{!demo && positionQuery.isFetching ? " · 위치 확인 중" : ""}</p>
                    <ul>
                      {rows.map((place) => (
                        <li key={place.id}>
                          <button type="button" onClick={() => select(place)} aria-pressed={selectedPlace?.id === place.id && selectedPlace.kind === place.kind}>
                            <span><strong>{place.name}</strong><small>{place.note ? place.note + " · " : ""}{FORMAT.format(place.count)}건</small></span>
                            <b>{price(place.mean)}</b>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </section>
            );
          })}
        </aside>
      </div>
      <footer>단가 면적 기준 · 아파트 전용면적 / 집합상가 원천 전용·연면적. 상가 위치는 도로의 대표점입니다.</footer>
    </main>
  );
}
