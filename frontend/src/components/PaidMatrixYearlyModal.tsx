import { useEffect, useMemo, useState } from "react";
import { simpleTableHeadClass } from "../constants/displayUi";
import { useAppStore } from "../store";
import type { MatrixYearlyStat } from "../types";
import MatrixYearlyTrendChart from "./MatrixYearlyTrendChart";

interface Props {
  open: boolean;
  onClose: () => void;
  loading: boolean;
  error: string | null;
  zoneType: string;
  landCategory: string;
  rows: MatrixYearlyStat[];
  /** 적용 범위 안내(기본: 필터 분석 기준 문구) */
  scopeNote?: string;
}

type PanelMode = "chart" | "data";

/** 유료 매트릭스 칸: 동일 필터 적용 상태에서 연도별 추이(차트) 또는 연도별 수치 표 */
export default function PaidMatrixYearlyModal({
  open,
  onClose,
  loading,
  error,
  zoneType,
  landCategory,
  rows,
  scopeNote,
}: Props) {
  const [panel, setPanel] = useState<PanelMode>("chart");
  const uiTableTone = useAppStore((s) => s.uiTableTone);

  useEffect(() => {
    if (open) setPanel("chart");
  }, [open, zoneType, landCategory]);

  const sortedRows = useMemo(
    () => [...rows].sort((a, b) => a.year - b.year),
    [rows]
  );

  if (!open) return null;

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
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col border border-slate-200">
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
            {!loading && !error && rows.length > 0 && (
              <div
                className="mt-2 inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5 gap-0.5"
                role="tablist"
                aria-label="보기 형식"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={panel === "chart"}
                  className={`px-2.5 py-1 text-[11px] font-medium rounded transition-colors ${
                    panel === "chart"
                      ? "bg-white text-slate-800 shadow-sm border border-slate-100"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                  onClick={() => setPanel("chart")}
                >
                  차트
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={panel === "data"}
                  className={`px-2.5 py-1 text-[11px] font-medium rounded transition-colors ${
                    panel === "data"
                      ? "bg-white text-slate-800 shadow-sm border border-slate-100"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                  onClick={() => setPanel("data")}
                >
                  데이터
                </button>
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
          {!loading && !error && rows.length > 0 && panel === "chart" && (
            <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-3">
              <p className="text-[10px] font-semibold text-slate-600 px-1 mb-2">추이 (꺾은선)</p>
              <MatrixYearlyTrendChart rows={rows} />
            </div>
          )}
          {!loading && !error && rows.length > 0 && panel === "data" && (
            <div className="rounded-lg border border-slate-100 bg-white overflow-hidden">
              <p className="text-[10px] font-semibold text-slate-600 px-3 pt-3 pb-1">
                연도별 수치 (같은 조건 요약 집계)
              </p>
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className={simpleTableHeadClass(uiTableTone)}>
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
          )}
        </div>
      </div>
    </div>
  );
}
