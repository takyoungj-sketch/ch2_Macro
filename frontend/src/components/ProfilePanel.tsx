import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRegionalProfile, fetchRegions } from "../api/client";
import { REGIONS_CATALOG_QUERY_KEY } from "../constants/regionsCatalog";
import { useAppStore } from "../store";
import type { RegionalProfileResponse } from "../types";
import { parseApiError } from "../utils/apiError";
import {
  PROFILE_REGION_LEVEL_LABEL,
  resolveProfileRegionLabel,
} from "../utils/regionDisplay";
import { resolveProfileRegionFromTier } from "../utils/upperTierStats";
import ProfileBrowserPanel from "./profile/ProfileBrowserPanel";
import ProfileInsightSidebar from "./profile/ProfileInsightSidebar";
import ProfileMetaBar from "./profile/ProfileMetaBar";
import ProfileSummaryPanel from "./profile/ProfileSummaryPanel";

type ProfileTab = "summary" | "browser";

export default function ProfilePanel() {
  const tierSelection = useAppStore((s) => s.tierSelection);
  const statsDisplayKick = useAppStore((s) => s.statsDisplayKick);
  const freeStatsWindowYears = useAppStore((s) => s.freeStatsWindowYears);
  const profileTarget = useMemo(() => resolveProfileRegionFromTier(tierSelection), [tierSelection]);

  const { data: regions = [] } = useQuery({
    queryKey: REGIONS_CATALOG_QUERY_KEY,
    queryFn: () => fetchRegions(),
    staleTime: 60 * 60 * 1000,
  });

  const regionLabel = useMemo(() => {
    if (!profileTarget) return null;
    return resolveProfileRegionLabel(regions, profileTarget);
  }, [regions, profileTarget]);

  const [tab, setTab] = useState<ProfileTab>("summary");
  const [data, setData] = useState<RegionalProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [committed, setCommitted] = useState(false);

  useEffect(() => {
    if (!profileTarget) {
      setData(null);
      setError(null);
      setCommitted(false);
      return;
    }
    if (statsDisplayKick <= 0) {
      setData(null);
      setError(null);
      setCommitted(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCommitted(true);
    fetchRegionalProfile({
      region_level: profileTarget.level,
      region_code: profileTarget.code,
      window_years: freeStatsWindowYears,
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
  }, [profileTarget?.level, profileTarget?.code, statsDisplayKick, freeStatsWindowYears]);

  if (!profileTarget) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6 text-sm text-slate-600 dark:text-slate-300 max-w-3xl">
        <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-2">지역 프로필</h2>
        <p>
          시·도, 시군구, 읍면동, 또는 <strong>법정동·리 1곳</strong>을 선택한 뒤 좌측{" "}
          <strong>프로필 조회</strong>를 누르세요.
        </p>
        <p className="mt-2 text-xs text-slate-500">
          법정동·리만 고른 경우 같은 읍·면·동 프로필로 조회합니다
        </p>
      </div>
    );
  }

  if (!committed && !loading) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6 text-sm text-slate-600 dark:text-slate-300 max-w-3xl">
        <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-2">지역 프로필</h2>
        <p>
          <strong>{regionLabel ?? profileTarget.level}</strong>
          {regionLabel ? (
            <span className="ml-2 text-xs text-slate-500 font-mono">{profileTarget.code}</span>
          ) : (
            <>
              {" "}
              · <code className="text-xs">{profileTarget.code}</code>
            </>
          )}
          {profileTarget.escalatedFromBeop ? (
            <span className="ml-2 text-xs text-violet-600">(법정동 → 읍면동 프로필)</span>
          ) : null}
        </p>
        <p className="mt-2">
          좌측 하단 <strong>프로필 조회</strong> 버튼을 눌러 feature를 불러오세요.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">지역 프로필</h2>
          {regionLabel ? (
            <p className="text-lg font-bold text-violet-800 dark:text-violet-200 mt-1 leading-snug">
              {regionLabel}
            </p>
          ) : null}
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {profileTarget
              ? `${PROFILE_REGION_LEVEL_LABEL[profileTarget.level]} · ${profileTarget.code}`
              : "Regional Profile Browser · 충북 파일럿"}
            {profileTarget?.escalatedFromBeop ? " · 법정동 → 읍면동" : ""}
          </p>
        </div>
        <div className="flex gap-1 bg-slate-100 dark:bg-slate-700 rounded-lg p-1">
          <button
            type="button"
            onClick={() => setTab("summary")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
              tab === "summary"
                ? "bg-white dark:bg-slate-600 text-violet-700 dark:text-violet-300 shadow-sm"
                : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
            }`}
          >
            프로필 요약
          </button>
          <button
            type="button"
            onClick={() => setTab("browser")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
              tab === "browser"
                ? "bg-white dark:bg-slate-600 text-violet-700 dark:text-violet-300 shadow-sm"
                : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
            }`}
          >
            Feature Browser
          </button>
        </div>
      </div>

      {loading && <p className="text-sm text-slate-500">불러오는 중…</p>}
      {error && (
        <p className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {data && (
        <>
          <ProfileMetaBar meta={data.meta} regionLabel={regionLabel} />
          {tab === "summary" ? (
            <div className="grid lg:grid-cols-[1fr_16rem] gap-6 items-start">
              <div className="min-w-0">
                <ProfileSummaryPanel features={data.features} />
              </div>
              <ProfileInsightSidebar
                features={data.features}
                eupmyeondongCode={
                  data.meta.region_level === "eupmyeondong"
                    ? data.meta.region_code
                    : profileTarget.level === "eupmyeondong"
                      ? profileTarget.code
                      : null
                }
                profileVersion={data.meta.profile_version}
                windowYears={data.meta.window_years}
              />
            </div>
          ) : (
            <ProfileBrowserPanel features={data.features} />
          )}
        </>
      )}
    </div>
  );
}
