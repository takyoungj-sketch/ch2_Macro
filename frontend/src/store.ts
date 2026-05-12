import { create } from "zustand";
import { runPaidAnalysis as runPaidAnalysisApi } from "./api/client";
import {
  type UiTableTone,
  clampFontStep,
  persistFontStep,
  persistTableTone,
  readStoredFontStep,
  readStoredTableTone,
} from "./constants/displayUi";
import { getDefaultPaidSelectedYears } from "./constants/paidFilters";
import type { PaidAnalysisRequest, PaidAnalysisResponse, RegionItem, ViewMode } from "./types";
import { parseApiError, type ParsedApiError } from "./utils/apiError";
import { buildPaidPayload } from "./utils/paidAnalysisPayload";
import type { RegionFiveFields } from "./utils/resolveRegionFiveFields";
import type { TierCodes } from "./utils/regionTier";
import { emptyTierCodes, resolveUnionBeopjungriCodes } from "./utils/regionTier";

const EMPTY_REGION_SEGMENTS: RegionFiveFields = ["", "", "", "", ""];

const MAX_BEOPJUNGRI_PICK = 200;
const MAX_SIGUNGU_TIER_PICK = 20;
const MAX_EUP_TIER_PICK = 40;

function normalizeAndSortCodes(codes: readonly string[]): string[] {
  return [...new Set(codes.map((c) => c.trim()).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "ko-KR")
  );
}
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
  /** 검색·칩에서 법정단위 추가(무료는 항상 1개로 교체) */
  addPickedBeopjungri: (code: string) => void;
  /** 검색 등에서 법정코드 여러 개를 한 번에 병합(유료; 중복 제거·200 상한). 무료는 단건일 때만 반영 가능 */
  mergePickedBeopjungriCodes: (codes: readonly string[]) => boolean;
  mergePickedSigunguCodes: (
    codes: readonly string[],
    regions: readonly RegionItem[]
  ) => boolean;
  mergePickedEupmyeondongCodes: (
    codes: readonly string[],
    regions: readonly RegionItem[]
  ) => boolean;
  removePickedBeopjungri: (code: string) => void;
  removePickedSigungu: (code: string) => void;
  removePickedEupmyeondong: (code: string) => void;
  clearTierSelection: () => void;

  /**
   * 기본 통계 패널 갱신. 인자 없으면 현재 tier 그대로.
   * 단계별 적용처럼 법정코드 목록만으로 덮어쓸 때에만 평평한 코드 배열을 넘김.
   */
  kickPaidBasicStatsAnalysis: (flattenTierToBeops?: readonly string[]) => void;
  setPaidBasicBaseKey: (key: string | null) => void;
  /** 현재 지역+필터로 유료 매트릭스 분석 — promise 기반, 직접 호출 */
  runPaidFilteredAnalysis: (resolvedBeopjungriCodes: readonly string[]) => Promise<void>;
  /** 진행 중인 분석을 폐기하고 idle 로 */
  cancelPaidFilteredAnalysis: () => void;

  setPaidRequest: (req: Partial<PaidAnalysisRequest>) => void;
  togglePaidRoadExclude: (road: string) => void;
  togglePaidAreaExclude: (area: string) => void;
  togglePaidYear: (year: number) => void;
  resetPaidExcluded: () => void;

  /** 전역 표시 설정 (localStorage 유지). */
  uiFontScaleStep: number;
  uiTableTone: UiTableTone;
  bumpUiFontScale: (direction: 1 | -1) => void;
  setUiTableTone: (tone: UiTableTone) => void;
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
    beopjungri_codes: normalizeAndSortCodes(codes),
  };
}

export const useAppStore = create<AppState>((set, get) => ({
  viewMode: "free",
  regionSegments: [...EMPTY_REGION_SEGMENTS],
  tierSelection: emptyTierCodes(),
  uiFontScaleStep: readStoredFontStep(),
  uiTableTone: readStoredTableTone(),
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

  addPickedBeopjungri: (code) =>
    set((s) => {
      const c = String(code ?? "").trim();
      if (!c) return s;
      if (s.viewMode === "free") {
        return { tierSelection: tierOnlyBeopjungri([c]) };
      }
      const cur = s.tierSelection.beopjungri_codes.map((x) => x.trim()).filter(Boolean);
      if (cur.includes(c)) return s;
      if (cur.length >= MAX_BEOPJUNGRI_PICK) return s;
      return {
        tierSelection: {
          ...s.tierSelection,
          beopjungri_codes: normalizeAndSortCodes([...cur, c]),
        },
      };
    }),

  mergePickedBeopjungriCodes: (incoming) => {
    const uniqIn = [...new Set(incoming.map((c) => String(c ?? "").trim()).filter(Boolean))];
    if (uniqIn.length === 0) return false;
    const s = get();
    if (s.viewMode === "free") {
      if (uniqIn.length !== 1) return false;
      set({ tierSelection: tierOnlyBeopjungri(normalizeAndSortCodes(uniqIn)) });
      return true;
    }
    const merged = normalizeAndSortCodes([...s.tierSelection.beopjungri_codes, ...uniqIn]);
    if (merged.length > MAX_BEOPJUNGRI_PICK) return false;
    const before = normalizeAndSortCodes(s.tierSelection.beopjungri_codes).join("|");
    const after = merged.join("|");
    if (before === after) return false;
    set({
      tierSelection: {
        ...s.tierSelection,
        beopjungri_codes: merged,
      },
    });
    return true;
  },

  mergePickedSigunguCodes: (incoming, regions) => {
    const uniqIn = [...new Set(incoming.map((c) => String(c ?? "").trim()).filter(Boolean))];
    if (uniqIn.length === 0) return false;
    const s = get();
    if (s.viewMode === "free") return false;
    const merged = normalizeAndSortCodes([...s.tierSelection.sigungu_codes, ...uniqIn]);
    if (merged.length > MAX_SIGUNGU_TIER_PICK) return false;
    const next: TierCodes = { ...s.tierSelection, sigungu_codes: merged };
    if (resolveUnionBeopjungriCodes(regions, next).length > MAX_BEOPJUNGRI_PICK) return false;
    if (normalizeAndSortCodes(s.tierSelection.sigungu_codes).join("|") === merged.join("|")) {
      return false;
    }
    set({ tierSelection: next });
    return true;
  },

  mergePickedEupmyeondongCodes: (incoming, regions) => {
    const uniqIn = [...new Set(incoming.map((c) => String(c ?? "").trim()).filter(Boolean))];
    if (uniqIn.length === 0) return false;
    const s = get();
    if (s.viewMode === "free") return false;
    const merged = normalizeAndSortCodes([
      ...s.tierSelection.eupmyeondong_codes,
      ...uniqIn,
    ]);
    if (merged.length > MAX_EUP_TIER_PICK) return false;
    const next: TierCodes = { ...s.tierSelection, eupmyeondong_codes: merged };
    if (resolveUnionBeopjungriCodes(regions, next).length > MAX_BEOPJUNGRI_PICK) return false;
    if (
      normalizeAndSortCodes(s.tierSelection.eupmyeondong_codes).join("|") === merged.join("|")
    ) {
      return false;
    }
    set({ tierSelection: next });
    return true;
  },

  removePickedBeopjungri: (code) =>
    set((s) => {
      const c = String(code ?? "").trim();
      if (!c) return s;
      const next = s.tierSelection.beopjungri_codes.filter((x) => x.trim() !== c);
      return {
        tierSelection: {
          ...s.tierSelection,
          beopjungri_codes: normalizeAndSortCodes(next),
        },
      };
    }),

  removePickedSigungu: (code) =>
    set((s) => {
      const c = String(code ?? "").trim();
      if (!c) return s;
      const next = s.tierSelection.sigungu_codes.filter((x) => x.trim() !== c);
      return {
        tierSelection: {
          ...s.tierSelection,
          sigungu_codes: normalizeAndSortCodes(next),
        },
      };
    }),

  removePickedEupmyeondong: (code) =>
    set((s) => {
      const c = String(code ?? "").trim();
      if (!c) return s;
      const next = s.tierSelection.eupmyeondong_codes.filter((x) => x.trim() !== c);
      return {
        tierSelection: {
          ...s.tierSelection,
          eupmyeondong_codes: normalizeAndSortCodes(next),
        },
      };
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

  kickPaidBasicStatsAnalysis: (flattenTierToBeops) =>
    set((s) => ({
      ...(flattenTierToBeops != null && flattenTierToBeops.length > 0
        ? { tierSelection: tierOnlyBeopjungri(normalizeAndSortCodes(flattenTierToBeops)) }
        : {}),
      paidBasicStatsKick: s.paidBasicStatsKick + 1,
      paidResultView: "basic",
      paidBasicBaseKey: null,
      paidAnalysisStatus: "idle",
      paidAnalysisResult: null,
      paidAnalysisError: null,
      paidAnalysisStartedAt: null,
    })),

  setPaidBasicBaseKey: (key) => set({ paidBasicBaseKey: key }),

  runPaidFilteredAnalysis: async (resolvedBeopjungriCodes) => {
    const codes = [...resolvedBeopjungriCodes.map((c) => String(c ?? "").trim()).filter(Boolean)];
    if (codes.length === 0) {
      return;
    }
    const s = get();
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

  bumpUiFontScale: (direction) =>
    set((s) => {
      const next = clampFontStep(s.uiFontScaleStep + direction);
      persistFontStep(next);
      return { uiFontScaleStep: next };
    }),

  setUiTableTone: (tone) => {
    persistTableTone(tone);
    set({ uiTableTone: tone });
  },
}));
