import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import type { AssetType, BuiltTransactionRow } from "../types";
import { isOnlyDetached, isUnifiedAsset } from "../utils/assetTypes";
import {
  builtTxAdminCols,
  builtTxBuildingYear,
  builtTxSortValue,
  formatBuiltTxCell,
  formatBuiltTxContractDate,
  type BuiltTxSortDir,
  type BuiltTxSortKey,
} from "../utils/builtTxDisplay";

const PAGE_SIZE = 25;

type ColFilterType = "select" | "text" | "sort-only";

interface ColDef {
  key: BuiltTxSortKey;
  label: string;
  align?: "left" | "right";
  filterType: ColFilterType;
  textPlaceholder?: string;
}

const ASSET_LABELS: Record<string, string> = {
  commercial: "상업",
  factory: "공장",
  detached: "단독",
};

function buildCols(assetType: AssetType): ColDef[] {
  const cols: ColDef[] = [
    { key: "contract_date", label: "계약일", filterType: "select" },
    { key: "sido", label: "시도", filterType: "select" },
    { key: "sigungu", label: "시군구", filterType: "select" },
    { key: "gu_eup", label: "구·읍", filterType: "select" },
    { key: "dong_ri", label: "읍·면·동", filterType: "select" },
    { key: "ri", label: "리", filterType: "select" },
    { key: "lot", label: "지번", filterType: "text", textPlaceholder: "검색" },
    { key: "road_name", label: "도로명", filterType: "text", textPlaceholder: "검색" },
  ];
  if (isUnifiedAsset(assetType)) {
    cols.unshift({ key: "asset_type", label: "유형", filterType: "select" });
  }
  if (!isOnlyDetached(assetType)) {
    cols.push({ key: "zone_type", label: "용도지역", filterType: "select" });
  }
  cols.push({
    key: "building_use",
    label: isOnlyDetached(assetType) ? "주택유형" : "건축물용도",
    filterType: "select",
  });
  cols.push(
    { key: "price", label: "금액(만)", align: "right", filterType: "sort-only" },
    { key: "gross_area", label: "연면적", align: "right", filterType: "sort-only" },
    { key: "land_area", label: "대지", align: "right", filterType: "sort-only" },
    { key: "building_year", label: "건축연도", align: "right", filterType: "sort-only" },
    { key: "road_width", label: "도로조건", filterType: "select" },
  );
  return cols;
}

function getSelectDisplayValue(r: BuiltTransactionRow, key: BuiltTxSortKey): string {
  if (key === "contract_date") return formatBuiltTxContractDate(r);
  const v = builtTxSortValue(r, key);
  if (v == null || v === "") return "—";
  return String(v);
}

function compareValues(
  a: string | number | null,
  b: string | number | null,
  dir: BuiltTxSortDir,
): number {
  const mul = dir === "asc" ? 1 : -1;
  if (a == null && b == null) return 0;
  if (a == null) return 1 * mul;
  if (b == null) return -1 * mul;
  if (typeof a === "number" && typeof b === "number") return (a - b) * mul;
  return String(a).localeCompare(String(b), "ko", { numeric: true, sensitivity: "base" }) * mul;
}

function fmtNum(n?: number | null, digits = 0) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

interface DropdownPanelProps {
  colKey: BuiltTxSortKey;
  allValues: string[];
  included: Set<string> | undefined;
  onToggle: (val: string) => void;
  onToggleAll: () => void;
  onClose: () => void;
  containerRef: React.RefObject<HTMLDivElement | null>;
}

function DropdownPanel({
  colKey,
  allValues,
  included,
  onToggle,
  onToggleAll,
  onClose,
  containerRef,
}: DropdownPanelProps) {
  const [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [containerRef, onClose]);

  const q = search.trim().toLowerCase();
  const filtered = q ? allValues.filter((v) => v.toLowerCase().includes(q)) : allValues;
  const isAllSelected = included === undefined;

  const isChecked = (val: string) => {
    if (included === undefined) return true;
    if (included.size === 0) return false;
    return included.has(val);
  };

  return (
    <div
      className="absolute z-50 top-full left-0 mt-0.5 w-44 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg shadow-lg text-[11px] overflow-hidden"
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div className="px-2 pt-2 pb-1 border-b border-slate-100 dark:border-slate-700">
        <input
          ref={searchRef}
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="값 검색…"
          className="w-full px-1.5 py-1 border border-slate-200 dark:border-slate-600 rounded text-[10px] text-slate-700 dark:text-slate-200 placeholder:text-slate-400 bg-white dark:bg-slate-900"
        />
      </div>
      <div className="px-2 py-1 border-b border-slate-100 dark:border-slate-700">
        <label className="flex items-center gap-1.5 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50 rounded px-0.5 py-0.5">
          <input
            type="checkbox"
            checked={isAllSelected}
            onChange={onToggleAll}
            className="accent-blue-600 w-3 h-3"
          />
          <span className="font-semibold text-slate-700 dark:text-slate-200">전체 선택</span>
          <span className="text-slate-400 ml-auto text-[9px]">
            {isAllSelected ? "클릭시 해제" : "클릭시 전체선택"}
          </span>
        </label>
      </div>
      <div className="max-h-52 overflow-y-auto">
        {filtered.length === 0 ? (
          <p className="text-center text-slate-400 py-3">결과 없음</p>
        ) : (
          filtered.map((val) => (
            <label
              key={`${colKey}-${val}`}
              className="flex items-center gap-1.5 px-2 py-1 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50"
            >
              <input
                type="checkbox"
                checked={isChecked(val)}
                onChange={() => onToggle(val)}
                className="accent-blue-600 w-3 h-3 shrink-0"
              />
              <span className="truncate text-slate-800 dark:text-slate-100">{val}</span>
            </label>
          ))
        )}
      </div>
      <div className="px-2 py-1.5 border-t border-slate-100 dark:border-slate-700 flex justify-end">
        <button
          type="button"
          onClick={onClose}
          className="text-[10px] px-2 py-0.5 rounded bg-blue-600 text-white hover:bg-blue-700"
        >
          확인
        </button>
      </div>
    </div>
  );
}

export default function BuiltTransactionTable({
  items,
  assetType,
  truncated,
}: {
  items: BuiltTransactionRow[];
  assetType: AssetType;
  truncated?: boolean;
}) {
  const COLS = useMemo(() => buildCols(assetType), [assetType]);
  const SELECT_COLS = useMemo(() => COLS.filter((c) => c.filterType === "select"), [COLS]);
  const TEXT_COLS = useMemo(() => COLS.filter((c) => c.filterType === "text"), [COLS]);

  const [selectFilters, setSelectFilters] = useState<Partial<Record<BuiltTxSortKey, Set<string>>>>({});
  const [textFilters, setTextFilters] = useState<Partial<Record<BuiltTxSortKey, string>>>({});
  const [sortKey, setSortKey] = useState<BuiltTxSortKey>("contract_date");
  const [sortDir, setSortDir] = useState<BuiltTxSortDir>("desc");
  const [page, setPage] = useState(1);
  const [openFilterCol, setOpenFilterCol] = useState<BuiltTxSortKey | null>(null);
  const dropdownContainerRefs = useRef<Partial<Record<BuiltTxSortKey, HTMLDivElement | null>>>({});

  useEffect(() => {
    setSelectFilters({});
    setTextFilters({});
    setPage(1);
    setSortKey("contract_date");
    setSortDir("desc");
  }, [items, assetType]);

  useEffect(() => {
    if (!openFilterCol) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpenFilterCol(null);
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [openFilterCol]);

  const distinctValues = useMemo(() => {
    const result: Partial<Record<BuiltTxSortKey, string[]>> = {};
    for (const col of SELECT_COLS) {
      const vals = new Set<string>();
      for (const item of items) {
        vals.add(getSelectDisplayValue(item, col.key));
      }
      result[col.key] = [...vals].sort((a, b) =>
        a.localeCompare(b, "ko", { numeric: true }),
      );
    }
    return result;
  }, [items, SELECT_COLS]);

  const activeFilterCount =
    Object.values(selectFilters).filter((s) => s !== undefined).length +
    Object.values(textFilters).filter((v) => v?.trim()).length;

  const processed = useMemo(() => {
    let rows = [...items];

    for (const col of SELECT_COLS) {
      const sel = selectFilters[col.key];
      if (sel === undefined) continue;
      if (sel.size === 0) {
        rows = [];
        break;
      }
      rows = rows.filter((r) => sel.has(getSelectDisplayValue(r, col.key)));
    }

    for (const col of TEXT_COLS) {
      const q = textFilters[col.key]?.trim().toLowerCase();
      if (!q) continue;
      rows = rows.filter((r) => {
        const v = builtTxSortValue(r, col.key);
        return v != null && String(v).toLowerCase().includes(q);
      });
    }

    rows.sort((a, b) =>
      compareValues(builtTxSortValue(a, sortKey), builtTxSortValue(b, sortKey), sortDir),
    );
    return rows;
  }, [items, SELECT_COLS, TEXT_COLS, selectFilters, textFilters, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(processed.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const offset = (safePage - 1) * PAGE_SIZE;
  const pageRows = processed.slice(offset, offset + PAGE_SIZE);

  const handleSort = (key: BuiltTxSortKey) => {
    setPage(1);
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(
        key === "contract_date" || key === "price" || key === "gross_area" || key === "land_area"
          ? "desc"
          : "asc",
      );
    }
  };

  const toggleSelectValue = (key: BuiltTxSortKey, val: string) => {
    setPage(1);
    setSelectFilters((prev) => {
      const allVals = distinctValues[key] ?? [];
      const cur = prev[key];
      let next: Set<string>;
      if (cur === undefined) {
        next = new Set(allVals.filter((v) => v !== val));
      } else {
        next = new Set(cur);
        if (next.has(val)) next.delete(val);
        else next.add(val);
      }
      const nextFilters = { ...prev };
      if (next.size >= allVals.length) delete nextFilters[key];
      else nextFilters[key] = next;
      return nextFilters;
    });
  };

  const toggleAllValues = (key: BuiltTxSortKey) => {
    setPage(1);
    setSelectFilters((prev) => {
      const next = { ...prev };
      if (prev[key] === undefined) next[key] = new Set<string>();
      else delete next[key];
      return next;
    });
  };

  const clearFilters = () => {
    setSelectFilters({});
    setTextFilters({});
    setPage(1);
  };

  const isFilterActive = (key: BuiltTxSortKey) => {
    const col = COLS.find((c) => c.key === key);
    if (col?.filterType === "select") {
      return selectFilters[key] !== undefined;
    }
    return Boolean(textFilters[key]?.trim());
  };

  const selectFilterLabel = (key: BuiltTxSortKey) => {
    const sel = selectFilters[key];
    if (sel === undefined) return "전체";
    if (sel.size === 0) return "선택 없음";
    return `${sel.size}개 선택`;
  };

  const showZone = !isOnlyDetached(assetType);
  const showAssetCol = isUnifiedAsset(assetType);

  return (
    <div className="space-y-2 flex flex-col flex-1 min-h-0">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-2 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700 text-[11px]">
        <span className="text-slate-500 dark:text-slate-400">
          로드 <strong className="text-slate-700 dark:text-slate-200">{items.length.toLocaleString("ko-KR")}</strong>건
        </span>
        {activeFilterCount > 0 && (
          <>
            <span className="text-indigo-700 dark:text-indigo-400">
              필터 결과 <strong>{processed.length.toLocaleString("ko-KR")}</strong>건
            </span>
            <button
              type="button"
              onClick={clearFilters}
              className="ml-auto px-2 py-0.5 rounded border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 text-[10px]"
            >
              필터 초기화 ({activeFilterCount})
            </button>
          </>
        )}
        {processed.length === 0 && activeFilterCount > 0 && (
          <span className="text-amber-700 dark:text-amber-400 font-medium">
            표시할 거래 없음 — 필터를 조정하거나 초기화하세요
          </span>
        )}
        {activeFilterCount === 0 && processed.length > 0 && (
          <span className="text-slate-400 ml-auto text-[10px]">▾ 열 제목 아래 필터를 사용하세요</span>
        )}
        {truncated && (
          <span className="text-amber-700 dark:text-amber-400 text-[10px]">
            · 상한 초과 — 로드된 건에만 필터 적용
          </span>
        )}
      </div>

      <div className="modal-table-wrap flex-1 min-h-[280px] overflow-x-auto overflow-y-auto rounded-lg border border-slate-100 dark:border-slate-700">
        <table className="w-full text-[11px] border-collapse min-w-[1100px] modal-inner-table">
          <thead className="sticky top-0 z-10">
            <tr className="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              {COLS.map((col) => {
                const filterOn = isFilterActive(col.key);
                return (
                  <th
                    key={col.key}
                    className={clsx(
                      "border px-1.5 py-1 font-medium align-top",
                      col.align === "right" ? "text-right" : "text-left",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => handleSort(col.key)}
                      className={clsx(
                        "flex items-center gap-0.5 w-full hover:text-slate-900 dark:hover:text-slate-100",
                        col.align === "right" ? "justify-end" : "justify-start",
                      )}
                      title="클릭: 정렬"
                    >
                      <span>{col.label}</span>
                      {sortKey === col.key && (
                        <span className="text-[9px] text-indigo-600" aria-hidden>
                          {sortDir === "asc" ? "▲" : "▼"}
                        </span>
                      )}
                    </button>

                    {col.filterType === "select" && (
                      <div
                        className="relative mt-0.5"
                        ref={(el) => {
                          dropdownContainerRefs.current[col.key] = el;
                        }}
                      >
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenFilterCol((prev) => (prev === col.key ? null : col.key));
                          }}
                          className={clsx(
                            "w-full flex items-center justify-between px-1.5 py-0.5 rounded border text-[10px] font-normal transition-colors",
                            selectFilters[col.key] !== undefined && selectFilters[col.key]!.size === 0
                              ? "border-amber-400 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300"
                              : filterOn
                                ? "border-blue-400 bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300"
                                : "border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-500 hover:border-slate-300",
                          )}
                        >
                          <span>{selectFilterLabel(col.key)}</span>
                          <span aria-hidden>▾</span>
                        </button>
                        {openFilterCol === col.key && (
                          <DropdownPanel
                            colKey={col.key}
                            allValues={distinctValues[col.key] ?? []}
                            included={selectFilters[col.key]}
                            onToggle={(val) => toggleSelectValue(col.key, val)}
                            onToggleAll={() => toggleAllValues(col.key)}
                            onClose={() => setOpenFilterCol(null)}
                            containerRef={{
                              current: dropdownContainerRefs.current[col.key] ?? null,
                            }}
                          />
                        )}
                      </div>
                    )}

                    {col.filterType === "text" && (
                      <input
                        type="search"
                        value={textFilters[col.key] ?? ""}
                        onChange={(e) => {
                          setPage(1);
                          setTextFilters((prev) => {
                            const next = { ...prev };
                            if (!e.target.value.trim()) delete next[col.key];
                            else next[col.key] = e.target.value;
                            return next;
                          });
                        }}
                        placeholder={col.textPlaceholder ?? "검색"}
                        className={clsx(
                          "mt-0.5 w-full min-w-0 px-1 py-0.5 text-[10px] font-normal border rounded bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 placeholder:text-slate-400",
                          textFilters[col.key]?.trim()
                            ? "border-blue-400"
                            : "border-slate-200 dark:border-slate-600",
                        )}
                        onClick={(e) => e.stopPropagation()}
                      />
                    )}

                    {col.filterType === "sort-only" && (
                      <div
                        className={clsx(
                          "mt-0.5 flex gap-0.5",
                          col.align === "right" ? "justify-end" : "justify-start",
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            setSortKey(col.key);
                            setSortDir("asc");
                            setPage(1);
                          }}
                          className={clsx(
                            "px-1 py-0.5 text-[9px] rounded border transition-colors",
                            sortKey === col.key && sortDir === "asc"
                              ? "border-blue-400 bg-blue-50 dark:bg-blue-950/40 text-blue-700 font-semibold"
                              : "border-slate-200 dark:border-slate-600 text-slate-400 hover:border-slate-300",
                          )}
                          title="오름차순"
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSortKey(col.key);
                            setSortDir("desc");
                            setPage(1);
                          }}
                          className={clsx(
                            "px-1 py-0.5 text-[9px] rounded border transition-colors",
                            sortKey === col.key && sortDir === "desc"
                              ? "border-blue-400 bg-blue-50 dark:bg-blue-950/40 text-blue-700 font-semibold"
                              : "border-slate-200 dark:border-slate-600 text-slate-400 hover:border-slate-300",
                          )}
                          title="내림차순"
                        >
                          ↓
                        </button>
                      </div>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={COLS.length}
                  className="border px-2 py-6 text-center text-slate-400 align-top h-40"
                >
                  {activeFilterCount > 0
                    ? "필터 조건에 맞는 거래가 없습니다."
                    : "조건에 맞는 거래가 없습니다."}
                </td>
              </tr>
            ) : (
              pageRows.map((r) => {
                const admin = builtTxAdminCols(r);
                const byear = builtTxBuildingYear(r);
                return (
                  <tr key={r.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                    {showAssetCol && (
                      <td className="border px-2 py-1 whitespace-nowrap">
                        {ASSET_LABELS[r.asset_type] ?? r.asset_type}
                      </td>
                    )}
                    <td className="border px-2 py-1 tabular-nums whitespace-nowrap">
                      {formatBuiltTxContractDate(r)}
                    </td>
                    <td className="border px-2 py-1 max-w-[72px] truncate" title={admin.sido ?? undefined}>
                      {formatBuiltTxCell(admin.sido)}
                    </td>
                    <td className="border px-2 py-1 max-w-[88px] truncate" title={admin.sigungu ?? undefined}>
                      {formatBuiltTxCell(admin.sigungu)}
                    </td>
                    <td className="border px-2 py-1 max-w-[88px] truncate" title={admin.gu_eup ?? undefined}>
                      {formatBuiltTxCell(admin.gu_eup)}
                    </td>
                    <td className="border px-2 py-1 max-w-[88px] truncate" title={admin.dong_ri ?? undefined}>
                      {formatBuiltTxCell(admin.dong_ri)}
                    </td>
                    <td className="border px-2 py-1 max-w-[88px] truncate" title={admin.ri ?? undefined}>
                      {formatBuiltTxCell(admin.ri)}
                    </td>
                    <td className="border px-2 py-1 max-w-[4.5rem] truncate" title={admin.lot ?? undefined}>
                      {formatBuiltTxCell(admin.lot)}
                    </td>
                    <td className="border px-2 py-1 max-w-[9rem] truncate" title={r.road_name ?? undefined}>
                      {formatBuiltTxCell(r.road_name)}
                    </td>
                    {showZone && (
                      <td className="border px-2 py-1 whitespace-nowrap">
                        {showAssetCol && r.asset_type === "detached"
                          ? "—"
                          : formatBuiltTxCell(r.zone_type)}
                      </td>
                    )}
                    <td className="border px-2 py-1 whitespace-nowrap">
                      {formatBuiltTxCell(r.building_use)}
                    </td>
                    <td className="border px-2 py-1 text-right tabular-nums">{fmtNum(r.price)}</td>
                    <td className="border px-2 py-1 text-right tabular-nums">{fmtNum(r.gross_area, 1)}</td>
                    <td className="border px-2 py-1 text-right tabular-nums">{fmtNum(r.land_area, 1)}</td>
                    <td className="border px-2 py-1 text-right tabular-nums">{byear ?? "—"}</td>
                    <td className="border px-2 py-1 max-w-[8rem] truncate" title={r.road_width_label ?? undefined}>
                      {formatBuiltTxCell(r.road_width_label)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <span className="text-slate-400">
          {processed.length > 0
            ? `${(offset + 1).toLocaleString("ko-KR")}–${Math.min(offset + pageRows.length, processed.length).toLocaleString("ko-KR")} / ${processed.length.toLocaleString("ko-KR")}`
            : "0건"}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={safePage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="px-2 py-1 rounded border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            이전
          </button>
          <button
            type="button"
            disabled={safePage >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="px-2 py-1 rounded border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            다음
          </button>
        </div>
      </div>
    </div>
  );
}
