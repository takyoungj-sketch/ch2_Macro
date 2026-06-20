import { useEffect, useMemo, useState } from "react";
import { fetchRegionalProfile } from "../api/client";
import { useAppStore } from "../store";
import type { RegionalProfileResponse } from "../types";
import { parseApiError } from "../utils/apiError";
import { resolveUpperSingleFromTier } from "../utils/upperTierStats";

const FEATURE_LABELS: Record<string, string> = {
  population: "인구(명)",
  population_density: "인구밀도",
  apartment_count: "아파트 거래수",
  apartment_mean: "아파트 평균단가",
  apartment_median: "아파트 중앙단가",
  land_residential_mean: "토지(주거) 평균단가",
  land_residential_median: "토지(주거) 중앙단가",
  land_commercial_mean: "토지(상업) 평균단가",
  land_industrial_mean: "토지(공업) 평균단가",
  ratio_residential_zone: "주거 zone 거래비중",
  ratio_commercial_zone: "상업 zone 거래비중",
  ratio_agri_zone: "농림·녹지 거래비중",
  ratio_land_danji: "대지 거래비중",
  ratio_land_rice: "전·답 거래비중",
  ratio_land_forest: "임야 거래비중",
};

function formatFeatureValue(key: string, value: number): string {
  if (key.startsWith("ratio_")) {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (key.includes("mean") || key.includes("median")) {
    return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 1 })} 만원/㎡`;
  }
  if (key === "population") {
    return `${Math.round(value).toLocaleString("ko-KR")}명`;
  }
  return value.toLocaleString("ko-KR");
}

export default function ProfilePanel() {
  const tierSelection = useAppStore((s) => s.tierSelection);
  const upperSingle = useMemo(() => resolveUpperSingleFromTier(tierSelection), [tierSelection]);

  const [data, setData] = useState<RegionalProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!upperSingle) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchRegionalProfile({
      region_level: upperSingle.level,
      region_code: upperSingle.code,
    })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(parseApiError(err).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [upperSingle?.level, upperSingle?.code]);

  if (!upperSingle) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6 text-sm text-slate-600 dark:text-slate-300">
        <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-2">지역 프로필</h2>
        <p>시·도, 시군구, 또는 읍면동을 <strong>하나만</strong> 선택하면 Profile feature를 조회할 수 있습니다.</p>
        <p className="mt-2 text-xs text-slate-500">
          충북 파일럿 · profile_version=v1.0-chungbuk · 법정동·리 복수 선택 시 미지원
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6 space-y-4 max-w-3xl">
      <div>
        <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">지역 프로필</h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Regional Profile (운영·검증용) · 충북 파일럿
        </p>
      </div>

      {loading && <p className="text-sm text-slate-500">불러오는 중…</p>}
      {error && (
        <p className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {data && (
        <>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-slate-300 border border-slate-100 dark:border-slate-700 rounded-lg p-3">
            <dt className="text-slate-500">버전</dt>
            <dd>{data.meta.profile_version}</dd>
            <dt className="text-slate-500">기준월</dt>
            <dd>{data.meta.as_of_month}</dd>
            <dt className="text-slate-500">창</dt>
            <dd>{data.meta.window_years}년</dd>
            <dt className="text-slate-500">검증</dt>
            <dd>{data.meta.validation_status}</dd>
            <dt className="text-slate-500">feature 수</dt>
            <dd>{data.meta.feature_count ?? Object.keys(data.features).length}</dd>
          </dl>

          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-600 text-left text-xs text-slate-500">
                  <th className="py-2 pr-3 font-medium">Feature</th>
                  <th className="py-2 pr-3 font-medium">값</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.features)
                  .sort(([a], [b]) => a.localeCompare(b, "ko-KR"))
                  .map(([key, raw]) => {
                    const num = typeof raw === "number" ? raw : Number(raw);
                    if (!Number.isFinite(num)) return null;
                    return (
                      <tr key={key} className="border-b border-slate-100 dark:border-slate-700/80">
                        <td className="py-1.5 pr-3 font-mono text-[11px] text-slate-700 dark:text-slate-200">
                          {FEATURE_LABELS[key] ? (
                            <>
                              {FEATURE_LABELS[key]}
                              <span className="block text-[10px] text-slate-400">{key}</span>
                            </>
                          ) : (
                            key
                          )}
                        </td>
                        <td className="py-1.5 pr-3 tabular-nums">{formatFeatureValue(key, num)}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
