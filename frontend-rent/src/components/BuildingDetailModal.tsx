import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import type { LeaseMetric, RentBuildingRow, RentConversionRate, RentRollingPoint } from "../types";
import { fetchAllRentTransactions, fetchRentRolling } from "../api/client";
import type { StatsWindowYears } from "./StatsWindowToggle";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { assetTypeLabel } from "../types";
import DraggableModalShell from "./DraggableModalShell";
import RentRegressionPanel from "./RentRegressionPanel";
import RentTransactionTable from "./RentTransactionTable";

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

const RB_IDENT_MIN = 1;
const RB_IDENT_MAX = 15;

function fmtR(v: number | null | undefined) {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v.toFixed(2)}%`;
}

function rbInIdentBand(r: number): boolean {
  return r >= RB_IDENT_MIN && r <= RB_IDENT_MAX;
}

/** 창 안 전세·반전세 P50으로 건물 r_b. 1–15% 클립은 지역 평균 식별용이며 화면에서는 숨기지 않음. */
function buildingRb(row: RentBuildingRow): number | null {
  const j = row.jeonse.median;
  const d = row.mixed.deposit.median;
  const m = row.mixed.monthly.median;
  if (j == null || d == null || m == null || j <= d || m <= 0) return null;
  if (row.jeonse.n < 3 || row.mixed.n < 3) return null;
  const r = ((12 * m) / (j - d)) * 100;
  if (!Number.isFinite(r) || r <= 0) return null;
  return r;
}

function poolMean(rows: RentBuildingRow[]): number | null {
  const rs = rows.map(buildingRb).filter((r): r is number => r != null);
  if (!rs.length) return null;
  return rs.reduce((a, b) => a + b, 0) / rs.length;
}

function fmtStat(v: number | null | undefined) {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toLocaleString("ko-KR", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  });
}

function MetricLine({ label, metric }: { label: string; metric: LeaseMetric }) {
  const hasCi = metric.ci_lower != null && metric.ci_upper != null;
  return (
    <div className="space-y-0.5">
      <p className="text-[11px] font-medium text-slate-600 dark:text-slate-300">{label}</p>
      <p className="text-sm tabular-nums">
        <span className="text-[10px] font-normal text-slate-400 mr-1">중앙값</span>
        {fmtStat(metric.median)}
      </p>
      <p className="text-[11px] tabular-nums text-slate-600 dark:text-slate-300">
        <span className="text-[10px] font-normal text-slate-400 mr-1">평균</span>
        {fmtStat(metric.mean)}
      </p>
      <p className="text-[10px] text-slate-400 tabular-nums">
        95% 신뢰구간{" "}
        {hasCi ? `${fmtStat(metric.ci_lower)} ~ ${fmtStat(metric.ci_upper)}` : "없음"}
      </p>
    </div>
  );
}

function LeaseKindCard({
  title,
  n,
  children,
}: {
  title: string;
  n: number;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-2.5 space-y-2">
      <p className="text-xs font-semibold">
        {title}{" "}
        <span className="font-normal text-slate-400">{n.toLocaleString("ko-KR")}건</span>
      </p>
      {children}
    </div>
  );
}

function RbDerivation({ row, r }: { row: RentBuildingRow; r: number | null }) {
  const j = row.jeonse.median;
  const d = row.mixed.deposit.median;
  const m = row.mixed.monthly.median;
  if (row.jeonse.n < 3 || row.mixed.n < 3) {
    return (
      <p className="text-[11px] text-slate-500">
        전세 {row.jeonse.n.toLocaleString("ko-KR")}건 · 반전세{" "}
        {row.mixed.n.toLocaleString("ko-KR")}건. 각각 3건 이상일 때 이 건물 전환율을 계산합니다.
      </p>
    );
  }
  if (j == null || d == null || m == null || m <= 0) {
    return (
      <p className="text-[11px] text-slate-500">전세·반전세 중앙값이 없어 계산하지 못했습니다.</p>
    );
  }
  if (j <= d) {
    return (
      <p className="text-[11px] text-slate-500">
        전세 보증금 중앙값({fmtStat(j)})이 반전세 보증금({fmtStat(d)})보다 커야 합니다.
      </p>
    );
  }
  return (
    <div className="text-[11px] leading-relaxed space-y-1">
      <p className="text-slate-500">
        위 전세·반전세 중앙값(만원/㎡)을 넣었습니다. 순수 월세는 쓰지 않습니다.
      </p>
      <p className="tabular-nums">
        r = 12 × 월세 / (전세 보증금 − 반전세 보증금) × 100
      </p>
      <p className="tabular-nums">
        = 12 × {fmtStat(m)} / ({fmtStat(j)} − {fmtStat(d)}) × 100
      </p>
      <p className="tabular-nums font-semibold">= {fmtR(r)}</p>
    </div>
  );
}

function PeerPicker({
  peers,
  extraKeys,
  onToggle,
}: {
  peers: RentBuildingRow[];
  extraKeys: string[];
  onToggle: (key: string) => void;
}) {
  return (
    <div className="max-h-28 overflow-y-auto border border-slate-200 dark:border-slate-700 rounded">
      {peers.map((p) => {
        const r = buildingRb(p);
        return (
          <label
            key={p.building_key}
            className="flex items-center gap-2 px-2 py-1 text-[11px] border-b border-slate-100 dark:border-slate-800 last:border-b-0"
          >
            <input
              type="checkbox"
              checked={extraKeys.includes(p.building_key)}
              onChange={() => onToggle(p.building_key)}
            />
            <span className="truncate flex-1">{p.display_name}</span>
            <span className="tabular-nums text-slate-500 shrink-0">
              {fmtR(r)}
              {r != null && !rbInIdentBand(r) ? (
                <span className="ml-1 text-amber-600">구간밖</span>
              ) : null}
            </span>
          </label>
        );
      })}
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
    queryKey: ["rent-tx-all", row.building_key, row.asset_type],
    queryFn: () =>
      fetchAllRentTransactions({
        buildingKey: row.building_key,
        assetType: row.asset_type,
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
      {identifiablePeers.length > 0 && panel === "regression" && (
        <div className="mb-3 space-y-1">
          <h3 className="text-sm font-semibold">인접·동일권 건물 추가</h3>
          <p className="text-[10px] text-slate-400">
            같은 목록에서 건물을 더하면 통합 회귀에 함께 들어갑니다.
          </p>
          <PeerPicker peers={identifiablePeers} extraKeys={extraKeys} onToggle={togglePeer} />
        </div>
      )}

      {panel === "conversion" && (
        <div className="space-y-3">
          <section className="space-y-2">
            <div>
              <h3 className="text-sm font-semibold">이 건물 거래</h3>
              <p className="text-[10px] text-slate-400">
                {windowYears}년 창 · 원값 · 단위 만원/㎡ · 전환율 산식은 중앙값, 평균은 참고
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <LeaseKindCard title="전세" n={row.jeonse.n}>
                <MetricLine label="보증금(만원/㎡)" metric={row.jeonse} />
              </LeaseKindCard>
              <LeaseKindCard title="반전세" n={row.mixed.n}>
                <MetricLine label="보증금(만원/㎡)" metric={row.mixed.deposit} />
                <MetricLine label="월세(만원/㎡)" metric={row.mixed.monthly} />
              </LeaseKindCard>
              <LeaseKindCard title="월세" n={row.monthly.n}>
                <MetricLine label="월세(만원/㎡)" metric={row.monthly} />
              </LeaseKindCard>
            </div>
          </section>

          <section className="rounded-lg border border-indigo-200 dark:border-indigo-800 p-3 text-xs space-y-2">
            <h3 className="text-sm font-semibold inline-flex items-center gap-1">
              적용 전환율
              <StatsGlossaryHelp termId="rent_conversion_rate" size="xs" />
            </h3>
            <div>
              <p>
                이 건물 <span className="font-semibold tabular-nums">{fmtR(focusR)}</span>
                {focusR != null && !rbInIdentBand(focusR) && (
                  <span className="text-amber-700 dark:text-amber-300">
                    {" "}
                    · 식별 구간({RB_IDENT_MIN}–{RB_IDENT_MAX}%) 밖 · 지역 평균에는 넣지 않음
                  </span>
                )}
              </p>
              <RbDerivation row={row} r={focusR} />
            </div>
            <div className="border-t border-indigo-100 dark:border-indigo-900 pt-2 space-y-0.5">
              <p className="text-slate-500">
                목록 환산에는 지역·주택유형·{windowYears}년 건물 전환율 평균을 씁니다.
              </p>
              <p>
                지역 평균
                {appliedRate?.n_buildings ? ` · 표본 ${appliedRate.n_buildings}동` : ""}
                {` · ${windowYears}년 `}
                <span className="font-semibold tabular-nums">{fmtR(regionR)}</span>
                <span className="ml-1 text-slate-400">({regionLabel})</span>
                {appliedRate?.fallback && (
                  <span className="ml-1 text-amber-600">읍면동 게이트 미달</span>
                )}
              </p>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 dark:border-slate-700 p-3 space-y-2">
            <h3 className="text-sm font-semibold">인접·동일권 건물 추가</h3>
            <p className="text-[10px] text-slate-400">
              같은 목록에서 건물을 고르면 이 건물과 함께 단순평균합니다. 회귀 탭에도 같이 들어갑니다.
            </p>
            <p className="text-xs">
              선택 풀({poolRows.length}동) 평균{" "}
              <span className="font-semibold tabular-nums">{fmtR(poolR)}</span>
            </p>
            {identifiablePeers.length > 0 ? (
              <PeerPicker peers={identifiablePeers} extraKeys={extraKeys} onToggle={togglePeer} />
            ) : (
              <p className="text-[11px] text-slate-400">
                같은 목록에 전환율을 계산할 수 있는 인접 건물이 없습니다.
              </p>
            )}
          </section>
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
        <div className="space-y-2 flex flex-col min-h-0">
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
              <RentTransactionTable items={txQ.data.items} truncated={txQ.data.truncated} />
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
