import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import {
  FilterStatusBar,
  SelectFilter,
  SortButtons,
  compareValues,
  filterInputClass,
  inRange,
  parseBound,
  rangeIsActive,
  type RangeBound,
  type SortDir,
} from "@ch2/stats-table-filter";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { BuildingStatsRow } from "../api/client";
import { assetTypeLabel } from "../types";
import { collectiveMatchBadge } from "../utils/matchBadge";
import { rowFromTypeSibling } from "../utils/typeSibling";
import DualHorizontalScroll from "./DualHorizontalScroll";

type ColKey =
  | "asset_type"
  | "display_name"
  | "count"
  | "median"
  | "mean"
  | "ci"
  | "building_year"
  | "households"
  | "builder"
  | "jibun"
  | "road"
  | "land_price";

type FilterKind = "select" | "text" | "range";

type ColDef = {
  key: ColKey;
  label: string;
  title?: string;
  kind: FilterKind;
  wideOnly?: boolean;
  glossary?: "type_stats_vs_complex_scale";
};

const COLS: ColDef[] = [
  { key: "asset_type", label: "유형", kind: "select" },
  { key: "display_name", label: "건물명", kind: "text" },
  { key: "count", label: "거래수", kind: "range" },
  { key: "median", label: "중앙(만원/㎡)", kind: "range" },
  { key: "mean", label: "평균(만원/㎡)", kind: "range" },
  { key: "ci", label: "신뢰구간(만원/㎡)", title: "95% 신뢰구간. 범위는 구간의 가운데 값입니다.", kind: "range", wideOnly: true },
  { key: "building_year", label: "신축연도", title: "실거래 건축연도", kind: "range" },
  {
    key: "households",
    label: "세대수",
    title: "K-apt 전체 세대수. K-apt가 없으면 표제부 해당 용도 동 합산. 오피스텔은 세대수가 비면 호수",
    kind: "range",
    glossary: "type_stats_vs_complex_scale",
  },
  { key: "builder", label: "시공사", title: "K-apt 시공사 대표 1곳. 공동시공은 첫 회사+외. 표제부만 있으면 없음", kind: "text" },
  { key: "jibun", label: "지번 주소", kind: "text" },
  { key: "road", label: "도로명 주소", kind: "text", wideOnly: true },
  { key: "land_price", label: "개별공시지가(원/㎡)", title: "최신 대표 필지 개별공시지가", kind: "range", wideOnly: true },
];

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function fmtCiCompact(lo: number | null | undefined, hi: number | null | undefined) {
  if (lo == null || hi == null) return "—";
  return `${fmtPrice(lo)}~${fmtPrice(hi)}`;
}

function fmtLandPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return Math.round(v).toLocaleString("ko-KR");
}

function householdsCellTitle(row: BuildingStatsRow): string | undefined {
  if (row.households_flagged) return "원본 이상값 — 값은 그대로 표시";
  if (row.scale_scope === "complex" || (row.type_siblings?.length ?? 0) > 0) {
    return "단지 전체 세대수. 이 유형 재고가 아닙니다. 유형별 거래 통계는 별도입니다.";
  }
  return "K-apt 전체 세대수. 없으면 표제부 해당 용도 동 합산. 오피스텔은 세대수가 비면 호수";
}

function landPriceTitle(row: BuildingStatsRow): string | undefined {
  if (row.assessed_land_price == null) return undefined;
  return row.assessed_land_price_year != null ? `${row.assessed_land_price_year}년 · 원/㎡` : "원/㎡";
}

export function buildingMatchesQuery(row: BuildingStatsRow, q: string): boolean {
  if (!q) return false;
  const hay = [row.display_name, row.jibun_address, row.road_address, row.address, row.asset_type, row.builder_label]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

function textValue(row: BuildingStatsRow, key: ColKey): string {
  switch (key) {
    case "asset_type":
      return assetTypeLabel(row.asset_type);
    case "display_name":
      return row.display_name || "—";
    case "builder":
      return row.builder_label?.trim() || "—";
    case "jibun":
      return (row.jibun_address || row.address || "").trim() || "—";
    case "road":
      return row.road_address?.trim() || "—";
    default:
      return "";
  }
}

function numberValue(row: BuildingStatsRow, key: ColKey): number | null {
  switch (key) {
    case "count":
      return row.count;
    case "median":
      return row.median ?? null;
    case "mean":
      return row.mean ?? null;
    case "ci": {
      if (row.ci_lower == null || row.ci_upper == null) return null;
      return (row.ci_lower + row.ci_upper) / 2;
    }
    case "building_year":
      return row.building_year ?? null;
    case "households":
      return row.households ?? null;
    case "land_price":
      return row.assessed_land_price ?? null;
    default:
      return null;
  }
}

function sortValue(row: BuildingStatsRow, key: ColKey): string | number | null {
  if (key === "asset_type" || key === "display_name" || key === "builder" || key === "jibun" || key === "road") {
    const text = textValue(row, key);
    return text === "—" ? null : text;
  }
  return numberValue(row, key);
}

function BuildingTableRow({
  row,
  highlighted,
  wide,
  onSelect,
}: {
  row: BuildingStatsRow;
  highlighted?: boolean;
  wide: boolean;
  onSelect: (row: BuildingStatsRow) => void;
}) {
  return (
    <tr
      className={clsx(
        "hover:bg-indigo-50 dark:hover:bg-indigo-950/40 cursor-pointer",
        highlighted && "!bg-yellow-200 dark:!bg-yellow-700/50",
      )}
      onClick={() => onSelect(row)}
      title={row.display_name}
      data-building-highlight={highlighted ? "1" : undefined}
    >
      <td className="text-[10px] whitespace-nowrap text-center">{assetTypeLabel(row.asset_type)}</td>
      <td className="name">
        {row.display_name}
        {!row.is_reliable && <span className="ml-0.5 text-[9px] text-amber-600">n&lt;15</span>}
        {row.asset_type !== "presale" &&
          (() => {
            const badge = collectiveMatchBadge(row.match_tier);
            return (
              <span
                className={clsx("ml-0.5 text-[9px]", badge.tone === "amber" ? "text-amber-600" : "text-slate-500")}
                title={`조인 ${row.match_tier || "없음"}`}
              >
                {badge.label}
              </span>
            );
          })()}
        {(row.type_siblings ?? []).map((sib) => (
          <button
            key={sib.building_key}
            type="button"
            className="ml-1 px-1 py-0 rounded bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300 text-[9px] font-medium hover:bg-indigo-100"
            title={`${assetTypeLabel(sib.asset_type)} 모달 열기 · 중앙값 ${fmtPrice(sib.median)}`}
            onClick={(e) => {
              e.stopPropagation();
              onSelect(rowFromTypeSibling(row, sib));
            }}
          >
            {assetTypeLabel(sib.asset_type)} {sib.count.toLocaleString("ko-KR")}건 별도
          </button>
        ))}
      </td>
      <td className="num">{row.count}</td>
      <td className="num">{fmtPrice(row.median)}</td>
      <td className="num">{fmtPrice(row.mean)}</td>
      {wide && <td className="num text-[10px]">{fmtCiCompact(row.ci_lower, row.ci_upper)}</td>}
      <td className="num">{row.building_year ?? "—"}</td>
      <td className="num" title={householdsCellTitle(row)}>
        {row.households == null ? (
          "—"
        ) : (
          <>
            {row.households.toLocaleString("ko-KR")}
            {row.households_flagged ? <span className="ml-0.5 text-[9px] text-amber-600">!</span> : null}
          </>
        )}
      </td>
      <td
        className="truncate"
        title={
          row.builder_label
            ? row.builder_is_joint
              ? `${row.builder_label} · 공동시공, 첫 시공사만 표시`
              : row.builder_label
            : undefined
        }
      >
        {row.builder_label ?? "—"}
      </td>
      <td className="addr truncate" title={row.jibun_address || row.address || undefined}>
        {row.jibun_address ?? row.address ?? "—"}
      </td>
      {wide && (
        <td className="addr truncate" title={row.road_address || undefined}>
          {row.road_address ?? "—"}
        </td>
      )}
      {wide && (
        <td className="num" title={landPriceTitle(row)}>
          {fmtLandPrice(row.assessed_land_price)}
        </td>
      )}
    </tr>
  );
}

export default function BuildingStatsTable({
  items,
  wide,
  highlightQuery,
  onSelect,
}: {
  items: BuildingStatsRow[];
  wide: boolean;
  highlightQuery: string;
  onSelect: (row: BuildingStatsRow) => void;
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
        if (!visible.has(col.key)) continue;
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

  const filterCount =
    cols.filter((c) => {
      if (c.kind === "text") return Boolean(texts[c.key]?.trim());
      if (c.kind === "select") return selects[c.key] !== undefined;
      const bound = ranges[c.key];
      return rangeIsActive(bound);
    }).length;

  const clearFilters = () => {
    setTexts({});
    setRanges({});
    setSelects({});
  };

  return (
    <div className="card p-0 w-full">
      <FilterStatusBar shown={shown.length} total={items.length} filterCount={filterCount} onClear={clearFilters} />
      <DualHorizontalScroll key={wide ? "wide" : "compact"}>
        <table className={clsx("data buildings-table", wide && "is-wide")}>
          <colgroup>
            <col className="col-type" />
            <col className="col-name" />
            <col className="col-num" />
            <col className="col-num" />
            <col className="col-num" />
            {wide && <col className="col-num" />}
            <col className="col-year" />
            <col className="col-hh" />
            <col className="col-builder" />
            <col className="col-jibun" />
            {wide && <col className="col-road" />}
            {wide && <col className="col-land" />}
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
                  표시할 건물이 없습니다. 필터를 조정하거나 초기화하세요.
                </td>
              </tr>
            ) : (
              shown.map((row) => (
                <BuildingTableRow
                  key={`${row.building_key}|${row.asset_type}`}
                  row={row}
                  wide={wide}
                  highlighted={buildingMatchesQuery(row, highlightQuery)}
                  onSelect={onSelect}
                />
              ))
            )}
          </tbody>
        </table>
      </DualHorizontalScroll>
    </div>
  );
}
