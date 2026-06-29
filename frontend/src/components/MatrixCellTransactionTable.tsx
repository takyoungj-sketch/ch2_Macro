import { useMemo, useState, useRef, useEffect } from "react";
import clsx from "clsx";
import { simpleTableHeadClass } from "../constants/displayUi";
import type { MatrixCellTransactionItem } from "../types";
import {
  formatLandTxCell,
  formatLandTxContractDate,
  landTxAdminCols,
  landTxSortValue,
  type LandTxSortDir,
  type LandTxSortKey,
} from "../utils/landTxDisplay";

const PAGE_SIZE = 25;

/** "sort-only" = 정렬만, 필터 입력 없음 */
type ColFilterType = "select" | "text" | "sort-only";

interface ColDef {
  key: LandTxSortKey;
  label: string;
  align?: "left" | "right";
  bold?: boolean;
  filterType: ColFilterType;
  textPlaceholder?: string;
}

const COLS: ColDef[] = [
  { key: "contract_date", label: "계약일", filterType: "select" },
  { key: "sigungu", label: "시군구", filterType: "select" },
  { key: "eupmyeondong", label: "읍·면·동", filterType: "select" },
  { key: "ri", label: "동·리", filterType: "select" },
  { key: "lot", label: "지번", filterType: "text", textPlaceholder: "검색" },
  { key: "area", label: "면적(㎡)", align: "right", filterType: "sort-only" },
  { key: "price", label: "금액(만원)", align: "right", filterType: "sort-only" },
  { key: "unit_price", label: "단가", align: "right", bold: true, filterType: "sort-only" },
  { key: "road", label: "도로", filterType: "select" },
  { key: "partial", label: "지분", filterType: "select" },
  { key: "deal_type", label: "유형", filterType: "select" },
];

const SELECT_COLS = COLS.filter((c) => c.filterType === "select");
const TEXT_COLS = COLS.filter((c) => c.filterType === "text");

/** 드롭다운 필터에서 사용하는 표시값 추출 */
function getSelectDisplayValue(r: MatrixCellTransactionItem, key: LandTxSortKey): string {
  const admin = landTxAdminCols(r);
  switch (key) {
    case "contract_date":
      return String(r.contract_year);
    case "sigungu":
      return admin.sigungu?.trim() || "—";
    case "eupmyeondong":
      return admin.eupmyeondong?.trim() || "—";
    case "ri":
      return admin.ri?.trim() || "—";
    case "road":
      return r.road_condition?.trim() || "—";
    case "partial":
      return r.partial_ownership_label?.trim() || "—";
    case "deal_type":
      return r.deal_type?.trim() || "—";
    default:
      return "";
  }
}

function compareValues(
  a: string | number | null,
  b: string | number | null,
  dir: LandTxSortDir,
): number {
  const mul = dir === "asc" ? 1 : -1;
  if (a == null && b == null) return 0;
  if (a == null) return 1 * mul;
  if (b == null) return -1 * mul;
  if (typeof a === "number" && typeof b === "number") return (a - b) * mul;
  return (
    String(a).localeCompare(String(b), "ko", { numeric: true, sensitivity: "base" }) * mul
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 드롭다운 패널
// ─────────────────────────────────────────────────────────────────────────────
interface DropdownPanelProps {
  colKey: LandTxSortKey;
  allValues: string[];
  /** undefined = 전체 포함, Set = 포함할 값 집합 (빈 Set = 전체 해제) */
  included: Set<string> | undefined;
  onToggle: (val: string) => void;
  /** 전체 선택 ↔ 전체 해제 토글 */
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

  // 외부 클릭 닫기
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [containerRef, onClose]);

  const q = search.trim().toLowerCase();
  const filtered = q ? allValues.filter((v) => v.toLowerCase().includes(q)) : allValues;
  // undefined = 전체 선택, 빈 Set = 전체 해제, 값 있는 Set = 일부 선택
  const isAllSelected = included === undefined;

  const isChecked = (val: string) => {
    if (included === undefined) return true;   // 전체 선택
    if (included.size === 0) return false;     // 전체 해제
    return included.has(val);
  };

  return (
    <div
      className="absolute z-50 top-full left-0 mt-0.5 w-44 bg-white border border-slate-200 rounded-lg shadow-lg text-[11px] overflow-hidden"
      onMouseDown={(e) => e.stopPropagation()}
    >
      {/* 검색 */}
      <div className="px-2 pt-2 pb-1 border-b border-slate-100">
        <input
          ref={searchRef}
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="값 검색…"
          className="w-full px-1.5 py-1 border border-slate-200 rounded text-[10px] text-slate-700 placeholder:text-slate-400"
        />
      </div>
      {/* 전체 선택 */}
      <div className="px-2 py-1 border-b border-slate-100">
        <label className="flex items-center gap-1.5 cursor-pointer hover:bg-slate-50 rounded px-0.5 py-0.5">
          <input
            type="checkbox"
            checked={isAllSelected}
            onChange={onToggleAll}
            className="accent-blue-600 w-3 h-3"
          />
          <span className="font-semibold text-slate-700">
            {isAllSelected ? "전체 선택" : "전체 선택"}
          </span>
          <span className="text-slate-400 ml-auto text-[9px]">
            {isAllSelected ? "클릭시 해제" : "클릭시 전체선택"}
          </span>
        </label>
      </div>
      {/* 값 목록 */}
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

// ─────────────────────────────────────────────────────────────────────────────
// 메인 컴포넌트
// ─────────────────────────────────────────────────────────────────────────────
export default function MatrixCellTransactionTable({
  items,
  truncated,
}: {
  items: MatrixCellTransactionItem[];
  truncated?: boolean;
}) {
  /** Select 필터: 포함할 값 집합. undefined = 전체 포함 */
  const [selectFilters, setSelectFilters] = useState<
    Partial<Record<LandTxSortKey, Set<string>>>
  >({});
  /** 텍스트 필터 */
  const [textFilters, setTextFilters] = useState<
    Partial<Record<LandTxSortKey, string>>
  >({});
  const [sortKey, setSortKey] = useState<LandTxSortKey>("contract_date");
  const [sortDir, setSortDir] = useState<LandTxSortDir>("desc");
  const [page, setPage] = useState(1);
  const [openFilterCol, setOpenFilterCol] = useState<LandTxSortKey | null>(null);
  const dropdownContainerRefs = useRef<Partial<Record<LandTxSortKey, HTMLDivElement | null>>>({});

  // Escape 키로 드롭다운 닫기
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

  // 각 select 열의 전체 고유값
  const distinctValues = useMemo(() => {
    const result: Partial<Record<LandTxSortKey, string[]>> = {};
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
  }, [items]);

  // undefined = 비활성, Set(어떤 크기든) = 활성
  const activeFilterCount =
    Object.values(selectFilters).filter((s) => s !== undefined).length +
    Object.values(textFilters).filter((v) => v?.trim()).length;

  const processed = useMemo(() => {
    let rows = [...items];

    // select 필터
    for (const col of SELECT_COLS) {
      const sel = selectFilters[col.key];
      if (sel === undefined) continue;          // 비활성 = 전체 통과
      if (sel.size === 0) { rows = []; break; } // 전체 해제 = 아무것도 없음
      rows = rows.filter((r) => sel.has(getSelectDisplayValue(r, col.key)));
    }

    // 텍스트 필터
    for (const col of TEXT_COLS) {
      const q = textFilters[col.key]?.trim().toLowerCase();
      if (!q) continue;
      rows = rows.filter((r) => {
        if (col.key === "lot") return (r.lot_display ?? "").toLowerCase().includes(q);
        if (col.key === "area")
          return r.area_sqm != null && String(r.area_sqm).includes(q);
        if (col.key === "price") return String(r.total_price_10k).includes(q);
        if (col.key === "unit_price")
          return (
            r.unit_price_per_sqm != null &&
            r.unit_price_per_sqm.toFixed(1).includes(q)
          );
        return false;
      });
    }

    rows.sort((a, b) =>
      compareValues(landTxSortValue(a, sortKey), landTxSortValue(b, sortKey), sortDir),
    );
    return rows;
  }, [items, selectFilters, textFilters, sortKey, sortDir]);

  // 필터 결과 요약 통계
  const filteredStats = useMemo(() => {
    const prices = processed
      .map((r) => r.unit_price_per_sqm)
      .filter((p): p is number => p != null && Number.isFinite(p));
    const mean =
      prices.length > 0 ? prices.reduce((a, b) => a + b, 0) / prices.length : null;
    const sorted = [...prices].sort((a, b) => a - b);
    const median =
      sorted.length > 0
        ? sorted.length % 2 === 1
          ? sorted[Math.floor(sorted.length / 2)]!
          : (sorted[sorted.length / 2 - 1]! + sorted[sorted.length / 2]!) / 2
        : null;
    return { count: processed.length, mean, median };
  }, [processed]);

  const totalPages = Math.max(1, Math.ceil(processed.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const offset = (safePage - 1) * PAGE_SIZE;
  const pageRows = processed.slice(offset, offset + PAGE_SIZE);

  const handleSort = (key: LandTxSortKey) => {
    setPage(1);
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(
        key === "contract_date" || key === "price" || key === "unit_price"
          ? "desc"
          : "asc",
      );
    }
  };

  const toggleSelectValue = (key: LandTxSortKey, val: string) => {
    setPage(1);
    setSelectFilters((prev) => {
      const allVals = distinctValues[key] ?? [];
      const cur = prev[key];
      let next: Set<string>;

      if (cur === undefined) {
        // 전체 선택 상태 → 이 값만 해제 → 나머지 포함 Set 생성
        next = new Set(allVals.filter((v) => v !== val));
      } else {
        next = new Set(cur);
        if (next.has(val)) next.delete(val);
        else next.add(val);
      }

      const nextFilters = { ...prev };
      if (next.size >= allVals.length) {
        delete nextFilters[key]; // 전부 포함이면 필터 비활성화
      } else {
        nextFilters[key] = next; // 빈 Set도 허용 (전체 해제 상태 유지)
      }
      return nextFilters;
    });
  };

  /** 전체 선택 ↔ 전체 해제 토글 */
  const toggleAllValues = (key: LandTxSortKey) => {
    setPage(1);
    setSelectFilters((prev) => {
      const next = { ...prev };
      if (prev[key] === undefined) {
        // 전체 선택 → 전체 해제 (빈 Set)
        next[key] = new Set<string>();
      } else {
        // 일부/전체 해제 → 전체 선택 (undefined)
        delete next[key];
      }
      return next;
    });
  };

  const clearFilters = () => {
    setSelectFilters({});
    setTextFilters({});
    setPage(1);
  };

  const isFilterActive = (key: LandTxSortKey) => {
    if (COLS.find((c) => c.key === key)?.filterType === "select") {
      const s = selectFilters[key];
      return s != null && s.size > 0;
    }
    return Boolean(textFilters[key]?.trim());
  };

  return (
    <div className="space-y-2">
      {/* ── 요약 통계 바 ── */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-2 py-1.5 rounded-lg bg-slate-50 border border-slate-100 text-[11px]">
        <span className="text-slate-500">
          전체{" "}
          <strong className="text-slate-700">
            {items.length.toLocaleString("ko-KR")}
          </strong>
          건
        </span>
        {activeFilterCount > 0 && (
          <>
            <span className="text-indigo-700">
              필터 결과{" "}
              <strong>{filteredStats.count.toLocaleString("ko-KR")}</strong>건
            </span>
            {filteredStats.mean != null && (
              <span className="text-blue-700">
                평균 단가{" "}
                <strong>
                  {filteredStats.mean.toLocaleString("ko-KR", {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })}
                </strong>
                만원/㎡
              </span>
            )}
            {filteredStats.median != null && (
              <span className="text-slate-500">
                중앙값{" "}
                <strong className="text-slate-700">
                  {filteredStats.median.toLocaleString("ko-KR", {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })}
                </strong>
                만원/㎡
              </span>
            )}
            <button
              type="button"
              onClick={clearFilters}
              className="ml-auto px-2 py-0.5 rounded border border-slate-200 text-slate-600 hover:bg-slate-100 text-[10px]"
            >
              필터 초기화 ({activeFilterCount})
            </button>
          </>
        )}
        {activeFilterCount === 0 && (
          <span className="text-slate-400 ml-auto text-[10px]">
            ▾ 열 제목 아래 필터를 사용하세요
          </span>
        )}
        {truncated && (
          <span className="text-amber-700 text-[10px]">
            · 상한 초과 — 로드된 건에만 필터 적용
          </span>
        )}
      </div>

      {/* ── 테이블 ── */}
      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <table className="w-full text-[11px] border-collapse min-w-[1040px]">
          <thead>
            <tr className={simpleTableHeadClass("neutral")}>
              {COLS.map((col) => {
                const filterOn = isFilterActive(col.key);
                return (
                  <th
                    key={col.key}
                    className={clsx(
                      "border border-slate-200 px-1.5 py-1 font-medium align-top",
                      col.align === "right" ? "text-right" : "text-left",
                      col.bold && "text-blue-700",
                    )}
                  >
                    {/* 정렬 버튼 */}
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

                    {/* ── select 필터 ── */}
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
                            setOpenFilterCol((prev) =>
                              prev === col.key ? null : col.key,
                            );
                          }}
                          className={clsx(
                            "w-full flex items-center justify-between px-1.5 py-0.5 rounded border text-[10px] font-normal transition-colors",
                            filterOn
                              ? "border-blue-400 bg-blue-50 text-blue-700"
                              : "border-slate-200 bg-white text-slate-500 hover:border-slate-300",
                          )}
                          title="필터 선택"
                        >
                          <span>
                            {filterOn
                              ? `${selectFilters[col.key]!.size}개 선택`
                              : "전체"}
                          </span>
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

                    {/* ── text 필터 ── */}
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
                          textFilters[col.key]?.trim()
                            ? "border-blue-400"
                            : "border-slate-200",
                        )}
                        onClick={(e) => e.stopPropagation()}
                      />
                    )}

                    {/* ── sort-only: 오름/내림차순 버튼 ── */}
                    {col.filterType === "sort-only" && (
                      <div className="mt-0.5 flex gap-0.5 justify-end">
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
                              : "border-slate-200 text-slate-400 hover:border-slate-300 hover:text-slate-600",
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
                              : "border-slate-200 text-slate-400 hover:border-slate-300 hover:text-slate-600",
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
                <td
                  colSpan={COLS.length}
                  className="border border-slate-200 px-2 py-6 text-center text-slate-400"
                >
                  {activeFilterCount > 0
                    ? "필터 조건에 맞는 거래가 없습니다."
                    : "조건에 맞는 거래가 없습니다."}
                </td>
              </tr>
            ) : (
              pageRows.map((r) => {
                const admin = landTxAdminCols(r);
                return (
                  <tr key={r.id} className="hover:bg-slate-50/50">
                    <td className="border border-slate-200 px-2 py-1 tabular-nums whitespace-nowrap">
                      {formatLandTxContractDate(r)}
                    </td>
                    <td
                      className="border border-slate-200 px-2 py-1 max-w-[120px] truncate whitespace-nowrap"
                      title={admin.sigungu ?? undefined}
                    >
                      {formatLandTxCell(admin.sigungu)}
                    </td>
                    <td
                      className="border border-slate-200 px-2 py-1 max-w-[88px] truncate whitespace-nowrap"
                      title={admin.eupmyeondong ?? undefined}
                    >
                      {formatLandTxCell(admin.eupmyeondong)}
                    </td>
                    <td
                      className="border border-slate-200 px-2 py-1 max-w-[88px] truncate whitespace-nowrap"
                      title={admin.ri ?? undefined}
                    >
                      {formatLandTxCell(admin.ri)}
                    </td>
                    <td
                      className="border border-slate-200 px-2 py-1 max-w-[100px] truncate whitespace-nowrap"
                      title={r.lot_display?.trim() || undefined}
                    >
                      {formatLandTxCell(r.lot_display)}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 text-right tabular-nums whitespace-nowrap">
                      {r.area_sqm != null
                        ? Number(r.area_sqm).toLocaleString("ko-KR", {
                            maximumFractionDigits: 2,
                          })
                        : "—"}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 text-right tabular-nums whitespace-nowrap">
                      {Number(r.total_price_10k).toLocaleString("ko-KR", {
                        maximumFractionDigits: 0,
                      })}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-semibold whitespace-nowrap">
                      {r.unit_price_per_sqm != null
                        ? Number(r.unit_price_per_sqm).toLocaleString("ko-KR", {
                            minimumFractionDigits: 1,
                            maximumFractionDigits: 1,
                          })
                        : "—"}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                      {r.road_condition ?? "—"}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                      {formatLandTxCell(r.partial_ownership_label)}
                    </td>
                    <td className="border border-slate-200 px-2 py-1 whitespace-nowrap">
                      {formatLandTxCell(r.deal_type)}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ── 페이지네이션 ── */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <span className="text-slate-400">
          {processed.length > 0
            ? `${(offset + 1).toLocaleString("ko-KR")}–${Math.min(
                offset + pageRows.length,
                processed.length,
              ).toLocaleString("ko-KR")} / ${processed.length.toLocaleString("ko-KR")}`
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
