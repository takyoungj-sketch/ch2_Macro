import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { JimokGroupTop3Item, LandTopItem, RegionalProfileFeatures } from "../types";
import { deepLinkTo } from "../utils/deepLinks";
import { formatInt, formatPercent, formatUnitPrice } from "../utils/format";
import { jimokGroupTop3Items, landTopItems } from "../utils/profileFeatures";

interface Props {
  features: RegionalProfileFeatures;
  regionLevel: string;
  regionCode: string;
}

export default function LandProfileCard({ features, regionLevel, regionCode }: Props) {
  const zoneJimokTops = landTopItems(features);
  const jimokOnlyTops = jimokGroupTop3Items(features);

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">토지 거래 구조 (최근 3년)</h2>
          <StatsGlossaryHelp termId="land_top3" size="sm" />
        </div>
        <a href={deepLinkTo("land", { regionLevel, regionCode })} className="btn btn-primary text-xs">
          토지 상세분석 →
        </a>
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        용도×지목군 거래건수 Top 3 · 쌍둥이 도시 비교 지표 (D-029)
      </p>

      {zoneJimokTops.length > 0 ? (
        <LandZoneJimokTop3 items={zoneJimokTops} />
      ) : jimokOnlyTops.length > 0 ? (
        <JimokTop3 items={jimokOnlyTops} legacy />
      ) : (
        <p className="mt-4 text-sm text-slate-400">최근 3년 토지 거래 통계 없음</p>
      )}
    </div>
  );
}

function LandZoneJimokTop3({ items }: { items: LandTopItem[] }) {
  return (
    <ol className="mt-4 space-y-2">
      {items.map((item, i) => (
        <li
          key={`${item.zone}-${item.jimok_code}-${i}`}
          className="flex flex-wrap items-center gap-2 rounded-md bg-slate-50 px-3 py-2 text-sm dark:bg-slate-900/40"
        >
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200">
            {i + 1}
          </span>
          <span className="font-medium">
            {item.zone} × {item.jimok}
          </span>
          <span className="text-slate-500 dark:text-slate-400">
            {formatInt(item.count)}건
            {item.mean_manwon_per_sqm != null ? ` · 평균 ${formatUnitPrice(item.mean_manwon_per_sqm)}` : ""}
          </span>
        </li>
      ))}
    </ol>
  );
}

function JimokTop3({ items, legacy }: { items: JimokGroupTop3Item[]; legacy?: boolean }) {
  return (
    <div className="mt-4">
      {legacy && (
        <p className="mb-2 text-xs text-amber-600 dark:text-amber-400">
          용도×지목군 Top3 미적재 — 지목군 합산 Top3 표시
        </p>
      )}
      <ol className="space-y-2">
        {items.map((item, i) => (
          <li
            key={item.group}
            className="flex items-center gap-2 rounded-md bg-slate-50 px-3 py-2 text-sm dark:bg-slate-900/40"
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200">
              {i + 1}
            </span>
            <span className="font-medium">{item.label}</span>
            <span className="text-slate-500 dark:text-slate-400">
              {formatInt(item.count)}건 ({formatPercent(item.share, 0)})
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
