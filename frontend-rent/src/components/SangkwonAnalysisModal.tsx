import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSangkwonAnnual, fetchSangkwonPolygons } from "../api/client";
import { buildSangkwonContext } from "../api/aiContext";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { fetchCollectiveMapResolveCodes, fetchMapBoundaries } from "../api/mapClient";
import { formatScopeAddr2 } from "../utils/flatSidoRegion";
import { filterAdminFeaturesByCodes, sangkwonHitsForAdmin } from "../utils/sangkwonIntersect";
import DraggableModalShell from "./DraggableModalShell";
import SangkwonModalMap from "./SangkwonModalMap";
import SangkwonPanel from "./SangkwonPanel";
import SangkwonTrendModal from "./SangkwonTrendModal";

export type SangkwonAnalysisScope = {
  addr1: string;
  addr2: string;
  /** 청주 등: 구. 동만 골랐으면 부모 구. 강남구처럼 시군구가 addr2면 빈 배열. */
  sangkwonGuList: string[];
};

type Props = {
  scope: SangkwonAnalysisScope;
  onClose: () => void;
};

export function sangkwonScopeLabel(scope: SangkwonAnalysisScope): string {
  if (scope.sangkwonGuList.length) return scope.sangkwonGuList.join(", ");
  return formatScopeAddr2(scope.addr2, scope.addr1) || scope.addr1;
}

export default function SangkwonAnalysisModal({ scope, onClose }: Props) {
  const regionLabel = sangkwonScopeLabel(scope);
  const [selected, setSelected] = useState<string | null>(null);
  const [showTrend, setShowTrend] = useState(false);

  const resolveQ = useQuery({
    queryKey: ["sangkwon-resolve", scope.addr1, scope.addr2, scope.sangkwonGuList],
    queryFn: () =>
      fetchCollectiveMapResolveCodes({
        addr1: scope.addr1,
        addr2: scope.addr2,
        gu: scope.sangkwonGuList,
        leaf: [],
      }),
  });

  const boundsQ = useQuery({
    queryKey: [
      "sangkwon-bounds",
      resolveQ.data?.level,
      resolveQ.data?.selected_codes,
      resolveQ.data?.context_sido_code,
      resolveQ.data?.context_sigungu_code,
    ],
    queryFn: () =>
      fetchMapBoundaries({
        level: resolveQ.data!.level!,
        selected: resolveQ.data!.selected_codes,
        contextSidoCode: resolveQ.data!.context_sido_code,
        contextSigunguCode: resolveQ.data!.context_sigungu_code,
      }),
    enabled: Boolean(resolveQ.data?.has_selection && resolveQ.data.level),
  });

  const polyQ = useQuery({
    queryKey: ["sangkwon-polygons", scope.addr1],
    queryFn: () => fetchSangkwonPolygons(scope.addr1),
    staleTime: 60 * 60 * 1000,
  });

  const adminFeatures = useMemo(
    () =>
      filterAdminFeaturesByCodes(
        boundsQ.data?.feature_collection?.features ?? [],
        resolveQ.data?.selected_codes ?? [],
      ),
    [boundsQ.data, resolveQ.data?.selected_codes],
  );

  const hits = useMemo(
    () =>
      sangkwonHitsForAdmin(
        adminFeatures,
        polyQ.data?.features?.length
          ? { type: "FeatureCollection", features: polyQ.data.features }
          : null,
      ),
    [adminFeatures, polyQ.data],
  );

  const hitPolys = useMemo(() => {
    const names = new Set(hits.map((h) => h.sec_nm));
    return (polyQ.data?.features ?? []).filter((f) =>
      names.has(String(f.properties?.sec_nm ?? "").trim()),
    );
  }, [hits, polyQ.data]);

  useEffect(() => {
    setSelected((prev) => {
      if (prev && hits.some((h) => h.sec_nm === prev)) return prev;
      return hits[0]?.sec_nm ?? null;
    });
  }, [hits]);

  const annualQ = useQuery({
    queryKey: ["sangkwon-annual", selected],
    queryFn: () => fetchSangkwonAnnual(selected!),
    enabled: !!selected,
  });

  const sangkwonAiContext = useMemo(() => {
    if (!selected || !annualQ.data) return null;
    return buildSangkwonContext({
      regionLabel,
      secNm: selected,
      year: annualQ.data.year,
      windowLabel: annualQ.data.window_label,
      rows: annualQ.data.rows,
    });
  }, [selected, annualQ.data, regionLabel]);

  const loading = resolveQ.isLoading || boundsQ.isLoading || polyQ.isLoading;

  return (
    <>
      <PublishAiContext context={sangkwonAiContext} />
      <DraggableModalShell
        open
        onClose={onClose}
        titleId="sangkwon-analysis"
        title="상권통계"
        subtitle={`${regionLabel} · 한국부동산원 상업용 임대동향 · 주거 전월세와 다른 통계`}
        usePortal
        resizable
        allowFullscreen
        allowFontScale
        defaultWidth={980}
        defaultHeight={760}
        minWidth={480}
        minHeight={360}
        bodyClassName="flex-1 min-h-0 overflow-hidden px-4 py-3 flex flex-col"
      >
        {loading && <p className="text-sm text-slate-500">상권 경계를 찾는 중…</p>}
        {resolveQ.isError && (
          <p className="text-sm text-red-600">시군구 경계를 불러오지 못했습니다.</p>
        )}
        {!loading && !hits.length && (
          <div className="rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-3 py-3 space-y-2 text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
            <p className="font-medium">
              {regionLabel} 인근에는 부동산원 대표 상권이 없습니다.
            </p>
            <p>
              상권통계는 읍·면·동이 아니라 시군구(구) 경계 기준입니다. 해당 시군구와 겹치는
              공표 상권이 없으면 오류가 아니라 인근에 상권이 없는 것입니다.
            </p>
          </div>
        )}
        {hits.length > 0 && (
          <div className="flex flex-col gap-2 min-h-0 flex-1 h-full">
            <div className="min-h-[14rem] h-[40%] shrink-0">
              <SangkwonModalMap
                adminFeatures={adminFeatures}
                sangkwonFeatures={hitPolys}
                selected={selected}
                onSelect={setSelected}
              />
            </div>
            <p className="text-[10px] text-slate-400 shrink-0">
              노란 선은 {regionLabel} 경계. 청록은 교차 상권 · 클릭 또는 칩으로 선택.
            </p>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <SangkwonPanel
                hits={hits}
                selected={selected}
                onSelect={setSelected}
                onOpenTrend={() => setShowTrend(true)}
                annual={annualQ.data}
                loading={annualQ.isLoading}
              />
            </div>
          </div>
        )}
      </DraggableModalShell>
      {showTrend && selected && (
        <SangkwonTrendModal name={selected} onClose={() => setShowTrend(false)} />
      )}
    </>
  );
}
