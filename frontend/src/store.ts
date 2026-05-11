import { create } from "zustand";
import type { PaidAnalysisRequest, ViewMode } from "./types";

interface AppState {
  viewMode: ViewMode;
  selectedCode: string | null;
  selectedCodes: string[];
  paidRequest: PaidAnalysisRequest;

  setViewMode: (m: ViewMode) => void;
  setSelectedCode: (code: string | null) => void;
  toggleSelectedCode: (code: string) => void;
  setPaidRequest: (req: Partial<PaidAnalysisRequest>) => void;
}

const defaultPaidRequest: PaidAnalysisRequest = {
  region_codes: [],
  year_from: null,
  year_to: null,
  road_conditions: null,
  area_categories: null,
  land_categories: null,
  zone_types: null,
  exclude_partial: false,
  exclude_outlier: false,
};

export const useAppStore = create<AppState>((set) => ({
  viewMode: "free",
  selectedCode: null,
  selectedCodes: [],
  paidRequest: defaultPaidRequest,

  setViewMode: (m) => set({ viewMode: m }),

  setSelectedCode: (code) => set({ selectedCode: code }),

  toggleSelectedCode: (code) =>
    set((s) => {
      const exists = s.selectedCodes.includes(code);
      const next = exists
        ? s.selectedCodes.filter((c) => c !== code)
        : [...s.selectedCodes, code];
      return {
        selectedCodes: next,
        paidRequest: { ...s.paidRequest, region_codes: next },
      };
    }),

  setPaidRequest: (req) =>
    set((s) => ({ paidRequest: { ...s.paidRequest, ...req } })),
}));
