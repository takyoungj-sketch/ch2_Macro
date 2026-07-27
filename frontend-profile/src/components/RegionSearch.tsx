import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  buildFlattenedRegionSuggestions,
  commonTierCodesFromLooseRows,
  flatEntryToSearchResult,
  formatRegionHierarchyLabel,
  isLooseMultiSegmentQuery,
  resolveBeopjungriFromLooseAddressLine,
  resolveLooseAddressViaTokenSearch,
  tryResolveUniqueRegionSearch,
  uniquePickToSearchResult,
  type RegionSearchFlatEntry,
  type RegionNameInfo,
  type RegionSearchResult,
} from "@ch2/region-picker";
import { fetchRegions, searchRegions } from "../api/profile";

export type { RegionSearchResult };

interface Props {
  onSelect: (region: RegionSearchResult) => void;
  /** URL·외부 딥링크로 선택된 지역 — 검색창 라벨 동기화 (D-030 P1-e). */
  displayQuery?: string;
}

function flatEntryBadge(entry: RegionSearchFlatEntry): string | null {
  switch (entry.kind) {
    case "sido_aggregate":
      return "시/도";
    case "city_aggregate":
      return "시";
    case "sigungu_aggregate":
      return "시군구";
    case "eup_aggregate":
      return "읍·면·동";
    case "beopjungri":
      return "리";
  }
}

export default function RegionSearch({ onSelect, displayQuery }: Props) {
  const [query, setQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const [localError, setLocalError] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (displayQuery != null) setQuery(displayQuery);
  }, [displayQuery]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  const { data: catalog = [], isLoading: catalogLoading, isFetching: catalogFetching } = useQuery({
    queryKey: ["region-catalog", "full"],
    queryFn: () => fetchRegions(),
    staleTime: Infinity,
  });

  const searchEnabled = debouncedSearch.length >= 2;
  const { data: searchHits = [], isFetching: searchLoading } = useQuery({
    queryKey: ["region-search", debouncedSearch],
    queryFn: () => searchRegions(debouncedSearch),
    enabled: searchEnabled,
    staleTime: 60_000,
  });

  const looseResolve = useMemo(() => {
    if (!isLooseMultiSegmentQuery(debouncedSearch)) return null;
    if (catalog.length === 0) return null;
    return resolveBeopjungriFromLooseAddressLine(catalog, debouncedSearch);
  }, [debouncedSearch, catalog]);

  const flatSuggestions = useMemo((): RegionSearchFlatEntry[] => {
    if (looseResolve != null) {
      if (looseResolve.codes.length <= 1) return [];
      const map = new Map<string, (typeof catalog)[number]>();
      for (const r of looseResolve.rows) {
        const c = String(r.beopjungri_code ?? "").trim();
        if (!c) continue;
        if (!map.has(c)) map.set(c, r);
      }
      return [...map.values()]
        .sort((a, b) =>
          formatRegionHierarchyLabel(a).localeCompare(formatRegionHierarchyLabel(b), "ko-KR"),
        )
        .map((row) => ({ kind: "beopjungri" as const, row }));
    }
    if (!searchEnabled) return [];
    return buildFlattenedRegionSuggestions(searchHits, debouncedSearch, {
      maxSigungu: 50,
      maxAgg: 40,
      maxBeop: 400,
    });
  }, [looseResolve, searchHits, debouncedSearch, searchEnabled]);

  useEffect(() => {
    setHighlightIdx(flatSuggestions.length > 0 ? 0 : -1);
  }, [flatSuggestions]);

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>("[data-hl=true]");
    el?.scrollIntoView({ block: "nearest" });
  }, [highlightIdx]);

  const pickResult = (result: RegionSearchResult) => {
    setLocalError(null);
    onSelect(result);
    setQuery(result.label);
    setOpen(false);
    setHighlightIdx(-1);
  };

  const pickEntry = (entry: RegionSearchFlatEntry) => {
    pickResult(flatEntryToSearchResult(entry));
  };

  const applyLooseResolve = (
    resolved: { rows: RegionNameInfo[]; codes: string[] },
  ) => {
    const { rows, codes } = resolved;
    if (codes.length === 1) {
      pickEntry({ kind: "beopjungri", row: rows[0]! });
      return;
    }
    if (codes.length === 0) {
      setLocalError("입력한 지명 조합과 맞는 법정동·리가 없습니다.");
      return;
    }

    const { eupmyeondongCode, sigunguCode } = commonTierCodesFromLooseRows(rows);
    if (eupmyeondongCode) {
      const sample = rows.find((r) => r.eupmyeondong_code === eupmyeondongCode)!;
      pickEntry({
        kind: "eup_aggregate",
        eupCode: eupmyeondongCode,
        primaryLabel: [sample.sido_name, sample.sigungu_name, sample.eupmyeondong_name]
          .filter(Boolean)
          .join(" "),
        subtitle: "읍·면·동",
        countInSample: rows.length,
        sample,
      });
      return;
    }
    if (sigunguCode) {
      const sample = rows.find((r) => r.sigungu_code === sigunguCode)!;
      pickEntry({
        kind: "sigungu_aggregate",
        sigunguCode,
        primaryLabel: [sample.sido_name, sample.sigungu_name].filter(Boolean).join(" "),
        subtitle: "시군구",
        countInSample: rows.length,
        sample,
      });
      return;
    }

    if (flatSuggestions.length > 0) {
      pickEntry(flatSuggestions[highlightIdx >= 0 ? highlightIdx : 0]!);
      return;
    }

    setLocalError(
      "후보가 여러 행정구역에 걸쳐 있습니다. 아래 목록에서 고르거나, 지명을 더 붙여 한 곳만 되게 해 주세요.",
    );
  };

  const onSearchKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      setQuery("");
      setLocalError(null);
      return;
    }

    const qLive = query.trim();

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

    if (e.key !== "Enter") return;
    e.preventDefault();

    if (qLive.length < 2) return;
    if ((catalogLoading || catalogFetching) && catalog.length === 0) {
      setLocalError("지역 목록을 불러온 뒤 Enter로 확정해 주세요.");
      return;
    }

    if (isLooseMultiSegmentQuery(qLive)) {
      let resolved = resolveBeopjungriFromLooseAddressLine(catalog, qLive);
      if (resolved.codes.length === 0) {
        resolved = await resolveLooseAddressViaTokenSearch(
          (token) => fetchRegions({ search: token, limit: 400 }),
          qLive,
        );
      }
      applyLooseResolve(resolved);
      return;
    }

    if (flatSuggestions.length > 0) {
      pickEntry(flatSuggestions[highlightIdx >= 0 ? highlightIdx : 0]!);
      return;
    }

    const resolved = tryResolveUniqueRegionSearch(catalog, qLive, "paid");
    if (resolved) {
      pickResult(uniquePickToSearchResult(resolved));
      return;
    }

    setLocalError(
      "엔터로 확정할 단일 후보가 없습니다. 아래 목록에서 항목을 고르거나, 동명이면 상위 행정구역 이름을 덧붙이세요.",
    );
  };

  const loading = searchLoading && searchEnabled;
  const showDropdown = open && (query.trim().length >= 2 || loading || catalogLoading);

  return (
    <div ref={boxRef} className="relative w-full max-w-md">
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setLocalError(null);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onSearchKeyDown}
        placeholder="지역명·법정동코드·주소 한 줄 (예: 흥덕구 가경동, 4313010600)"
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500 dark:border-slate-600 dark:bg-slate-900"
      />
      {localError && <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">{localError}</p>}
      {showDropdown && (
        <div className="absolute z-10 mt-1 w-full rounded-md border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
          {loading || (catalogLoading && flatSuggestions.length === 0) ? (
            <div className="px-3 py-2 text-sm text-slate-400">검색 중...</div>
          ) : flatSuggestions.length === 0 ? (
            <div className="px-3 py-2 text-sm text-slate-400">결과 없음</div>
          ) : (
            <ul ref={listRef} className="max-h-80 overflow-y-auto py-1">
              {flatSuggestions.map((entry, idx) => {
                const hl = idx === highlightIdx;
                const badge = flatEntryBadge(entry);
                const primary =
                  entry.kind === "beopjungri"
                    ? formatRegionHierarchyLabel(entry.row)
                    : entry.primaryLabel;
                const subtitle =
                  entry.kind === "beopjungri"
                    ? String(entry.row.beopjungri_code).trim()
                    : entry.subtitle;

                return (
                  <li key={`${entry.kind}-${idx}-${subtitle}`}>
                    <button
                      type="button"
                      data-hl={hl ? "true" : undefined}
                      className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700 ${
                        hl ? "bg-slate-100 dark:bg-slate-700" : ""
                      }`}
                      onMouseEnter={() => setHighlightIdx(idx)}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => pickEntry(entry)}
                    >
                      <span>
                        <span className="font-medium">{primary}</span>
                        <span className="ml-1.5 text-xs text-slate-400">{subtitle}</span>
                      </span>
                      {badge && (
                        <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 dark:bg-slate-700 dark:text-slate-300">
                          {badge}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
