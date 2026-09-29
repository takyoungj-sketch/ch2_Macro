import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import {
  FilterStatusBar,
  SelectFilter,
  SortButtons,
  compareValues,
  filterInputClass,
  inRange,
  rangeIsActive,
  type RangeBound,
  type SortDir,
} from "@ch2/stats-table-filter";
import { commercialAssetTypeLabel, type CommercialClusterRow } from "../types";
import DualHorizontalScroll from "./DualHorizontalScroll";

type ColKey = "asset_type" | "road" | "count" | "median" | "mean" | "ci" | "district";
type FilterKind = "select" | "text" | "range";

type ColDef = {
  key: ColKey;
  label: string;
  title?: string;
  kind: FilterKind;
  wideOnly?: boolean;
  glossary?: "commercial_cluster";
};

const COLS: ColDef[] = [
  { key: "asset_type", label: "유형", kind: "select" },
  { key: "road", label: "도로명", kind: "text", glossary: "commercial_cluster" },
  { key: "count", label: "거래수", kind: "range" },
  { key: "median", label: "중앙(만원/㎡)", kind: "range" },
  { key: "mean", label: "평균(만원/㎡)", kind: "range" },
  { key: "ci", label: "신뢰구간(만원/㎡)", title: "95% 신뢰구간. 범위는 구간의 가운데 값입니다.", kind: "range", wideOnly: true },
  { key: "district", label: "구·동", kind: "text" },
];

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function fmtCi(lo: number | null | undefined, hi: number | null | undefined) {
  if (lo == null || hi == null) return "—";
  return `${fmtPrice(lo)}~${fmtPrice(hi)}`;
}

export function clusterMatchesQuery(row: CommercialClusterRow, q: string): boolean {
  if (!q) return false;
  const hay = [row.road_name, row.display_label, row.addr3, row.addr4, row.asset_type]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

function textValue(row: CommercialClusterRow, key: ColKey): string {
  switch (key) {
    case "asset_type":
      return commercialAssetTypeLabel(row.asset_type);
    case "road":
      return (row.road_name || row.display_label || "").trim() || "—";
    case "district": {
      const text = [row.addr3, row.addr4].filter(Boolean).join(" · ");
      return text || "—";
    }
    default:
      return "";
  }
}

function numberValue(row: CommercialClusterRow, key: ColKey): number | null {
  switch (key) {
    case "count":
      return row.count;
    case "median":
      return row.median ?? null;
    case "mean":
      return row.mean ?? null;
    case "ci":
      if (row.ci_lower == null || row.ci_upper == null) return null;
      return (row.ci_lower + row.ci_upper) / 2;
    default:
      return null;
  }
}

function sortValue(row: CommercialClusterRow, key: ColKey): string | number | null {
  if (key === "asset_type" || key === "road" || key === "district") {
    const text = textValue(row, key);
    return text === "—" ? null : text;
  }
  return numberValue(row, key);
}

export default function CommercialClusterTable({
  items,
  wide,
  highlightQuery,
  selectedKey,
  onSelect,
}: {
  items: CommercialClusterRow[];
  wide: boolean;
  highlightQuery: string;
  selectedKey?: string | null;
  onSelect: (row: CommercialClusterRow) => void;
}) {
  const cols = useMemo(() => COLS.filter((c) => wide || !c.wideOnly), [wide]);
  const [sortKey, setSortKey] = useState<ColKey>("count");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [texts, setTexts] = useState<Partial<Record<ColKey, string>>>({});
  const [ranges, setRanges] = useState<Partial<Record<ColKey, RangeBound>>>({});
  const [selects, setSelects] = useState<Partial<Record<ColKey, Set<string>>>>({});

  useEffect(() => {
    setSortKey("count");
    setSortDir("desc");
    setTexts({});
    setRanges({});
    setSelects({});
  }, [items]);

  useEffect(() => {
    if (!cols.some((c) => c.key === sortKey)) {
      setSortKey("count");
      setSortDir("desc");
    }
  }, [cols, sortKey]);

  const typeValues = useMemo(() => {
    const set = new Set(items.map((row) => textValue(row, "asset_type")));
    return [...set].sort((a, b) => a.localeCompare(b, "ko"));
  }, [items]);

  const shown = useMemo(() => {
    const visible = new Set(cols.map((c) => c.key));
    const rows = items.filter((row) => {
      for (const col of cols) {
        if (col.kind === "text") {
          const q = texts[col.key]?.trim().toLowerCase();
          if (q && !textValue(row, col.key).toLowerCase().includes(q)) return false;
        } else if (col.kind === "select") {
          const sel = selects[col.key];
          if (sel && !sel.has(textValue(row, col.key))) return false;
        } else if (!inRange(numberValue(row, col.key), ranges[col.key])) {
          return false;
        }
      }
      return true;
    });
    const key = visible.has(sortKey) ? sortKey : "count";
    const dir = visible.has(sortKey) ? sortDir : "desc";
    rows.sort((a, b) => compareValues(sortValue(a, key), sortValue(b, key), dir));
    return rows;
  }, [items, cols, texts, ranges, selects, sortKey, sortDir]);

  const filterCount = cols.filter((c) => {
    if (c.kind === "text") return Boolean(texts[c.key]?.trim());
    if (c.kind === "select") return selects[c.key] !== undefined;
    return rangeIsActive(ranges[c.key]);
  }).length;

  return (
    <div className="card p-0 w-full">
      <FilterStatusBar
        shown={shown.length}
        total={items.length}
        filterCount={filterCount}
        onClear={() => {
          setTexts({});
          setRanges({});
          setSelects({});
        }}
        sortDirty={sortKey !== "count" || sortDir !== "desc"}
        onResetSort={() => {
          setSortKey("count");
          setSortDir("desc");
        }}
      />
      <DualHorizontalScroll key={wide ? "wide" : "compact"}>
        <table className={clsx("data commercial-clusters-table", wide && "is-wide")}>
          <colgroup>
            <col className="col-type" />
            <col className="col-road" />
            <col className="col-num" />
            <col className="col-num" />
            <col className="col-num" />
            {wide && <col className="col-num" />}
            <col className="col-district" />
          </colgroup>
          <thead className="sticky top-0 z-10">
            <tr>
              {cols.map((col) => (
                <th key={col.key} title={col.title}>
                  <span className="inline-flex items-center justify-center gap-0.5">
                    {col.label}
                    {col.glossary && <StatsGlossaryHelp termId={col.glossary} size="xs" />}
                  </span>
                  <SortButtons
                    active={sortKey === col.key}
                    dir={sortDir}
                    onAsc={() => {
                      setSortKey(col.key);
                      setSortDir("asc");
                    }}
                    onDesc={() => {
                      setSortKey(col.key);
                      setSortDir("desc");
                    }}
                  />
                  {col.kind === "range" && (
                    <div className="mt-0.5 flex gap-0.5">
                      <input
                        type="text"
                        inputMode="decimal"
                        placeholder="최소"
                        aria-label={`${col.label} 최소`}
                        className={filterInputClass}
                        value={ranges[col.key]?.min ?? ""}
                        onChange={(e) =>
                          setRanges((prev) => ({
                            ...prev,
                            [col.key]: { min: e.target.value, max: prev[col.key]?.max ?? "" },
                          }))
                        }
                      />
                      <input
                        type="text"
                        inputMode="decimal"
                        placeholder="최대"
                        aria-label={`${col.label} 최대`}
                        className={filterInputClass}
                        value={ranges[col.key]?.max ?? ""}
                        onChange={(e) =>
                          setRanges((prev) => ({
                            ...prev,
                            [col.key]: { min: prev[col.key]?.min ?? "", max: e.target.value },
                          }))
                        }
                      />
                    </div>
                  )}
                  {col.kind === "text" && (
                    <input
                      type="search"
                      placeholder="포함"
                      aria-label={`${col.label} 포함`}
                      className={clsx(filterInputClass, "mt-0.5")}
                      value={texts[col.key] ?? ""}
                      onChange={(e) => setTexts((prev) => ({ ...prev, [col.key]: e.target.value }))}
                    />
                  )}
                  {col.kind === "select" && (
                    <SelectFilter
                      values={typeValues}
                      included={selects[col.key]}
                      onApply={(next) =>
                        setSelects((prev) => {
                          const copy = { ...prev };
                          if (next === undefined) delete copy[col.key];
                          else copy[col.key] = next;
                          return copy;
                        })
                      }
                    />
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 ? (
              <tr>
                <td colSpan={cols.length} className="py-6 text-slate-400">
                  표시할 도로가 없습니다. 필터를 조정하거나 초기화하세요.
                </td>
              </tr>
            ) : (
              shown.map((row) => {
                const highlighted = clusterMatchesQuery(row, highlightQuery);
                const selected = selectedKey != null && selectedKey === `${row.cluster_key}|${row.asset_type}`;
                return (
                  <tr
                    key={`${row.cluster_key}|${row.asset_type}`}
                    className={clsx(
                      "hover:bg-indigo-50 dark:hover:bg-indigo-950/40 cursor-pointer",
                      highlighted
                        ? "!bg-yellow-200 dark:!bg-yellow-700/50"
                        : selected && "bg-indigo-50 dark:bg-indigo-950/50",
                    )}
                    onClick={() => onSelect(row)}
                    data-cluster-highlight={highlighted ? "1" : undefined}
                  >
                    <td className="text-[10px] whitespace-nowrap text-center">{commercialAssetTypeLabel(row.asset_type)}</td>
                    <td className="name">
                      {row.road_name || row.display_label}
                      {!row.is_reliable && <span className="ml-0.5 text-[9px] text-amber-600">n&lt;15</span>}
                    </td>
                    <td className="num">{row.count}</td>
                    <td className="num">{fmtPrice(row.median)}</td>
                    <td className="num">{fmtPrice(row.mean)}</td>
                    {wide && <td className="num text-[10px]">{fmtCi(row.ci_lower, row.ci_upper)}</td>}
                    <td className="col-district text-[10px] text-slate-600 dark:text-slate-300">
                      {[row.addr3, row.addr4].filter(Boolean).join(" · ") || "—"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </DualHorizontalScroll>
    </div>
  );
}
