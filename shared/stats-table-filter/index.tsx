// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

export type SortDir = "asc" | "desc";
export type RangeBound = { min: string; max: string };

export function compareValues(a: string | number | null, b: string | number | null, dir: SortDir): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  const mul = dir === "asc" ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") return (a - b) * mul;
  return String(a).localeCompare(String(b), "ko", { numeric: true, sensitivity: "base" }) * mul;
}

export function parseBound(raw: string): number | null {
  const t = raw.trim().replace(/,/g, "");
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

export function inRange(value: number | null, bound: RangeBound | undefined): boolean {
  if (!bound) return true;
  const min = parseBound(bound.min);
  const max = parseBound(bound.max);
  if (min == null && max == null) return true;
  if (value == null) return false;
  if (min != null && value < min) return false;
  if (max != null && value > max) return false;
  return true;
}

export function rangeIsActive(bound: RangeBound | undefined): boolean {
  return Boolean(bound && (parseBound(bound.min) != null || parseBound(bound.max) != null));
}

export const filterInputClass =
  "w-full min-w-0 px-0.5 py-0.5 text-[10px] font-normal border border-slate-200 dark:border-slate-600 rounded bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200";

export function SortButtons({
  active,
  dir,
  onAsc,
  onDesc,
}: {
  active: boolean;
  dir: SortDir;
  onAsc: () => void;
  onDesc: () => void;
}) {
  const btn = (on: boolean) =>
    clsx(
      "px-1 py-0.5 text-[9px] rounded border transition-colors",
      on
        ? "border-blue-400 bg-blue-50 dark:bg-blue-950/40 text-blue-700 font-semibold"
        : "border-slate-200 dark:border-slate-600 text-slate-400 hover:border-slate-300",
    );
  return (
    <div className="mt-0.5 flex justify-center gap-0.5">
      <button type="button" className={btn(active && dir === "asc")} title="오름차순" onClick={onAsc}>
        ↑
      </button>
      <button type="button" className={btn(active && dir === "desc")} title="내림차순" onClick={onDesc}>
        ↓
      </button>
    </div>
  );
}

export function SelectFilter({
  values,
  included,
  onApply,
}: {
  values: string[];
  included: Set<string> | undefined;
  onApply: (next: Set<string> | undefined) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState<Set<string> | undefined>(included);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    setDraft(included === undefined ? undefined : new Set(included));
    setSearch("");
  }, [open, included]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const q = search.trim().toLowerCase();
  const shown = q ? values.filter((v) => v.toLowerCase().includes(q)) : values;
  const label = included === undefined ? "전체" : included.size === 0 ? "선택 없음" : `${included.size}개`;
  const checked = (val: string) => draft === undefined || draft.has(val);

  return (
    <div className="relative mt-0.5" ref={boxRef}>
      <button
        type="button"
        className={clsx(
          "w-full flex items-center justify-between px-1 py-0.5 rounded border text-[10px] font-normal",
          included === undefined
            ? "border-slate-200 dark:border-slate-600 text-slate-500"
            : "border-blue-400 bg-blue-50 dark:bg-blue-950/40 text-blue-700",
        )}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="truncate">{label}</span>
        <span aria-hidden>▾</span>
      </button>
      {open && (
        <div
          className="absolute z-50 top-full left-0 mt-0.5 w-44 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg shadow-lg text-[11px] overflow-hidden"
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="px-2 pt-2 pb-1 border-b border-slate-100 dark:border-slate-700">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="값 검색…"
              className="w-full px-1.5 py-1 border border-slate-200 dark:border-slate-600 rounded text-[10px] font-normal bg-white dark:bg-slate-900"
            />
          </div>
          <label className="flex items-center gap-1.5 px-2 py-1 border-b border-slate-100 dark:border-slate-700">
            <input
              type="checkbox"
              className="accent-blue-600 w-3 h-3"
              checked={draft === undefined}
              onChange={() => setDraft((cur) => (cur === undefined ? new Set() : undefined))}
            />
            <span className="font-semibold">전체 선택</span>
          </label>
          <div className="max-h-52 overflow-y-auto">
            {shown.map((val) => (
              <label key={val} className="flex items-center gap-1.5 px-2 py-1 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/50">
                <input
                  type="checkbox"
                  className="accent-blue-600 w-3 h-3"
                  checked={checked(val)}
                  onChange={() =>
                    setDraft((cur) => {
                      const next = cur === undefined ? new Set(values) : new Set(cur);
                      if (next.has(val)) next.delete(val);
                      else next.add(val);
                      return next.size >= values.length ? undefined : next;
                    })
                  }
                />
                <span className="truncate">{val}</span>
              </label>
            ))}
          </div>
          <div className="px-2 py-1.5 border-t border-slate-100 dark:border-slate-700 flex justify-end gap-1">
            <button type="button" className="text-[10px] px-2 py-0.5 rounded border border-slate-200 dark:border-slate-600" onClick={() => setOpen(false)}>
              취소
            </button>
            <button
              type="button"
              className="text-[10px] px-2 py-0.5 rounded bg-blue-600 text-white"
              onClick={() => {
                onApply(draft === undefined ? undefined : new Set(draft));
                setOpen(false);
              }}
            >
              확인
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function FilterStatusBar({
  shown,
  total,
  filterCount,
  onClear,
  sortDirty = false,
  onResetSort,
}: {
  shown: number;
  total: number;
  filterCount: number;
  onClear: () => void;
  sortDirty?: boolean;
  onResetSort?: () => void;
}) {
  const showSort = sortDirty && Boolean(onResetSort);
  if (filterCount <= 0 && !showSort) return null;
  const btn =
    "px-2 py-0.5 rounded border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300";
  return (
    <div className="flex items-center gap-2 px-2 py-1 text-[11px] border-b border-slate-100 dark:border-slate-700">
      <span className="text-indigo-700 dark:text-indigo-300">
        표시 {shown.toLocaleString("ko-KR")} / {total.toLocaleString("ko-KR")}
      </span>
      <span className="ml-auto flex items-center gap-1">
        {showSort && (
          <button type="button" className={btn} onClick={onResetSort}>
            정렬 초기화
          </button>
        )}
        {filterCount > 0 && (
          <button type="button" className={btn} onClick={onClear}>
            필터 초기화 ({filterCount})
          </button>
        )}
      </span>
    </div>
  );
}
