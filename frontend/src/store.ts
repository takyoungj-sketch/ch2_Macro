import { create } from "zustand";
import { getDefaultPaidSelectedYears } from "./constants/paidFilters";
import type { PaidAnalysisRequest, ViewMode } from "./types";
import type { RegionFiveFields } from "./utils/resolveRegionFiveFields";
import type { TierCodes } from "./utils/regionTier";
import { emptyTierCodes } from "./utils/regionTier";

const EMPTY_REGION_SEGMENTS: RegionFiveFields = ["", "", "", "", ""];

export type PaidResultView = "idle" | "basic" | "filtered";

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
  /** 필터 분석 mutate 틱 */
  paidRunKick: number;

  paidResultView: PaidResultView;

  setViewMode: (m: ViewMode) => void;
  setRegionSegment: (idx: 0 | 1 | 2 | 3 | 4, value: string) => void;
  applyBeopjungriCodes: (codes: readonly string[]) => void;
  clearTierSelection: () => void;

  /** 지역 반영 후 무료와 동일한 기본 통계 화면 */
  kickPaidBasicStatsAnalysis: (beopjungriCodes: readonly string[]) => void;
  /** 현재 지역+c필터로 유료 매트릭스 분석 */
  runPaidFilteredAnalysis: () => void;
  bumpPaidRunKick: () => void;

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
};

function tierOnlyBeopjungri(codes: readonly string[]): TierCodes {
  return {
    ...emptyTierCodes(),
    beopjungri_codes: codes.map((c) => c.trim()).filter(Boolean),
  };
}

export const useAppStore = create<AppState>((set) => ({
  viewMode: "free",
  regionSegments: [...EMPTY_REGION_SEGMENTS],
  tierSelection: emptyTierCodes(),
  paidRequest: { ...defaultPaidRequest },
  paidRoadExcluded: [],
  paidAreaExcluded: [],
  paidBasicStatsKick: 0,
  paidRunKick: 0,

  paidResultView: "idle",

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
    }),

  kickPaidBasicStatsAnalysis: (beopjungriCodes) =>
    set((s) => ({
      tierSelection: tierOnlyBeopjungri(beopjungriCodes),
      paidBasicStatsKick: s.paidBasicStatsKick + 1,
      paidResultView: "basic",
    })),

  runPaidFilteredAnalysis: () =>
    set((s) => {
      if (s.tierSelection.beopjungri_codes.length === 0) {
        return s;
      }
      return { paidRunKick: s.paidRunKick + 1, paidResultView: "filtered" };
    }),

  bumpPaidRunKick: () => set((s) => ({ paidRunKick: s.paidRunKick + 1 })),

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
