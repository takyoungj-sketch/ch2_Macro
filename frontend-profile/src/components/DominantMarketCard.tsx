import type { RegionalProfileFeatures, YearlyMix, YearlyMixType } from "../types";
import { DOMINANT_TYPE_APP, DOMINANT_TYPE_LABEL, deepLinkTo } from "../utils/deepLinks";
import { formatAmountManwon, formatInt, formatPercent, formatUnitPrice } from "../utils/format";

interface Props {
  regionLevel: string;
  regionCode: string;
  regionShortName: string;
  yearlyMix: YearlyMix;
  features: RegionalProfileFeatures;
}

const PRICE_PREFIXES: Record<YearlyMixType, { prefix: string; label: string }[]> = {
  토지: [],
  상가: [
    { prefix: "commercial", label: "상업업무" },
    { prefix: "collective_shop", label: "집합상가" },
  ],
  공장: [
    { prefix: "factory", label: "공장창고" },
    { prefix: "collective_factory", label: "집합공장" },
  ],
  단독다가구: [{ prefix: "detached", label: "단독다가구" }],
  아파트: [{ prefix: "apartment", label: "아파트" }],
  오피스텔: [{ prefix: "officetel", label: "오피스텔" }],
  연립다세대: [{ prefix: "rowhouse", label: "연립다세대" }],
  분양권: [{ prefix: "presale", label: "분양권" }],
};

/** 대표 시장 요약 — 토지 Top3·아파트 분위는 LandProfileCard / ApartmentProfileCard. */
export default function DominantMarketCard({
  regionLevel,
  regionCode,
  regionShortName,
  yearlyMix,
  features,
}: Props) {
  const dominant = yearlyMix.dominant_type;
  const totals = yearlyMix.totals_by_type[dominant];
  const app = DOMINANT_TYPE_APP[dominant];
  const href = deepLinkTo(app, { regionLevel, regionCode });
  const showDominantPrice =
    dominant !== "토지" && dominant !== "아파트" && PRICE_PREFIXES[dominant].length > 0;

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          {regionShortName}의 대표 부동산 시장 — {dominant}
        </h2>
        <a href={href} className="btn btn-primary text-xs">
          {DOMINANT_TYPE_LABEL[dominant]} →
        </a>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricBox label="최근 3년 거래건수" value={`${formatInt(totals?.count)}건`} />
        <MetricBox label="최근 3년 거래액" value={formatAmountManwon(totals?.amount)} />
        <MetricBox label="거래건수 비중" value={formatPercent(yearlyMix.count_share_by_type[dominant])} />
        <MetricBox label="거래금액 비중" value={formatPercent(yearlyMix.amount_share_by_type[dominant])} />
      </div>

      {showDominantPrice && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {PRICE_PREFIXES[dominant].map(({ prefix, label }) => (
            <PriceDistribution key={prefix} label={label} features={features} prefix={prefix} />
          ))}
        </div>
      )}
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2 dark:bg-slate-900/40">
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-0.5 font-semibold">{value}</div>
    </div>
  );
}

function PriceDistribution({
  label,
  features,
  prefix,
}: {
  label: string;
  features: RegionalProfileFeatures;
  prefix: string;
}) {
  const count = features[`${prefix}_count`] as number | undefined;
  const median = features[`${prefix}_median`] as number | undefined;
  const p25 = features[`${prefix}_p25`] as number | undefined;
  const p75 = features[`${prefix}_p75`] as number | undefined;

  if (!count) {
    return (
      <div className="rounded-md border border-dashed border-slate-300 p-3 text-sm text-slate-400 dark:border-slate-600">
        {label}: 표본 부족(단가 통계 없음)
      </div>
    );
  }

  return (
    <div className="rounded-md bg-slate-50 p-3 dark:bg-slate-900/40">
      <div className="text-sm font-medium">{label} 단가 분포 ({formatInt(count)}건)</div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-sm">
        <span>25% {formatUnitPrice(p25)}</span>
        <span className="font-semibold">중앙값 {formatUnitPrice(median)}</span>
        <span>75% {formatUnitPrice(p75)}</span>
      </div>
    </div>
  );
}
