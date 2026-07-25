import type { MatrixCellTransactionItem } from "../types";

export function formatLandTxContractDate(r: MatrixCellTransactionItem): string {
  const cd = r.contract_date?.slice(0, 10);
  if (cd) return cd;
  return `${r.contract_year}.${String(r.contract_month).padStart(2, "0")}`;
}

export function formatLandTxCell(value: string | null | undefined): string {
  const t = (value ?? "").trim();
  return t || "—";
}

/** 시군구·읍면동·동·리 — beopjungri가 eupmyeondong과 같으면 ri는 null(중복 표시 방지). */
export function landTxAdminCols(
  r: Pick<MatrixCellTransactionItem, "sigungu_name" | "eupmyeondong_name" | "beopjungri_name">,
): { sigungu: string | null; eupmyeondong: string | null; ri: string | null } {
  const sigungu = r.sigungu_name?.trim() || null;
  const eup = r.eupmyeondong_name?.trim() || null;
  const beop = r.beopjungri_name?.trim() || null;
  const ri =
    beop && eup && beop.localeCompare(eup, "ko", { sensitivity: "base" }) === 0 ? null : beop;
  return { sigungu, eupmyeondong: eup, ri };
}

/** regionDisplay.formatRegionHierarchyLabel 과 동일 dedupe — 한 줄 주소용 */
export function landTxAddressLine(
  r: Pick<MatrixCellTransactionItem, "sigungu_name" | "eupmyeondong_name" | "beopjungri_name">,
): string {
  const raw = [r.sigungu_name, r.eupmyeondong_name, r.beopjungri_name].map((s) =>
    String(s ?? "").trim(),
  );
  const seen = new Set<string>();
  const parts: string[] = [];
  for (const x of raw) {
    if (!x) continue;
    const k = x.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    parts.push(x);
  }
  return parts.join(" ") || "—";
}

export function landTxContractSortKey(r: MatrixCellTransactionItem): number {
  if (r.contract_date) {
    const d = r.contract_date.slice(0, 10).replace(/-/g, "");
    const n = Number(d);
    if (Number.isFinite(n)) return n;
  }
  return r.contract_year * 100 + r.contract_month;
}

export type LandTxSortKey =
  | "contract_date"
  | "sigungu"
  | "eupmyeondong"
  | "ri"
  | "lot"
  | "land_category"
  | "area"
  | "price"
  | "unit_price"
  | "road"
  | "partial"
  | "deal_type";

export type LandTxSortDir = "asc" | "desc";

export function landTxSortValue(r: MatrixCellTransactionItem, key: LandTxSortKey): string | number | null {
  const admin = landTxAdminCols(r);
  switch (key) {
    case "contract_date":
      return landTxContractSortKey(r);
    case "sigungu":
      return admin.sigungu ?? "";
    case "eupmyeondong":
      return admin.eupmyeondong ?? "";
    case "ri":
      return admin.ri ?? "";
    case "lot":
      return r.lot_display?.trim() ?? "";
    case "land_category":
      return r.land_category?.trim() ?? "";
    case "area":
      return r.area_sqm ?? null;
    case "price":
      return r.total_price_10k;
    case "unit_price":
      return r.unit_price_per_sqm ?? null;
    case "road":
      return r.road_condition?.trim() ?? "";
    case "partial":
      return r.partial_ownership_label?.trim() ?? "";
    case "deal_type":
      return r.deal_type?.trim() ?? "";
    default:
      return null;
  }
}

export function landTxFilterText(r: MatrixCellTransactionItem, key: LandTxSortKey): string {
  const v = landTxSortValue(r, key);
  if (v == null || v === "") return "";
  if (key === "contract_date") return formatLandTxContractDate(r);
  if (typeof v === "number") return String(v);
  return String(v);
}
