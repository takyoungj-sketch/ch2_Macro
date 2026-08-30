import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { YEARLY_MIX_TYPES, type NationalShareByType, type YearlyMix } from "../types";
import { formatPercent } from "../utils/format";

interface Props {
  yearlyMix: YearlyMix;
  nationalShare?: NationalShareByType | null;
}

function describeMarket(yearlyMix: YearlyMix): string {
  const dominant = yearlyMix.dominant_type;
  const countShare = yearlyMix.count_share_by_type[dominant] ?? 0;
  const amountShare = yearlyMix.amount_share_by_type[dominant] ?? 0;
  const sameLeader = countShare > 0 && amountShare > 0;
  return (
    `지역 시장 유형: ${dominant} 중심형 시장. ` +
    `최근 3년 거래건수의 ${formatPercent(countShare, 0)}가 ${dominant} 거래이며, ` +
    (sameLeader
      ? `거래금액 기준으로도 ${dominant}이 가장 큰 비중(${formatPercent(amountShare, 0)})을 차지합니다.`
      : `거래금액 기준 비중은 ${formatPercent(amountShare, 0)}입니다.`)
  );
}

function rankedShares(shares: Record<string, number>): [string, number][] {
  return YEARLY_MIX_TYPES.map((t) => [t, shares[t] ?? 0] as [string, number])
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);
}

function specializationLabel(local: number, national: number | undefined): string | null {
  if (national == null || Number.isNaN(national)) return null;
  const pp = (local - national) * 100;
  if (Math.abs(pp) < 0.5) return "평균 수준";
  const n = Math.round(pp);
  const sign = n > 0 ? "+" : "";
  return `전국 평균 대비 ${sign}${n}%p`;
}

export default function MarketComposition({ yearlyMix, nationalShare }: Props) {
  const byCount = rankedShares(yearlyMix.count_share_by_type);
  const byAmount = rankedShares(yearlyMix.amount_share_by_type);

  return (
    <div className="card p-5">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">지역 시장 구성 (최근 3년 합산)</h2>
        <StatsGlossaryHelp termId="yearly_mix" size="sm" />
        {nationalShare ? <StatsGlossaryHelp termId="market_specialization" size="sm" /> : null}
      </div>
      <p className="mt-2 rounded-md bg-slate-50 px-3 py-2 text-sm dark:bg-slate-900/40">
        {describeMarket(yearlyMix)}
      </p>

      <div className="mt-4 grid gap-5 sm:grid-cols-2">
        <ShareBars title="거래건수 기준 비중" items={byCount} national={nationalShare?.count} />
        <ShareBars title="거래금액 기준 비중" items={byAmount} national={nationalShare?.amount} />
      </div>
    </div>
  );
}

function ShareBars({
  title,
  items,
  national,
}: {
  title: string;
  items: [string, number][];
  national?: Record<string, number>;
}) {
  return (
    <div>
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">{title}</div>
      <div className="mt-2 space-y-1.5">
        {items.map(([type, share]) => {
          const badge = specializationLabel(share, national?.[type]);
          return (
            <div key={type} className="flex items-center gap-2 text-sm">
              <div className="w-20 shrink-0 truncate">{type}</div>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                <div
                  className="h-full rounded-full bg-slate-500 dark:bg-slate-400"
                  style={{ width: `${Math.max(2, share * 100)}%` }}
                />
              </div>
              <div className="w-12 shrink-0 text-right text-xs text-slate-500 dark:text-slate-400">
                {formatPercent(share, 0)}
              </div>
              {badge ? (
                <div
                  className="w-36 shrink-0 truncate text-right text-[11px] text-slate-500 dark:text-slate-400"
                  title={badge}
                >
                  {badge}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
