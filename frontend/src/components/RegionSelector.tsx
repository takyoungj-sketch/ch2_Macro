import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRegions } from "../api/client";
import { useAppStore } from "../store";
import { resolveBeopjungriCodes } from "../utils/regionTier";
import {
  resolveBeopjungriFromFiveFields,
  type RegionFiveFields,
} from "../utils/resolveRegionFiveFields";

const FIELD_LABELS = [
  "① 시·도",
  "② 시·군",
  "③ 구 (없으면 비움)",
  "④ 읍·면·동",
  "⑤ 리·동 세부 (동만이면 비움)",
];

const FIELD_PLACEHOLDERS = [
  "예: 충청북도 또는 충북",
  "예: 청주시",
  "예: 흥덕구",
  "예: 가경동, 남이면",
  "예: 가좌리 (동 단위면 비움)",
];

export default function RegionSelector() {
  const {
    viewMode,
    tierSelection,
    regionSegments,
    setRegionSegment,
    clearTierSelection,
    applyBeopjungriCodes,
    kickPaidBasicStatsAnalysis,
  } = useAppStore();

  const [localError, setLocalError] = useState<string | null>(null);

  const { data: regions = [], isLoading } = useQuery({
    queryKey: ["regions"],
    queryFn: () => fetchRegions(),
  });

  const textLookup = useMemo(
    () => resolveBeopjungriFromFiveFields(regions, regionSegments as RegionFiveFields),
    [regions, regionSegments]
  );

  /** 현재 매칭(입력 즉시, 적용 버튼과 무관) */
  const previewCount = textLookup.codes.length;
  const resolvedCount = resolveBeopjungriCodes(regions, tierSelection).length;

  const syncSegment = (idx: 0 | 1 | 2 | 3 | 4, value: string) => {
    setLocalError(null);
    setRegionSegment(idx, value);
  };

  const commitFree = () => {
    setLocalError(null);
    const { codes, sampleLabel } = textLookup;

    const anyInput = regionSegments.some((x: string) => x.trim());
    if (!anyInput) {
      setLocalError("최소 한 칸 이상 입력한 뒤 조회해 주세요.");
      return;
    }

    if (codes.length === 0) {
      setLocalError("조건과 일치하는 법정동·리가 없습니다. 이름을 확인해 보세요.");
      return;
    }

    applyBeopjungriCodes(codes);
    if (codes.length === 1) {
      setLocalError(null);
    }
  };

  const commitPaid = () => {
    setLocalError(null);
    const { codes } = textLookup;

    const anyInput = regionSegments.some((x: string) => x.trim());
    if (!anyInput) {
      setLocalError("최소 한 칸 이상 입력한 뒤 분석해 주세요.");
      return;
    }

    if (codes.length === 0) {
      setLocalError("조건과 일치하는 법정동·리가 없습니다. 이름을 확인해 보세요.");
      return;
    }

    kickPaidBasicStatsAnalysis(codes);
  };

  return (
    <div className="bg-white rounded-xl shadow-sm p-3 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-sm font-bold text-slate-700">지역 입력</h2>
        <button
          type="button"
          onClick={() => {
            clearTierSelection();
            setLocalError(null);
          }}
          className="text-[10px] text-slate-500 underline underline-offset-2 hover:text-red-600 shrink-0"
        >
          초기화
        </button>
      </div>

      <fieldset className="space-y-1.5 border-0 m-0 p-0">
        <legend className="sr-only">법정 행정구역 단계별 이름 입력</legend>
        {FIELD_LABELS.map((label, idx) => {
          const key = `${idx}-${label}`;
          const i = idx as 0 | 1 | 2 | 3 | 4;
          return (
            <label
              key={key}
              htmlFor={`region-tier-${idx}`}
              className="block text-[11px] text-slate-600 leading-tight space-y-0.5"
            >
              <span className="block font-semibold text-slate-700">{label}</span>
              <input
                id={`region-tier-${idx}`}
                type="text"
                value={regionSegments[i]}
                placeholder={FIELD_PLACEHOLDERS[idx]}
                onChange={(e) => syncSegment(i, e.target.value)}
                autoComplete="off"
                spellCheck={false}
                className="w-full border border-slate-300 rounded-md px-2 py-1.5 text-[12px]"
              />
            </label>
          );
        })}
      </fieldset>

      {isLoading ? (
        <p className="text-[11px] text-slate-400">지역 코드 목록 불러오는 중…</p>
      ) : (
        <p className="text-[11px] text-slate-600 leading-snug">
          현재 입력으로{" "}
          <span className="font-semibold text-slate-800">{previewCount}</span>
          건 매칭
          {textLookup.sampleLabel && previewCount <= 120 && previewCount > 0 && (
            <span className="block mt-1 text-[10px] text-slate-400 truncate">
              예: {textLookup.sampleLabel}
            </span>
          )}
        </p>
      )}

      {localError ? (
        <p className="text-[11px] text-red-600 leading-snug" role="alert">
          {localError}
        </p>
      ) : null}

      {viewMode === "free" ? (
        <button
          type="button"
          onClick={commitFree}
          className="w-full py-2 rounded-lg bg-slate-800 text-white text-sm font-semibold
                     hover:bg-slate-900 disabled:opacity-40 transition-colors"
          disabled={isLoading}
        >
          무료 통계 조회
        </button>
      ) : (
        <button
          type="button"
          onClick={commitPaid}
          className="w-full py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold
                     hover:bg-blue-700 disabled:opacity-40 transition-colors"
          disabled={isLoading}
        >
          기본 통계 보기
        </button>
      )}

      <p className="text-[10px] text-slate-500 leading-snug border-t border-slate-100 pt-2">
        시·구 이름은 포함 일치입니다(띄어쓰기 무시). ④·⑤는{" "}
        <strong className="text-slate-700">쉼표로 여러 개</strong>(예: 복대동, 가경동)를 넣으면{" "}
        <strong className="text-slate-700">합산(OR)</strong>됩니다.
        다섯 칸 빈 상태는 읍면동 레벨 이하에서 모두 허용됩니다.
        서원구 <strong className="text-slate-700">남이면 가좌리</strong>는 ④ 남이면, ⑤ 가좌리로
        적습니다. 반영된 법정단위{" "}
        <span className="font-semibold text-slate-800">{resolvedCount}</span>곳 ·{" "}
        {viewMode === "free" ? (
          <span className="text-blue-700 font-medium">1곳일 때만 통계를 불러옵니다.</span>
        ) : (
          <span className="text-blue-700 font-medium">
            복수 법정단위 선택 시 「기본 통계 보기」로 합산합니다. 필요하면 필터 표에서 「필터 분석
            실행」을 사용하세요.
          </span>
        )}
      </p>
    </div>
  );
}
