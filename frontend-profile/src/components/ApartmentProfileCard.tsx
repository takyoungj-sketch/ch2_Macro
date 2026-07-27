import type { RegionLevel, RegionalProfileFeatures } from "../types";
import { formatInt, formatUnitPrice } from "../utils/format";
import {
  APARTMENT_PERCENTILE_MIN_COUNT,
  apartmentPercentiles,
  apartmentTradeCount,
} from "../utils/profileFeatures";

interface Props {
  regionLevel: RegionLevel;
  features: RegionalProfileFeatures;
}

export default function ApartmentProfileCard({ regionLevel, features }: Props) {
  const apt = apartmentPercentiles(features);
  const tradeCount = apartmentTradeCount(features);

  return (
    <div className="card p-5">
      <h2 className="text-lg font-semibold">아파트 ㎡당 단가 분포 (최근 3년)</h2>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        P25 · P50(중앙값) · P75 · 쌍둥이 도시 비교 지표 (D-029)
      </p>

      {apt ? (
        <div className="mt-4">
          <div className="text-sm text-slate-500 dark:text-slate-400">
            표본 {formatInt(apt.count)}건 · 단위: 만원/㎡
          </div>
          <div className="mt-3 grid grid-cols-3 gap-3">
            <PercentileBox label="P25 (하위 25%)" value={apt.p25} />
            <PercentileBox label="P50 (중앙값)" value={apt.median} highlight />
            <PercentileBox label="P75 (상위 25%)" value={apt.p75} />
          </div>
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-400">
          {regionLevel === "beopjungri" && tradeCount > 0 && tradeCount < APARTMENT_PERCENTILE_MIN_COUNT
            ? `최근 3년 아파트 거래 ${formatInt(tradeCount)}건 — 분위(P25/P50/P75) 산출에는 최소 ${APARTMENT_PERCENTILE_MIN_COUNT}건이 필요합니다.`
            : "최근 3년 아파트 거래 표본 없음"}
        </p>
      )}
    </div>
  );
}

function PercentileBox({
  label,
  value,
  highlight,
}: {
  label: string;
  value?: number;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-md px-3 py-3 text-center ${
        highlight ? "bg-emerald-50 ring-1 ring-emerald-200 dark:bg-emerald-950/30 dark:ring-emerald-800" : "bg-slate-50 dark:bg-slate-900/40"
      }`}
    >
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`mt-1 text-base font-semibold ${highlight ? "text-emerald-800 dark:text-emerald-200" : ""}`}>
        {value != null ? formatUnitPrice(value) : "-"}
      </div>
    </div>
  );
}
