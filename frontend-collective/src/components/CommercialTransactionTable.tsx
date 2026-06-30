import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import type { CommercialTransactionRow } from "../types";
import {
  commercialTxDongCell,
  commercialTxRoadWidth,
  commercialTxSortValue,
  formatCommercialTxCell,
  formatCommercialTxContractDate,
  type CommercialTxSortDir,
  type CommercialTxSortKey,
} from "../utils/commercialTxDisplay";

const PAGE_SIZE = 25;

type ColFilterType = "select" | "text" | "sort-only";

interface ColDef {
  key: CommercialTxSortKey;
  label: string;
  align?: "left" | "right";
  filterType: ColFilterType;
  textPlaceholder?: string;
}

function buildCols(isShop: boolean): ColDef[] {
  const cols: ColDef[] = [{ key: "contract_date", label: "계약일", filterType: "select" }];
  if (isShop) {
    cols.push({ key: "lot_number", label: "번지", filterType: "text", textPlaceholder: "검색" });
  }
  cols.push(
    { key: "dong", label: "동", filterType: "select" },
    { key: "zone_type", label: "용도지역", filterType: "select" },
    { key: "building_use", label: "건축물용도", filterType: "select" },
    { key: "road_width", label: "도로폭", filterType: "select" },
  );
  if (!isShop) {
    cols.push({ key: "area_bucket", label: "면적구간", filterType: "select" });
  }
  cols.push(
    { key: "gross_area", label: "연면적(㎡)", align: "right", filterType: "sort-only" },
    { key: "floor", label: "층", align: "right", filterType: "sort-only" },
    { key: "building_year", label: "준공", align: "right", filterType: "sort-only" },
    { key: "price", label: "금액(만원)", align: "right", filterType: "sort-only" },
    { key: "unit_price", label: "단가", align: "right", filterType: "sort-only" },
  );
  return cols;
}

function getSelectDisplayValue(r: CommercialTransactionRow, key: CommercialTxSortKey): string {
  if (key === "contract_date") return formatCommercialTxContractDate(r);
  const v = commercialTxSortValue(r, key);
  if (v == null || v === "") return "—";
  return String(v);
}

function compareValues(
  a: string | number | null,
  b: string | number | null,
  dir: CommercialTxSortDir,
): number {
  const mul = dir === "asc" ? 1 : -1;
  if (a == null && b == null) return 0;
  if (a == null) return 1 * mul;
  if (b == null) return -1 * mul;
  if (typeof a === "number" && typeof b === "number") return (a - b) * mul;
  return String(a).localeCompare(String(b), "ko", { numeric: true, sensitivity: "base" }) * mul;
}

function fmtNum(n?: number | null, digits = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

interface DropdownPanelProps {
  colKey: CommercialTxSortKey;
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
      className="absolute z-50 top-full left-0 mt-0.5 w-44 bg-white border border-slate-200 rounded-lg shadow-lg text-[11px] overflow-hidden"
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div className="px-2 pt-2 pb-1 border-b border-slate-100">
        <input
          ref={searchRef}
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="값 검색…"
          className="w-full px-1.5 py-1 border border-slate-200 rounded text-[10px] text-slate-700 placeholder:text-slate-400 bg-white"
        />
      </div>
      <div className="px-2 py-1 border-b border-slate-100">
        <label className="flex items-center gap-1.5 cursor-pointer hover:bg-slate-50 rounded px-0.5 py-0.5">
          <input
            type="checkbox"
            checked={isAllSelected}
            onChange={onToggleAll}
            className="accent-blue-600 w-3 h-3"
          />
          <span className="font-semibold text-slate-700">전체 선택</span>
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
              className="flex items-center gap-1.5 px-2 py-1 cursor-pointer hover:bg-slate-50"
            >
              <input
                type="checkbox"
                checked={isChecked(val)}
                onChange={() => onToggle(val)}
                className="accent-blue-600 w-3 h-3 shrink-0"
              />
              <span className="truncate text-slate-800">{val}</span>
            </label>
          ))
        )}
      </div>
      <div className="px-2 py-1.5 border-t border-slate-100 flex justify-end">
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

export default function CommercialTransactionTable({
  items,
  isShop,
  truncated,
}: {
  items: CommercialTransactionRow[];
  isShop: boolean;
  truncated?: boolean;
}) {
  const COLS = useMemo(() => buildCols(isShop), [isShop]);
  const SELECT_COLS = useMemo(() => COLS.filter((c) => c.filterType === "select"), [COLS]);
  const TEXT_COLS = useMemo(() => COLS.filter((c) => c.filterType === "text"), [COLS]);

  const [selectFilters, setSelectFilters] = useState<Partial<Record<CommercialTxSortKey, Set<string>>>>({});
  const [textFilters, setTextFilters] = useState<Partial<Record<CommercialTxSortKey, string>>>({});
  const [sortKey, setSortKey] = useState<CommercialTxSortKey>("contract_date");
  const [sortDir, setSortDir] = useState<CommercialTxSortDir>("desc");
  const [page, setPage] = useState(1);
  const [openFilterCol, setOpenFilterCol] = useState<CommercialTxSortKey | null>(null);
  const dropdownContainerRefs = useRef<Partial<Record<CommercialTxSortKey, HTMLDivElement | null>>>({});

  useEffect(() => {
    setSelectFilters({});
    setTextFilters({});
    setPage(1);
    setSortKey("contract_date");
    setSortDir("desc");
  }, [items, isShop]);

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
    const result: Partial<Record<CommercialTxSortKey, string[]>> = {};
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
        const v = commercialTxSortValue(r, col.key);
        return v != null && String(v).toLowerCase().includes(q);
      });
    }

    rows.sort((a, b) =>
      compareValues(commercialTxSortValue(a, sortKey), commercialTxSortValue(b, sortKey), sortDir),
    );
    return rows;
  }, [items, SELECT_COLS, TEXT_COLS, selectFilters, textFilters, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(processed.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const offset = (safePage - 1) * PAGE_SIZE;
  const pageRows = processed.slice(offset, offset + PAGE_SIZE);

  const handleSort = (key: CommercialTxSortKey) => {
    setPage(1);
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(
        key === "contract_date" || key === "price" || key === "unit_price" || key === "gross_area"
          ? "desc"
          : "asc",
      );
    }
  };

  const toggleSelectValue = (key: CommercialTxSortKey, val: string) => {
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

  const toggleAllValues = (key: CommercialTxSortKey) => {
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

  const isFilterActive = (key: CommercialTxSortKey) => {
    const col = COLS.find((c) => c.key === key);
    if (col?.filterType === "select") return selectFilters[key] !== undefined;
    return Boolean(textFilters[key]?.trim());
  };

  const selectFilterLabel = (key: CommercialTxSortKey) => {
    const sel = selectFilters[key];
    if (sel === undefined) return "전체";
    if (sel.size === 0) return "선택 없음";
    return `${sel.size}개 선택`;
  };

  return (
    <div className="space-y-2 flex flex-col flex-1 min-h-0">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-2 py-1.5 rounded-lg bg-slate-50 border border-slate-100 text-[11px]">
        <span className="text-slate-500">
          로드 <strong className="text-slate-700">{items.length.toLocaleString("ko-KR")}</strong>건
        </span>
        {activeFilterCount > 0 && (
          <>
            <span className="text-indigo-700">
              필터 결과 <strong>{processed.length.toLocaleString("ko-KR")}</strong>건
            </span>
            <button
              type="button"
              onClick={clearFilters}
              className="ml-auto px-2 py-0.5 rounded border border-slate-200 text-slate-600 hover:bg-slate-100 text-[10px]"
            >
              필터 초기화 ({activeFilterCount})
            </button>
          </>
        )}
        {processed.length === 0 && activeFilterCount > 0 && (
          <span className="text-amber-700 font-medium">
            표시할 거래 없음 — 필터를 조정하거나 초기화하세요
          </span>
        )}
        {activeFilterCount === 0 && processed.length > 0 && (
          <span className="text-slate-400 ml-auto text-[10px]">▾ 열 제목 아래 필터를 사용하세요</span>
        )}
        {truncated && (
          <span className="text-amber-700 text-[10px]">· 상한 초과 — 로드된 건에만 필터 적용</span>
        )}
      </div>

      <div className="flex-1 min-h-[280px] overflow-x-auto overflow-y-auto rounded-lg border border-slate-100">
        <table className="w-full text-[11px] border-collapse min-w-[720px]">
          <thead className="sticky top-0 z-10">
            <tr className="bg-slate-50 text-slate-600">
              {COLS.map((col) => {
                const filterOn = isFilterActive(col.key);
                return (
                  <th
                    key={col.key}
                    className={clsx(
                      "border border-slate-200 px-1.5 py-1 font-medium align-top",
                      col.align === "right" ? "text-right" : "text-left",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => handleSort(col.key)}
                      className={clsx(
                        "flex items-center gap-0.5 w-full hover:text-slate-900",
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
                              ? "border-amber-400 bg-amber-50 text-amber-800"
                              : filterOn
                                ? "border-blue-400 bg-blue-50 text-blue-700"
                                : "border-slate-200 bg-white text-slate-500 hover:border-slate-300",
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
                          "mt-0.5 w-full min-w-0 px-1 py-0.5 text-[10px] font-normal border rounded bg-white text-slate-700 placeholder:text-slate-400",
                          textFilters[col.key]?.trim() ? "border-blue-400" : "border-slate-200",
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
                              ? "border-blue-400 bg-blue-50 text-blue-700 font-semibold"
                              : "border-slate-200 text-slate-400 hover:border-slate-300",
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
                              ? "border-blue-400 bg-blue-50 text-blue-700 font-semibold"
                              : "border-slate-200 text-slate-400 hover:border-slate-300",
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
          <tbody className="text-slate-800">
            {pageRows.length === 0 ? (
              <tr>
                <td colSpan={COLS.length} className="border border-slate-200 px-2 py-6 text-center text-slate-400 align-top h-40">
                  {activeFilterCount > 0
                    ? "필터 조건에 맞는 거래가 없습니다."
                    : "조건에 맞는 거래가 없습니다."}
                </td>
              </tr>
            ) : (
              pageRows.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50/50">
                  <td className="border border-slate-200 px-2 py-1 tabular-nums whitespace-nowrap">
                    {formatCommercialTxContractDate(t)}
                  </td>
                  {isShop && (
                    <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                      {formatCommercialTxCell(t.lot_number)}
                    </td>
                  )}
                  <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                    {commercialTxDongCell(t)}
                  </td>
                  <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                    {formatCommercialTxCell(t.zone_type)}
                  </td>
                  <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                    {formatCommercialTxCell(t.building_use)}
                  </td>
                  <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                    {commercialTxRoadWidth(t)}
                  </td>
                  {!isShop && (
                    <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                      {formatCommercialTxCell(t.area_bucket_label)}
                    </td>
                  )}
                  <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                    {fmtNum(t.gross_area)}
                  </td>
                  <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                    {t.floor != null ? (Number.isInteger(t.floor) ? t.floor : t.floor.toFixed(1)) : "—"}
                  </td>
                  <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                    {t.building_year ?? "—"}
                  </td>
                  <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                    {fmtNum(t.price, 0)}
                  </td>
                  <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-semibold">
                    {fmtNum(t.unit_price)}
                  </td>
                </tr>
              ))
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
            className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
          >
            이전
          </button>
          <button
            type="button"
            disabled={safePage >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
          >
            다음
          </button>
        </div>
      </div>
    </div>
  );
}
