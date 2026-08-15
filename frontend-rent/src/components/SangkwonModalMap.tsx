import bbox from "@turf/bbox";
import { useEffect, useMemo, useRef } from "react";
import MapGL, { Layer, Marker, Source, type MapRef } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { vworldSatelliteTileUrl } from "../api/mapClient";
import { applySelectionFitBounds, boundsFromGeoJson } from "../utils/mapFitBounds";

const VWORLD_KEY = (import.meta.env.VITE_VWORLD_API_KEY ?? "").trim();

type Props = {
  adminFeatures: GeoJSON.Feature[];
  sangkwonFeatures: GeoJSON.Feature[];
  selected: string | null;
  onSelect: (name: string) => void;
};

function featureName(f: GeoJSON.Feature): string {
  return String(f.properties?.sec_nm ?? "").trim();
}

function labelPoint(f: GeoJSON.Feature): { lng: number; lat: number } | null {
  try {
    const [w, s, e, n] = bbox(f);
    if (![w, s, e, n].every(Number.isFinite)) return null;
    return { lng: (w + e) / 2, lat: (s + n) / 2 };
  } catch {
    return null;
  }
}

export default function SangkwonModalMap({
  adminFeatures,
  sangkwonFeatures,
  selected,
  onSelect,
}: Props) {
  const mapRef = useRef<MapRef | null>(null);
  const boxRef = useRef<HTMLDivElement | null>(null);

  const adminFc = useMemo(
    (): GeoJSON.FeatureCollection => ({ type: "FeatureCollection", features: adminFeatures }),
    [adminFeatures],
  );

  const sangkwonFc = useMemo((): GeoJSON.FeatureCollection => {
    const features = sangkwonFeatures.map((f) => ({
      ...f,
      properties: {
        ...f.properties,
        ch2_sk_selected: featureName(f) === selected ? 1 : 0,
      },
    }));
    return { type: "FeatureCollection", features };
  }, [sangkwonFeatures, selected]);

  const tileUrl = VWORLD_KEY ? vworldSatelliteTileUrl(VWORLD_KEY) : undefined;
  const mapStyle = useMemo(
    () => ({
      version: 8 as const,
      sources: {
        basemap: {
          type: "raster" as const,
          tiles: [tileUrl ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: tileUrl ? "© VWorld" : "© OpenStreetMap",
        },
      },
      layers: [{ id: "basemap", type: "raster" as const, source: "basemap" }],
    }),
    [tileUrl],
  );

  const fitKey = useMemo(
    () =>
      [
        selected ?? "",
        ...sangkwonFeatures.map(featureName).sort(),
        adminFeatures.length,
      ].join("|"),
    [selected, sangkwonFeatures, adminFeatures.length],
  );

  useEffect(() => {
    const map = mapRef.current?.getMap();
    const el = boxRef.current;
    if (!map || !el) return;
    const selectedFeat = selected
      ? sangkwonFeatures.find((f) => featureName(f) === selected)
      : null;
    const fitFc: GeoJSON.FeatureCollection = selectedFeat
      ? { type: "FeatureCollection", features: [selectedFeat] }
      : sangkwonFc.features.length
        ? sangkwonFc
        : adminFc;
    const bounds = boundsFromGeoJson(fitFc);
    if (!bounds) return;
    const run = () => {
      map.resize();
      applySelectionFitBounds(map, {
        bounds,
        containerWidthPx: el.clientWidth,
        level: "sigungu",
        duration: 500,
      });
    };
    const t = window.setTimeout(run, 80);
    return () => window.clearTimeout(t);
  }, [fitKey, adminFc, sangkwonFc, sangkwonFeatures, selected]);

  return (
    <div ref={boxRef} className="relative h-56 w-full overflow-hidden rounded-lg border border-slate-200 dark:border-slate-600">
      <MapGL
        ref={mapRef}
        initialViewState={{ longitude: 127.8, latitude: 36.2, zoom: 9, pitch: 0, bearing: 0 }}
        style={{ width: "100%", height: "100%" }}
        mapStyle={mapStyle as never}
        dragPan
        dragRotate={false}
        interactiveLayerIds={sangkwonFc.features.length ? ["sk-fill"] : []}
        onClick={(evt) => {
          const name = String(evt.features?.[0]?.properties?.sec_nm ?? "").trim();
          if (name) onSelect(name);
        }}
        attributionControl={false}
      >
        {adminFc.features.length ? (
          <Source id="sk-admin" type="geojson" data={adminFc}>
            <Layer
              id="sk-admin-line"
              type="line"
              paint={{
                "line-color": "#f59e0b",
                "line-width": 2,
                "line-opacity": 0.9,
              }}
            />
          </Source>
        ) : null}
        {sangkwonFc.features.length ? (
          <Source id="sk-poly" type="geojson" data={sangkwonFc}>
            <Layer
              id="sk-fill"
              type="fill"
              paint={{
                "fill-color": [
                  "case",
                  ["==", ["get", "ch2_sk_selected"], 1],
                  "#0d9488",
                  "#14b8a6",
                ],
                "fill-opacity": [
                  "case",
                  ["==", ["get", "ch2_sk_selected"], 1],
                  0.32,
                  0.12,
                ],
              }}
            />
            <Layer
              id="sk-line"
              type="line"
              paint={{
                "line-color": [
                  "case",
                  ["==", ["get", "ch2_sk_selected"], 1],
                  "#0f766e",
                  "#5eead4",
                ],
                "line-width": ["case", ["==", ["get", "ch2_sk_selected"], 1], 2.4, 1.4],
              }}
            />
          </Source>
        ) : null}
        {sangkwonFeatures.map((f) => {
          const name = featureName(f);
          const pt = labelPoint(f);
          if (!name || !pt) return null;
          const on = name === selected;
          return (
            <Marker key={name} longitude={pt.lng} latitude={pt.lat} anchor="center">
              <button
                type="button"
                className={`max-w-[7rem] truncate rounded px-1 py-0.5 text-[10px] font-semibold shadow-sm ${
                  on
                    ? "bg-teal-600 text-white"
                    : "bg-slate-900/75 text-white"
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(name);
                }}
              >
                {name}
              </button>
            </Marker>
          );
        })}
      </MapGL>
    </div>
  );
}
