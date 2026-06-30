import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  downloadBuiltTransactionsCsv,
  fetchAllBuiltTransactions,
  type TransactionQueryParams,
} from "../api/client";
import type { AssetType } from "../types";
import BuiltTransactionTable from "./BuiltTransactionTable";

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
  return "CSV보내기에 실패했습니다.";
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
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (open) setExportError(null);
  }, [open, exportParams]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const txQ = useQuery({
    queryKey: ["built-tx-modal-all", exportParams],
    queryFn: () => fetchAllBuiltTransactions(exportParams),
    enabled: open,
  });

  if (!open) return null;

  const total = txQ.data?.total ?? 0;
  const items = txQ.data?.items ?? [];
  const truncated = txQ.data?.truncated ?? false;

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
        className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 modal-shell rounded-xl shadow-xl max-w-6xl w-[calc(100%-2rem)] min-h-[min(520px,85vh)] max-h-[85vh] flex flex-col border"
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

        <div className="flex-1 min-h-[360px] overflow-y-auto px-4 py-3 space-y-2 flex flex-col">
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
                  {truncated && (
                    <span className="text-amber-700 ml-1">
                      · 최대 {items.length.toLocaleString("ko-KR")}건만 로드됨
                    </span>
                  )}
                </p>
                <button
                  type="button"
                  disabled={exportLoading || total === 0}
                  onClick={() => void handleExport()}
                  className="shrink-0 px-2.5 py-1 rounded border border-slate-200 text-[11px] font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                >
                  {exportLoading ? "보내는 중…" : "CSV보내기"}
                </button>
              </div>
              {exportError && <p className="text-[11px] text-red-600">{exportError}</p>}
              {items.length > 0 ? (
                <div className="flex-1 min-h-0 flex flex-col">
                  <BuiltTransactionTable items={items} assetType={assetType} truncated={truncated} />
                </div>
              ) : (
                <p className="text-xs text-slate-400 text-center py-6">조건에 맞는 거래가 없습니다.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
