import { useQuery } from "@tanstack/react-query";
import { fetchProfileTwinNeighbors } from "../../api/client";
import { DEFAULT_PROFILE_VERSION } from "../../constants/profileVersion";
import { buildProfileInsights } from "../../utils/profileFeatureDisplay";

function InsightCard({
  title,
  value,
  sub,
}: {
  title: string;
  value: string;
  sub?: string | null;
}) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/80 p-3">
      <p className="text-[11px] text-slate-500 dark:text-slate-400">{title}</p>
      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mt-1">{value}</p>
      {sub ? <p className="text-[11px] text-slate-500 mt-1">{sub}</p> : null}
    </div>
  );
}

export default function ProfileInsightSidebar({
  features,
  eupmyeondongCode,
  profileVersion,
  windowYears,
}: {
  features: Record<string, number>;
  eupmyeondongCode?: string | null;
  profileVersion?: string;
  windowYears: number;
}) {
  const insights = buildProfileInsights(features);

  const twinCode =
    eupmyeondongCode && eupmyeondongCode.length >= 8
      ? eupmyeondongCode.trim().slice(0, 8)
      : null;

  const { data: twins, isError } = useQuery({
    queryKey: ["profile-twins", twinCode, windowYears, profileVersion],
    queryFn: () =>
      fetchProfileTwinNeighbors({
        eupmyeondong_code: twinCode!,
        profile_version: profileVersion,
        window_years: windowYears,
        top_k: 3,
      }),
    enabled: Boolean(twinCode),
    staleTime: 30 * 60 * 1000,
  });

  return (
    <aside className="space-y-3 lg:sticky lg:top-4">
      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">요약</h3>
      <InsightCard title="지역 유형" value={insights.regionCharacter} />
      {insights.landMarketRank ? (
        <InsightCard title="토지 시장 (단가 수준)" value={insights.landMarketRank} />
      ) : null}
      {insights.apartmentActivity ? (
        <InsightCard title="아파트 거래 활성도" value={insights.apartmentActivity} />
      ) : null}
      {insights.topComposition ? (
        <InsightCard title="토지 거래 구성" value={insights.topComposition} />
      ) : null}
      {twins && twins.neighbors.length > 0 ? (
        <div className="rounded-lg border border-violet-200 dark:border-violet-900/50 bg-violet-50/60 dark:bg-violet-950/20 p-3">
          <p className="text-[11px] font-semibold text-violet-800 dark:text-violet-300 mb-2">
            쌍둥이 지역 (Profile)
          </p>
          <ol className="space-y-2">
            {twins.neighbors.map((n) => (
              <li key={n.rank} className="text-[11px] text-slate-800 dark:text-slate-200">
                <span className="font-medium text-violet-900 dark:text-violet-200">
                  [{n.rank}] {n.twin_eupmyeondong_name}
                </span>
                <span className="block text-slate-500">
                  {n.twin_sido_name} {n.twin_sigungu_name}
                </span>
              </li>
            ))}
          </ol>
        </div>
      ) : twinCode && !isError ? (
        <p className="text-[10px] text-slate-400">
          쌍둥이 지역 데이터가 없습니다 ({profileVersion ?? DEFAULT_PROFILE_VERSION} · {windowYears}
          년).
        </p>
      ) : null}
      {insights.cautionLines.length > 0 ? (
        <div className="rounded-lg border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/30 p-3">
          <p className="text-[11px] font-semibold text-amber-800 dark:text-amber-300 mb-1">주의</p>
          <ul className="text-[11px] text-amber-900 dark:text-amber-200 space-y-1 list-disc list-inside">
            {insights.cautionLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </aside>
  );
}
