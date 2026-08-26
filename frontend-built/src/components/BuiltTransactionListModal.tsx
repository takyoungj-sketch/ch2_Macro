import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  downloadBuiltTransactionsCsv,
  fetchAllBuiltTransactions,
  type TransactionQueryParams,
} from "../api/client";
import type { AssetType } from "../types";
import BuiltTransactionTable from "./BuiltTransactionTable";
import DraggableModalShell from "./DraggableModalShell";

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

function defaultTxModalSize(): { width: number; height: number } {
  if (typeof window === "undefined") return { width: 960, height: 640 };
  return {
    width: Math.min(1152, window.innerWidth - 32),
    height: Math.min(Math.round(window.innerHeight * 0.85), Math.max(520, window.innerHeight - 48)),
  };
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
  const [defaultSize] = useState(defaultTxModalSize);

  useEffect(() => {
    if (open) setExportError(null);
  }, [open, exportParams]);

  const txQ = useQuery({
    queryKey: ["built-tx-modal-all", exportParams],
    queryFn: () => fetchAllBuiltTransactions(exportParams),
    enabled: open,
  });

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
    <DraggableModalShell
      open={open}
      onClose={onClose}
      titleId="built-tx-modal-title"
      title="거래 목록"
      subtitle={summary}
      maxWidthClass="max-w-6xl"
      resizable
      defaultWidth={defaultSize.width}
      defaultHeight={defaultSize.height}
      minWidth={480}
      minHeight={360}
      zClassName="z-[100]"
    >
      <div className="h-full min-h-0 space-y-2 flex flex-col">
        {txQ.isLoading && (
          <p className="text-xs text-slate-400 text-center py-6">목록 불러오는 중…</p>
        )}
        {txQ.isError && (
          <p className="text-xs text-red-600 text-center py-6">거래 목록을 불러오지 못했습니다.</p>
        )}
        {txQ.data && (
          <>
            <div className="flex flex-wrap items-start justify-between gap-2 shrink-0">
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
            {exportError && <p className="text-[11px] text-red-600 shrink-0">{exportError}</p>}
            {items.length > 0 ? (
              <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
                <BuiltTransactionTable
                  items={items}
                  assetType={assetType}
                  truncated={truncated}
                  enrich={Boolean(exportParams.enrich)}
                />
              </div>
            ) : (
              <p className="text-xs text-slate-400 text-center py-6">조건에 맞는 거래가 없습니다.</p>
            )}
          </>
        )}
      </div>
    </DraggableModalShell>
  );
}
