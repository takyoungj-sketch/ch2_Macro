import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { downloadBuiltTransactionsCsv, fetchTransactions, type TransactionQueryParams } from "../api/client";
import type { AssetType, BuiltTransactionRow } from "../types";

const TX_PAGE = 25;

const ASSET_TYPE_LABELS: Record<string, string> = {
  commercial: "상업",
  factory: "공장",
  detached: "단독",
};

function fmtNum(n?: number | null, digits = 0) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtContractDate(r: BuiltTransactionRow) {
  if (r.contract_date) return r.contract_date;
  if (r.contract_year != null && r.contract_month != null) {
    return `${r.contract_year}-${String(r.contract_month).padStart(2, "0")}`;
  }
  return r.contract_year != null ? String(r.contract_year) : (r.trade_year_label ?? "—");
}

function TransactionTable({ items, assetType }: { items: BuiltTransactionRow[]; assetType: AssetType }) {
  const useLabel = assetType === "detached" ? "주택유형" : "건축물용도";
  return (
    <div className="modal-table-wrap overflow-x-auto">
      <table className="w-full text-[11px] border-collapse min-w-[720px] modal-inner-table">
        <thead>
          <tr>
            {assetType === "all" && (
              <th className="border px-2 py-1.5 text-left font-medium">유형</th>
            )}
            <th className="border px-2 py-1.5 text-left font-medium">주소</th>
            <th className="border px-2 py-1.5 text-left font-medium">계약일</th>
            {assetType !== "detached" && assetType !== "all" && (
              <th className="border px-2 py-1.5 text-left font-medium">용도지역</th>
            )}
            {assetType === "all" && (
              <th className="border px-2 py-1.5 text-left font-medium">용도지역</th>
            )}
            <th className="border px-2 py-1.5 text-left font-medium">{useLabel}</th>
            <th className="border px-2 py-1.5 text-right font-medium">금액(만)</th>
            <th className="border px-2 py-1.5 text-right font-medium">연면적</th>
            <th className="border px-2 py-1.5 text-right font-medium">대지</th>
            <th className="border px-2 py-1.5 text-right font-medium">연식</th>
            <th className="border px-2 py-1.5 text-left font-medium">도로조건</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id}>
              {assetType === "all" && (
                <td className="border px-2 py-1 whitespace-nowrap">
                  {ASSET_TYPE_LABELS[r.asset_type] ?? r.asset_type}
                </td>
              )}
              <td className="border px-2 py-1 max-w-[14rem] truncate" title={r.display_address ?? undefined}>
                {r.display_address ?? "—"}
              </td>
              <td className="border px-2 py-1 tabular-nums whitespace-nowrap">{fmtContractDate(r)}</td>
              {assetType !== "detached" && assetType !== "all" && (
                <td className="border px-2 py-1 whitespace-nowrap">{r.zone_type ?? "—"}</td>
              )}
              {assetType === "all" && (
                <td className="border px-2 py-1 whitespace-nowrap">
                  {r.asset_type === "detached" ? "—" : (r.zone_type ?? "—")}
                </td>
              )}
              <td className="border px-2 py-1 whitespace-nowrap">{r.building_use ?? "—"}</td>
              <td className="border px-2 py-1 text-right tabular-nums">{fmtNum(r.price)}</td>
              <td className="border px-2 py-1 text-right tabular-nums">{fmtNum(r.gross_area, 1)}</td>
              <td className="border px-2 py-1 text-right tabular-nums">{fmtNum(r.land_area, 1)}</td>
              <td className="border px-2 py-1 text-right tabular-nums">{fmtNum(r.building_age, 0)}</td>
              <td className="border px-2 py-1 max-w-[8rem] truncate" title={r.road_width_label ?? undefined}>
                {r.road_width_label ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

async function txExportErrorMessage(err: unknown): Promise<string> {
  const ax = err as { response?: { data?: Blob | { detail?: string } } };
  const data = ax.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text) as { detail?: string };
      if (parsed.detail) return parsed.detail;
    } catch {
      /* fall through */
    }
  } else if (data && typeof data === "object" && "detail" in data && data.detail) {
    return String(data.detail);
  }
  return "CSV 내보내기에 실패했습니다.";
}

export default function BuiltTransactionListModal({
  open,
  onClose,
  assetType,
  exportParams,
  summary,
}: {
  open: boolean;
  onClose: () => void;
  assetType: AssetType;
  exportParams: Omit<TransactionQueryParams, "page" | "page_size">;
  summary?: string;
}) {
  const [page, setPage] = useState(1);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setPage(1);
      setExportError(null);
    }
  }, [open, exportParams]);

  useEffect(() => {
    setPage(1);
  }, [exportParams]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const txQ = useQuery({
    queryKey: ["built-tx-modal", exportParams, page],
    queryFn: () =>
      fetchTransactions({
        ...exportParams,
        page,
        page_size: TX_PAGE,
      }),
    enabled: open,
  });

  if (!open) return null;

  const total = txQ.data?.total ?? 0;
  const items = txQ.data?.items ?? [];
  const offset = (page - 1) * TX_PAGE;

  const handleExport = async () => {
    setExportLoading(true);
    setExportError(null);
    try {
      await downloadBuiltTransactionsCsv(exportParams);
    } catch (err) {
      setExportError(await txExportErrorMessage(err));
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/35"
      role="dialog"
      aria-modal="true"
      aria-labelledby="built-tx-modal-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 modal-shell rounded-xl shadow-xl max-w-5xl w-[calc(100%-2rem)] max-h-[85vh] flex flex-col border"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 modal-header shrink-0">
          <div className="flex justify-between items-start gap-2">
            <div className="min-w-0">
              <h2 id="built-tx-modal-title" className="text-sm font-bold">
                거래 목록
              </h2>
              {summary && (
                <p className="text-[11px] text-slate-500 mt-0.5">{summary}</p>
              )}
            </div>
            <button
              type="button"
              aria-label="닫기"
              className="text-slate-400 hover:text-slate-700 text-xl leading-none px-1 shrink-0"
              onClick={onClose}
            >
              ×
            </button>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-2">
          {txQ.isLoading && (
            <p className="text-xs text-slate-400 text-center py-6">목록 불러오는 중…</p>
          )}
          {txQ.isError && (
            <p className="text-xs text-red-600 text-center py-6">거래 목록을 불러오지 못했습니다.</p>
          )}
          {txQ.data && (
            <>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-[11px] text-slate-500">
                  전체 <strong className="text-slate-700">{total.toLocaleString("ko-KR")}</strong>건
                  <span className="text-slate-400 ml-1">· 페이지당 {TX_PAGE}건</span>
                </p>
                <button
                  type="button"
                  disabled={exportLoading || total === 0}
                  onClick={() => void handleExport()}
                  className="shrink-0 px-2.5 py-1 rounded border border-slate-200 text-[11px] font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                >
                  {exportLoading ? "내보내는 중…" : "CSV 내보내기"}
                </button>
              </div>
              {exportError && <p className="text-[11px] text-red-600">{exportError}</p>}
              {items.length > 0 ? (
                <TransactionTable items={items} assetType={assetType} />
              ) : (
                <p className="text-xs text-slate-400 text-center py-6">조건에 맞는 거래가 없습니다.</p>
              )}
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                <span className="text-slate-400">
                  {total > 0
                    ? `${(offset + 1).toLocaleString("ko-KR")}–${Math.min(offset + items.length, total).toLocaleString("ko-KR")} / ${total.toLocaleString("ko-KR")}`
                    : "0건"}
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
                  >
                    이전
                  </button>
                  <button
                    type="button"
                    disabled={offset + TX_PAGE >= total}
                    onClick={() => setPage((p) => p + 1)}
                    className="px-2 py-1 rounded border border-slate-200 text-slate-600 disabled:opacity-40 hover:bg-slate-50"
                  >
                    다음
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
