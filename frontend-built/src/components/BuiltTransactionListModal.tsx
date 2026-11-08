import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  downloadBuiltTransactionsCsv,
  fetchAllBuiltTransactions,
  type TransactionQueryParams,
} from "../api/client";
import type { AssetType, BuiltTransactionRow } from "../types";
import { isOnlyDetached, isUnifiedAsset } from "../utils/assetTypes";
import type { BuiltTxDrillDownFilters } from "../utils/builtTxAggregate";
import {
  defaultBands,
  type BandMap,
  type RowOverride,
} from "../utils/allocationCost";
import {
  TRANSACTION_AGGREGATE_HELP,
  TRANSACTION_CSV_HELP,
} from "../utils/builtTransactionHelp";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import BuiltTransactionAggregate from "./BuiltTransactionAggregate";
import BuiltTransactionTable from "./BuiltTransactionTable";
import { AllocationDetailDialog, AllocationReferenceDialog } from "./AllocationUi";
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
  const [allocation, setAllocation] = useState(false);
  const [bands, setBands] = useState<BandMap>(() => defaultBands());
  const [rowOverrides, setRowOverrides] = useState<Record<number, RowOverride>>({});
  const [refOpen, setRefOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [txView, setTxView] = useState<"list" | "aggregate">("list");
  const [externalFilters, setExternalFilters] = useState<BuiltTxDrillDownFilters | undefined>(undefined);
  const [externalToken, setExternalToken] = useState(0);

  useEffect(() => {
    if (open) setExportError(null);
    if (!open) {
      setAllocation(false);
      setRefOpen(false);
      setDetailId(null);
      setTxView("list");
      setBands(defaultBands());
      setRowOverrides({});
    }
  }, [open, exportParams]);

  const txQ = useQuery({
    queryKey: ["built-tx-modal-all", exportParams],
    queryFn: () => fetchAllBuiltTransactions(exportParams),
    enabled: open,
  });

  const total = txQ.data?.total ?? 0;
  const items = txQ.data?.items ?? [];
  const truncated = txQ.data?.truncated ?? false;

  const detailRow: BuiltTransactionRow | null =
    detailId == null ? null : items.find((row) => row.id === detailId) ?? null;

  const patchOverride = (id: number, patch: RowOverride) => {
    setRowOverrides((prev) => {
      const next = { ...prev, [id]: { ...prev[id] } };
      (Object.keys(patch) as (keyof RowOverride)[]).forEach((key) => {
        const value = patch[key];
        if (value == null) delete next[id][key];
        else next[id][key] = value;
      });
      if (Object.keys(next[id]).length === 0) delete next[id];
      return next;
    });
  };

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
              <div className="flex flex-wrap items-center justify-end gap-1.5">
                {items.length > 0 && (
                  <span className="inline-flex items-center gap-0.5">
                    <div
                      className="inline-flex rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5"
                      role="tablist"
                      aria-label="거래 보기"
                    >
                      {(
                        [
                          ["list", "목록"],
                          ["aggregate", "집계"],
                        ] as const
                      ).map(([id, label]) => (
                        <button
                          key={id}
                          type="button"
                          role="tab"
                          aria-selected={txView === id}
                          className={clsx(
                            "px-2 py-0.5 text-[11px] rounded transition-colors",
                            txView === id
                              ? "bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 shadow-sm font-medium"
                              : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200",
                          )}
                          onClick={() => setTxView(id)}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <AnalysisHelpPanel explain={TRANSACTION_AGGREGATE_HELP} title="거래목록 집계 설명" />
                  </span>
                )}
                <span className="inline-flex items-center gap-0.5">
                  <button
                    type="button"
                    aria-haspopup="dialog"
                    aria-expanded={refOpen}
                    onClick={() => {
                      setDetailId(null);
                      setRefOpen(true);
                    }}
                    className={clsx(
                      "shrink-0 px-2.5 py-1 rounded border text-[11px] font-medium whitespace-nowrap",
                      allocation
                        ? "border-blue-600 bg-blue-600 text-white"
                        : "border-slate-200 text-slate-700 bg-white hover:bg-slate-50",
                    )}
                  >
                    간이 토지 배분단가
                  </button>
                </span>
                <span className="inline-flex items-center gap-0.5">
                  <button
                    type="button"
                    disabled={exportLoading || total === 0}
                    onClick={() => void handleExport()}
                    className="shrink-0 px-2.5 py-1 rounded border border-slate-200 text-[11px] font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                  >
                    {exportLoading ? "보내는 중…" : "CSV보내기"}
                  </button>
                  <AnalysisHelpPanel explain={TRANSACTION_CSV_HELP} title="CSV보내기 설명" />
                </span>
              </div>
            </div>
            {allocation && (
              <p className="text-[11px] text-slate-500 leading-4">
                토지 배분단가는 원가 가정에 따라 계산한 참고값입니다. 목록의 원가·내용연수·배분단가를 누르면 거래별로 조정할 수 있습니다. 설명과 원가표는 ‘간이 토지 배분단가’ 버튼에서 다시 확인하세요.
              </p>
            )}
            {exportError && <p className="text-[11px] text-red-600 shrink-0">{exportError}</p>}
            {items.length > 0 ? (
              <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
                {txView === "aggregate" ? (
                  <BuiltTransactionAggregate
                    items={items}
                    total={total}
                    truncated={truncated}
                    showStructure={Boolean(exportParams.enrich)}
                    showAsset={isUnifiedAsset(assetType)}
                    useLabel={isOnlyDetached(assetType) ? "주택유형" : "건축물용도"}
                    allocation={allocation}
                    bands={bands}
                    rowOverrides={rowOverrides}
                    onDrillDown={(filters) => {
                      setExternalFilters(filters);
                      setExternalToken((token) => token + 1);
                      setTxView("list");
                    }}
                  />
                ) : (
                  <BuiltTransactionTable
                    items={items}
                    assetType={assetType}
                    truncated={truncated}
                    enrich={Boolean(exportParams.enrich)}
                    allocation={allocation}
                    bands={bands}
                    rowOverrides={rowOverrides}
                    onOpenAllocation={setDetailId}
                    activeRowId={detailId}
                    externalSelectFilters={externalFilters}
                    externalFilterToken={externalToken}
                  />
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-400 text-center py-6">조건에 맞는 거래가 없습니다.</p>
            )}
          </>
        )}
      </div>
      <AllocationReferenceDialog
        open={refOpen}
        bands={bands}
        items={items}
        onConfirm={(nextBands, showAllocation) => {
          setBands(nextBands);
          setAllocation(showAllocation);
          if (showAllocation) setTxView("list");
          setRefOpen(false);
        }}
        onClose={() => setRefOpen(false)}
      />
      <AllocationDetailDialog
        row={detailRow}
        bands={bands}
        override={detailId == null ? undefined : rowOverrides[detailId]}
        onOverride={patchOverride}
        onClear={(id) => {
          setRowOverrides((prev) => {
            const next = { ...prev };
            delete next[id];
            return next;
          });
        }}
        onClose={() => setDetailId(null)}
      />
    </DraggableModalShell>
  );
}
