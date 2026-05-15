import { useEffect, useMemo, useState } from "react";
import {
  fetchMatrixCellHistogram,
  fetchMatrixCellTransactions,
} from "../api/client";
import { simpleTableHeadClass } from "../constants/displayUi";
import type {
  MatrixCellHistogramResponse,
  MatrixCellTransactionsResponse,
  MatrixYearlyRequest,
  MatrixYearlyStat,
} from "../types";
import { parseApiError } from "../utils/apiError";
import MatrixCellHistogramChart from "./MatrixCellHistogramChart";
import MatrixYearlyTrendChart from "./MatrixYearlyTrendChart";

interface Props {
  open: boolean;
  onClose: () => void;
  loading: boolean;
  error: string | null;
  zoneType: string;
  landCategory: string;
  rows: MatrixYearlyStat[];
  /** matrix-yearly 호출과 동일한 필터 본문 (분포·원데이터 API 재사용) */
  filterRequest: MatrixYearlyRequest | null;
  /** 적용 범위 안내(기본: 필터 분석 기준 문구) */
  scopeNote?: string;
}

type PanelMode = "trend" | "histogram" | "transactions";

const TX_PAGE = 25;

/** 유료 매트릭스 칸: 연도별 추이 + 단가 분포 + 원거래 목록 */
export default function PaidMatrixYearlyModal({
  open,
  onClose,
  loading,
  error,
  zoneType,
  landCategory,
  rows,
  filterRequest,
  scopeNote,
}: Props) {
  const [panel, setPanel] = useState<PanelMode>("trend");
  const [histScope, setHistScope] = useState<"all" | "single">("all");
  const [histYear, setHistYear] = useState<number | null>(null);
  const [histLoading, setHistLoading] = useState(false);
  const [histError, setHistError] = useState<string | null>(null);
  const [histData, setHistData] = useState<MatrixCellHistogramResponse | null>(null);

  const [txOffset, setTxOffset] = useState(0);
  const [txLoading, setTxLoading] = useState(false);
  const [txError, setTxError] = useState<string | null>(null);
  const [txData, setTxData] = useState<MatrixCellTransactionsResponse | null>(null);

  useEffect(() => {
    if (open) {
      setPanel("trend");
      setHistScope("all");
      setHistYear(null);
      setHistData(null);
      setHistError(null);
      setTxOffset(0);
      setTxData(null);
      setTxError(null);
    }
  }, [open, zoneType, landCategory]);

  const sortedRows = useMemo(
    () => [...rows].sort((a, b) => a.year - b.year),
    [rows]
  );

  useEffect(() => {
    if (sortedRows.length === 0) return;
    setHistYear((y) => {
      const years = sortedRows.map((r) => r.year);
      if (y != null && years.includes(y)) return y;
      return years[0]!;
    });
  }, [sortedRows]);

  useEffect(() => {
    if (!open || panel !== "histogram" || !filterRequest) return;
    const yearForReq =
      histScope === "single"
        ? histYear ?? sortedRows[0]?.year ?? null
        : null;
    if (histScope === "single" && yearForReq == null) return;

    let cancelled = false;
    (async () => {
      setHistLoading(true);
      setHistError(null);
      try {
        const body = {
          ...filterRequest,
          histogram_scope: histScope,
          histogram_year: yearForReq,
          bin_count: 20,
        };
        const data = await fetchMatrixCellHistogram(body);
        if (!cancelled) setHistData(data);
      } catch (e) {
        if (!cancelled) {
          setHistData(null);
          setHistError(parseApiError(e).message);
        }
      } finally {
        if (!cancelled) setHistLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, panel, filterRequest, histScope, histYear, sortedRows]);

  useEffect(() => {
    if (!open || panel !== "transactions" || !filterRequest) return;
    let cancelled = false;
    (async () => {
      setTxLoading(true);
      setTxError(null);
      try {
        const data = await fetchMatrixCellTransactions({
          ...filterRequest,
          offset: txOffset,
          limit: TX_PAGE,
        });
        if (!cancelled) setTxData(data);
      } catch (e) {
        if (!cancelled) {
          setTxData(null);
          setTxError(parseApiError(e).message);
        }
      } finally {
        if (!cancelled) setTxLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, panel, filterRequest, txOffset]);

  useEffect(() => {
    if (panel !== "transactions") return;
    setTxOffset(0);
  }, [panel, filterRequest]);

  if (!open) return null;

  const canDetail = Boolean(filterRequest) && !loading && !error && rows.length > 0;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/35"
      role="dialog"
      aria-modal="true"
      aria-labelledby="paid-matrix-yearly-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[85vh] flex flex-col border border-slate-200">
        <div className="flex justify-between items-start gap-2 px-4 py-3 border-b border-slate-100">
          <div className="min-w-0 flex-1">
            <h2 id="paid-matrix-yearly-title" className="text-sm font-bold text-slate-800">
              연도별 평균 변동
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
              용도 <span className="font-semibold text-slate-700">{zoneType}</span> · 지목{" "}
              <span className="font-semibold text-slate-700">{landCategory}</span>
              <span className="block text-[10px] mt-1 text-slate-400">
                {scopeNote ?? "선택한 분석 필터 및 지역 범위가 그대로 적용됩니다."}
              </span>
            </p>
            {canDetail && (
              <div
                className="mt-2 inline-flex flex-wrap rounded-md border border-slate-200 bg-slate-50 p-0.5 gap-0.5"
                role="tablist"
                aria-label="보기 형식"
              >
                {(
                  [
                    ["trend", "추세·요약"],
                    ["histogram", "단가 분포"],
                    ["transactions", "거래 목록"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={panel === id}
                    className={`px-2.5 py-1 text-[11px] font-medium rounded transition-colors ${
                      panel === id
                        ? "bg-white text-slate-800 shadow-sm border border-slate-100"
                        : "text-slate-500 hover:text-slate-700"
                    }`}
                    onClick={() => setPanel(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            type="button"
            aria-label="닫기"
            className="shrink-0 text-slate-400 hover:text-slate-700 text-xl leading-none px-1"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-auto px-4 py-3 space-y-4">
          {loading && (
            <p className="text-xs text-slate-400 text-center py-6">연도별 집계 중…</p>
          )}
          {error && (
            <p className="text-xs text-red-500 text-center py-6">{error}</p>
          )}
          {!loading && !error && rows.length === 0 && (
            <p className="text-xs text-slate-400 text-center py-6">표시할 연도별 데이터가 없습니다.</p>
          )}

          {canDetail && panel === "trend" && (
            <>
              <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-3">
                <p className="text-[10px] font-semibold text-slate-600 px-1 mb-2">추이 (꺾은선)</p>
                <MatrixYearlyTrendChart rows={rows} />
              </div>
              <div className="rounded-lg border border-slate-100 bg-white overflow-hidden">
                <p className="text-[10px] font-semibold text-slate-600 px-3 pt-3 pb-1">
                  연도별 수치 (같은 조건 요약 집계)
                </p>
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className={simpleTableHeadClass("neutral")}>
                      <th className="border border-slate-200 px-2 py-1.5 text-left font-medium">
                        연도
                      </th>
                      <th className="border border-slate-200 px-2 py-1.5 text-right font-medium">
                        건수
                      </th>
                      <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700">
                        평균(만원/㎡)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-800">
                    {sortedRows.map((r) => (
                      <tr key={r.year}>
                        <td className="border border-slate-200 px-2 py-1 tabular-nums">{r.year}</td>
                        <td className="border border-slate-200 px-2 py-1 text-right tabular-nums">
                          {r.count.toLocaleString("ko-KR")}
                        </td>
                        <td className="border border-slate-200 px-2 py-1 text-right tabular-nums text-blue-600 font-bold">
                          {r.mean_unit_price_per_sqm != null
                            ? Number(r.mean_unit_price_per_sqm).toLocaleString("ko-KR", {
                                minimumFractionDigits: 1,
                                maximumFractionDigits: 1,
                              })
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {canDetail && panel === "histogram" && filterRequest && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="text-slate-500">표본 범위</span>
                <select
                  value={histScope}
                  onChange={(e) =>
                    setHistScope(e.target.value === "single" ? "single" : "all")
                  }
                  className="border border-slate-200 rounded px-2 py-1 bg-white text-slate-800"
                >
                  <option value="all">필터 연도 전체</option>
                  <option value="single">특정 연도만</option>
                </select>
                {histScope === "single" && (
                  <select
                    value={histYear ?? ""}
                    onChange={(e) => setHistYear(Number(e.target.value))}
                    className="border border-slate-200 rounded px-2 py-1 bg-white text-slate-800"
                  >
                    {sortedRows.map((r) => (
                      <option key={r.year} value={r.year}>
                        {r.year}년 ({r.count.toLocaleString("ko-KR")}건)
                      </option>
                    ))}
                  </select>
                )}
              </div>
              {histLoading && (
                <p className="text-xs text-slate-400 text-center py-4">분포 계산 중…</p>
              )}
              {histError && (
                <p className="text-xs text-red-500 text-center py-4">{histError}</p>
              )}
              {!histLoading && !histError && histData && (
                <>
                  <p className="text-[10px] text-slate-500 leading-relaxed">
                    표본 수 <strong className="text-slate-700">{histData.n.toLocaleString("ko-KR")}</strong>
                    건 · 이상치 제외{" "}
                    <strong className="text-slate-700">{histData.exclude_outlier ? "적용" : "안 함"}</strong>
                    {histData.exclude_outlier ? (
                      <span>
                        {" "}
                        (IQR×{histData.outlier_iqr_multiplier})
                      </span>
                    ) : null}
                    {histData.histogram_scope === "single" && histData.histogram_year != null ? (
                      <span>
                        {" "}
                        · 대상 연도 <strong className="text-slate-700">{histData.histogram_year}</strong>
                      </span>
                    ) : null}
                  </p>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-2">
                    <MatrixCellHistogramChart data={histData} />
                  </div>
                </>
              )}
            </div>
          )}

          {canDetail && panel === "transactions" && filterRequest && (
            <div className="space-y-2">
              {txLoading && (
                <p className="text-xs text-slate-400 text-center py-4">목록 불러오는 중…</p>
              )}
              {txError && (
                <p className="text-xs text-red-500 text-center py-4">{txError}</p>
              )}
              {!txLoading && !txError && txData && (
                <>
                  <p className="text-[10px] text-slate-500">
                    전체{" "}
                    <strong className="text-slate-700">
                      {txData.total.toLocaleString("ko-KR")}
                    </strong>
                    건 · 이상치 제외{" "}
                    <strong className="text-slate-700">{txData.exclude_outlier ? "적용" : "안 함"}</strong>
                    {txData.exclude_outlier ? (
                      <span> (IQR×{txData.outlier_iqr_multiplier})</span>
                    ) : null}
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-slate-100">
                    <table className="w-full text-[11px] border-collapse min-w-[640px]">
                      <thead>
                        <tr className={simpleTableHeadClass("neutral")}>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium whitespace-nowrap">
                            계약
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium whitespace-nowrap">
                            지역
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium whitespace-nowrap">
                            면적(㎡)
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-medium whitespace-nowrap">
                            금액(만원)
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-right font-bold text-blue-700 whitespace-nowrap">
                            단가
                          </th>
                          <th className="border border-slate-200 px-2 py-1.5 text-left font-medium whitespace-nowrap">
                            도로
                          </th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-800">
                        {txData.items.map((r) => (
                          <tr key={r.id}>
                            <td className="border border-slate-200 px-2 py-1 tabular-nums whitespace-nowrap">
                              {r.contract_year}.{String(r.contract_month).padStart(2, "0")}
                            </td>
                            <td
                              className="border border-slate-200 px-2 py-1 max-w-[11rem] truncate"
                              title={r.beopjungri_name ?? r.beopjungri_code}
                            >
                              {r.beopjungri_name ?? r.beopjungri_code}
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
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    <span className="text-slate-400">
                      {txData.total > 0
                        ? `${(txData.offset + 1).toLocaleString("ko-KR")}–${Math.min(txData.offset + txData.items.length, txData.total).toLocaleString("ko-KR")} / ${txData.total.toLocaleString("ko-KR")}`
                        : "0건"}
                    </span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={txOffset <= 0}
                        onClick={() => setTxOffset((o) => Math.max(0, o - TX_PAGE))}
                        className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
                      >
                        이전
                      </button>
                      <button
                        type="button"
                        disabled={txOffset + TX_PAGE >= txData.total}
                        onClick={() => setTxOffset((o) => o + TX_PAGE)}
                        className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
                      >
                        다음
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
