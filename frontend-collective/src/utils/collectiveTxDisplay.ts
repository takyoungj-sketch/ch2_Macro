import type { AssetType, CollectiveTransactionRow } from "../types";

export function formatCollectiveTxCell(value: string | null | undefined): string {
  const t = (value ?? "").trim();
  return t || "—";
}

const MOLIT_DEAL_TYPES = new Set(["중개거래", "직거래"]);

/** 거래유형: 중개거래·직거래만. 주소·빈값은 공란. */
export function formatCollectiveDealType(value: string | null | undefined): string {
  const t = (value ?? "").trim();
  return MOLIT_DEAL_TYPES.has(t) ? t : "—";
}

export function formatCollectiveTxContractDate(r: CollectiveTransactionRow): string {
  if (r.contract_date) return r.contract_date;
  if (r.contract_year == null) return "—";
  if (r.contract_month) {
    return `${r.contract_year}-${String(r.contract_month).padStart(2, "0")}-01`;
  }
  return String(r.contract_year);
}

export function collectiveTxContractSortKey(r: CollectiveTransactionRow): number {
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

export function collectiveTxDongCell(t: CollectiveTransactionRow, assetType: AssetType): string {
  return assetType === "presale"
    ? formatCollectiveTxCell(t.housing_subtype)
    : formatCollectiveTxCell(t.dong);
}

export type CollectiveTxSortKey =
  | "building"
  | "contract_date"
  | "dong"
  | "floor"
  | "exclusive_area"
  | "price"
  | "unit_price"
  | "buyer_type"
  | "seller_type"
  | "deal_type";

export type CollectiveTxSortDir = "asc" | "desc";

export function collectiveTxSortValue(
  r: CollectiveTransactionRow,
  key: CollectiveTxSortKey,
  assetType: AssetType,
): string | number | null {
  switch (key) {
    case "building":
      return r.display_name?.trim() || "—";
    case "contract_date":
      return collectiveTxContractSortKey(r);
    case "dong":
      return collectiveTxDongCell(r, assetType);
    case "floor":
      return r.floor ?? null;
    case "exclusive_area":
      return r.exclusive_area ?? null;
    case "price":
      return r.price;
    case "unit_price":
      return r.unit_price ?? null;
    case "buyer_type":
      return r.buyer_type?.trim() || "—";
    case "seller_type":
      return r.seller_type?.trim() || "—";
    case "deal_type":
      return formatCollectiveDealType(r.deal_type);
    default:
      return null;
  }
}
