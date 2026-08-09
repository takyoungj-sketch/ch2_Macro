export type MapAdminLevel = "sido" | "sigungu" | "eupmyeondong" | "beopjungri";

/** neighbor 그래프·선택 비교용 — 읍면동은 8자리 canonical. */
export function canonAdminCode(level: string | null | undefined, code: string): string {
  const c = code.trim();
  if (!c) return c;
  if (level === "beopjungri" && c.length >= 10 && !c.endsWith("00")) return c;
  if (c.length >= 10 && c.endsWith("00")) return c.slice(0, 8);
  if (c.length >= 8) return c.slice(0, 8);
  return c;
}

export type MapSelectionState = {
  level: MapAdminLevel | null;
  selectedCodes: string[];
  contextSidoCode: string | null;
  contextSigunguCode: string | null;
  labels: Record<string, string>;
  hasSelection: boolean;
};

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
