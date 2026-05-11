import { Fragment } from "react";
import clsx from "clsx";
import type { MatrixCell, StatsResult } from "../types";

/** 고정 레이아웃 (만원/㎡) — 통계 라벨 열 없음 */
const COL_ZONE_PX = 96; // 이전 대비 용도지역 열 0.6배 (160×0.6)
const COL_VALUE_PX = 88;
const ROW_PX = 28;
/** 지목 헤더 1행 높이(고정값) — sticky 2행 offset과 맞춤 */
const THEAD_ROW1_HEIGHT = ROW_PX + 8;

/** 평균적인 셀 테두리 (1px — 경계선 강조는 별도) */
const CELL = "box-border border border-slate-200";
/** 용도지역 열 ↔ 지목 데이터 구간 세로 경계 — 굵게(2px) 대비 ×0.7 */
const ZONE_TO_DATA = "border-r-[1.4px] border-r-slate-400";
/** 지목 블록(좌+우 두 열) 사이 세로 경계 — 1.5px 대비 ×1.2 */
const BETWEEN_CATEGORIES_LEFT = "border-l-[1.8px] border-l-slate-400";

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

/** 무료 패널 상단(지역명 행 우측) 등에서 재사용 */
export function MatrixStatsLegend() {
  return (
    <table
      className="table-fixed shrink-0 border-collapse border border-slate-200 bg-white text-[9px] leading-tight text-slate-600"
      style={{ width: 236 }}
      aria-label="매트릭스 셀 구조 범례"
    >
      <tbody>
        <tr>
          <td className="border border-slate-200 px-0.5 py-px">거래수</td>
          <td className="border border-slate-200 px-0.5 py-px">최소</td>
        </tr>
        <tr>
          <td
            rowSpan={2}
            className="border border-slate-200 px-0.5 py-px text-center align-middle font-semibold text-slate-700 leading-tight"
          >
            평균
          </td>
          <td className="border border-slate-200 px-0.5 py-px">25%값</td>
        </tr>
        <tr>
          <td className="border border-slate-200 px-0.5 py-px">중위</td>
        </tr>
        <tr>
          <td className="border border-slate-200 px-0.5 py-px">표준편차</td>
          <td className="border border-slate-200 px-0.5 py-px">75%값</td>
        </tr>
        <tr>
          <td className="border border-slate-200 px-0.5 py-px">신뢰구간(95%)</td>
          <td className="border border-slate-200 px-0.5 py-px">최대</td>
        </tr>
      </tbody>
    </table>
  );
}

interface Props {
  /** 빈 문자열이면 표 위 제목 비표시 */
  title?: string;
  matrix?: MatrixCell[] | null;
  byZone?: Record<string, StatsResult>;
  byLandCategory?: Record<string, StatsResult>;
  /** 무료처럼 범례를 상단별도 배치하면 false */
  showEmbeddedLegend?: boolean;
}

function cellHl(reliable?: boolean): string {
  return reliable ? "bg-amber-50" : "";
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

export default function MatrixStatsTable({
  title = "용도지역 × 지목 분석표",
  matrix,
  byZone = {},
  byLandCategory = {},
  showEmbeddedLegend = true,
}: Props) {
  const cells = matrix ?? [];
  const showHeadingRow =
    (title ?? "").trim().length > 0 || showEmbeddedLegend;

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
            {showEmbeddedLegend ? <MatrixStatsLegend /> : null}
          </div>
        ) : null}
        <p className="text-xs text-slate-400">표시할 매트릭스 데이터가 없습니다.</p>
      </div>
    );
  }

  const lookup = new Map(
    cells
      .filter((cell) => cell.stats != null)
      .map((cell) => [`${cell.zone_type}|||${cell.land_category}`, cell.stats])
  );

  const zones = sortLabels(
    Array.from(new Set(cells.map((cell) => cell.zone_type))),
    byZone,
    (label) =>
      cells
        .filter((cell) => cell.zone_type === label)
        .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0)
  );

  const landCategories = sortLabels(
    Array.from(new Set(cells.map((cell) => cell.land_category))),
    byLandCategory,
    (label) =>
      cells
        .filter((cell) => cell.land_category === label)
        .reduce((sum, cell) => sum + (cell.stats?.count ?? 0), 0)
  );

  const tableWidth = COL_ZONE_PX + landCategories.length * (COL_VALUE_PX * 2);

  return (
    <div>
      {showHeadingRow ? (
        <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {(title ?? "").trim() ? (
              <h3 className="text-sm font-semibold text-slate-600">{title}</h3>
            ) : null}
          </div>
          {showEmbeddedLegend ? <MatrixStatsLegend /> : null}
        </div>
      ) : null}

      <div className="max-h-[min(72vh,56rem)] overflow-auto border border-slate-200 rounded-lg overscroll-contain">
        <table
          className="table-fixed border-collapse bg-white text-xs leading-tight"
          style={{ width: tableWidth }}
        >
          <colgroup>
            <col style={{ width: COL_ZONE_PX }} />
            {landCategories.map((category) => (
              <Fragment key={`col-${category}`}>
                <col style={{ width: COL_VALUE_PX }} />
                <col style={{ width: COL_VALUE_PX }} />
              </Fragment>
            ))}
          </colgroup>
          <thead>
            <tr className="bg-slate-100 text-slate-600" style={{ height: THEAD_ROW1_HEIGHT }}>
              <th
                className={clsx(
                  "sticky left-0 top-0 z-[31] bg-slate-100 px-1 py-1 align-middle text-center font-medium shadow-[inset_0_-1px_0_0_rgb(226_232_240)]",
                  cellZoneCol()
                )}
              >
                용도지역
              </th>
              {landCategories.map((category, ci) => (
                <th
                  key={category}
                  colSpan={2}
                  className={clsx(
                    "sticky top-0 z-[21] bg-slate-100 max-w-0 px-1 py-1 text-center align-middle text-sm font-medium truncate shadow-[inset_0_-1px_0_0_rgb(226_232_240)]",
                    cellLeftCat(ci)
                  )}
                  title={`${category} ${fmtCount(byLandCategory[category]?.count ?? countCategory(cells, category))}건`}
                >
                  <span className="flex flex-col items-center gap-px leading-tight">
                    <span className="block truncate w-full text-sm font-semibold text-slate-700">
                      {category}
                    </span>
                    <span className="text-[11px] text-slate-400 font-normal">
                      {fmtCount(byLandCategory[category]?.count ?? countCategory(cells, category))}
                      건
                    </span>
                  </span>
                </th>
              ))}
            </tr>
            <tr className="bg-slate-50 text-slate-400" style={{ height: ROW_PX }}>
              <th
                className={clsx(
                  "sticky left-0 z-[31] bg-slate-50 p-0 shadow-[inset_0_-1px_0_0_rgb(226_232_240)]",
                  cellZoneCol()
                )}
                style={{ top: THEAD_ROW1_HEIGHT }}
              />
              {landCategories.map((category, ci) => (
                <Fragment key={`${category}-subhead`}>
                  <th
                    className={clsx(
                      "sticky z-[21] bg-slate-50 px-1 py-0.5 text-center font-normal truncate text-[11px] shadow-[inset_0_-1px_0_0_rgb(226_232_240)]",
                      cellLeftCat(ci)
                    )}
                    style={{ top: THEAD_ROW1_HEIGHT }}
                  >
                    좌
                  </th>
                  <th
                    className={clsx(
                      "sticky z-[21] bg-slate-50 px-1 py-0.5 text-center font-normal truncate text-[11px] shadow-[inset_0_-1px_0_0_rgb(226_232_240)]",
                      cellRightCat()
                    )}
                    style={{ top: THEAD_ROW1_HEIGHT }}
                  >
                    우
                  </th>
                </Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {zones.map((zone, zi) => (
              <Fragment key={zone}>
                {/* ① 거래수 | 최소 */}
                <tr
                  className={clsx(zi > 0 && "border-t-[2.8px] border-t-slate-400")}
                  style={{ height: ROW_PX }}
                >
                  <th
                    rowSpan={5}
                    className={clsx(
                      "sticky left-0 z-10 bg-white px-1 py-1 align-middle text-center text-sm font-semibold text-slate-700",
                      cellZoneCol()
                    )}

                    title={zone}
                  >
                    <div className="line-clamp-2 break-all text-center">{zone}</div>
                    <div className="mt-0.5 text-[10px] font-normal leading-tight text-slate-400">
                      {fmtCount(byZone[zone]?.count ?? countZone(cells, zone))}건
                    </div>
                  </th>
                  {landCategories.map((category, ci) => {
                    const stats = lookup.get(`${zone}|||${category}`);
                    const deal = hasDeals(stats);
                    const faint = faintBlock(stats);

                    return (
                      <Fragment key={`${zone}-${category}-r0`}>
                        <td
                          className={clsx(
                            cellLeftCat(ci),
                            "px-1 py-0 text-right align-middle tabular-nums truncate",
                            faint,
                            cellHl(stats?.is_reliable),
                            stats?.is_reliable ? "text-slate-900 font-medium" : "text-blue-950"
                          )}
                          title={
                            deal ? `거래수: ${fmtCount(stats!.count)}` : "거래수"
                          }
                        >
                          {deal ? fmtCount(stats!.count) : "-"}
                        </td>
                        <td
                          className={clsx(
                            cellRightCat(),
                            "px-1 py-0 align-middle text-right tabular-nums truncate text-slate-600",
                            faint,
                            cellHl(stats?.is_reliable)
                          )}
                          title={deal ? `최소: ${fmtD1(stats!.min)}` : "최소"}
                        >
                          {deal ? fmtD1(stats!.min) : "-"}
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
                {/* ②③ 평균(rowspan 2) | 25%, 중위 */}
                <tr style={{ height: ROW_PX }}>
                  {landCategories.map((category, ci) => {
                    const stats = lookup.get(`${zone}|||${category}`);
                    const deal = hasDeals(stats);
                    const faint = faintBlock(stats);
                    return (
                      <Fragment key={`${zone}-${category}-r1`}>
                        <td
                          rowSpan={2}
                          className={clsx(
                            cellLeftCat(ci),
                            "px-1 py-0 align-middle text-right font-bold tabular-nums leading-tight truncate text-blue-950 text-[1.125rem]",
                            faint,
                            cellHl(stats?.is_reliable)
                          )}
                          title={deal ? `평균: ${fmtD1(stats!.mean)}` : "평균"}
                        >
                          {deal ? fmtD1(stats!.mean) : "-"}
                        </td>
                        <td
                          className={clsx(
                            cellRightCat(),
                            "px-1 py-0 align-middle text-right tabular-nums truncate text-slate-600",
                            faint,
                            cellHl(stats?.is_reliable)
                          )}
                          title={deal ? `25%: ${fmtD1(stats!.p25)}` : "25%"}
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
                    return (
                      <td
                        key={`${zone}-${category}-r2`}
                        className={clsx(
                          cellRightCat(),
                          "px-1 py-0 align-middle text-right tabular-nums truncate font-bold text-slate-700",
                          faint,
                          cellHl(stats?.is_reliable)
                        )}
                        title={deal ? `중위: ${fmtD1(stats!.median)}` : "중위값"}
                      >
                        {deal ? fmtD1(stats!.median) : "-"}
                      </td>
                    );
                  })}
                </tr>
                {/* ④ 표준편차 | 75% */}
                <tr style={{ height: ROW_PX }}>
                  {landCategories.map((category, ci) => {
                    const stats = lookup.get(`${zone}|||${category}`);
                    const deal = hasDeals(stats);
                    const faint = faintBlock(stats);
                    return (
                      <Fragment key={`${zone}-${category}-r3`}>
                        <td
                          className={clsx(
                            cellLeftCat(ci),
                            "px-1 py-0 align-middle text-right tabular-nums font-semibold truncate text-blue-900 text-[10px]",
                            faint,
                            cellHl(stats?.is_reliable)
                          )}
                          title={deal ? `표준편차: ${fmtD1(stats!.std)}` : "표준편차"}
                        >
                          {deal ? fmtD1(stats!.std) : "-"}
                        </td>
                        <td
                          className={clsx(
                            cellRightCat(),
                            "px-1 py-0 align-middle text-right tabular-nums truncate text-slate-600",
                            faint,
                            cellHl(stats?.is_reliable)
                          )}
                          title={deal ? `75%: ${fmtD1(stats!.p75)}` : "75%"}
                        >
                          {deal ? fmtD1(stats!.p75) : "-"}
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
                {/* ⑤ 신뢰구간 | 최대 */}
                <tr style={{ height: ROW_PX }}>
                  {landCategories.map((category, ci) => {
                    const stats = lookup.get(`${zone}|||${category}`);
                    const deal = hasDeals(stats);
                    const faint = faintBlock(stats);
                    const ciTxt =
                      stats && deal
                        ? fmtCiRange(stats.ci_lower, stats.ci_upper)
                        : "-";
                    return (
                      <Fragment key={`${zone}-${category}-r4`}>
                        <td
                          className={clsx(
                            cellLeftCat(ci),
                            "px-1 py-0 align-middle text-right tabular-nums font-semibold truncate text-blue-900",
                            faint,
                            cellHl(stats?.is_reliable)
                          )}
                          title={
                            deal
                              ? `95% 신뢰구간: ${fmtCiRange(stats!.ci_lower, stats!.ci_upper)}`
                              : "신뢰구간"
                          }
                        >
                          {deal ? ciTxt : "-"}
                        </td>
                        <td
                          className={clsx(
                            cellRightCat(),
                            "px-1 py-0 align-middle text-right tabular-nums truncate text-slate-600",
                            faint,
                            cellHl(stats?.is_reliable)
                          )}
                          title={deal ? `최대: ${fmtD1(stats!.max)}` : "최대"}
                        >
                          {deal ? fmtD1(stats!.max) : "-"}
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
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
