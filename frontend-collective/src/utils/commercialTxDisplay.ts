import type { CommercialTransactionRow } from "../types";

export function formatCommercialTxCell(value: string | null | undefined): string {
  const t = (value ?? "").trim();
  return t || "—";
}

export function formatCommercialTxContractDate(r: CommercialTransactionRow): string {
  if (r.contract_date) return r.contract_date;
  if (r.contract_year == null) return "—";
  if (r.contract_month) {
    return `${r.contract_year}-${String(r.contract_month).padStart(2, "0")}-01`;
  }
  return String(r.contract_year);
}

export function commercialTxContractSortKey(r: CommercialTransactionRow): number {
  if (r.contract_date) {
    const d = r.contract_date.slice(0, 10).replace(/-/g, "");
    const n = Number(d);
    if (Number.isFinite(n)) return n;
  }
  if (r.contract_year != null && r.contract_month != null) {
    return r.contract_year * 100 + r.contract_month;
  }
  return r.contract_year ?? 0;
}

export function commercialTxDongCell(t: CommercialTransactionRow): string {
  const s = [t.addr3, t.addr4].filter(Boolean).join(" · ");
  return s || "—";
}

export function commercialTxRoadWidth(t: CommercialTransactionRow): string {
  if (t.road_width_label) return t.road_width_label;
  if (t.road_code != null) return `${t.road_code}m`;
  return "—";
}

export type CommercialTxSortKey =
  | "contract_date"
  | "lot_number"
  | "dong"
  | "zone_type"
  | "building_use"
  | "road_width"
  | "area_bucket"
  | "gross_area"
  | "floor"
  | "building_year"
  | "price"
  | "unit_price";

export type CommercialTxSortDir = "asc" | "desc";

export function commercialTxSortValue(
  r: CommercialTransactionRow,
  key: CommercialTxSortKey,
): string | number | null {
  switch (key) {
    case "contract_date":
      return commercialTxContractSortKey(r);
    case "lot_number":
      return r.lot_number?.trim() || "";
    case "dong":
      return commercialTxDongCell(r);
    case "zone_type":
      return r.zone_type?.trim() || "—";
    case "building_use":
      return r.building_use?.trim() || "—";
    case "road_width":
      return commercialTxRoadWidth(r);
    case "area_bucket":
      return r.area_bucket_label?.trim() || "—";
    case "gross_area":
      return r.gross_area ?? null;
    case "floor":
      return r.floor ?? null;
    case "building_year":
      return r.building_year ?? null;
    case "price":
      return r.price;
    case "unit_price":
      return r.unit_price ?? null;
    default:
      return null;
  }
}
