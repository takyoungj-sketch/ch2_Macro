import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import type { LeaseMetric, RentBuildingRow, RentConversionRate, RentRollingPoint } from "../types";
import { fetchRentRolling, fetchRentTransactions, type RentTransactionRow } from "../api/client";
import type { StatsWindowYears } from "./StatsWindowToggle";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { assetTypeLabel } from "../types";
import DraggableModalShell from "./DraggableModalShell";
import RentRegressionPanel from "./RentRegressionPanel";

type PanelMode = "conversion" | "rolling" | "transactions" | "regression";

const TABS: { id: PanelMode; label: string }[] = [
  { id: "conversion", label: "전환율" },
  { id: "rolling", label: "롤링 구간" },
  { id: "transactions", label: "거래 목록" },
  { id: "regression", label: "회귀 분석" },
];

function fmtUnit(v: number | null | undefined) {
  if (v == null) return "—";
  const digits = Math.abs(v) < 10 ? 1 : 0;
  return v.toLocaleString("ko-KR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits === 1 ? 1 : 0,
  });
}

function fmtR(v: number | null | undefined) {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v.toFixed(2)}%`;
}

function buildingRb(row: RentBuildingRow): number | null {
  const j = row.jeonse.median;
  const d = row.mixed.deposit.median;
  const m = row.mixed.monthly.median;
  if (j == null || d == null || m == null || j <= d || m <= 0) return null;
  if (row.jeonse.n < 3 || row.mixed.n < 3) return null;
  const r = ((12 * m) / (j - d)) * 100;
  if (r < 1 || r > 15) return null;
  return r;
}

function poolMean(rows: RentBuildingRow[]): number | null {
  const rs = rows.map(buildingRb).filter((r): r is number => r != null);
  if (!rs.length) return null;
  return rs.reduce((a, b) => a + b, 0) / rs.length;
}

function fmtCi(m: LeaseMetric) {
  if (m.ci_lower == null || m.ci_upper == null) return "—";
  return `${fmtUnit(m.ci_lower)}~${fmtUnit(m.ci_upper)}`;
}

function leaseKindLabel(kind: string) {
  if (kind === "mixed") return "반전세";
  if (kind === "monthly") return "월세";
  return "전세";
}

function Block({
  title,
  n,
  lines,
}: {
  title: string;
  n: number;
  lines: { label: string; metric: LeaseMetric }[];
}) {
  return (
    <div className="rounded border border-slate-200 dark:border-slate-700 p-2 space-y-0.5">
      <p className="text-xs font-semibold">
        {title} <span className="font-normal text-slate-400">n={n}</span>
      </p>
      {lines.map((line) => (
        <p key={line.label} className="text-[11px]">
          {line.label} {fmtUnit(line.metric.median)}
          <span className="ml-1 text-slate-400">({fmtCi(line.metric)})</span>
        </p>
      ))}
    </div>
  );
}

function TransactionTable({ items }: { items: RentTransactionRow[] }) {
  return (
    <div className="modal-table-wrap overflow-x-auto">
      <table className="w-full text-xs border-collapse modal-inner-table">
        <thead>
          <tr>
            <th className="border px-2 py-1">계약일</th>
            <th className="border px-2 py-1">유형</th>
            <th className="border px-2 py-1">층</th>
            <th className="border px-2 py-1">면적</th>
            <th className="border px-2 py-1">보증금</th>
            <th className="border px-2 py-1">월세</th>
            <th className="border px-2 py-1">보/㎡</th>
            <th className="border px-2 py-1">월/㎡</th>
          </tr>
        </thead>
        <tbody>
          {items.map((tx) => (
            <tr key={tx.id}>
              <td className="border px-2 py-1 tabular-nums">{tx.contract_date ?? "—"}</td>
              <td className="border px-2 py-1">{leaseKindLabel(tx.lease_kind)}</td>
              <td className="border px-2 py-1 tabular-nums">{tx.floor ?? "—"}</td>
              <td className="border px-2 py-1 tabular-nums">
                {tx.exclusive_area != null ? tx.exclusive_area.toFixed(1) : "—"}
              </td>
              <td className="border px-2 py-1 tabular-nums">
                {fmtUnit(tx.deposit_manwon)}
              </td>
              <td className="border px-2 py-1 tabular-nums">
                {fmtUnit(tx.monthly_rent_manwon)}
              </td>
              <td className="border px-2 py-1 tabular-nums">{fmtUnit(tx.deposit_per_m2)}</td>
              <td className="border px-2 py-1 tabular-nums">{fmtUnit(tx.monthly_per_m2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BuildingDetailModal({
  row,
  windowYears,
  peers,
  appliedRate,
  onClose,
}: {
  row: RentBuildingRow;
  windowYears: StatsWindowYears;
  peers: RentBuildingRow[];
  appliedRate: RentConversionRate | null;
  onClose: () => void;
}) {
  const [panel, setPanel] = useState<PanelMode>("conversion");
  const [extraKeys, setExtraKeys] = useState<string[]>([]);
  const [txPage, setTxPage] = useState(1);

  const rollingQ = useQuery({
    queryKey: ["rent-rolling", row.building_key, row.asset_type, windowYears],
    queryFn: () =>
      fetchRentRolling({
        buildingKey: row.building_key,
        assetType: row.asset_type,
        windowYears,
      }),
    enabled: panel === "rolling",
  });

  const txQ = useQuery({
    queryKey: ["rent-tx", row.building_key, row.asset_type, txPage],
    queryFn: () =>
      fetchRentTransactions({
        buildingKey: row.building_key,
        assetType: row.asset_type,
        page: txPage,
        pageSize: 50,
      }),
    enabled: panel === "transactions",
  });

  const focusR = buildingRb(row);
  const identifiablePeers = useMemo(
    () => peers.filter((p) => p.building_key !== row.building_key && buildingRb(p) != null),
    [peers, row.building_key],
  );
  const poolRows = useMemo(() => {
    const selected = peers.filter((p) => extraKeys.includes(p.building_key));
    return [row, ...selected];
  }, [peers, extraKeys, row]);
  const poolR = poolMean(poolRows);
  const regionR = appliedRate?.gate_passed ? appliedRate.r_selected : null;
  const regionLabel =
    appliedRate?.scope === "dong" && !appliedRate.fallback
      ? appliedRate.addr3 || "읍면동"
      : appliedRate?.fallback
        ? "시군구(동 미달)"
        : "시군구";

  function togglePeer(key: string) {
    setExtraKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }

  const n = (row.jeonse?.n ?? 0) + (row.mixed?.n ?? 0) + (row.monthly?.n ?? 0);

  return (
    <DraggableModalShell
      open
      onClose={onClose}
      titleId="rent-building-detail-title"
      title={row.display_name}
      subtitle={
        <>
          {assetTypeLabel(row.asset_type)} · 거래 {n.toLocaleString("ko-KR")}건
          {row.building_year ? ` · ${row.building_year}년 준공` : ""}
          {row.jibun_address ? ` · ${row.jibun_address}` : ""}
        </>
      }
      headerExtra={
        <div className="flex flex-wrap gap-0.5 rounded-md border modal-tab-bar p-0.5" role="tablist">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={panel === id}
              className={clsx(
                "px-2 py-1 text-[11px] font-medium rounded transition-colors whitespace-nowrap",
                panel === id ? "modal-tab-active" : "modal-tab-idle",
              )}
              onClick={() => setPanel(id)}
            >
              {label}
            </button>
          ))}
        </div>
      }
      allowFullscreen
      allowFontScale
      resizable
      maxWidthClass="max-w-4xl"
    >
      {identifiablePeers.length > 0 && (panel === "conversion" || panel === "regression") && (
        <div className="mb-3 space-y-1">
          <h3 className="text-sm font-semibold">인접·동일권 건물 추가</h3>
          <p className="text-[10px] text-slate-400">
            같은 목록에서 건물을 더하면 전환율 풀·통합 회귀에 함께 들어갑니다.
          </p>
          <div className="max-h-28 overflow-y-auto border border-slate-200 dark:border-slate-700 rounded">
            {identifiablePeers.map((p) => (
              <label
                key={p.building_key}
                className="flex items-center gap-2 px-2 py-1 text-[11px] border-b border-slate-100 dark:border-slate-800"
              >
                <input
                  type="checkbox"
                  checked={extraKeys.includes(p.building_key)}
                  onChange={() => togglePeer(p.building_key)}
                />
                <span className="truncate flex-1">{p.display_name}</span>
                <span className="tabular-nums text-slate-500">{fmtR(buildingRb(p))}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {panel === "conversion" && (
        <div className="space-y-3">
          <div className="rounded-lg border border-indigo-200 dark:border-indigo-800 p-3 text-xs space-y-1">
            <h3 className="text-sm font-semibold inline-flex items-center gap-1">
              적용 전환율
              <StatsGlossaryHelp termId="rent_conversion_rate" size="xs" />
            </h3>
            <p className="text-slate-500">
              지역·주택유형·{windowYears}년 거래자료를 이용해 산출한 전환율
            </p>
            <p>
              이 건물 <span className="font-semibold">{fmtR(focusR)}</span>
              {focusR == null && (
                <span className="text-slate-400"> · 전세·반전세가 함께 있어야 식별</span>
              )}
            </p>
            <p>
              지역 건물 전환율 평균
              {appliedRate?.n_buildings ? ` · 표본 ${appliedRate.n_buildings}동` : ""}
              {` · ${windowYears}년 `}
              <span className="font-semibold">{fmtR(regionR)}</span>
              <span className="ml-1 text-slate-400">({regionLabel})</span>
              {appliedRate?.fallback && (
                <span className="ml-1 text-amber-600">읍면동 게이트 미달</span>
              )}
            </p>
            <p>
              선택 풀({poolRows.length}동) 평균 <span className="font-semibold">{fmtR(poolR)}</span>
            </p>
          </div>
          <p className="text-[10px] text-slate-400">단가 단위 만원/㎡ · 아래 3유형은 원값</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <Block title="전세" n={row.jeonse.n} lines={[{ label: "보증금/㎡", metric: row.jeonse }]} />
            <Block
              title="반전세"
              n={row.mixed.n}
              lines={[
                { label: "보증금/㎡", metric: row.mixed.deposit },
                { label: "월세/㎡", metric: row.mixed.monthly },
              ]}
            />
            <Block title="월세" n={row.monthly.n} lines={[{ label: "월세/㎡", metric: row.monthly }]} />
          </div>
        </div>
      )}

      {panel === "rolling" && (
        <div>
          <h3 className="text-sm font-semibold mb-1">롤링 추세 (P50)</h3>
          {rollingQ.isLoading && <p className="text-xs text-slate-400">불러오는 중…</p>}
          {rollingQ.data && rollingQ.data.length === 0 && (
            <p className="text-xs text-slate-400">롤링 마트가 없습니다.</p>
          )}
          {rollingQ.data && rollingQ.data.length > 0 && (
            <div className="modal-table-wrap overflow-x-auto">
              <table className="w-full text-xs border-collapse modal-inner-table">
                <thead>
                  <tr>
                    <th className="border px-2 py-1">구간</th>
                    <th className="border px-2 py-1">전세 P50</th>
                    <th className="border px-2 py-1">반전세 보/월</th>
                    <th className="border px-2 py-1">월세 P50</th>
                  </tr>
                </thead>
                <tbody>
                  {rollingQ.data.map((p: RentRollingPoint) => (
                    <tr key={p.bucket_index}>
                      <td className="border px-2 py-1 text-[10px]">{p.label}</td>
                      <td className="border px-2 py-1 tabular-nums">
                        {p.jeonse.n ? `${fmtUnit(p.jeonse.median)} (${p.jeonse.n})` : "—"}
                      </td>
                      <td className="border px-2 py-1 tabular-nums">
                        {p.mixed.n
                          ? `보 ${fmtUnit(p.mixed.deposit.median)} · 월 ${fmtUnit(p.mixed.monthly.median)} (${p.mixed.n})`
                          : "—"}
                      </td>
                      <td className="border px-2 py-1 tabular-nums">
                        {p.monthly.n ? `${fmtUnit(p.monthly.median)} (${p.monthly.n})` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {panel === "transactions" && (
        <div className="space-y-2">
          {txQ.isLoading && <p className="text-xs text-slate-400">불러오는 중…</p>}
          {txQ.isError && <p className="text-xs text-red-600">거래 목록을 불러오지 못했습니다.</p>}
          {txQ.data && (
            <>
              <p className="text-[11px] text-slate-500">
                원장 {txQ.data.total.toLocaleString("ko-KR")}건 · 보증금·월세 단위 만원
                {row.asset_type === "detached" ? (
                  <> · 단독은 단지명이 없어 읍·면·동+지번(가림) 묶음</>
                ) : null}
              </p>
              <TransactionTable items={txQ.data.items} />
              {txQ.data.total > 50 && (
                <div className="flex items-center gap-2 text-xs">
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={txPage <= 1}
                    onClick={() => setTxPage((p) => Math.max(1, p - 1))}
                  >
                    이전
                  </button>
                  <span>
                    {txPage} / {Math.ceil(txQ.data.total / 50)}
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={txPage * 50 >= txQ.data.total}
                    onClick={() => setTxPage((p) => p + 1)}
                  >
                    다음
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {panel === "regression" && (
        <RentRegressionPanel
          buildingKey={row.building_key}
          extraKeys={extraKeys}
          assetType={String(row.asset_type)}
        />
      )}
    </DraggableModalShell>
  );
}
