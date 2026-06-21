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

function formatTwinBlockScores(detail: Record<string, unknown>): string | null {
  const sLand = detail.s_land;
  const sColl = detail.s_collective;
  const sProf = detail.s_profile;
  if (
    typeof sLand !== "number" &&
    typeof sColl !== "number" &&
    typeof sProf !== "number"
  ) {
    return null;
  }
  const parts: string[] = [];
  if (typeof sLand === "number") parts.push(`토지 ${sLand.toFixed(2)}`);
  if (typeof sColl === "number") parts.push(`집합 ${sColl.toFixed(2)}`);
  if (typeof sProf === "number") parts.push(`Profile ${sProf.toFixed(2)}`);
  return parts.join(" · ");
}

const REASON_LABELS: Record<string, string> = {
  LAND_STRUCT_STRONG: "토지 거래구조 매우 유사",
  LAND_STRUCT_SIMILAR: "토지 거래구조 유사",
  LAND_PRICE_STRONG: "토지 단가 수준 매우 유사",
  LAND_PRICE_SIMILAR: "토지 단가 수준 유사",
  COLL_PATTERN_STRONG: "집합 거래구성 매우 유사",
  COLL_PATTERN_SIMILAR: "집합 거래구성 유사",
  COLL_PRICE_STRONG: "아파트 가격대 매우 유사",
  COLL_PRICE_SIMILAR: "아파트 가격대 유사",
  POP_STRONG: "인구 규모 유사",
  POP_SIMILAR: "인구 규모 비슷",
  DENSITY_STRONG: "인구 밀도 유사",
  DENSITY_SIMILAR: "인구 밀도 비슷",
};

function formatTwinReasons(detail: Record<string, unknown>): string | null {
  const raw = detail.reason_codes;
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const labels = raw
    .map((code) => (typeof code === "string" ? REASON_LABELS[code] : undefined))
    .filter((v): v is string => Boolean(v))
    .slice(0, 3);
  return labels.length > 0 ? labels.join(", ") : null;
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
            쌍둥이 지역
            {twins.algorithm_version === 6 ? " (하이브리드)" : twins.algorithm_version === 5 ? " (Profile)" : ""}
          </p>
          <ol className="space-y-2">
            {twins.neighbors.map((n) => {
              const blocks = formatTwinBlockScores(n.detail_scores);
              const reasons = formatTwinReasons(n.detail_scores);
              return (
                <li key={n.rank} className="text-[11px] text-slate-800 dark:text-slate-200">
                  <span className="font-medium text-violet-900 dark:text-violet-200">
                    [{n.rank}] {n.twin_eupmyeondong_name}
                  </span>
                  <span className="block text-slate-500">
                    {n.twin_sido_name} {n.twin_sigungu_name}
                  </span>
                  {reasons ? (
                    <span className="block text-[10px] text-slate-600 dark:text-slate-300 mt-0.5">
                      {reasons}
                    </span>
                  ) : null}
                  {blocks ? (
                    <span className="block text-[10px] text-violet-700/80 dark:text-violet-300/80 mt-0.5">
                      {blocks}
                    </span>
                  ) : null}
                </li>
              );
            })}
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
