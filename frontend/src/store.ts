import { create } from "zustand";
import {
  fetchFreeStatsBulk,
  runPaidAnalysis as runPaidAnalysisApi,
} from "./api/client";
import {
  clampFontStep,
  persistFontStep,
  readStoredFontStep,
} from "./constants/displayUi";
import { getDefaultPaidSelectedYears } from "./constants/paidFilters";
import type {
  FreeStatsWindowYears,
  PaidAnalysisRequest,
  PaidAnalysisResponse,
  RegionItem,
  ViewMode,
} from "./types";
import { normalizeFreeStatsWindowYears } from "./types";
import { parseApiError, type ParsedApiError } from "./utils/apiError";
import { buildPaidPayload } from "./utils/paidAnalysisPayload";
import type { RegionFiveFields } from "./utils/resolveRegionFiveFields";
import type { TierCodes } from "./utils/regionTier";
import { emptyTierCodes, resolveUnionBeopjungriCodes } from "./utils/regionTier";

const EMPTY_REGION_SEGMENTS: RegionFiveFields = ["", "", "", "", ""];

const MAX_BEOPJUNGRI_PICK = 200;
const MAX_SIGUNGU_TIER_PICK = 20;
const MAX_EUP_TIER_PICK = 40;
const MAX_SIDO_TIER_PICK = 6;

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

  /** 유료: 기본통계(/free 통계 패널) 재조회 틱 — commitStatsDisplayScope 와 함께 증가 */
  paidBasicStatsKick: number;

  /**
   * 기본 통계 패널: 「무료 통계 조회」/「기본 통계 보기」 확정 시점의 법정리 스코프.
   * 선택이 바뀌면 키가 어긋나 자동 조회되지 않는다.
   */
  statsDisplayScopeKey: string | null;
  statsDisplayKick: number;

  /** 무료·기본통계 V2: 계약일 기준 롤링 창 (3년 또는 5년) */
  freeStatsWindowYears: FreeStatsWindowYears;
  setFreeStatsWindowYears: (y: FreeStatsWindowYears) => void;

  paidResultView: PaidResultView;
  paidBasicBaseKey: string | null;
  /**
   * 마지막 기본통계(/free/v2) 응답의 beopjungri_code(쉼표 구분)와 동기화.
   * 사전집계에서 제외된 코드 없이 kept만 담겨 analyze·모달과 동일한 행 집합을 쓰기 위함.
   */
  paidBulkBeopjungriCodes: string[] | null;

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
  /** 시·도(2자리 sido_code) 단독 선택용. 유료 모드 한정. */
  mergePickedSidoCodes: (
    codes: readonly string[],
    regions: readonly RegionItem[]
  ) => boolean;
  removePickedBeopjungri: (code: string) => void;
  removePickedSigungu: (code: string) => void;
  removePickedEupmyeondong: (code: string) => void;
  removePickedSido: (code: string) => void;
  clearTierSelection: () => void;

  /**
   * 기본 통계 패널 갱신. 인자 없으면 현재 tier 그대로.
   * 단계별 적용처럼 법정코드 목록만으로 덮어쓸 때에만 평평한 코드 배열을 넘김.
   */
  kickPaidBasicStatsAnalysis: (flattenTierToBeops?: readonly string[]) => void;
  commitStatsDisplayScope: (scopeKey: string) => void;
  /** 기본통계 응답의 analysis_base_key + beopjungri_code를 한 번에 반영 */
  syncPaidBasicStatsMeta: (payload: {
    analysis_base_key?: string | null;
    beopjungri_code?: string | null;
  }) => void;
  /** 현재 지역+필터로 유료 매트릭스 분석 — promise 기반, 직접 호출 */
  runPaidFilteredAnalysis: (resolvedBeopjungriCodes: readonly string[]) => Promise<void>;
  /** 진행 중인 분석을 폐기하고 idle 로 */
  cancelPaidFilteredAnalysis: () => void;

  setPaidRequest: (req: Partial<PaidAnalysisRequest>) => void;
  togglePaidRoadExclude: (road: string) => void;
  togglePaidAreaExclude: (area: string) => void;
  togglePaidYear: (year: number) => void;
  resetPaidExcluded: () => void;

  /** 글자 크기 단계(본문 zoom, localStorage 유지) */
  uiFontScaleStep: number;
  bumpUiFontScale: (direction: 1 | -1) => void;
}

const defaultPaidRequest: PaidAnalysisRequest = {
  region_selections: null,
  region_codes: null,
  year_from: null,
  year_to: null,
  years: getDefaultPaidSelectedYears(),
  road_conditions: null,
  area_categories: null,
  area_sqm_min: null,
  area_sqm_max: null,
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
  paidRequest: { ...defaultPaidRequest },
  paidRoadExcluded: [],
  paidAreaExcluded: [],
  paidBasicStatsKick: 0,
  statsDisplayScopeKey: null,
  statsDisplayKick: 0,
  freeStatsWindowYears: 5,

  paidResultView: "idle",
  paidBasicBaseKey: null,
  paidBulkBeopjungriCodes: null,

  paidAnalysisStatus: "idle",
  paidAnalysisResult: null,
  paidAnalysisError: null,
  paidAnalysisRequestId: 0,
  paidAnalysisStartedAt: null,

  setViewMode: (m) =>
    set((s) => {
      if (m !== "free") {
        /**
         * 무료 → 유료 전환은 새 분석 세션의 시작점이다.
         * 사용자는 유료에서 지역을 다시 고르길 원하므로 모든 tier 선택과 분석 잔재를 비운다.
         * (유료 → 유료 안에서 paidResultView 만 바뀌는 경우는 setViewMode 가 아닌 별도 액션.)
         */
        if (s.viewMode === "free") {
          return {
            viewMode: m,
            tierSelection: emptyTierCodes(),
            regionSegments: [...EMPTY_REGION_SEGMENTS],
            paidResultView: "idle",
            paidBasicBaseKey: null,
            paidBulkBeopjungriCodes: null,
            paidAnalysisStatus: "idle",
            paidAnalysisResult: null,
            paidAnalysisError: null,
            paidAnalysisStartedAt: null,
            statsDisplayScopeKey: null,
            statsDisplayKick: 0,
            paidBasicStatsKick: 0,
          };
        }
        return {
          viewMode: m,
          paidResultView: s.paidResultView,
          statsDisplayScopeKey: null,
          statsDisplayKick: 0,
        };
      }
      /**
       * 무료 화면은 단건(법정동·리 1개)만 다룬다.
       * 유료에서 시군구·읍면동 다중 선택을 한 채로 무료로 돌아오면
       * resolveUnionBeopjungriCodes 가 1개 초과 코드를 돌려줘 무료 패널 canFetch 가 막혀
       * 화면이 비어 보이는 문제가 있어, 마지막 법정코드만 보존한다.
       */
      const beops = s.tierSelection.beopjungri_codes.filter(Boolean);
      const lastBeop = beops.length > 0 ? [beops[beops.length - 1]!] : [];
      const needsTrim =
        s.tierSelection.sigungu_codes.length > 0 ||
        s.tierSelection.eupmyeondong_codes.length > 0 ||
        beops.length > 1;
      return {
        viewMode: m,
        paidResultView: "idle",
        tierSelection: needsTrim ? tierOnlyBeopjungri(lastBeop) : s.tierSelection,
        // 유료 잔재 정리(매트릭스/캐시키 등은 무료 모드와 무관)
        paidBasicBaseKey: null,
        paidBulkBeopjungriCodes: null,
        paidAnalysisStatus: "idle",
        paidAnalysisResult: null,
        paidAnalysisError: null,
        paidAnalysisStartedAt: null,
        statsDisplayScopeKey: null,
        statsDisplayKick: 0,
        paidBasicStatsKick: 0,
      };
    }),

  setFreeStatsWindowYears: (y) =>
    set({ freeStatsWindowYears: normalizeFreeStatsWindowYears(y) }),

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

  mergePickedSidoCodes: (incoming, regions) => {
    const uniqIn = [...new Set(incoming.map((c) => String(c ?? "").trim()).filter(Boolean))];
    if (uniqIn.length === 0) return false;
    const s = get();
    if (s.viewMode === "free") return false;
    const merged = normalizeAndSortCodes([...s.tierSelection.sido_codes, ...uniqIn]);
    if (merged.length > MAX_SIDO_TIER_PICK) return false;
    const next: TierCodes = { ...s.tierSelection, sido_codes: merged };
    if (resolveUnionBeopjungriCodes(regions, next).length > MAX_BEOPJUNGRI_PICK) return false;
    if (normalizeAndSortCodes(s.tierSelection.sido_codes).join("|") === merged.join("|")) {
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

  removePickedSido: (code) =>
    set((s) => {
      const c = String(code ?? "").trim();
      if (!c) return s;
      const next = s.tierSelection.sido_codes.filter((x) => x.trim() !== c);
      return {
        tierSelection: {
          ...s.tierSelection,
          sido_codes: normalizeAndSortCodes(next),
        },
      };
    }),

  clearTierSelection: () =>
    set({
      tierSelection: emptyTierCodes(),
      regionSegments: [...EMPTY_REGION_SEGMENTS],
      paidResultView: "idle",
      paidBasicBaseKey: null,
      paidBulkBeopjungriCodes: null,
      paidAnalysisStatus: "idle",
      paidAnalysisResult: null,
      paidAnalysisError: null,
      paidAnalysisStartedAt: null,
      statsDisplayScopeKey: null,
      statsDisplayKick: 0,
      paidBasicStatsKick: 0,
    }),

  kickPaidBasicStatsAnalysis: (flattenTierToBeops) =>
    set((s) => ({
      ...(flattenTierToBeops != null && flattenTierToBeops.length > 0
        ? { tierSelection: tierOnlyBeopjungri(normalizeAndSortCodes(flattenTierToBeops)) }
        : {}),
      paidResultView: "basic",
      paidBasicBaseKey: null,
      paidBulkBeopjungriCodes: null,
      paidAnalysisStatus: "idle",
      paidAnalysisResult: null,
      paidAnalysisError: null,
      paidAnalysisStartedAt: null,
    })),

  commitStatsDisplayScope: (scopeKey: string) =>
    set((s) => ({
      statsDisplayScopeKey: scopeKey,
      statsDisplayKick: s.statsDisplayKick + 1,
      paidBasicStatsKick: s.paidBasicStatsKick + 1,
    })),

  syncPaidBasicStatsMeta: (payload) =>
    set(() => {
      const raw = payload.beopjungri_code;
      const split =
        raw == null || String(raw).trim() === ""
          ? null
          : normalizeAndSortCodes(String(raw).split(","));
      return {
        paidBasicBaseKey: payload.analysis_base_key ?? null,
        paidBulkBeopjungriCodes: split != null && split.length > 0 ? split : null,
      };
    }),

  runPaidFilteredAnalysis: async (resolvedBeopjungriCodes) => {
    const resolved = normalizeAndSortCodes(resolvedBeopjungriCodes);
    if (resolved.length === 0) {
      return;
    }

    /**
     * 분석 시작 시점에 reqId 를 먼저 올리고 loading 으로 진입한다.
     * - bulk 사전조회가 끝나기 전 사용자가 다시 「필터 분석 실행」을 눌러도,
     *   reqId 가 달라지므로 늦게 도착한 bulk/analyze 응답은 set 단계에서 폐기된다.
     * - UI 가 즉시 「분석 중…」 으로 전환되어 멍한 무반응 구간이 사라진다.
     */
    const reqId = get().paidAnalysisRequestId + 1;
    set({
      paidResultView: "filtered",
      paidAnalysisStatus: "loading",
      paidAnalysisError: null,
      paidAnalysisRequestId: reqId,
      paidAnalysisStartedAt: Date.now(),
    });

    const s0 = get();
    let codes: string[];
    const rc = resolved;
    const sc =
      s0.paidBulkBeopjungriCodes != null
        ? normalizeAndSortCodes(s0.paidBulkBeopjungriCodes)
        : [];
    /** 사전집계 kept(부분 코드) vs 선택 전체가 다르면 스토어 값이 더 넓거나 더 좁을 수 있어 재확인 필요 */
    const storeMatchesTierSelection =
      sc.length > 0 && sc.length === rc.length && sc.every((c, i) => c === rc[i]);
    if (storeMatchesTierSelection) {
      codes = [...sc];
    } else if (resolved.length > 1) {
      /**
       * 필터 분석 화면만 볼 때 PaidAnalysisPanel 이 아직 없어 기본통계 동기화가 안 된 경우가 많다.
       * 복수 법정단위는 free/v2/bulk 의 kept(beopjungri_code)와 analyze·모달이 같아야 한다.
       */
      const w = normalizeFreeStatsWindowYears(s0.freeStatsWindowYears);
      try {
        const bulk = await fetchFreeStatsBulk(resolved, { window_years: w });
        // bulk 결과를 store 에 반영하기 전에 cancel/재호출 여부 재확인.
        if (get().paidAnalysisRequestId !== reqId) return;
        const split = normalizeAndSortCodes(
          String(bulk.beopjungri_code ?? "")
            .split(",")
            .map((c) => c.trim())
            .filter(Boolean)
        );
        if (split.length > 0) {
          get().syncPaidBasicStatsMeta({
            analysis_base_key: bulk.analysis_base_key ?? null,
            beopjungri_code: bulk.beopjungri_code ?? null,
          });
          codes = split;
        } else {
          codes = resolved;
        }
      } catch {
        if (get().paidAnalysisRequestId !== reqId) return;
        codes = resolved;
      }
    } else {
      codes = resolved;
    }

    const st = get();
    const payload = buildPaidPayload(
      st.paidRequest,
      codes,
      st.paidRoadExcluded,
      st.paidAreaExcluded,
      st.paidBasicBaseKey
    );
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

}));
