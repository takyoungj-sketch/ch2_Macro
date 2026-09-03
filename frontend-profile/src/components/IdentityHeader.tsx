import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { RegionNameInfo, YearlyMix } from "../types";
import { cityFullLabel, cityShortLabel, formatRegionHierarchyLabel, isSejongPseudoSigunguCode, isSejongRegionRow } from "@ch2/region-picker";
import { formatAmountManwon, formatInt, formatPercent } from "../utils/format";
import { sidoName } from "../utils/sido";

interface Props {
  regionLevel: string;
  regionCode: string;
  regionName: RegionNameInfo | null;
  population?: number;
  yearlyMix?: YearlyMix;
}

function fullAddressLabel(regionLevel: string, regionCode: string, name: RegionNameInfo | null): string {
  if (regionLevel === "sido") return sidoName(regionCode);
  if (regionLevel === "city") return cityFullLabel(name, regionCode);
  if (!name) return regionCode;
  if (regionLevel === "sigungu") {
    if (isSejongPseudoSigunguCode(regionCode)) return `${name.sido_name || "세종특별자치시"} 전체`;
    return `${name.sido_name} ${name.sigungu_name}`;
  }
  if (regionLevel === "beopjungri") {
    return formatRegionHierarchyLabel(name);
  }
  if (isSejongRegionRow(name)) return `${name.sido_name} ${name.sigungu_name}`;
  return `${name.sido_name} ${name.sigungu_name} ${name.eupmyeondong_name}`;
}

function shortLabel(regionLevel: string, regionCode: string, name: RegionNameInfo | null): string {
  if (regionLevel === "sido") return sidoName(regionCode);
  if (regionLevel === "city") return cityShortLabel(name, regionCode);
  if (!name) return regionCode;
  if (regionLevel === "sigungu") {
    if (isSejongPseudoSigunguCode(regionCode)) return `${name.sido_name || "세종특별자치시"} 전체`;
    return name.sigungu_name;
  }
  if (regionLevel === "beopjungri") return name.beopjungri_name;
  if (isSejongRegionRow(name)) return name.sigungu_name;
  return name.eupmyeondong_name;
}

export default function IdentityHeader({ regionLevel, regionCode, regionName, population, yearlyMix }: Props) {
  const title = shortLabel(regionLevel, regionCode, regionName);
  const address = fullAddressLabel(regionLevel, regionCode, regionName);
  const dominant = yearlyMix?.dominant_type;
  const dominantShare = dominant ? yearlyMix?.count_share_by_type?.[dominant] : undefined;

  return (
    <div className="card p-5">
      <div className="text-xs text-slate-500 dark:text-slate-400">{address}</div>
      <div className="mt-1 flex items-center gap-2">
        <h1 className="text-2xl font-bold">{title} 지역 프로필</h1>
        <StatsGlossaryHelp termId="regional_profile" size="sm" />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatBox label="인구" value={population ? `${formatInt(population)}명` : "-"} />
        <StatBox
          label="최근 3년 총 거래건수"
          value={yearlyMix ? `${formatInt(yearlyMix.total_count_3y)}건` : "-"}
        />
        <StatBox
          label="최근 3년 총 거래액"
          value={yearlyMix ? formatAmountManwon(yearlyMix.total_amount_3y) : "-"}
        />
        <StatBox
          label="대표 시장"
          value={dominant ? `${dominant}${dominantShare ? ` (${formatPercent(dominantShare, 0)})` : ""}` : "-"}
        />
      </div>
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2 dark:bg-slate-900/40">
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-0.5 text-lg font-semibold">{value}</div>
    </div>
  );
}
