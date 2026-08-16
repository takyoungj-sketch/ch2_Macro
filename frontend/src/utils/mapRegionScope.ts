import type { RegionItem } from "../types";
import { cityBucketFromSigungu } from "./cityBucket";
import { isSejongRegionRow } from "./sejongRegion";
import type { TierCodes } from "./regionTier";

export type MapAdminLevel = "sido" | "sigungu" | "eupmyeondong" | "beopjungri";

export type MapSelectionState = {
  level: MapAdminLevel | null;
  selectedCodes: string[];
  contextSidoCode: string | null;
  contextSigunguCode: string | null;
  labels: Record<string, string>;
  hasSelection: boolean;
};

function normCodes(codes: readonly string[]): string[] {
  return [...new Set(codes.map((c) => String(c ?? "").trim()).filter(Boolean))];
}

function labelForSigungu(regions: readonly RegionItem[], code: string): string {
  const row = regions.find((r) => String(r.sigungu_code ?? "").trim() === code);
  if (!row) return code;
  return [row.sido_name, row.sigungu_name].filter(Boolean).join(" ");
}

function labelForEup(regions: readonly RegionItem[], code: string): string {
  const row = regions.find((r) => String(r.eupmyeondong_code ?? "").trim() === code);
  if (!row) return code;
  if (isSejongRegionRow(row)) {
    return [row.sido_name, row.sigungu_name].filter(Boolean).join(" ");
  }
  return [row.sido_name, row.sigungu_name, row.eupmyeondong_name].filter(Boolean).join(" ");
}

function labelForBeop(regions: readonly RegionItem[], code: string): string {
  const row = regions.find((r) => String(r.beopjungri_code ?? "").trim() === code);
  if (!row) return code;
  if (isSejongRegionRow(row)) {
    return [row.sido_name, row.sigungu_name, row.beopjungri_name].filter(Boolean).join(" ");
  }
  return [row.sido_name, row.sigungu_name, row.eupmyeondong_name, row.beopjungri_name]
    .filter(Boolean)
    .join(" ");
}

/** 좌측 tierSelection → 지도 경계·highlight 스코프 */
export function resolveMapSelectionState(
  tier: TierCodes,
  regions: readonly RegionItem[],
): MapSelectionState {
  const sido = normCodes(tier.sido_codes);
  const sigungu = normCodes(tier.sigungu_codes);
  const city = normCodes(tier.city_codes);
  const eup = normCodes(tier.eupmyeondong_codes);
  const beop = normCodes(tier.beopjungri_codes);

  const labels: Record<string, string> = {};

  if (sido.length > 0 && sigungu.length === 0 && city.length === 0 && eup.length === 0 && beop.length === 0) {
    for (const c of sido) {
      const row = regions.find((r) => String(r.sido_code ?? "").trim() === c);
      labels[c] = row?.sido_name?.trim() || c;
    }
    return {
      level: "sido",
      selectedCodes: sido,
      contextSidoCode: sido[0] ?? null,
      contextSigunguCode: null,
      labels,
      hasSelection: true,
    };
  }

  if (sigungu.length > 0 && sido.length === 0 && city.length === 0 && eup.length === 0 && beop.length === 0) {
    for (const c of sigungu) {
      labels[c] = labelForSigungu(regions, c);
    }
    const ctxSido = sigungu[0]?.slice(0, 2) ?? null;
    return {
      level: "sigungu",
      selectedCodes: sigungu,
      contextSidoCode: ctxSido,
      contextSigunguCode: sigungu[0] ?? null,
      labels,
      hasSelection: true,
    };
  }

  if (city.length > 0 && sido.length === 0 && sigungu.length === 0 && eup.length === 0 && beop.length === 0) {
    // city_codes 는 의사 시 버킷(43110 청주, 44130 천안). 구 코드(43111…)와 startsWith 불일치 → 버킷 매칭.
    const buckets = new Set(city);
    const derivedSigungu = normCodes(
      regions
        .filter((r) => {
          const b = cityBucketFromSigungu(String(r.sigungu_code ?? ""));
          return Boolean(b && buckets.has(b));
        })
        .map((r) => String(r.sigungu_code ?? "").trim()),
    );
    for (const c of derivedSigungu) {
      labels[c] = labelForSigungu(regions, c);
    }
    return {
      level: "sigungu",
      selectedCodes: derivedSigungu.length ? derivedSigungu : city,
      contextSidoCode: city[0]?.slice(0, 2) ?? null,
      contextSigunguCode: derivedSigungu[0] ?? null,
      labels,
      hasSelection: derivedSigungu.length > 0,
    };
  }

  if (beop.length > 0 && sido.length === 0 && sigungu.length === 0 && city.length === 0) {
    const fromEup = eup.length
      ? regions
          .filter((r) => eup.includes(String(r.eupmyeondong_code ?? "").trim()))
          .map((r) => String(r.beopjungri_code ?? "").trim())
          .filter(Boolean)
      : [];
    const selected = normCodes([...beop, ...fromEup]);
    for (const c of selected) {
      labels[c] = labelForBeop(regions, c);
    }
    const ctxSigungu = selected[0]?.slice(0, 5) ?? null;
    return {
      level: "beopjungri",
      selectedCodes: selected,
      contextSidoCode: selected[0]?.slice(0, 2) ?? null,
      contextSigunguCode: ctxSigungu,
      labels,
      hasSelection: true,
    };
  }

  if (eup.length > 0 && sido.length === 0 && sigungu.length === 0 && city.length === 0 && beop.length === 0) {
    for (const c of eup) {
      labels[c] = labelForEup(regions, c);
    }
    return {
      level: "eupmyeondong",
      selectedCodes: eup,
      contextSidoCode: eup[0]?.slice(0, 2) ?? null,
      contextSigunguCode: eup[0]?.slice(0, 5) ?? null,
      labels,
      hasSelection: true,
    };
  }

  return {
    level: null,
    selectedCodes: [],
    contextSidoCode: null,
    contextSigunguCode: null,
    labels: {},
    hasSelection: false,
  };
}

/** GeoJSON feature properties → 행정 코드 */
export function featureAdminCode(
  props: Record<string, unknown> | null | undefined,
  level: MapAdminLevel,
): string | null {
  if (!props) return null;
  const ch2 = props.ch2_code;
  if (ch2 != null && String(ch2).trim()) return String(ch2).trim();
  const keys =
    level === "sido"
      ? ["ctprvn_cd", "sido_cd"]
      : level === "sigungu"
        ? ["sig_cd", "sigungu_cd"]
        : level === "eupmyeondong"
          ? ["emd_cd", "eupmyeondong_cd"]
          : ["bdong_cd", "beopjungri_code", "li_cd", "emd_cd"];
  for (const k of keys) {
    const v = props[k];
    if (v != null && String(v).trim()) {
      const s = String(v).trim();
      if (level === "beopjungri" && k === "emd_cd" && s.length === 8) {
        return s + "00";
      }
      return s;
    }
  }
  return null;
}
