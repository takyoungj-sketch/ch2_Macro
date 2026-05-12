import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRegions } from "../api/client";
import { useAppStore } from "../store";
import {
  resolveUnionBeopjungriCodes,
} from "../utils/regionTier";
import {
  resolveBeopjungriFromFiveFields,
  type RegionFiveFields,
} from "../utils/resolveRegionFiveFields";
import type { RegionItem } from "../types";
import { formatRegionHierarchyLabel } from "../utils/regionDisplay";
import { buildFlattenedRegionSuggestions } from "../utils/regionSearchSuggest";
import { REGION_PICK_MANY_WARN_AT, REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";

const FIELD_LABELS = [
  "① 시·도",
  "② 시·군",
  "③ 구 (없으면 비움)",
  "④ 읍·면·동",
  "⑤ 리·동 세부 (동만이면 비움)",
];

const FIELD_PLACEHOLDERS = [
  "예: 충청북도 또는 충북",
  "예: 청주시",
  "예: 흥덕구",
  "예: 가경동, 남이면",
  "예: 가좌리 (동 단위면 비움)",
];

function labelSigunguChip(regions: RegionItem[], code: string): string {
  const c = String(code).trim();
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

export default function RegionSelector() {
  const {
    viewMode,
    tierSelection,
    regionSegments,
    setRegionSegment,
    clearTierSelection,
    applyBeopjungriCodes,
    kickPaidBasicStatsAnalysis,
    addPickedBeopjungri,
    removePickedBeopjungri,
    mergePickedSigunguCodes,
    mergePickedEupmyeondongCodes,
    removePickedSigungu,
    removePickedEupmyeondong,
  } = useAppStore();

  const [localError, setLocalError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [highlightIdx, setHighlightIdx] = useState(-1);
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
  }, [debouncedSearch]);

  const searchEnabled = debouncedSearch.length >= 2;

  const { data: searchHits = [], isFetching: searchFetching } = useQuery({
    queryKey: ["regions", "search", debouncedSearch],
    queryFn: () =>
      fetchRegions({ search: debouncedSearch, limit: 400 }),
    enabled: searchEnabled,
    staleTime: 60_000,
  });

  const flatSuggestions = useMemo(
    () =>
      buildFlattenedRegionSuggestions(searchHits, debouncedSearch, {
        maxSigungu: 50,
        maxAgg: 40,
        maxBeop: 400,
      }),
    [searchHits, debouncedSearch]
  );

  const textLookup = useMemo(
    () => resolveBeopjungriFromFiveFields(regions, regionSegments as RegionFiveFields),
    [regions, regionSegments]
  );

  const resolvedUnionCodes = useMemo(
    () => resolveUnionBeopjungriCodes(regions, tierSelection),
    [regions, tierSelection]
  );

  /** 현재 매칭(단계별 고급 입력, 적용 버튼과 무관) */
  const previewDrillDownCount = textLookup.codes.length;
  const pickedCodes = tierSelection.beopjungri_codes;
  const selectionChipCount =
    tierSelection.sigungu_codes.length +
    tierSelection.eupmyeondong_codes.length +
    tierSelection.beopjungri_codes.length;
  const resolvedCount = resolvedUnionCodes.length;

  const labelForCode = (code: string) => {
    const c = String(code).trim();
    const row = regions.find((r) => String(r.beopjungri_code).trim() === c);
    return row ? formatRegionHierarchyLabel(row) : c;
  };

  const syncSegment = (idx: 0 | 1 | 2 | 3 | 4, value: string) => {
    setLocalError(null);
    setRegionSegment(idx, value);
  };

  const pickBeopRow = (r: RegionItem) => {
    setLocalError(null);
    const c = String(r.beopjungri_code ?? "").trim();
    if (!c || viewMode !== "paid") {
      addPickedBeopjungri(r.beopjungri_code);
      setSearchInput("");
      setDebouncedSearch("");
      setHighlightIdx(-1);
      inputRef.current?.focus();
      return;
    }
    const cur = tierSelection.beopjungri_codes.map((x) => x.trim()).filter(Boolean);
    if (cur.includes(c)) {
      setSearchInput("");
      setDebouncedSearch("");
      setHighlightIdx(-1);
      inputRef.current?.focus();
      return;
    }
    const trial = {
      ...tierSelection,
      beopjungri_codes: [...cur, c].sort((a, b) => a.localeCompare(b, "ko-KR")),
    };
    if (resolveUnionBeopjungriCodes(regions, trial).length > 200) {
      setLocalError(
        "합산에 포함되는 법정단위 수가 한도(200)를 넘습니다. 시군구·법정 선택을 줄여 주세요."
      );
      return;
    }
    addPickedBeopjungri(r.beopjungri_code);
    setSearchInput("");
    setDebouncedSearch("");
    setHighlightIdx(-1);
    inputRef.current?.focus();
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
        "추가하지 못했습니다. 이미 있거나 선택 상한을 넘깁니다(시군구 칩 최대 개수·합산 법정 200개)."
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
    const ok = mergePickedEupmyeondongCodes([eupCode], regions);
    if (!ok) {
      setLocalError(
        "추가하지 못했습니다. 이미 있거나 선택 상한을 넘깁니다(읍면동 칩 최대 개수·합산 법정 200개)."
      );
      return;
    }
    setSearchInput("");
    setDebouncedSearch("");
    setHighlightIdx(-1);
    inputRef.current?.focus();
  };

  const onSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!flatSuggestions.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIdx((i) => Math.min(i + 1, flatSuggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const entry = flatSuggestions[highlightIdx >= 0 ? highlightIdx : 0];
      if (entry.kind === "sigungu_aggregate") handlePickSigunguAggregate(entry.sigunguCode);
      else if (entry.kind === "eup_aggregate") handlePickEupAggregate(entry.eupCode);
      else pickBeopRow(entry.row);
    } else if (e.key === "Escape") {
      setSearchInput("");
    }
  };

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>("[data-hl=true]");
    el?.scrollIntoView({ block: "nearest" });
  }, [highlightIdx]);

  const commitFree = () => {
    setLocalError(null);
    if (resolvedUnionCodes.length === 0) {
      setLocalError("먼저 아래 검색 또는 단계별 입력으로 법정동·리 하나를 선택하세요.");
      return;
    }
    if (
      tierSelection.sigungu_codes.length > 0 ||
      tierSelection.eupmyeondong_codes.length > 0
    ) {
      setLocalError(
        "무료 모드에서는 시군구·읍면 전체 행만 있는 선택을 쓸 수 없습니다. 법정단위 하나를 검색해서 고르세요."
      );
      return;
    }
    if (resolvedUnionCodes.length > 1 || pickedCodes.length !== 1) {
      setLocalError("무료 통계는 법정동·리 한 곳만 선택할 수 있습니다. 칩에서 하나만 남기세요.");
      return;
    }
    applyBeopjungriCodes(resolvedUnionCodes);
  };

  const commitPaid = () => {
    setLocalError(null);

    const anySegment = regionSegments.some((x: string) => x.trim());
    if (resolvedUnionCodes.length === 0) {
      if (!anySegment) {
        setLocalError("검색에서 지역을 추가하거나 단계별 입력 후 여기 적용 해 주세요.");
        return;
      }
      const { codes: drilled } = textLookup;
      if (drilled.length === 0) {
        setLocalError("조건과 일치하는 법정동·리가 없습니다. 이름을 확인해 보세요.");
        return;
      }
      kickPaidBasicStatsAnalysis(drilled);
      return;
    }

    kickPaidBasicStatsAnalysis();
  };

  const applyDrillToChipsPaid = () => {
    setLocalError(null);
    const { codes, sampleLabel } = textLookup;
    const anyInput = regionSegments.some((x: string) => x.trim());

    if (!anyInput) {
      setLocalError("단계별 필드 중 최소 한 칸 이상 입력한 뒤 적용 해 주세요.");
      return;
    }
    if (codes.length === 0) {
      setLocalError("조건과 일치하는 법정동·리가 없습니다. 이름을 확인해 보세요.");
      return;
    }
    if (viewMode === "free") {
      if (codes.length > 1 && sampleLabel) {
        setLocalError(
          `${codes.length}곳이 매칭되었습니다. 무료는 한 곳만 가능하니 검색으로 좁히거나 이름을 더 구체적으로 입력해 주세요.`
        );
        return;
      }
      applyBeopjungriCodes(codes);
      return;
    }
    /** 유료: OR 매칭된 전체 코드를 선택에 설정 */
    applyBeopjungriCodes(codes);
  };

  return (
    <div className="bg-white rounded-xl shadow-sm p-3 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-sm font-bold text-slate-700">지역 입력</h2>
        <button
          type="button"
          onClick={() => {
            clearTierSelection();
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
          이름·코드 검색
        </label>
        <input
          ref={inputRef}
          id="region-search"
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="예: 흥덕구, 서원구, 청주시 가경동 (2자 이상)"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={onSearchKeyDown}
          disabled={catalogLoading}
          className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-[12px]"
        />
        {searchEnabled ? (
          <div className="relative">
            {(searchFetching || catalogLoading) && (
              <p className="text-[10px] text-slate-400 py-1">검색 중…</p>
            )}
            {!searchFetching && searchHits.length === 0 && (
              <p className="text-[10px] text-slate-500 py-1">일치 결과가 없습니다.</p>
            )}
            {!searchFetching && searchHits.length > 0 && flatSuggestions.length === 0 && (
              <p className="text-[10px] text-slate-500 py-1">
                시군구·읍면·법정 이름·코드와 직접 맞는 항목만 목록에 올립니다. 다른 단어로 시도해
                보세요.
              </p>
            )}
            {flatSuggestions.length > 0 && (
              <ul
                ref={listRef}
                role="listbox"
                className="absolute z-20 mt-0.5 max-h-52 w-full overflow-auto rounded-md border border-slate-200 bg-white shadow-lg text-[11px]"
              >
                {flatSuggestions.map((entry, idx) => {
                  const hl = idx === highlightIdx;
                  const showSigunguHeader =
                    entry.kind === "sigungu_aggregate" &&
                    (idx === 0 || flatSuggestions[idx - 1]?.kind !== "sigungu_aggregate");
                  const showEupHeader =
                    entry.kind === "eup_aggregate" &&
                    (idx === 0 || flatSuggestions[idx - 1]?.kind !== "eup_aggregate");
                  const showBeopHeader =
                    entry.kind === "beopjungri" &&
                    (idx === 0 || flatSuggestions[idx - 1]?.kind !== "beopjungri");

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
                            className={`w-full text-left px-2 py-1.5 hover:bg-blue-50 ${hl ? "bg-blue-50" : ""
                              }`}
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
                            읍·면·동 포함 (클릭 시 읍면 한 줄로 선택 — 분석 때 하위 법정 포함)
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
                              [읍·면 포함]
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

                  const row = entry.row;
                  const lbl = formatRegionHierarchyLabel(row);
                  return (
                    <Fragment key={`bp-${String(row.beopjungri_code).trim()}`}>
                      {showBeopHeader ? (
                        <li
                          className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-500"
                          aria-hidden
                        >
                          법정동·리 (이름·코드 일치)
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
          </div>
        ) : searchInput.trim().length > 0 ? (
          <p className="text-[10px] text-slate-500">검색은 두 글자 이상 입력해 주세요.</p>
        ) : null}
      </div>

      <div className="rounded-lg border border-slate-100 bg-slate-50/80 px-2 py-2 space-y-1">
        <p className="text-[11px] font-semibold text-slate-700">
          {viewMode === "paid" ? "선택된 지역" : "선택 (무료는 1개)"}{" "}
          <span className="font-normal text-slate-500">
            항목 {selectionChipCount} · 합산 법정 {resolvedCount}곳
          </span>
        </p>
        {selectionChipCount === 0 ? (
          <p className="text-[10px] text-slate-500 leading-snug">검색 결과를 눌러 추가하세요.</p>
        ) : (
          <div className="flex flex-wrap gap-1">
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
            {tierSelection.eupmyeondong_codes.map((code) => (
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
            {pickedCodes.map((code) => (
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
            ))}
          </div>
        )}
        {viewMode === "paid" &&
          resolvedCount >= REGION_PICK_MANY_WARN_AT &&
          resolvedCount < 200 && (
          <p className="text-[10px] text-slate-500">합산 단위가 많을수록 집계에 시간이 걸릴 수 있습니다.</p>
        )}
      </div>

      <details className="rounded-lg border border-dashed border-slate-200 bg-white text-[11px] text-slate-600">
        <summary className="cursor-pointer px-2 py-1.5 font-semibold text-slate-700 select-none hover:bg-slate-50 rounded-lg">
          단계별로 찾기 (고급)
        </summary>
        <div className="px-2 pb-2 pt-1 space-y-1.5 border-t border-slate-100 mt-1">
          <fieldset className="space-y-1.5 border-0 m-0 p-0">
            <legend className="sr-only">법정 행정구역 단계별 이름 입력</legend>
            {FIELD_LABELS.map((label, idx) => {
              const key = `${idx}-${label}`;
              const i = idx as 0 | 1 | 2 | 3 | 4;
              return (
                <label
                  key={key}
                  htmlFor={`region-tier-${idx}`}
                  className="block text-[11px] text-slate-600 leading-tight space-y-0.5"
                >
                  <span className="block font-semibold text-slate-700">{label}</span>
                  <input
                    id={`region-tier-${idx}`}
                    type="text"
                    value={regionSegments[i]}
                    placeholder={FIELD_PLACEHOLDERS[idx]}
                    onChange={(e) => syncSegment(i, e.target.value)}
                    autoComplete="off"
                    spellCheck={false}
                    disabled={catalogLoading && regions.length === 0}
                    className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-[12px]"
                  />
                </label>
              );
            })}
          </fieldset>

          {catalogLoading && regions.length === 0 ? (
            <p className="text-[11px] text-slate-400">지역 코드 목록 불러오는 중…</p>
          ) : (
            <p className="text-[11px] text-slate-600 leading-snug">
              현재 입력으로{" "}
              <span className="font-semibold text-slate-800">{previewDrillDownCount}</span>
              건 매칭
              {textLookup.sampleLabel &&
                previewDrillDownCount > 0 &&
                previewDrillDownCount <= 120 && (
                  <span className="block mt-1 text-[10px] text-slate-400 truncate">
                    예: {textLookup.sampleLabel}
                  </span>
                )}
            </p>
          )}

          <button
            type="button"
            onClick={applyDrillToChipsPaid}
            className="w-full py-1.5 rounded-md border border-slate-300 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
          >
            {viewMode === "paid"
              ? "위 조건 매칭 전체를 선택 목록에 반영"
              : "위 조건이 한 곳이면 선택에 반영"}
          </button>
        </div>
      </details>

      {localError ? (
        <p className="text-[11px] text-red-600 leading-snug" role="alert">
          {localError}
        </p>
      ) : null}

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

      <p className="text-[10px] text-slate-500 leading-snug border-t border-slate-100 pt-2">
        검색 결과에는 시·도~법정동·리 전체 경로가 표시되어 동명을 구분합니다. 「시군구 포함」「읍·면
        포함」을 누르면 목록에는 그 행정단위가 한 줄로만 드며, 분석 시 하위 모든 법정단위가
        포함됩니다 (유료). 복수 합산에서는 사전집계가 없는 극소 단위는 서버가 자동 제외합니다. 현재 선택
        항목{" "}
        <span className="font-semibold text-slate-800">{selectionChipCount}</span>개 · 합산 법정{" "}
        <span className="font-semibold text-slate-800">{resolvedCount}</span>곳 ·{" "}
        {viewMode === "free" ? (
          <span className="text-blue-700 font-medium">
            「무료 통계 조회」는 선택이 정확히 1개일 때만 진행합니다.
          </span>
        ) : (
          <span className="text-blue-700 font-medium">
            유료에서는 여러 칩 선택 후 「기본 통계 보기」로 합산합니다. 선택이 비어 있을 때 단계별
            조건만 채워 두었다면 그 OR 매칭 전체가 한 번에 반영됩니다.
          </span>
        )}
      </p>
    </div>
  );
}
