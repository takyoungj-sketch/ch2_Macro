import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRegions } from "../api/client";
import { useAppStore } from "../store";
import {
  resolveBeopjungriFromLooseAddressLine,
  isLooseMultiSegmentQuery,
  commonTierCodesFromLooseRows,
} from "../utils/resolveLooseAddressLine";
import { tryResolveUniqueRegionSearch } from "../utils/resolveUniqueRegionNameSearch";
import { statsScopeKeyFromBeopjungriCodes } from "../utils/statsScopeKey";
import type { RegionItem } from "../types";
import { formatRegionHierarchyLabel } from "../utils/regionDisplay";
import FreeStatsWindowToggle from "./FreeStatsWindowToggle";
import { buildFlattenedRegionSuggestions, type RegionSearchFlatEntry } from "../utils/regionSearchSuggest";
import {
  resolveUnionBeopjungriCodes,
  paidSubSigunguSelectionsCount,
  reconcilePaidSubSigunguPickOrder,
} from "../utils/regionTier";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { MAX_PAID_LEAF_BEOPJUNGRI_PICK } from "../constants/tierPickLimits";
import { cityBucketFromSigungu } from "../utils/cityBucket";
import { isSejongPseudoSigunguCode } from "../utils/sejongRegion";
import { resolveProfileRegionFromTier } from "../utils/upperTierStats";

function labelSigunguChip(regions: RegionItem[], code: string): string {
  const c = String(code).trim();
  if (isSejongPseudoSigunguCode(c)) {
    const row = regions.find((r) => isSejongPseudoSigunguCode(String(r.sigungu_code ?? "").trim()));
    const sido = row?.sido_name ? String(row.sido_name).trim() : "세종특별자치시";
    return `${sido} 전체`;
  }
  const row = regions.find((r) => String(r.sigungu_code ?? "").trim() === c);
  if (!row) return c;
  return [row.sido_name, row.sigungu_name]
    .map((x) => String(x ?? "").trim())
    .filter(Boolean)
    .join(" ");
}

function labelEupChip(regions: RegionItem[], code: string): string {
  const c = String(code).trim();
  const row = regions.find((r) => String(r.eupmyeondong_code ?? "").trim() === c);
  if (!row) return c;
  return [row.sido_name, row.sigungu_name, row.eupmyeondong_name]
    .map((x) => String(x ?? "").trim())
    .filter(Boolean)
    .join(" ");
}

function labelSidoChip(regions: RegionItem[], code: string): string {
  const c = String(code).trim();
  const row = regions.find((r) => String(r.sido_code ?? "").trim() === c);
  return row?.sido_name ? String(row.sido_name).trim() : c;
}

function labelCityChip(regions: RegionItem[], cityCode: string): string {
  const c = String(cityCode).trim();
  const row = regions.find(
    (r) => cityBucketFromSigungu(String(r.sigungu_code ?? "")) === c
  );
  if (!row) return c;
  const toks = String(row.sigungu_name ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  const head = toks[0] ?? "";
  const cityTok = /시$/.test(head) ? head : head || c;
  return [row.sido_name, cityTok].map((x) => String(x ?? "").trim()).filter(Boolean).join(" ");
}

export default function RegionSelector() {
  const {
    viewMode,
    tierSelection,
    paidSubSigunguPickOrder,
    clearTierSelection,
    applyBeopjungriCodes,
    kickPaidBasicStatsAnalysis,
    commitStatsDisplayScope,
    addPickedBeopjungri,
    removePickedBeopjungri,
    mergePickedSigunguCodes,
    mergePickedEupmyeondongCodes,
    mergePickedSidoCodes,
    mergePickedCityCodes,
    removePickedSigungu,
    removePickedEupmyeondong,
    removePickedSido,
    removePickedCity,
    replacePaidLeafBeopjungri,
    replacePaidLeafEupmyeondong,
  } = useAppStore();

  const [localError, setLocalError] = useState<string | null>(null);
  /** 유료: 법정동·리를 하나 추가한 뒤에는 검색 확정 여부 재개 전까지 다음 동·리를 직접 검색 추가할 수 없음. (+ 추가 지역 선택으로 해제.) */
  const [paidLeafAddGateOpen, setPaidLeafAddGateOpen] = useState(true);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const [suggestionsCollapsed, setSuggestionsCollapsed] = useState(false);
  const [suggestionsShortHeight, setSuggestionsShortHeight] = useState(false);
  const listRef = useRef<HTMLUListElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const { data: regions = [], isLoading: catalogLoading } = useQuery({
    queryKey: REGIONS_CATALOG_QUERY_KEY,
    queryFn: () => fetchRegions(),
    staleTime: 6 * 60 * 60 * 1000,
  });

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(searchInput.trim()), 280);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    setHighlightIdx(-1);
    setSuggestionsCollapsed(false);
    setSuggestionsShortHeight(false);
  }, [debouncedSearch]);

  const searchPanelOpen = debouncedSearch.trim().length >= 2;
  const apiSearchEnabled =
    debouncedSearch.length >= 2 && !isLooseMultiSegmentQuery(debouncedSearch);

  const { data: searchHits = [], isFetching: searchFetching } = useQuery({
    queryKey: ["regions", "search", debouncedSearch],
    queryFn: () =>
      fetchRegions({ search: debouncedSearch, limit: 400 }),
    enabled: apiSearchEnabled,
    staleTime: 60_000,
  });

  const looseResolve = useMemo(() => {
    if (!isLooseMultiSegmentQuery(debouncedSearch)) return null;
    if (regions.length === 0) return null;
    return resolveBeopjungriFromLooseAddressLine(regions, debouncedSearch);
  }, [debouncedSearch, regions]);

  const flatSuggestions = useMemo((): RegionSearchFlatEntry[] => {
    if (looseResolve != null) {
      if (looseResolve.codes.length <= 1) return [];
      const map = new Map<string, RegionItem>();
      for (const r of looseResolve.rows) {
        const c = String(r.beopjungri_code ?? "").trim();
        if (!c) continue;
        if (!map.has(c)) map.set(c, r);
      }
      return [...map.values()]
        .sort((a, b) =>
          formatRegionHierarchyLabel(a).localeCompare(formatRegionHierarchyLabel(b), "ko-KR")
        )
        .map((row) => ({ kind: "beopjungri" as const, row }));
    }
    return buildFlattenedRegionSuggestions(searchHits, debouncedSearch, {
      maxSigungu: 50,
      maxAgg: 40,
      maxBeop: 400,
    });
  }, [looseResolve, searchHits, debouncedSearch]);

  const resolvedUnionCodes = useMemo(
    () => resolveUnionBeopjungriCodes(regions, tierSelection),
    [regions, tierSelection]
  );

  const pickedCodes = tierSelection.beopjungri_codes.map((x) => x.trim()).filter(Boolean);

  /** 읍·면·동 행정 칩 + 법정동·리 줄 수의 합(시도·군구 위가 아닌 시군구 미만만). 최대 선택 한도 카운터에 사용 */
  const paidSubSigunguSelections = paidSubSigunguSelectionsCount(tierSelection);

  useEffect(() => {
    if (viewMode !== "paid") return;
    if (paidSubSigunguSelections === 0) setPaidLeafAddGateOpen(true);
  }, [viewMode, paidSubSigunguSelections]);

  /** 동일 이름이 이미 있으면 true — 게이트와 무관히 허용(반복 선택 무비용 정리 동작 유지). */
  const leafAlreadySelected = (code: string): boolean =>
    pickedCodes.includes(String(code ?? "").trim());

  /** 시·도·[시]·시군구 행정 칩(읍·면 단위 칩 제외 — 시군구 미만 혼합용). */
  const strictUpperTierChipCount =
    tierSelection.sido_codes.length +
    tierSelection.city_codes.length +
    tierSelection.sigungu_codes.length;

  /** 모든 상위 행정 칩(읍·면 포함 표시 카운팅 등). */
  const upperTierChipCount =
    strictUpperTierChipCount + tierSelection.eupmyeondong_codes.length;

  /** 유료: 시도·군구 위가 없고 시군구 미만 선택이 1개 이상일 때 「+ 추가」 없이 검색하면 교체. */
  const paidReplaceLeafWithoutPlus = (): boolean =>
    viewMode === "paid" &&
    strictUpperTierChipCount === 0 &&
    paidSubSigunguSelections >= 1 &&
    !paidLeafAddGateOpen;

  /** 칩 또는 목록 한 줄이라도 채워지면 비어 있지 않음(유료에서는 법정동·리는 아래 목록으로 표시). */
  const selectionChipCount = upperTierChipCount + tierSelection.beopjungri_codes.length;
  /** 시군구 미만 슬롯 가운데 아직 채울 수 있는 개수. */
  const paidExtraRegionsRemaining =
    MAX_PAID_LEAF_BEOPJUNGRI_PICK - paidSubSigunguSelections;
  /** 유료 시군구 미만: 읍면·법정을 한 줄에 세우기 위한 순서(스토어 + tier 정합 반영). */
  const paidUnifiedSubSigunguRows = useMemo(
    () =>
      viewMode === "paid" && strictUpperTierChipCount === 0
        ? reconcilePaidSubSigunguPickOrder(paidSubSigunguPickOrder, tierSelection)
        : [],
    [viewMode, strictUpperTierChipCount, paidSubSigunguPickOrder, tierSelection]
  );

  const resolvedCount = resolvedUnionCodes.length;

  const labelForCode = (code: string) => {
    const c = String(code).trim();
    const row = regions.find((r) => String(r.beopjungri_code).trim() === c);
    return row ? formatRegionHierarchyLabel(row) : c;
  };

  const finishLeafPick = () => {
    setSearchInput("");
    setDebouncedSearch("");
    setHighlightIdx(-1);
    inputRef.current?.focus();
  };

  const pickBeopRow = (r: RegionItem) => {
    setLocalError(null);
    const c = String(r.beopjungri_code ?? "").trim();
    if (!c) return;

    if (viewMode === "free") {
      addPickedBeopjungri(r.beopjungri_code);
      setPaidLeafAddGateOpen(true);
      finishLeafPick();
      return;
    }

    if (viewMode === "profile") {
      replacePaidLeafBeopjungri(c);
      finishLeafPick();
      return;
    }

    const cur = pickedCodes;
    if (leafAlreadySelected(c)) {
      finishLeafPick();
      return;
    }
    if (paidReplaceLeafWithoutPlus()) {
      replacePaidLeafBeopjungri(c);
      setPaidLeafAddGateOpen(false);
      finishLeafPick();
      return;
    }
    const eupSlots = tierSelection.eupmyeondong_codes.map((x) => x.trim()).filter(Boolean).length;
    if (eupSlots + cur.length >= MAX_PAID_LEAF_BEOPJUNGRI_PICK) {
      setLocalError(
        `시군구 미만 선택(읍·면·동 행정 단위와 법정동·리 줄 합산)은 최대 ${MAX_PAID_LEAF_BEOPJUNGRI_PICK}곳까지입니다. 칩·목록에서 지우거나 시·도·군구 단위로 바꿔 주세요.`
      );
      return;
    }
    addPickedBeopjungri(r.beopjungri_code);
    setPaidLeafAddGateOpen(false);
    finishLeafPick();
  };

  const handlePickSigunguAggregate = (sigunguCode: string) => {
    setLocalError(null);
    if (viewMode === "free") {
      setLocalError(
        "무료 통계는 법정동·리 한 곳만 선택할 수 있습니다. 목록에서 특정 법정단위를 고르거나, 유료에서 「시군구 포함」을 이용해 주세요."
      );
      return;
    }
    const ok = mergePickedSigunguCodes([sigunguCode], regions);
    if (!ok) {
      setLocalError(
        `추가하지 못했습니다. 시·군·구 칩은 한 번에 하나만 선택할 수 있습니다. 시군구 미만은 법정동·리 줄과 읍·면 행정 칩을 합쳐 최대 ${MAX_PAID_LEAF_BEOPJUNGRI_PICK}곳까지 복수할 수 있습니다.`
      );
      return;
    }
    setSearchInput("");
    setDebouncedSearch("");
    setHighlightIdx(-1);
    inputRef.current?.focus();
  };

  const handlePickSidoAggregate = (sidoCode: string) => {
    setLocalError(null);
    if (viewMode === "free") {
      setLocalError(
        "무료 통계는 법정동·리 한 곳만 선택할 수 있습니다. 유료에서 시·도 단위를 이용해 주세요."
      );
      return;
    }
    const ok = mergePickedSidoCodes([sidoCode], regions);
    if (!ok) {
      setLocalError("추가하지 못했습니다. 이미 있거나 선택 상한을 넘깁니다.");
      return;
    }
    setSearchInput("");
    setDebouncedSearch("");
    setHighlightIdx(-1);
    inputRef.current?.focus();
  };

  const handlePickCityAggregate = (cityCode: string) => {
    setLocalError(null);
    if (viewMode === "free") {
      setLocalError(
        "무료 통계는 법정동·리 한 곳만 선택할 수 있습니다. 유료에서 시 단위를 이용해 주세요."
      );
      return;
    }
    const cc = String(cityCode ?? "").trim();
    if (!cc) {
      setLocalError("시 단위 코드를 알 수 없습니다.");
      return;
    }
    const ok = mergePickedCityCodes([cc], regions);
    if (!ok) {
      setLocalError(
        "추가하지 못했습니다. 이미 있거나 시 단위 칩은 하나만 선택할 수 있습니다."
      );
      return;
    }
    setSearchInput("");
    setDebouncedSearch("");
    setHighlightIdx(-1);
    inputRef.current?.focus();
  };

  const handlePickEupAggregate = (eupCode: string) => {
    setLocalError(null);
    if (viewMode === "free") {
      setLocalError(
        "무료 통계는 법정동·리 한 곳만 선택할 수 있습니다. 목록에서 특정 법정단위를 고르거나, 유료에서 「읍·면 포함」을 이용해 주세요."
      );
      return;
    }
    const ec = String(eupCode ?? "").trim();
    if (!ec) return;

    if (viewMode === "profile") {
      replacePaidLeafEupmyeondong(ec);
      finishLeafPick();
      return;
    }

    if (paidReplaceLeafWithoutPlus()) {
      replacePaidLeafEupmyeondong(ec);
      setPaidLeafAddGateOpen(false);
      finishLeafPick();
      return;
    }

    const eupCur = tierSelection.eupmyeondong_codes.map((x) => x.trim()).filter(Boolean);
    if (eupCur.includes(ec)) {
      setLocalError("이미 선택한 읍·면·동 행정 단위입니다.");
      finishLeafPick();
      return;
    }
    if (pickedCodes.length + eupCur.length >= MAX_PAID_LEAF_BEOPJUNGRI_PICK) {
      setLocalError(
        `시군구 미만 선택(읍·면·동 행정 단위와 법정동·리 줄 합산)은 최대 ${MAX_PAID_LEAF_BEOPJUNGRI_PICK}곳까지입니다.`
      );
      return;
    }
    const ok = mergePickedEupmyeondongCodes([eupCode], regions);
    if (!ok) {
      setLocalError("추가하지 못했습니다. 선택이 이미 포함되어 있거나 한도입니다.");
      return;
    }
    setPaidLeafAddGateOpen(false);
    finishLeafPick();
  };

  const onSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      setSearchInput("");
      return;
    }

    const qLive = searchInput.trim();

    if (e.key === "ArrowDown") {
      if (!flatSuggestions.length) return;
      e.preventDefault();
      setHighlightIdx((i) => Math.min(i + 1, flatSuggestions.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      if (!flatSuggestions.length) return;
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, 0));
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();

      if (qLive.length < 2) return;
      if (catalogLoading && regions.length === 0) {
        setLocalError("지역 목록을 불러온 뒤 Enter로 확정해 주세요.");
        return;
      }

      if (isLooseMultiSegmentQuery(qLive)) {
        const { rows, codes } = resolveBeopjungriFromLooseAddressLine(regions, qLive);
        if (codes.length === 1) {
          setLocalError(null);
          pickBeopRow(rows[0]!);
          return;
        }
        if (codes.length === 0) {
          setLocalError("입력한 지명 조합과 맞는 법정동·리가 없습니다.");
          return;
        }

        const { eupmyeondongCode, sigunguCode } = commonTierCodesFromLooseRows(rows);

        if (viewMode === "paid") {
          if (eupmyeondongCode) {
            setLocalError(null);
            handlePickEupAggregate(eupmyeondongCode);
            return;
          }
          if (sigunguCode) {
            setLocalError(null);
            handlePickSigunguAggregate(sigunguCode);
            return;
          }
        } else if (eupmyeondongCode || sigunguCode) {
          setLocalError(
            "무료 통계는 법정동·리 한 곳만 선택할 수 있습니다. 아래 목록에서 특정 법정단위를 고르거나 상세 주소를 덧붙여 주세요."
          );
          return;
        }

        if (flatSuggestions.length > 0) {
          const entry = flatSuggestions[highlightIdx >= 0 ? highlightIdx : 0];
          if (entry.kind === "sido_aggregate") handlePickSidoAggregate(entry.sidoCode);
          else if (entry.kind === "city_aggregate") handlePickCityAggregate(entry.cityCode);
          else if (entry.kind === "sigungu_aggregate") handlePickSigunguAggregate(entry.sigunguCode);
          else if (entry.kind === "eup_aggregate") handlePickEupAggregate(entry.eupCode);
          else pickBeopRow(entry.row);
          return;
        }

        setLocalError(
          "후보가 여러 행정구역에 걸쳐 있습니다. 아래 목록에서 고르거나, 지명을 더 붙여 한 곳만 되게 해 주세요."
        );
        return;
      }

      if (flatSuggestions.length > 0) {
        const entry = flatSuggestions[highlightIdx >= 0 ? highlightIdx : 0];
        if (entry.kind === "sido_aggregate") handlePickSidoAggregate(entry.sidoCode);
        else if (entry.kind === "city_aggregate") handlePickCityAggregate(entry.cityCode);
        else if (entry.kind === "sigungu_aggregate") handlePickSigunguAggregate(entry.sigunguCode);
        else if (entry.kind === "eup_aggregate") handlePickEupAggregate(entry.eupCode);
        else pickBeopRow(entry.row);
        return;
      }

      const resolved = tryResolveUniqueRegionSearch(regions, qLive, viewMode);
      if (resolved) {
        setLocalError(null);
        if (resolved.kind === "beopjungri") pickBeopRow(resolved.row);
        else if (resolved.kind === "sigungu_aggregate") handlePickSigunguAggregate(resolved.sigunguCode);
        else if (resolved.kind === "eup_aggregate") handlePickEupAggregate(resolved.eupCode);
        else if (resolved.kind === "sido_aggregate") handlePickSidoAggregate(resolved.sidoCode);
        else if (resolved.kind === "city_aggregate") handlePickCityAggregate(resolved.cityCode);
        return;
      }

      setLocalError(
        "엔터로 확정할 단일 후보가 없습니다. 아래 목록에서 항목을 고르거나, 동명이면 상위 행정구역 이름을 덧붙이세요."
      );
    }
  };

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>("[data-hl=true]");
    el?.scrollIntoView({ block: "nearest" });
  }, [highlightIdx]);

  const commitFree = () => {
    setLocalError(null);
    if (resolvedUnionCodes.length === 0) {
      setLocalError("먼저 검색으로 법정동·리 하나를 선택하세요.");
      return;
    }
    if (
      tierSelection.sigungu_codes.length > 0 ||
      tierSelection.city_codes.length > 0 ||
      tierSelection.eupmyeondong_codes.length > 0
    ) {
      setLocalError(
        "무료 모드에서는 시군구·시(자치구 묶음)·읍면 전체 행만 있는 선택을 쓸 수 없습니다. 법정단위 하나를 검색해서 고르세요."
      );
      return;
    }
    if (resolvedUnionCodes.length > 1 || pickedCodes.length !== 1) {
      setLocalError("무료 통계는 법정동·리 한 곳만 선택할 수 있습니다. 칩에서 하나만 남기세요.");
      return;
    }
    applyBeopjungriCodes(resolvedUnionCodes);
    commitStatsDisplayScope(statsScopeKeyFromBeopjungriCodes(resolvedUnionCodes));
  };

  const commitPaid = () => {
    setLocalError(null);
    if (resolvedUnionCodes.length === 0) {
      setLocalError("검색에서 지역을 추가해 주세요.");
      return;
    }

    kickPaidBasicStatsAnalysis();
    commitStatsDisplayScope(statsScopeKeyFromBeopjungriCodes(resolvedUnionCodes));
  };

  const commitProfile = () => {
    setLocalError(null);
    const target = resolveProfileRegionFromTier(tierSelection);
    if (!target) {
      if (tierSelection.beopjungri_codes.length > 1) {
        setLocalError(
          "여러 법정동·리가 섞여 있습니다. 같은 읍·면·동 안의 항목만 남기거나, 검색에서 「읍·면·동 포함」을 선택하세요."
        );
        return;
      }
      if (resolvedUnionCodes.length === 0) {
        setLocalError("검색에서 지역을 추가해 주세요.");
        return;
      }
      setLocalError(
        "지역 프로필은 상위 행정구역(시·도·시군구·읍면동)을 하나만 선택할 수 있습니다. 복수 칩은 줄여 주세요."
      );
      return;
    }
    commitStatsDisplayScope(`profile:${target.level}:${target.code}`);
  };

  const suggestionListMaxClass = suggestionsShortHeight ? "max-h-28" : "max-h-52";

  return (
    <div className="bg-white rounded-xl shadow-sm p-3 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-sm font-bold text-slate-700">지역 입력</h2>
        <button
          type="button"
          onClick={() => {
            clearTierSelection();
            setPaidLeafAddGateOpen(true);
            setSearchInput("");
            setLocalError(null);
          }}
          className="text-[10px] text-slate-500 underline underline-offset-2 hover:text-red-600 shrink-0"
        >
          초기화
        </button>
      </div>

      <div className="space-y-1.5">
        <label className="block text-[11px] font-semibold text-slate-700" htmlFor="region-search">
          지역 이름·코드 검색
        </label>
        <input
          ref={inputRef}
          id="region-search"
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="예: 오창읍 화산리 · 흥덕구 가경동 (Enter로 확정)"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={onSearchKeyDown}
          disabled={catalogLoading}
          className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-[12px]"
        />
        {viewMode === "paid" &&
        strictUpperTierChipCount === 0 &&
        paidSubSigunguSelections >= 1 &&
        !paidLeafAddGateOpen ? (
          <p className="text-[10px] text-slate-500 leading-snug">
            다른 지역을 검색·선택하면 현재 선택이 <strong>바뀝니다</strong>. 이어서 추가하려면 아래 「+ 추가
            지역 선택」을 누르세요.
          </p>
        ) : null}
        {searchPanelOpen ? (
          <div className="relative">
            {flatSuggestions.length > 0 ? (
              <div className="flex flex-wrap items-center justify-end gap-x-2 gap-y-0.5">
                <button
                  type="button"
                  onClick={() => setSuggestionsShortHeight((s) => !s)}
                  className="text-[10px] text-slate-500 underline underline-offset-2 hover:text-slate-800"
                >
                  {suggestionsShortHeight ? "목록 크게" : "목록 낮게"}
                </button>
                <button
                  type="button"
                  onClick={() => setSuggestionsCollapsed((c) => !c)}
                  className="text-[10px] text-slate-500 underline underline-offset-2 hover:text-slate-800"
                >
                  {suggestionsCollapsed
                    ? `펼치기 (${flatSuggestions.length})`
                    : "목록 접기"}
                </button>
              </div>
            ) : null}
            {suggestionsCollapsed && flatSuggestions.length > 0 ? (
              <p className="text-[10px] text-slate-500 py-0.5 text-right">
                후보 {flatSuggestions.length}건 · 「펼치기」로 목록 표시
              </p>
            ) : null}
            {isLooseMultiSegmentQuery(debouncedSearch) ? (
              <>
                {catalogLoading && regions.length === 0 ? (
                  <p className="text-[10px] text-slate-400 py-1">지역 목록 불러오는 중…</p>
                ) : looseResolve && looseResolve.codes.length === 0 ? (
                  <p className="text-[10px] text-slate-500 py-1">
                    입력한 지명 조합과 맞는 법정동·리가 없습니다. 단어를 나누거나 철자를 확인해 보세요.
                  </p>
                ) : null}
                {flatSuggestions.length > 0 && !suggestionsCollapsed && (
                  <ul
                    ref={listRef}
                    role="listbox"
                    className={`absolute z-20 mt-0.5 ${suggestionListMaxClass} w-full overflow-auto rounded-md border border-slate-200 bg-white shadow-lg text-[11px]`}
                  >
                    {flatSuggestions.map((entry, idx) => {
                      if (entry.kind !== "beopjungri") return null;
                      const hl = idx === highlightIdx;
                      const row = entry.row;
                      const lbl = formatRegionHierarchyLabel(row);
                      return (
                        <Fragment key={`bp-${String(row.beopjungri_code).trim()}`}>
                          {idx === 0 ? (
                            <li
                              className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-500"
                              aria-hidden
                            >
                              법정동·리 (각 줄에 입력한 모든 지명이 경로에 포함된 단위)
                            </li>
                          ) : null}
                          <li role="presentation">
                            <button
                              type="button"
                              role="option"
                              data-hl={hl ? "true" : undefined}
                              aria-selected={hl}
                              className={`w-full text-left px-2 py-1.5 hover:bg-blue-50 ${
                                hl ? "bg-blue-50" : ""
                              }`}
                              onMouseEnter={() => setHighlightIdx(idx)}
                              onMouseDown={(e) => e.preventDefault()}
                              onClick={() => pickBeopRow(row)}
                            >
                              <span className="text-slate-800 leading-snug block">{lbl}</span>
                              <span className="text-[10px] text-slate-400 tabular-nums">
                                {String(row.beopjungri_code).trim()}
                              </span>
                            </button>
                          </li>
                        </Fragment>
                      );
                    })}
                  </ul>
                )}
              </>
            ) : (
              <>
                {(searchFetching || catalogLoading) && (
                  <p className="text-[10px] text-slate-400 py-1">검색 중…</p>
                )}
                {!searchFetching && searchHits.length === 0 && (
                  <p className="text-[10px] text-slate-500 py-1">일치 결과가 없습니다.</p>
                )}
                {!searchFetching && searchHits.length > 0 && flatSuggestions.length === 0 && (
                  <p className="text-[10px] text-slate-500 py-1">
                    시도·자치구 묶음·읍면 상위 카드 또는 법정코드 줄. …읍/…면 이름만 치면 읍면 단위 카드만 뜹니다. 다른 표현으로 시도해 보세요.
                  </p>
                )}
                {flatSuggestions.length > 0 && !suggestionsCollapsed && (
                  <ul
                    ref={listRef}
                    role="listbox"
                    className={`absolute z-20 mt-0.5 ${suggestionListMaxClass} w-full overflow-auto rounded-md border border-slate-200 bg-white shadow-lg text-[11px]`}
                  >
                    {flatSuggestions.map((entry, idx) => {
                  const hl = idx === highlightIdx;
                  const showSidoHeader =
                    entry.kind === "sido_aggregate" &&
                    (idx === 0 || flatSuggestions[idx - 1]?.kind !== "sido_aggregate");
                  const showCityHeader =
                    entry.kind === "city_aggregate" &&
                    (idx === 0 || flatSuggestions[idx - 1]?.kind !== "city_aggregate");
                  const showSigunguHeader =
                    entry.kind === "sigungu_aggregate" &&
                    (idx === 0 || flatSuggestions[idx - 1]?.kind !== "sigungu_aggregate");
                  const showEupHeader =
                    entry.kind === "eup_aggregate" &&
                    (idx === 0 || flatSuggestions[idx - 1]?.kind !== "eup_aggregate");
                  const showBeopHeader =
                    entry.kind === "beopjungri" &&
                    (idx === 0 || flatSuggestions[idx - 1]?.kind !== "beopjungri");

                  if (entry.kind === "sido_aggregate") {
                    return (
                      <Fragment key={`sid-${entry.sidoCode}`}>
                        {showSidoHeader ? (
                          <li
                            className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-500"
                            aria-hidden
                          >
                            시·도 (클릭 시 시도 전체 사전집계로 한 줄 분석)
                          </li>
                        ) : null}
                        <li role="presentation">
                          <button
                            type="button"
                            role="option"
                            data-hl={hl ? "true" : undefined}
                            aria-selected={hl}
                            className={`w-full text-left px-2 py-1.5 hover:bg-blue-50 ${
                              hl ? "bg-blue-50" : ""
                            }`}
                            onMouseEnter={() => setHighlightIdx(idx)}
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => handlePickSidoAggregate(entry.sidoCode)}
                          >
                            <span className="text-violet-900 text-[10px] font-semibold uppercase tracking-tight">
                              [시·도]
                            </span>
                            <span className="text-slate-800 leading-snug block">
                              {entry.primaryLabel}
                            </span>
                            <span className="text-[10px] text-slate-400">{entry.subtitle}</span>
                            <span className="text-[10px] text-slate-400 tabular-nums block">
                              코드 {entry.sidoCode}
                            </span>
                          </button>
                        </li>
                      </Fragment>
                    );
                  }

                  if (entry.kind === "city_aggregate") {
                    return (
                      <Fragment key={`city-${entry.sidoCode}-${entry.cityName}`}>
                        {showCityHeader ? (
                          <li
                            className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-500"
                            aria-hidden
                          >
                            시 (자치구를 묶어 한 번에 선택)
                          </li>
                        ) : null}
                        <li role="presentation">
                          <button
                            type="button"
                            role="option"
                            data-hl={hl ? "true" : undefined}
                            aria-selected={hl}
                            className={`w-full text-left px-2 py-1.5 hover:bg-blue-50 ${
                              hl ? "bg-blue-50" : ""
                            }`}
                            onMouseEnter={() => setHighlightIdx(idx)}
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => handlePickCityAggregate(entry.cityCode)}
                          >
                            <span className="text-indigo-900 text-[10px] font-semibold uppercase tracking-tight">
                              [시]
                            </span>
                            <span className="text-slate-800 leading-snug block">
                              {entry.primaryLabel}
                            </span>
                            <span className="text-[10px] text-slate-400">{entry.subtitle}</span>
                          </button>
                        </li>
                      </Fragment>
                    );
                  }

                  if (entry.kind === "sigungu_aggregate") {
                    return (
                      <Fragment key={`sgg-${entry.sigunguCode}`}>
                        {showSigunguHeader ? (
                          <li
                            className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-500"
                            aria-hidden
                          >
                            시·군·구 포함 (클릭 시 시군구 한 줄로 선택 — 분석 때 하위 법정 포함)
                          </li>
                        ) : null}
                        <li role="presentation">
                          <button
                            type="button"
                            role="option"
                            data-hl={hl ? "true" : undefined}
                            aria-selected={hl}
                            className={
                              hl
                                ? "w-full text-left px-2 py-1.5 hover:bg-blue-50 bg-blue-50"
                                : "w-full text-left px-2 py-1.5 hover:bg-blue-50"
                            }
                            onMouseEnter={() => setHighlightIdx(idx)}
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => handlePickSigunguAggregate(entry.sigunguCode)}
                          >
                            <span className="text-blue-900 text-[10px] font-semibold uppercase tracking-tight">
                              [시군구 포함]
                            </span>
                            <span className="text-slate-800 leading-snug block">
                              {entry.primaryLabel}
                            </span>
                            <span className="text-[10px] text-slate-400">{entry.subtitle}</span>
                            <span className="text-[10px] text-slate-400 tabular-nums block">
                              코드 {entry.sigunguCode}
                            </span>
                          </button>
                        </li>
                      </Fragment>
                    );
                  }

                  if (entry.kind === "eup_aggregate") {
                    return (
                      <Fragment key={`eup-${entry.eupCode}`}>
                        {showEupHeader ? (
                          <li
                            className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-500"
                            aria-hidden
                          >
                            읍·면 (행정 단위 한 줄 · 사전집계 eup 키)
                          </li>
                        ) : null}
                        <li role="presentation">
                          <button
                            type="button"
                            role="option"
                            data-hl={hl ? "true" : undefined}
                            aria-selected={hl}
                            className={`w-full text-left px-2 py-1.5 hover:bg-blue-50 ${
                              hl ? "bg-blue-50" : ""
                            }`}
                            onMouseEnter={() => setHighlightIdx(idx)}
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => handlePickEupAggregate(entry.eupCode)}
                          >
                            <span className="text-emerald-800 text-[10px] font-semibold uppercase tracking-tight">
                              [읍·면 행정]
                            </span>
                            <span className="text-slate-800 leading-snug block">
                              {entry.primaryLabel}
                            </span>
                            <span className="text-[10px] text-slate-400">{entry.subtitle}</span>
                            <span className="text-[10px] text-slate-400 tabular-nums block">
                              코드 {entry.eupCode}
                            </span>
                          </button>
                        </li>
                      </Fragment>
                    );
                  }

                  const row = entry.row;
                  const lbl = formatRegionHierarchyLabel(row);
                  return (
                    <Fragment key={`bp-${String(row.beopjungri_code).trim()}`}>
                      {showBeopHeader ? (
                        <li
                          className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-500"
                          aria-hidden
                        >
                          법정동·리 · 법정코드 줄
                        </li>
                      ) : null}
                      <li role="presentation">
                        <button
                          type="button"
                          role="option"
                          data-hl={hl ? "true" : undefined}
                          aria-selected={hl}
                          className={`w-full text-left px-2 py-1.5 hover:bg-blue-50 ${
                            hl ? "bg-blue-50" : ""
                          }`}
                          onMouseEnter={() => setHighlightIdx(idx)}
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => pickBeopRow(row)}
                        >
                          <span className="text-slate-800 leading-snug block">{lbl}</span>
                          <span className="text-[10px] text-slate-400 tabular-nums">
                            {String(row.beopjungri_code).trim()}
                          </span>
                        </button>
                      </li>
                    </Fragment>
                  );
                })}
                  </ul>
                )}
              </>
            )}
          </div>
        ) : null}
      </div>

      {viewMode === "paid" &&
      strictUpperTierChipCount === 0 &&
      paidSubSigunguSelections >= 1 &&
      paidSubSigunguSelections < MAX_PAID_LEAF_BEOPJUNGRI_PICK ? (
        <div className="flex flex-col gap-1">
          <button
            type="button"
            onClick={() => {
              setLocalError(null);
              setPaidLeafAddGateOpen(true);
              inputRef.current?.focus();
            }}
            disabled={paidLeafAddGateOpen}
            className="w-full py-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 text-[11px] font-semibold text-slate-700
                       hover:bg-slate-100 hover:border-slate-400 disabled:opacity-50 disabled:pointer-events-none transition-colors"
          >
            {paidLeafAddGateOpen
              ? "검색란에서 다음 행정이나 법정동·리를 검색해 주세요."
              : `+ 추가 지역 선택 (복수 · 남은 ${paidExtraRegionsRemaining}곳)`}
          </button>
        </div>
      ) : null}

      {viewMode === "paid" && strictUpperTierChipCount === 0 && paidUnifiedSubSigunguRows.length > 0 ? (
        <div className="rounded-lg border border-slate-100 bg-white px-2.5 py-2 space-y-1">
          <p className="text-[11px] font-semibold text-slate-700">
            선택한 지역 ({paidSubSigunguSelections}/{MAX_PAID_LEAF_BEOPJUNGRI_PICK}) — 시군구 미만
          </p>
          <ol className="list-decimal list-inside space-y-1 text-[11px] text-slate-800 marker:text-slate-400">
            {paidUnifiedSubSigunguRows.map((entry) => {
              const label =
                entry.kind === "eup"
                  ? labelEupChip(regions, entry.code)
                  : labelForCode(entry.code);
              return (
                <li key={`${entry.kind}-${entry.code}`} className="pl-1">
                  <span className="leading-snug inline align-middle">{label}</span>
                  <button
                    type="button"
                    className="ml-1 align-middle shrink-0 rounded-full p-0.5 hover:bg-red-50 text-[10px] text-slate-500 hover:text-red-700"
                    aria-label={`${label} 삭제`}
                    onClick={() =>
                      entry.kind === "eup"
                        ? removePickedEupmyeondong(entry.code)
                        : removePickedBeopjungri(entry.code)
                    }
                  >
                    삭제
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      ) : null}

      <div className="rounded-lg border border-slate-100 bg-slate-50/80 px-2 py-2 space-y-1">
        <p className="text-[11px] font-semibold text-slate-700">
          {viewMode === "paid" ? "선택된 지역" : "선택"}{" "}
          <span className="font-normal text-slate-500">
            항목 {selectionChipCount} · 합산 법정 {resolvedCount}곳
          </span>
        </p>
        {selectionChipCount === 0 ? null : (
          <div className="flex flex-wrap gap-1">
            {tierSelection.sido_codes.map((code) => (
              <span
                key={`sid-${code}`}
                className="inline-flex items-center gap-1 max-w-full rounded-full border border-violet-200 bg-white pl-2 pr-1 py-0.5 text-[10px] text-violet-950"
              >
                <span className="truncate max-w-[14rem]" title={`시도 ${code}`}>
                  [시·도] {labelSidoChip(regions, code)}
                </span>
                {viewMode === "paid" ? (
                  <button
                    type="button"
                    className="shrink-0 rounded-full p-0.5 hover:bg-red-50 text-slate-500 hover:text-red-700"
                    aria-label={`시도 삭제 ${code}`}
                    onClick={() => removePickedSido(code)}
                  >
                    ×
                  </button>
                ) : null}
              </span>
            ))}
            {tierSelection.city_codes.map((code) => (
              <span
                key={`city-${code}`}
                className="inline-flex items-center gap-1 max-w-full rounded-full border border-indigo-200 bg-white pl-2 pr-1 py-0.5 text-[10px] text-indigo-950"
              >
                <span className="truncate max-w-[14rem]" title={`의사 시(자치구 묶음) ${code}`}>
                  [시] {labelCityChip(regions, code)}
                </span>
                {viewMode === "paid" ? (
                  <button
                    type="button"
                    className="shrink-0 rounded-full p-0.5 hover:bg-red-50 text-slate-500 hover:text-red-700"
                    aria-label={`시(묶음) 삭제 ${code}`}
                    onClick={() => removePickedCity(code)}
                  >
                    ×
                  </button>
                ) : null}
              </span>
            ))}
            {tierSelection.sigungu_codes.map((code) => (
              <span
                key={`sgg-${code}`}
                className="inline-flex items-center gap-1 max-w-full rounded-full border border-blue-200 bg-white pl-2 pr-1 py-0.5 text-[10px] text-blue-950"
              >
                <span className="truncate max-w-[14rem]" title={`시군구 ${code}`}>
                  [시군구] {labelSigunguChip(regions, code)}
                </span>
                {viewMode === "paid" ? (
                  <button
                    type="button"
                    className="shrink-0 rounded-full p-0.5 hover:bg-red-50 text-slate-500 hover:text-red-700"
                    aria-label={`시군구 삭제 ${code}`}
                    onClick={() => removePickedSigungu(code)}
                  >
                    ×
                  </button>
                ) : null}
              </span>
            ))}
            {(viewMode !== "paid" || strictUpperTierChipCount > 0
              ? tierSelection.eupmyeondong_codes
              : []
            ).map((code) => (
              <span
                key={`eup-${code}`}
                className="inline-flex items-center gap-1 max-w-full rounded-full border border-emerald-200 bg-white pl-2 pr-1 py-0.5 text-[10px] text-emerald-950"
              >
                <span className="truncate max-w-[14rem]" title={`읍면동 ${code}`}>
                  [읍·면·동] {labelEupChip(regions, code)}
                </span>
                {viewMode === "paid" ? (
                  <button
                    type="button"
                    className="shrink-0 rounded-full p-0.5 hover:bg-red-50 text-slate-500 hover:text-red-700"
                    aria-label={`읍면동 삭제 ${code}`}
                    onClick={() => removePickedEupmyeondong(code)}
                  >
                    ×
                  </button>
                ) : null}
              </span>
            ))}
            {viewMode === "free"
              ? pickedCodes.map((code) => (
                  <span
                    key={`bp-${code}`}
                    className="inline-flex items-center gap-1 max-w-full rounded-full border border-slate-200 bg-white pl-2 pr-1 py-0.5 text-[10px] text-slate-700"
                  >
                    <span className="truncate max-w-[14rem]" title={labelForCode(code)}>
                      {labelForCode(code)}
                    </span>
                    <button
                      type="button"
                      className="shrink-0 rounded-full p-0.5 hover:bg-red-50 text-slate-500 hover:text-red-700"
                      aria-label={`삭제 ${code}`}
                      onClick={() => removePickedBeopjungri(code)}
                    >
                      ×
                    </button>
                  </span>
                ))
              : null}
          </div>
        )}
      </div>

      {localError ? (
        <p className="text-[11px] text-red-600 leading-snug" role="alert">
          {localError}
        </p>
      ) : null}

      <div className="rounded-lg border border-slate-100 bg-slate-50/80 px-2.5 py-2 space-y-2">
        <FreeStatsWindowToggle idPrefix="sidebar-v2" />
      </div>

      {viewMode === "free" ? (
        <button
          type="button"
          onClick={commitFree}
          className="w-full py-2 rounded-lg bg-slate-800 text-white text-sm font-semibold
                     hover:bg-slate-900 disabled:opacity-40 transition-colors"
          disabled={catalogLoading && regions.length === 0}
        >
          무료 통계 조회
        </button>
      ) : viewMode === "profile" ? (
        <button
          type="button"
          onClick={commitProfile}
          className="w-full py-2 rounded-lg bg-violet-600 text-white text-sm font-semibold
                     hover:bg-violet-700 disabled:opacity-40 transition-colors"
          disabled={catalogLoading && regions.length === 0}
        >
          프로필 조회
        </button>
      ) : (
        <button
          type="button"
          onClick={commitPaid}
          className="w-full py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold
                     hover:bg-blue-700 disabled:opacity-40 transition-colors"
          disabled={catalogLoading && regions.length === 0}
        >
          기본 통계 보기
        </button>
      )}

    </div>
  );
}
