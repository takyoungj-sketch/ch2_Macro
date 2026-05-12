import { create } from "zustand";
import { runPaidAnalysis as runPaidAnalysisApi } from "./api/client";
import { getDefaultPaidSelectedYears } from "./constants/paidFilters";
import type { PaidAnalysisRequest, PaidAnalysisResponse, ViewMode } from "./types";
import { parseApiError, type ParsedApiError } from "./utils/apiError";
import { buildPaidPayload } from "./utils/paidAnalysisPayload";
import type { RegionFiveFields } from "./utils/resolveRegionFiveFields";
import type { TierCodes } from "./utils/regionTier";
import { emptyTierCodes } from "./utils/regionTier";

const EMPTY_REGION_SEGMENTS: RegionFiveFields = ["", "", "", "", ""];

export type PaidResultView = "idle" | "basic" | "filtered";

export type PaidAnalysisStatus = "idle" | "loading" | "success" | "error";

interface AppState {
  viewMode: ViewMode;

  /** 키보드 입력 5단 */
  regionSegments: RegionFiveFields;

  tierSelection: TierCodes;
  paidRequest: PaidAnalysisRequest;
  /** 포함 여부 역: 목록에 있으면 API에서 해당 도로값 제외 */
  paidRoadExcluded: string[];
  paidAreaExcluded: string[];

  /** 유료: 기본통계(/free 통계 패널) 재조회 틱 */
  paidBasicStatsKick: number;

  paidResultView: PaidResultView;
  paidBasicBaseKey: string | null;

  /** 필터 분석 상태/결과 (effect/kick 없이 단일 진입점) */
  paidAnalysisStatus: PaidAnalysisStatus;
  paidAnalysisResult: PaidAnalysisResponse | null;
  paidAnalysisError: ParsedApiError | null;
  /** 진행 중인 분석 식별자 — race 시 마지막 호출의 결과만 채택 */
  paidAnalysisRequestId: number;
  paidAnalysisStartedAt: number | null;

  setViewMode: (m: ViewMode) => void;
  setRegionSegment: (idx: 0 | 1 | 2 | 3 | 4, value: string) => void;
  applyBeopjungriCodes: (codes: readonly string[]) => void;
  clearTierSelection: () => void;

  /** 지역 반영 후 무료와 동일한 기본 통계 화면 */
  kickPaidBasicStatsAnalysis: (beopjungriCodes: readonly string[]) => void;
  setPaidBasicBaseKey: (key: string | null) => void;
  /** 현재 지역+필터로 유료 매트릭스 분석 — promise 기반, 직접 호출 */
  runPaidFilteredAnalysis: () => Promise<void>;
  /** 진행 중인 분석을 폐기하고 idle 로 */
  cancelPaidFilteredAnalysis: () => void;

  setPaidRequest: (req: Partial<PaidAnalysisRequest>) => void;
  togglePaidRoadExclude: (road: string) => void;
  togglePaidAreaExclude: (area: string) => void;
  togglePaidYear: (year: number) => void;
  resetPaidExcluded: () => void;
}

const defaultPaidRequest: PaidAnalysisRequest = {
  region_selections: null,
  region_codes: null,
  year_from: null,
  year_to: null,
  years: getDefaultPaidSelectedYears(),
  road_conditions: null,
  area_categories: null,
  land_categories: null,
  zone_types: null,
  exclude_partial: false,
  exclude_outlier: false,
  outlier_iqr_multiplier: 3,
  base_cache_key: null,
};

function tierOnlyBeopjungri(codes: readonly string[]): TierCodes {
  return {
    ...emptyTierCodes(),
    beopjungri_codes: codes.map((c) => c.trim()).filter(Boolean),
  };
}

export const useAppStore = create<AppState>((set, get) => ({
  viewMode: "free",
  regionSegments: [...EMPTY_REGION_SEGMENTS],
  tierSelection: emptyTierCodes(),
  paidRequest: { ...defaultPaidRequest },
  paidRoadExcluded: [],
  paidAreaExcluded: [],
  paidBasicStatsKick: 0,

  paidResultView: "idle",
  paidBasicBaseKey: null,

  paidAnalysisStatus: "idle",
  paidAnalysisResult: null,
  paidAnalysisError: null,
  paidAnalysisRequestId: 0,
  paidAnalysisStartedAt: null,

  setViewMode: (m) =>
    set((s) => ({
      viewMode: m,
      paidResultView: m === "free" ? "idle" : s.paidResultView,
    })),

  setRegionSegment: (idx, value) =>
    set((s) => {
      const next = [...s.regionSegments] as [string, string, string, string, string];
      next[idx] = value;
      return { regionSegments: next };
    }),

  applyBeopjungriCodes: (codes) =>
    set({
      tierSelection: tierOnlyBeopjungri(codes),
    }),

  clearTierSelection: () =>
    set({
      tierSelection: emptyTierCodes(),
      regionSegments: [...EMPTY_REGION_SEGMENTS],
      paidResultView: "idle",
      paidBasicBaseKey: null,
      paidAnalysisStatus: "idle",
      paidAnalysisResult: null,
      paidAnalysisError: null,
      paidAnalysisStartedAt: null,
    }),

  kickPaidBasicStatsAnalysis: (beopjungriCodes) =>
    set((s) => ({
      tierSelection: tierOnlyBeopjungri(beopjungriCodes),
      paidBasicStatsKick: s.paidBasicStatsKick + 1,
      paidResultView: "basic",
      paidBasicBaseKey: null,
      paidAnalysisStatus: "idle",
      paidAnalysisResult: null,
      paidAnalysisError: null,
    })),

  setPaidBasicBaseKey: (key) => set({ paidBasicBaseKey: key }),

  runPaidFilteredAnalysis: async () => {
    const s = get();
    const codes = s.tierSelection.beopjungri_codes;
    if (codes.length === 0) {
      return;
    }
    const reqId = s.paidAnalysisRequestId + 1;
    const payload = buildPaidPayload(
      s.paidRequest,
      codes,
      s.paidRoadExcluded,
      s.paidAreaExcluded,
      s.paidBasicBaseKey
    );
    set({
      paidResultView: "filtered",
      paidAnalysisStatus: "loading",
      paidAnalysisError: null,
      paidAnalysisRequestId: reqId,
      paidAnalysisStartedAt: Date.now(),
    });
    try {
      const data = await runPaidAnalysisApi(payload);
      // 사이에 새 호출이나 cancel 이 일어났으면 결과 폐기.
      if (get().paidAnalysisRequestId !== reqId) return;
      set({
        paidAnalysisStatus: "success",
        paidAnalysisResult: data,
        paidAnalysisError: null,
        paidAnalysisStartedAt: null,
      });
    } catch (e) {
      if (get().paidAnalysisRequestId !== reqId) return;
      set({
        paidAnalysisStatus: "error",
        paidAnalysisError: parseApiError(e),
        paidAnalysisStartedAt: null,
      });
    }
  },

  cancelPaidFilteredAnalysis: () =>
    set((s) => ({
      paidAnalysisRequestId: s.paidAnalysisRequestId + 1,
      paidAnalysisStatus: "idle",
      paidAnalysisError: null,
      paidAnalysisStartedAt: null,
    })),

  setPaidRequest: (req) =>
    set((s) => ({
      paidRequest: { ...s.paidRequest, ...req },
    })),

  togglePaidRoadExclude: (road) =>
    set((s) => {
      const ex = s.paidRoadExcluded.includes(road)
        ? s.paidRoadExcluded.filter((x) => x !== road)
        : [...s.paidRoadExcluded, road];
      return { paidRoadExcluded: ex };
    }),

  togglePaidAreaExclude: (area) =>
    set((s) => {
      const ex = s.paidAreaExcluded.includes(area)
        ? s.paidAreaExcluded.filter((x) => x !== area)
        : [...s.paidAreaExcluded, area];
      return { paidAreaExcluded: ex };
    }),

  togglePaidYear: (year) =>
    set((s) => {
      const cur = [...(s.paidRequest.years ?? [])];
      const has = cur.includes(year);
      const next = (has ? cur.filter((y) => y !== year) : [...cur, year]).sort((a, b) => a - b);
      if (next.length === 0) {
        return s;
      }
      return {
        paidRequest: {
          ...s.paidRequest,
          years: next,
          year_from: null,
          year_to: null,
        },
      };
    }),

  resetPaidExcluded: () => set({ paidRoadExcluded: [], paidAreaExcluded: [] }),
}));
