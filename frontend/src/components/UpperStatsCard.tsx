import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchUpperStats } from "../api/client";
import { useAppStore } from "../store";
import type { FreeStatsWindowYears, RegionLevel } from "../types";
import { normalizeFreeStatsWindowYears } from "../types";

/**
 * 상위 행정구역(시도·시군구·읍면동) 사전집계 단건 조회 위젯.
 * 설계: docs/UPPER_STATS_DESIGN.md / DECISIONS D-009.
 *
 * 최소 연결: level + code 직접 입력 → `/api/paid/upper-stats/{level}/{code}`.
 * 추후 RegionSelector 와 자동 연동 예정.
 */
const LEVELS: { value: RegionLevel; label: string; digits: number }[] = [
  { value: "sido", label: "시도 (2자리)", digits: 2 },
  { value: "sigungu", label: "시군구 (5자리)", digits: 5 },
  { value: "eupmyeondong", label: "읍·면·동 (8자리)", digits: 8 },
];

function fmt(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "-";
  return Number(v).toLocaleString(undefined, {
    maximumFractionDigits: digits,
  });
}

export default function UpperStatsCard() {
  const freeStatsWindowYears = useAppStore((s) =>
    normalizeFreeStatsWindowYears(s.freeStatsWindowYears)
  );
  const [level, setLevel] = useState<RegionLevel>("sigungu");
  const [code, setCode] = useState("");
  const [enabled, setEnabled] = useState(false);

  const digits = LEVELS.find((l) => l.value === level)?.digits ?? 5;
  const codeOk = /^\d+$/.test(code) && code.length === digits;

  const { data, isFetching, isError, error } = useQuery({
    queryKey: ["upperStats", level, code.trim(), freeStatsWindowYears],
    queryFn: () =>
      fetchUpperStats(level, code.trim(), {
        window_years: freeStatsWindowYears as FreeStatsWindowYears,
      }),
    enabled: enabled && codeOk,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  return (
    <div className="bg-white rounded-xl shadow-sm p-5 max-w-xl mx-auto space-y-3 text-xs">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-800 text-sm">
          상위 행정구역 사전집계 (시범)
        </h3>
        <span className="text-[10px] text-slate-400">
          window={freeStatsWindowYears}년 · land_upper_stats_v2
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <select
          className="col-span-1 border border-slate-200 rounded-md px-2 py-1.5 text-xs"
          value={level}
          onChange={(e) => {
            setLevel(e.target.value as RegionLevel);
            setEnabled(false);
          }}
        >
          {LEVELS.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
        <input
          className="col-span-1 border border-slate-200 rounded-md px-2 py-1.5 text-xs tabular-nums"
          placeholder={`예: ${"1".padEnd(digits, "0")}`}
          inputMode="numeric"
          maxLength={digits}
          value={code}
          onChange={(e) => {
            setCode(e.target.value.replace(/\D/g, "").slice(0, digits));
            setEnabled(false);
          }}
        />
        <button
          type="button"
          className="col-span-1 rounded-md bg-blue-600 text-white text-xs font-semibold disabled:bg-slate-300"
          disabled={!codeOk || isFetching}
          onClick={() => setEnabled(true)}
        >
          조회
        </button>
      </div>

      {!codeOk && code.length > 0 && (
        <p className="text-rose-600">코드는 {digits}자리 숫자여야 합니다.</p>
      )}
      {isFetching && <p className="text-slate-500">조회 중…</p>}
      {isError && (
        <p className="text-rose-600 whitespace-pre-wrap">
          오류: {String((error as Error)?.message ?? error)}
        </p>
      )}

      {data && (
        <div className="border-t border-slate-100 pt-3 space-y-1.5">
          <div className="flex items-baseline justify-between">
            <span className="text-sm font-semibold text-slate-800">
              {data.region_name || `(${data.region_level} ${data.region_code})`}
            </span>
            <span className="text-[10px] text-slate-400 tabular-nums">
              {data.period_start} ~ {data.period_end}
            </span>
          </div>
          <dl className="grid grid-cols-4 gap-y-1.5 gap-x-3 text-xs">
            <dt className="text-slate-500">거래수</dt>
            <dd className="col-span-3 tabular-nums">
              {fmt(data.stats.count, 0)}건{" "}
              {data.stats.is_reliable ? (
                <span className="text-emerald-600">(신뢰)</span>
              ) : (
                <span className="text-amber-600">(표본 작음)</span>
              )}
            </dd>
            <dt className="text-slate-500">평균(원/㎡)</dt>
            <dd className="col-span-3 tabular-nums">{fmt(data.stats.mean)}</dd>
            <dt className="text-slate-500">중앙값</dt>
            <dd className="col-span-3 tabular-nums">{fmt(data.stats.median)}</dd>
            <dt className="text-slate-500">P25 / P75</dt>
            <dd className="col-span-3 tabular-nums">
              {fmt(data.stats.p25)} / {fmt(data.stats.p75)}
            </dd>
            <dt className="text-slate-500">95% CI</dt>
            <dd className="col-span-3 tabular-nums">
              [{fmt(data.stats.ci_lower)} – {fmt(data.stats.ci_upper)}]
            </dd>
          </dl>
        </div>
      )}
    </div>
  );
}
