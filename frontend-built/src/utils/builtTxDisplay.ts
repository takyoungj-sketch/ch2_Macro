import type { BuiltTransactionRow } from "../types";

export function formatBuiltTxCell(value: string | null | undefined): string {
  const t = (value ?? "").trim();
  return t || "—";
}

export function formatBuiltTxContractDate(r: BuiltTransactionRow): string {
  if (r.contract_date) return r.contract_date;
  if (r.contract_year != null && r.contract_month != null) {
    return `${r.contract_year}-${String(r.contract_month).padStart(2, "0")}`;
  }
  return r.contract_year != null ? String(r.contract_year) : (r.trade_year_label ?? "—");
}

export function builtTxContractSortKey(r: BuiltTransactionRow): number {
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

/** 시도·시군구·구/읍면동·읍면동·리·지번 (구 도시: addr3=구, addr4=읍면동, addr5=리) */
export function builtTxAdminCols(r: BuiltTransactionRow) {
  const sido = r.addr1?.trim() || null;
  const sigungu = r.addr2?.trim() || null;
  const guEup = r.addr3?.trim() || null;
  let dong = r.addr4?.trim() || null;
  let ri = r.addr5?.trim() || null;
  if (guEup && dong && guEup === dong) dong = null;
  if (ri && (ri === guEup || ri === dong)) ri = null;
  return {
    sido,
    sigungu,
    gu_eup: guEup,
    dong_ri: dong,
    ri,
    lot: r.lot_number?.trim() || null,
  };
}

export function builtTxLotHoverTitle(r: BuiltTransactionRow): string | undefined {
  const recovered = r.recovered_lot?.trim();
  if (recovered) return recovered;
  return r.lot_number?.trim() || undefined;
}

export function builtTxBuildingYear(r: BuiltTransactionRow): number | null {
  if (r.building_year != null) return r.building_year;
  if (r.contract_year != null && r.building_age != null) {
    return r.contract_year - Math.round(r.building_age);
  }
  return null;
}

export type BuiltTxSortKey =
  | "asset_type"
  | "contract_date"
  | "sido"
  | "sigungu"
  | "gu_eup"
  | "dong_ri"
  | "ri"
  | "lot"
  | "share"
  | "road_name"
  | "zone_type"
  | "building_use"
  | "structure_group"
  | "price"
  | "gross_area"
  | "land_area"
  | "building_year"
  | "road_width";

export type BuiltTxSortDir = "asc" | "desc";

const ASSET_LABELS: Record<string, string> = {
  commercial: "상업",
  factory: "공장",
  detached: "단독",
};

export function builtTxSortValue(
  r: BuiltTransactionRow,
  key: BuiltTxSortKey,
): string | number | null {
  const admin = builtTxAdminCols(r);
  switch (key) {
    case "asset_type":
      return ASSET_LABELS[r.asset_type] ?? r.asset_type;
    case "contract_date":
      return builtTxContractSortKey(r);
    case "sido":
      return admin.sido ?? "";
    case "sigungu":
      return admin.sigungu ?? "";
    case "gu_eup":
      return admin.gu_eup ?? "";
    case "dong_ri":
      return admin.dong_ri ?? "";
    case "ri":
      return admin.ri ?? "";
    case "lot":
      return admin.lot ?? "";
    case "share":
      return r.is_partial_ownership ? "지분" : "—";
    case "road_name":
      return r.road_name?.trim() || "";
    case "zone_type":
      return r.zone_type?.trim() || "—";
    case "building_use":
      return r.building_use?.trim() || "—";
    case "structure_group":
      return r.structure_group?.trim() || "—";
    case "price":
      return r.price;
    case "gross_area":
      return r.gross_area ?? null;
    case "land_area":
      return r.land_area ?? null;
    case "building_year":
      return builtTxBuildingYear(r);
    case "road_width":
      return r.road_width_label?.trim() || "—";
    default:
      return null;
  }
}
