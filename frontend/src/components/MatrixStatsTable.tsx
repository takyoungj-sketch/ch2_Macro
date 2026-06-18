import { Fragment, useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import {
  MATRIX_TABLE_TONE,
  matrixTheadPrimaryClass,
} from "../constants/displayUi";
import { buildMatrixLegendExplain, buildMatrixTableExplain } from "../constants/landStatsExplain";
import type { AnalysisExplain, MatrixCell, StatsResult } from "../types";
import AnalysisHelpPanel from "./AnalysisHelpPanel";

/** 고정 레이아웃 (만원/㎡) — 통계 라벨 열 없음 */
const COL_ZONE_PX = 96; // 이전 대비 용도지역 열 0.6배 (160×0.6)
const COL_VALUE_PX = 88;
/** 신뢰구간 등 긴 수치 — table-fixed 에서 필요 시 열 확장 (px) */
const COL_VALUE_CHAR_PX = 6.5;
const COL_VALUE_PAD_PX = 10;
const ROW_PX = 28;
/** 지목 헤더 1행 높이(고정값) — 건수 + 행·열 평균 */
const THEAD_ROW1_HEIGHT = ROW_PX + 20;

/** 평균적인 셀 테두리 (1px — 경계선 강조는 별도) */
const CELL = "box-border border border-slate-200";
/** 용도지역 열 ↔ 지목 데이터 구간 세로 경계 — 기존 1.4px 의 1.2배 */
const ZONE_TO_DATA = "border-r-[1.68px] border-r-slate-400";
/** 지목 블록(좌+우 두 열) 사이 세로 경계 — 이전 1.8px 의 1.5배 */
const BETWEEN_CATEGORIES_LEFT = "border-l-[2.7px] border-l-slate-400";

/** 표시 수치: 소수 첫째자리 고정 (만원/㎡ 등) */
const fmtD1 = (v: number | null | undefined) =>
  v == null
    ? "-"
    : Number(v).toLocaleString("ko-KR", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      });

/** 거래건수 등 카운트: 정수 (천단위 구분만) */
const fmtCount = (v: number | null | undefined) =>
  v == null
    ? "-"
    : Math.round(Number(v)).toLocaleString("ko-KR", {
        maximumFractionDigits: 0,
      });

function fmtCiRange(
  lo: number | null | undefined,
  hi: number | null | undefined
): string {
  if (lo == null || hi == null) return "-";
  return `${fmtD1(lo)}~${fmtD1(hi)}`;
}

/** 고정 폭(col)에서 텍스트가 들어갈 최소 너비 추정 */
function minColWidthForText(text: string): number {
  if (!text || text === "-") return COL_VALUE_PX;
  return Math.max(
    COL_VALUE_PX,
    Math.ceil(text.length * COL_VALUE_CHAR_PX) + COL_VALUE_PAD_PX
  );
}

/** 무료 패널 상단(지역명 행 우측) 등에서 재사용 */
export function MatrixStatsLegend({
  matchYearlyStatsHeight = false,
  className,
  helpExplain,
}: {
  /** YearlyStatsTable(총거래)과 나란히 높이·글자 크기 맞춤 */
  matchYearlyStatsHeight?: boolean;
  className?: string;
  /** 범례 옆 물음표 — 셀 수치 의미 설명 */
  helpExplain?: AnalysisExplain | null;
} = {}) {
  const cellClass = clsx(
    "border border-slate-200 text-center align-middle",
    matchYearlyStatsHeight ? "px-2 py-1" : "px-0.5 py-px",
  );

  const legendHelp = helpExplain ?? null;

  return (
    <div
      className={clsx(
        "shrink-0 flex items-start gap-1",
        matchYearlyStatsHeight && "self-stretch min-h-0",
        className,
      )}
    >
      <table
        className={clsx(
          "table-fixed border-collapse border border-slate-200 bg-white leading-tight text-slate-600",
          matchYearlyStatsHeight ? "h-full w-full text-[11px]" : "text-[9px]",
        )}
        style={{ width: matchYearlyStatsHeight ? 280 : 236 }}
        aria-label="매트릭스 셀 구조 범례"
      >
        <tbody className={matchYearlyStatsHeight ? "h-full" : undefined}>
          <tr style={matchYearlyStatsHeight ? { height: "20%" } : undefined}>
            <td className={cellClass}>거래수</td>
            <td className={cellClass}>최소</td>
          </tr>
          <tr style={matchYearlyStatsHeight ? { height: "20%" } : undefined}>
            <td
              rowSpan={2}
              className={clsx(
                cellClass,
                "font-bold text-blue-700 leading-tight",
              )}
            >
              평균
            </td>
            <td className={cellClass}>25%값</td>
          </tr>
          <tr style={matchYearlyStatsHeight ? { height: "20%" } : undefined}>
            <td className={cellClass}>중위</td>
          </tr>
          <tr style={matchYearlyStatsHeight ? { height: "20%" } : undefined}>
            <td className={cellClass}>표준편차</td>
            <td className={cellClass}>75%값</td>
          </tr>
          <tr style={matchYearlyStatsHeight ? { height: "20%" } : undefined}>
            <td className={cellClass}>신뢰구간(95%)</td>
            <td className={cellClass}>최대</td>
          </tr>
        </tbody>
      </table>
      {legendHelp ? <AnalysisHelpPanel explain={legendHelp} className="shrink-0" /> : null}
    </div>
  );
}

const matrixTableExplain = buildMatrixTableExplain();
const matrixLegendExplainDefault = buildMatrixLegendExplain();

interface Props {
  /** 빈 문자열이면 표 위 제목 비표시 */
  title?: string;
  matrix?: MatrixCell[] | null;
  byZone?: Record<string, StatsResult>;
  byLandCategory?: Record<string, StatsResult>;
  /** 무료처럼 범례를 상단별도 배치하면 false */
  showEmbeddedLegend?: boolean;
  /** 유료 전용 — 거래가 있는 칸을 클릭하면 교차 영역별 연도 추이 활성화 */
  onPaidMatrixCellClick?: (zoneType: string, landCategory: string) => void;
  /** 셀 추이 모달 등이 열려 있을 때 전체화면 Esc 닫기 억제 */
  suppressEscapeClose?: boolean;
}

function cellHl(reliable?: boolean): string {
  return reliable
    ? "bg-emerald-50 dark:bg-emerald-950/45"
    : "";
}

/** 거래 1건 이상인 경우에만 수치 표시, 없으면 '-' (0 표기 없음) */
function hasDeals(stats: StatsResult | undefined): stats is StatsResult {
  return !!stats && stats.count > 0;
}

/** 1~4건 구간만 흐리게 (15건 이상 신뢰 강조는 유지). 거래 없음도 약하게 */
function faintBlock(stats: StatsResult | undefined): string {
  if (!stats || stats.count < 1) return "opacity-50";
  if (stats.count < 5 && !stats.is_reliable) {
    return "opacity-70";
  }
  return "";
}

function cellZoneCol(): string {
  return clsx(CELL, ZONE_TO_DATA);
}

function cellLeftCat(catIndex: number): string {
  return clsx(CELL, catIndex > 0 && BETWEEN_CATEGORIES_LEFT);
}

function cellRightCat(): string {
  return CELL;
}

function paidInsightAttrs(
  deal: boolean,
  pick: Props["onPaidMatrixCellClick"],
  zoneType: string,
  landCategory: string
): {
  role?: "button";
  tabIndex?: number;
  onClick?: () => void;
  onKeyDown?: (e: KeyboardEvent<HTMLTableCellElement>) => void;
} {
  if (!deal || !pick) return {};
  return {
    role: "button",
    tabIndex: 0,
    onClick: () => pick(zoneType, landCategory),
    onKeyDown: (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        pick(zoneType, landCategory);
      }
    },
  };
}

interface GridProps {
  zones: string[];
  landCategories: string[];
  lookup: Map<string, StatsResult | undefined>;
  leftColWidths: number[];
  tableWidth: number;
  cells: MatrixCell[];
  byZone: Record<string, StatsResult>;
  byLandCategory: Record<string, StatsResult>;
  onPaidMatrixCellClick?: Props["onPaidMatrixCellClick"];
  scrollClassName?: string;
}

function MatrixStatsTableGrid({
  zones,
  landCategories,
  lookup,
  leftColWidths,
  tableWidth,
  cells,
  byZone,
  byLandCategory,
  onPaidMatrixCellClick,
  scrollClassName = "max-h-[min(72vh,56rem)] overflow-auto border border-slate-200 rounded-lg overscroll-contain",
}: GridProps) {
  const thMain = matrixTheadPrimaryClass(MATRIX_TABLE_TONE);

  return (
    <div className={scrollClassName}>
      <table
        className="table-fixed border-collapse bg-white text-xs leading-tight"
        style={{ width: tableWidth }}
      >
        <colgroup>
          <col style={{ width: COL_ZONE_PX }} />
          {landCategories.map((category, ci) => (
            <Fragment key={`col-${category}`}>
              <col style={{ width: leftColWidths[ci] }} />
              <col style={{ width: COL_VALUE_PX }} />
            </Fragment>
          ))}
        </colgroup>
        <thead>
          <tr style={{ height: THEAD_ROW1_HEIGHT }}>
            <th
              className={clsx(
                "sticky left-0 top-0 z-[31] px-1 py-1 align-middle text-center font-medium",
                thMain,
                cellZoneCol()
              )}
            >
              <span className="block leading-tight">용도지역\지목</span>
            </th>
            {landCategories.map((category, ci) => {
              const catStats = byLandCategory[category];
              const catCount = catStats?.count ?? countCategory(cells, category);
              const catMean = fmtMarginalMean(catStats, catCount);
              return (
                <th
                  key={category}
                  colSpan={2}
                  className={clsx(
                    "sticky top-0 z-[21] max-w-0 px-1 py-1 text-center align-middle text-sm font-medium truncate",
                    thMain,
                    cellLeftCat(ci)
                  )}
                  title={`${category} ${fmtCount(catCount)}건 · 평균 ${catMean}`}
                >
                  <span className="flex flex-col items-center gap-px leading-tight">
                    <span className="block truncate w-full text-sm font-semibold text-sky-950">
                      {category}
                    </span>
                    <span className="text-[11px] text-sky-800/85 font-normal">
                      {fmtCount(catCount)}건
                    </span>
                    <span className="text-[11px] font-bold tabular-nums text-blue-600">
                      {catMean}
                    </span>
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {zones.map((zone, zi) => {
            const zoneStats = byZone[zone];
            const zoneCount = zoneStats?.count ?? countZone(cells, zone);
            const zoneMean = fmtMarginalMean(zoneStats, zoneCount);
            return (
              <Fragment key={zone}>
                <tr
                  className={clsx(zi > 0 && "border-t-[2.8px] border-t-slate-400")}
                  style={{ height: ROW_PX }}
                >
                  <th
                    rowSpan={5}
                    className={clsx(
                      "sticky left-0 z-10 bg-sky-100 px-1 py-1 align-middle text-center text-sm font-semibold text-sky-950",
                      cellZoneCol()
                    )}
                    title={`${zone} ${fmtCount(zoneCount)}건 · 평균 ${zoneMean}`}
                  >
                    <div className="line-clamp-2 break-all text-center">{zone}</div>
                    <div className="mt-0.5 text-[10px] font-normal leading-tight text-sky-800/85">
                      {fmtCount(zoneCount)}건
                    </div>
                    <div className="mt-px text-[11px] font-bold tabular-nums leading-tight text-blue-600">
                      {zoneMean}
                    </div>
                  </th>
                  {landCategories.map((category, ci) => {
                    const stats = lookup.get(`${zone}|||${category}`);
                    const deal = hasDeals(stats);
                    const faint = faintBlock(stats);
                    const insight = paidInsightAttrs(
                      deal,
                      onPaidMatrixCellClick,
                      zone,
                      category
                    );

                    return (
                      <Fragment key={`${zone}-${category}-r0`}>
                        <td
                          {...insight}
                          className={clsx(
                            cellLeftCat(ci),
                            "px-1 py-0 text-right align-middle tabular-nums truncate",
                            faint,
                            cellHl(stats?.is_reliable),
                            stats?.is_reliable ? "text-slate-900 font-medium" : "text-slate-800",
                            insight.role &&
                              "cursor-pointer hover:bg-sky-50/50 outline-none focus-visible:ring-1 ring-sky-400"
                          )}
                          title={
                            deal
                              ? `거래수: ${fmtCount(stats!.count)}${insight.role ? " · 클릭: 연도별 추이" : ""}`
                              : "거래수"
                          }
                        >
                          {deal ? fmtCount(stats!.count) : "-"}
                        </td>
                        <td
                          {...insight}
                          className={clsx(
                            cellRightCat(),
                            "px-1 py-0 align-middle text-right tabular-nums truncate text-slate-600",
                            faint,
                            cellHl(stats?.is_reliable),
                            insight.role &&
                              "cursor-pointer hover:bg-sky-50/50 outline-none focus-visible:ring-1 ring-sky-400"
                          )}
                          title={
                            deal ? `최소: ${fmtD1(stats!.min)} · 클릭: 연도별 추이` : "최소"
                          }
                        >
                          {deal ? fmtD1(stats!.min) : "-"}
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
                <tr style={{ height: ROW_PX }}>
                  {landCategories.map((category, ci) => {
                    const stats = lookup.get(`${zone}|||${category}`);
                    const deal = hasDeals(stats);
                    const faint = faintBlock(stats);
                    const insight = paidInsightAttrs(
                      deal,
                      onPaidMatrixCellClick,
                      zone,
                      category
                    );
                    return (
                      <Fragment key={`${zone}-${category}-r1`}>
                        <td
                          rowSpan={2}
                          {...insight}
                          className={clsx(
                            cellLeftCat(ci),
                            "px-1 py-0 align-middle text-right font-bold tabular-nums leading-tight truncate text-blue-600 text-[1.0625rem]",
                            faint,
                            cellHl(stats?.is_reliable),
                            insight.role &&
                              "cursor-pointer hover:bg-sky-50/50 outline-none focus-visible:ring-1 ring-sky-400"
                          )}
                          title={
                            deal
                              ? `평균: ${fmtD1(stats!.mean)} · 클릭: 연도별 추이`
                              : "평균"
                          }
                        >
                          {deal ? fmtD1(stats!.mean) : "-"}
                        </td>
                        <td
                          {...insight}
                          className={clsx(
                            cellRightCat(),
                            "px-1 py-0 align-middle text-right tabular-nums truncate text-slate-600",
                            faint,
                            cellHl(stats?.is_reliable),
                            insight.role &&
                              "cursor-pointer hover:bg-sky-50/50 outline-none focus-visible:ring-1 ring-sky-400"
                          )}
                          title={
                            deal ? `25%: ${fmtD1(stats!.p25)} · 클릭: 연도별 추이` : "25%"
                          }
                        >
                          {deal ? fmtD1(stats!.p25) : "-"}
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
                <tr style={{ height: ROW_PX }}>
                  {landCategories.map((category) => {
                    const stats = lookup.get(`${zone}|||${category}`);
                    const deal = hasDeals(stats);
                    const faint = faintBlock(stats);
                    const insight = paidInsightAttrs(
                      deal,
                      onPaidMatrixCellClick,
                      zone,
                      category
                    );
                    return (
                      <td
                        key={`${zone}-${category}-r2`}
                        {...insight}
                        className={clsx(
                          cellRightCat(),
                          "px-1 py-0 align-middle text-right tabular-nums truncate font-bold text-slate-700",
                          faint,
                          cellHl(stats?.is_reliable),
                          insight.role &&
                            "cursor-pointer hover:bg-sky-50/50 outline-none focus-visible:ring-1 ring-sky-400"
                        )}
                        title={
                          deal ? `중위: ${fmtD1(stats!.median)} · 클릭: 연도별 추이` : "중위값"
                        }
                      >
                        {deal ? fmtD1(stats!.median) : "-"}
                      </td>
                    );
                  })}
                </tr>
                <tr style={{ height: ROW_PX }}>
                  {landCategories.map((category, ci) => {
                    const stats = lookup.get(`${zone}|||${category}`);
                    const deal = hasDeals(stats);
                    const faint = faintBlock(stats);
                    const insight = paidInsightAttrs(
                      deal,
                      onPaidMatrixCellClick,
                      zone,
                      category
                    );
                    return (
                      <Fragment key={`${zone}-${category}-r3`}>
                        <td
                          {...insight}
                          className={clsx(
                            cellLeftCat(ci),
                            "px-1 py-0 align-middle text-right tabular-nums font-semibold truncate text-slate-700 text-[10px]",
                            faint,
                            cellHl(stats?.is_reliable),
                            insight.role &&
                              "cursor-pointer hover:bg-sky-50/50 outline-none focus-visible:ring-1 ring-sky-400"
                          )}
                          title={
                            deal
                              ? `표준편차: ${fmtD1(stats!.std)} · 클릭: 연도별 추이`
                              : "표준편차"
                          }
                        >
                          {deal ? fmtD1(stats!.std) : "-"}
                        </td>
                        <td
                          {...insight}
                          className={clsx(
                            cellRightCat(),
                            "px-1 py-0 align-middle text-right tabular-nums truncate text-slate-600",
                            faint,
                            cellHl(stats?.is_reliable),
                            insight.role &&
                              "cursor-pointer hover:bg-sky-50/50 outline-none focus-visible:ring-1 ring-sky-400"
                          )}
                          title={
                            deal ? `75%: ${fmtD1(stats!.p75)} · 클릭: 연도별 추이` : "75%"
                          }
                        >
                          {deal ? fmtD1(stats!.p75) : "-"}
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
                <tr style={{ height: ROW_PX }}>
                  {landCategories.map((category, ci) => {
                    const stats = lookup.get(`${zone}|||${category}`);
                    const deal = hasDeals(stats);
                    const faint = faintBlock(stats);
                    const insight = paidInsightAttrs(
                      deal,
                      onPaidMatrixCellClick,
                      zone,
                      category
                    );
                    const ciTxt =
                      stats && deal ? fmtCiRange(stats.ci_lower, stats.ci_upper) : "-";
                    return (
                      <Fragment key={`${zone}-${category}-r4`}>
                        <td
                          {...insight}
                          className={clsx(
                            cellLeftCat(ci),
                            "px-1 py-0 align-middle text-right tabular-nums font-semibold whitespace-nowrap text-slate-700",
                            faint,
                            cellHl(stats?.is_reliable),
                            insight.role &&
                              "cursor-pointer hover:bg-sky-50/50 outline-none focus-visible:ring-1 ring-sky-400"
                          )}
                          title={
                            deal
                              ? `95% 신뢰구간: ${fmtCiRange(stats!.ci_lower, stats!.ci_upper)} · 클릭: 연도별 추이`
                              : "신뢰구간"
                          }
                        >
                          {deal ? ciTxt : "-"}
                        </td>
                        <td
                          {...insight}
                          className={clsx(
                            cellRightCat(),
                            "px-1 py-0 align-middle text-right tabular-nums truncate text-slate-600",
                            faint,
                            cellHl(stats?.is_reliable),
                            insight.role &&
                              "cursor-pointer hover:bg-sky-50/50 outline-none focus-visible:ring-1 ring-sky-400"
                          )}
                          title={
                            deal ? `최대: ${fmtD1(stats!.max)} · 클릭: 연도별 추이` : "최대"
                          }
                        >
                          {deal ? fmtD1(stats!.max) : "-"}
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MatrixFullscreenButton({
  onClick,
  label = "전체화면",
  variant = "open",
}: {
  onClick: () => void;
  label?: string;
  variant?: "open" | "close";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-600 shadow-sm hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
      title={
        variant === "close"
          ? "전체화면을 닫습니다 (Esc)"
          : "용도×지목 매트릭스를 화면 전체로 확대합니다"
      }
    >
      {variant === "open" ? (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="h-3.5 w-3.5 shrink-0"
          aria-hidden
        >
          <path d="M3 3a1 1 0 0 1 1-1h3a1 1 0 0 1 0 2H6.414l3.293 3.293a1 1 0 0 1-1.414 1.414L5 5.414V7a1 1 0 0 1-2 0V4a1 1 0 0 1 1-1Zm13 0a1 1 0 0 1 1 1v3a1 1 0 0 1-2 0V5.414l-3.293 3.293a1 1 0 1 1-1.414-1.414L14.586 4H13a1 1 0 0 1 0-2h3ZM3 13a1 1 0 0 1 1 1v3a1 1 0 0 0 1 1h3a1 1 0 0 0 0-2H5.414l3.293-3.293a1 1 0 1 1 1.414-1.414L7 15.586V14a1 1 0 0 0-1-1H4a1 1 0 0 1-1-1Zm14 0a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-3a1 1 0 0 1 0-2h1.586l-3.293-3.293a1 1 0 0 1 1.414-1.414L16 15.586V14a1 1 0 0 0-1-1h-1a1 1 0 0 1-1-1Z" />
        </svg>
      ) : null}
      {label}
    </button>
  );
}

export default function MatrixStatsTable({
  title = "용도지역 × 지목 분석표",
  matrix,
  byZone = {},
  byLandCategory = {},
  showEmbeddedLegend = true,
  onPaidMatrixCellClick,
  suppressEscapeClose = false,
}: Props) {
  const [fullscreen, setFullscreen] = useState(false);

  const cells = matrix ?? [];
  const showHeadingRow = (title ?? "").trim().length > 0 || showEmbeddedLegend;
  const headingText = (title ?? "").trim() || "용도지역 × 지목 분석표";

  const lookup = useMemo(
    () =>
      new Map(
        cells
          .filter((cell) => cell.stats != null)
          .map((cell) => [`${cell.zone_type}|||${cell.land_category}`, cell.stats])
      ),
    [cells]
  );

  const zones = useMemo(
    () =>
      sortLabels(
        Array.from(new Set(cells.map((cell) => cell.zone_type))),
        byZone,
        (label) =>
          cells
            .filter((cell) => cell.zone_type === label)
            .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0)
      ),
    [cells, byZone]
  );

  const landCategories = useMemo(
    () =>
      sortLabels(
        Array.from(new Set(cells.map((cell) => cell.land_category))),
        byLandCategory,
        (label) =>
          cells
            .filter((cell) => cell.land_category === label)
            .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0)
      ),
    [cells, byLandCategory]
  );

  const leftColWidths = useMemo(() => {
    return landCategories.map((category) => {
      let w = COL_VALUE_PX;
      for (const zone of zones) {
        const stats = lookup.get(`${zone}|||${category}`);
        if (!hasDeals(stats)) continue;
        w = Math.max(w, minColWidthForText(fmtCiRange(stats.ci_lower, stats.ci_upper)));
      }
      return w;
    });
  }, [landCategories, zones, lookup]);

  const tableWidth =
    COL_ZONE_PX + leftColWidths.reduce((sum, w) => sum + w + COL_VALUE_PX, 0);

  const gridProps: GridProps = {
    zones,
    landCategories,
    lookup,
    leftColWidths,
    tableWidth,
    cells,
    byZone,
    byLandCategory,
    onPaidMatrixCellClick,
  };

  useEffect(() => {
    if (!fullscreen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape" && !suppressEscapeClose) setFullscreen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [fullscreen, suppressEscapeClose]);

  if (cells.length === 0) {
    return (
      <div>
        {showHeadingRow ? (
          <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
            {(title ?? "").trim() ? (
              <h3 className="text-sm font-semibold text-slate-600">{title}</h3>
            ) : (
              <div />
            )}
            {showEmbeddedLegend ? (
              <MatrixStatsLegend helpExplain={matrixLegendExplainDefault} />
            ) : null}
          </div>
        ) : null}
        <p className="text-xs text-slate-400">표시할 매트릭스 데이터가 없습니다.</p>
      </div>
    );
  }

  const toolbar = (
    <div
      className={clsx(
        "mb-2 flex flex-wrap items-start justify-between gap-2",
        !showHeadingRow && "justify-end"
      )}
    >
      {showHeadingRow ? (
        <div className="min-w-0">
          {(title ?? "").trim() ? (
            <h3 className="text-sm font-semibold text-slate-600">{title}</h3>
          ) : null}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2 shrink-0 ml-auto">
        {showEmbeddedLegend ? (
          <MatrixStatsLegend helpExplain={matrixLegendExplainDefault} />
        ) : null}
        <AnalysisHelpPanel explain={matrixTableExplain} />
        <MatrixFullscreenButton onClick={() => setFullscreen(true)} />
      </div>
    </div>
  );

  return (
    <div>
      {toolbar}
      <MatrixStatsTableGrid {...gridProps} />

      {fullscreen &&
        createPortal(
          <div
            className="fixed inset-0 z-[120] flex flex-col bg-slate-100 dark:bg-slate-950"
            role="dialog"
            aria-modal="true"
            aria-labelledby="matrix-fullscreen-title"
          >
            <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 py-2.5 shadow-sm">
              <h3
                id="matrix-fullscreen-title"
                className="text-sm font-semibold text-slate-800"
              >
                {headingText}
              </h3>
              <div className="flex flex-wrap items-center gap-2">
                <MatrixStatsLegend helpExplain={matrixLegendExplainDefault} />
                <AnalysisHelpPanel explain={matrixTableExplain} />
                <MatrixFullscreenButton
                  variant="close"
                  label="닫기 (Esc)"
                  onClick={() => setFullscreen(false)}
                />
              </div>
            </header>
            <div className="min-h-0 flex-1 p-3">
              <MatrixStatsTableGrid
                {...gridProps}
                scrollClassName="h-full overflow-auto overscroll-contain rounded-lg border border-slate-200 bg-white shadow-sm"
              />
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}

function sortLabels(
  labels: string[],
  totals: Record<string, StatsResult>,
  fallbackCount: (label: string) => number
) {
  return labels.sort((a, b) => {
    const countDiff =
      (totals[b]?.count ?? fallbackCount(b)) -
      (totals[a]?.count ?? fallbackCount(a));
    return countDiff || a.localeCompare(b, "ko-KR");
  });
}

function countZone(matrix: MatrixCell[], zone: string) {
  return matrix
    .filter((cell) => cell.zone_type === zone)
    .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0);
}

function countCategory(matrix: MatrixCell[], category: string) {
  return matrix
    .filter((cell) => cell.land_category === category)
    .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0);
}

function fmtMarginalMean(
  stats: StatsResult | undefined,
  fallbackCount: number
): string {
  const count = stats?.count ?? fallbackCount;
  if (count < 1 || stats?.mean == null) return "-";
  return fmtD1(stats.mean);
}
