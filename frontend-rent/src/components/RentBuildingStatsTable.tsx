import { useEffect, useMemo, useState, type ReactNode } from "react";
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
import { assetTypeLabel, type LeaseMetric, type RentBuildingRow } from "../types";
import DualHorizontalScroll from "./DualHorizontalScroll";

type ColKey =
  | "asset_type"
  | "display_name"
  | "jeonse"
  | "sale"
  | "jeonse_pct"
  | "monthly"
  | "jeonse_equiv"
  | "equiv_pct"
  | "monthly_equiv"
  | "building_year"
  | "jibun"
  | "road";

type FilterKind = "select" | "text" | "range";

type ColDef = {
  key: ColKey;
  kind: FilterKind;
  wideOnly?: boolean;
  title: ReactNode;
  aria: string;
};

function fmtUnit(v: number | null | undefined) {
  if (v == null) return "—";
  const digits = Math.abs(v) < 10 ? 1 : 0;
  return v.toLocaleString("ko-KR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits === 1 ? 1 : 0,
  });
}

function ConvertedCell({ m }: { m: LeaseMetric }) {
  const v = m.mean ?? m.median;
  if (v == null) return <span className="text-slate-400">—</span>;
  return <span className="font-semibold">{fmtUnit(v)}</span>;
}

function Nlt15({ n }: { n: number }) {
  if (n <= 0 || n >= 15) return null;
  return <span className="ml-0.5 text-[9px] text-amber-600">n&lt;15</span>;
}

function MeanWithN({ v, n }: { v: number | null | undefined; n: number }) {
  if (v == null) return <span className="text-slate-400">—</span>;
  return (
    <span className="whitespace-nowrap">
      <span className="font-semibold">{fmtUnit(v)}</span>
      {n > 0 ? <span className="ml-0.5 text-slate-400 font-normal">({n.toLocaleString("ko-KR")})</span> : null}
    </span>
  );
}

function MonthlyMeanCell({
  v,
  mixedN,
  monthlyN,
}: {
  v: number | null | undefined;
  mixedN: number;
  monthlyN: number;
}) {
  if (v == null) return <span className="text-slate-400">—</span>;
  return (
    <span className="whitespace-nowrap">
      <span className="font-semibold">{fmtUnit(v)}</span>
      <span className="ml-0.5 text-slate-400 font-normal">
        ({mixedN.toLocaleString("ko-KR")}, {monthlyN.toLocaleString("ko-KR")})
      </span>
    </span>
  );
}

function ColTitle({
  label,
  unit,
  countUnit,
  termId,
}: {
  label: string;
  unit: string;
  countUnit?: string;
  termId: string;
}) {
  return (
    <span className="inline-flex items-center justify-center gap-0.5 leading-tight text-center">
      <span>
        {label}
        <span className="block font-normal text-[10px] text-slate-400">
          ({unit}){countUnit ? ` (${countUnit})` : ""}
        </span>
      </span>
      <StatsGlossaryHelp termId={termId} size="xs" />
    </span>
  );
}

const COLS: ColDef[] = [
  { key: "asset_type", kind: "select", aria: "유형", title: "유형" },
  { key: "display_name", kind: "text", aria: "건물명", title: "건물명" },
  {
    key: "jeonse",
    kind: "range",
    aria: "전세보증금",
    title: <ColTitle label="전세보증금" unit="만원/㎡" countUnit="건" termId="jeonse_deposit" />,
  },
  {
    key: "sale",
    kind: "range",
    aria: "매매가",
    title: <ColTitle label="매매가" unit="만원/㎡" countUnit="건" termId="sale_unit_mean" />,
  },
  {
    key: "jeonse_pct",
    kind: "range",
    aria: "전세가율",
    title: <ColTitle label="전세가율" unit="%" termId="jeonse_to_sale_pct" />,
  },
  {
    key: "monthly",
    kind: "range",
    aria: "월세",
    title: <ColTitle label="월세" unit="만원/㎡" countUnit="건" termId="monthly_rent_mean" />,
  },
  {
    key: "jeonse_equiv",
    kind: "range",
    wideOnly: true,
    aria: "전세환산값",
    title: <ColTitle label="전세환산값" unit="만원/㎡" termId="jeonse_equiv" />,
  },
  {
    key: "equiv_pct",
    kind: "range",
    wideOnly: true,
    aria: "전세환산가율",
    title: <ColTitle label="전세환산가율" unit="%" termId="jeonse_equiv_sale_pct" />,
  },
  {
    key: "monthly_equiv",
    kind: "range",
    wideOnly: true,
    aria: "월세환산값",
    title: <ColTitle label="월세환산값" unit="만원/㎡" termId="monthly_equiv" />,
  },
  { key: "building_year", kind: "range", aria: "준공", title: "준공" },
  { key: "jibun", kind: "text", aria: "지번주소", title: "지번주소" },
  { key: "road", kind: "text", wideOnly: true, aria: "도로명주소", title: "도로명주소" },
];

function monthlyRentMean(row: RentBuildingRow): number | null {
  let w = 0;
  let n = 0;
  const mixN = row.mixed?.n ?? 0;
  const mixM = row.mixed?.monthly?.mean;
  if (mixN > 0 && mixM != null) {
    w += mixM * mixN;
    n += mixN;
  }
  const monN = row.monthly?.n ?? 0;
  const monM = row.monthly?.mean;
  if (monN > 0 && monM != null) {
    w += monM * monN;
    n += monN;
  }
  return n ? w / n : null;
}

function metricValue(m: LeaseMetric | undefined): number | null {
  if (!m) return null;
  return m.mean ?? m.median ?? null;
}

export function buildingMatchesQuery(row: RentBuildingRow, q: string): boolean {
  if (!q) return false;
  const hay = [row.display_name, row.jibun_address, row.road_address, row.asset_type]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

function textValue(row: RentBuildingRow, key: ColKey): string {
  switch (key) {
    case "asset_type":
      return assetTypeLabel(row.asset_type);
    case "display_name":
      return row.display_name?.trim() || "—";
    case "jibun":
      return row.jibun_address?.trim() || "—";
    case "road":
      return row.road_address?.trim() || "—";
    default:
      return "";
  }
}

function numberValue(row: RentBuildingRow, key: ColKey): number | null {
  switch (key) {
    case "jeonse":
      return row.jeonse?.mean ?? null;
    case "sale":
      return row.sale?.mean ?? null;
    case "jeonse_pct":
      return row.jeonse_to_sale_pct ?? null;
    case "monthly":
      return monthlyRentMean(row);
    case "jeonse_equiv":
      return metricValue(row.jeonse_equiv);
    case "equiv_pct":
      return row.jeonse_equiv_sale_pct ?? null;
    case "monthly_equiv":
      return metricValue(row.monthly_equiv);
    case "building_year":
      return row.building_year ?? null;
    default:
      return null;
  }
}

function sortValue(row: RentBuildingRow, key: ColKey): string | number | null {
  if (key === "asset_type" || key === "display_name" || key === "jibun" || key === "road") {
    const text = textValue(row, key);
    return text === "—" ? null : text;
  }
  return numberValue(row, key);
}

export default function RentBuildingStatsTable({
  items,
  wide,
  highlightQuery,
  onSelect,
}: {
  items: RentBuildingRow[];
  wide: boolean;
  highlightQuery: string;
  onSelect: (row: RentBuildingRow) => void;
}) {
  const cols = useMemo(() => COLS.filter((c) => wide || !c.wideOnly), [wide]);
  const [sortKey, setSortKey] = useState<ColKey>("jeonse");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [texts, setTexts] = useState<Partial<Record<ColKey, string>>>({});
  const [ranges, setRanges] = useState<Partial<Record<ColKey, RangeBound>>>({});
  const [selects, setSelects] = useState<Partial<Record<ColKey, Set<string>>>>({});

  useEffect(() => {
    setSortKey("jeonse");
    setSortDir("desc");
    setTexts({});
    setRanges({});
    setSelects({});
  }, [items]);

  useEffect(() => {
    if (!cols.some((c) => c.key === sortKey)) {
      setSortKey("jeonse");
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
    const key = visible.has(sortKey) ? sortKey : "jeonse";
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
    <div className="card p-0">
      <FilterStatusBar
        shown={shown.length}
        total={items.length}
        filterCount={filterCount}
        onClear={() => {
          setTexts({});
          setRanges({});
          setSelects({});
        }}
      />
      <DualHorizontalScroll key={wide ? "wide" : "compact"}>
        <table className={clsx("data buildings-table", wide && "is-wide")}>
          <colgroup>
            <col className="col-type" />
            <col className="col-name" />
            <col className="col-num" />
            <col className="col-num" />
            <col className="col-num" />
            <col className="col-num" />
            {wide && <col className="col-num" />}
            {wide && <col className="col-num" />}
            {wide && <col className="col-num" />}
            <col className="col-year" />
            <col className="col-jibun" />
            {wide && <col className="col-road" />}
          </colgroup>
          <thead className="sticky top-0 z-10">
            <tr>
              {cols.map((col) => (
                <th key={col.key}>
                  {col.title}
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
                        aria-label={`${col.aria} 최소`}
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
                        aria-label={`${col.aria} 최대`}
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
                      aria-label={`${col.aria} 포함`}
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
                  표시할 건물이 없습니다. 필터를 조정하거나 초기화하세요.
                </td>
              </tr>
            ) : (
              shown.map((row) => {
                const saleN = row.sale?.n ?? 0;
                const jeonseN = row.jeonse?.n ?? 0;
                const mixedN = row.mixed?.n ?? 0;
                const monthlyN = row.monthly?.n ?? 0;
                const monthly = monthlyRentMean(row);
                const ratio = row.jeonse_to_sale_pct;
                const equivRatio = row.jeonse_equiv_sale_pct;
                const highlighted = buildingMatchesQuery(row, highlightQuery);
                return (
                  <tr
                    key={`${row.building_key}|${row.asset_type}`}
                    className={clsx(
                      "hover:bg-indigo-50 dark:hover:bg-indigo-950/40 cursor-pointer",
                      highlighted && "!bg-yellow-200 dark:!bg-yellow-700/50",
                    )}
                    data-building-highlight={highlighted ? "1" : undefined}
                    onClick={() => onSelect(row)}
                  >
                    <td className="text-[10px] text-center">{assetTypeLabel(row.asset_type)}</td>
                    <td className="name" title={row.display_name}>
                      {row.display_name}
                    </td>
                    <td className="lease">
                      <MeanWithN v={row.jeonse?.mean} n={jeonseN} />
                    </td>
                    <td className="lease">
                      <MeanWithN v={row.sale?.mean} n={saleN} />
                    </td>
                    <td className="num">
                      {ratio != null ? (
                        <>
                          {ratio.toFixed(1)}%
                          <Nlt15 n={jeonseN} />
                        </>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="lease">
                      <MonthlyMeanCell v={monthly} mixedN={mixedN} monthlyN={monthlyN} />
                    </td>
                    {wide && (
                      <td className="lease">
                        <ConvertedCell m={row.jeonse_equiv} />
                      </td>
                    )}
                    {wide && (
                      <td className="num">
                        {equivRatio != null ? (
                          <span className={equivRatio > 100 ? "text-amber-700 dark:text-amber-300" : undefined}>
                            {equivRatio.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                    )}
                    {wide && (
                      <td className="lease">
                        <ConvertedCell m={row.monthly_equiv} />
                      </td>
                    )}
                    <td className="num">{row.building_year ?? "—"}</td>
                    <td className="addr truncate" title={row.jibun_address}>
                      {row.jibun_address || "—"}
                    </td>
                    {wide && (
                      <td className="addr truncate text-slate-500" title={row.road_address}>
                        {row.road_address || "—"}
                      </td>
                    )}
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
