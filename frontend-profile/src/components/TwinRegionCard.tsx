import type { ProfileTwinNeighborItem } from "../types";
import { reasonLabel } from "../utils/reasonCodes";

interface Props {
  neighbors: ProfileTwinNeighborItem[];
  isLoading: boolean;
  isSigungu: boolean;
}

function reasonCodesOf(item: ProfileTwinNeighborItem): string[] {
  const codes = item.detail_scores?.reason_codes;
  if (Array.isArray(codes)) return codes.filter((c): c is string => typeof c === "string");
  return [];
}

export default function TwinRegionCard({ neighbors, isLoading, isSigungu }: Props) {
  return (
    <div className="card p-5">
      <h2 className="text-lg font-semibold">쌍둥이 지역 — {isSigungu ? "시군구" : "읍면동"}</h2>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        지역 프로필(인구, 8대 유형 구성비, 지목군, 가격분포)을 입력값으로 산출한 유사 지역
      </p>

      {isLoading ? (
        <p className="mt-3 text-sm text-slate-400">불러오는 중...</p>
      ) : neighbors.length === 0 ? (
        <p className="mt-3 text-sm text-slate-400">쌍둥이 지역 데이터가 없습니다.</p>
      ) : (
        <ol className="mt-3 space-y-2">
          {neighbors.map((n) => (
            <li
              key={`${n.twin_eupmyeondong_code ?? n.twin_sigungu_code}-${n.rank}`}
              className="rounded-md bg-slate-50 px-3 py-2 dark:bg-slate-900/40"
            >
              <div className="flex items-center justify-between">
                <div className="font-medium">
                  <span className="mr-1.5 text-xs text-slate-400">#{n.rank}</span>
                  {n.twin_sido_name} {n.twin_sigungu_name}
                  {n.twin_eupmyeondong_name ? ` ${n.twin_eupmyeondong_name}` : ""}
                </div>
                <div className="text-sm font-semibold">{(n.similarity_score * 100).toFixed(1)}%</div>
              </div>
              {reasonCodesOf(n).length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {reasonCodesOf(n).map((code) => (
                    <span
                      key={code}
                      className="rounded-full bg-slate-200 px-2 py-0.5 text-[11px] text-slate-600 dark:bg-slate-700 dark:text-slate-300"
                    >
                      {reasonLabel(code)}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
