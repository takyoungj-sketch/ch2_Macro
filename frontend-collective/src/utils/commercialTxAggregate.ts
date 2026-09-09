import type { CommercialTransactionRow } from "../types";
import {
  commercialTxDongCell,
  commercialTxRoadWidth,
  type CommercialTxSortKey,
} from "./commercialTxDisplay";
import {
  txContractYearLabel,
  type TxAggregateDimSpec,
  type TxCrossPreset,
} from "./txAggregate";

export type CommercialTxAggregateDim =
  | "dong"
  | "zone_type"
  | "building_use"
  | "road_width"
  | "area_bucket"
  | "contract_year";

export function commercialTxAggregateDimensions(
  isShop: boolean,
): TxAggregateDimSpec<CommercialTxAggregateDim>[] {
  const dims: TxAggregateDimSpec<CommercialTxAggregateDim>[] = [
    { id: "dong", label: "동", hint: "읍·면·동별 비교" },
    { id: "zone_type", label: "용도지역" },
    { id: "building_use", label: "건축물용도" },
    { id: "road_width", label: "도로폭" },
    { id: "contract_year", label: "계약연도" },
  ];
  if (!isShop) {
    dims.splice(4, 0, { id: "area_bucket", label: "면적구간" });
  }
  return dims;
}

export function commercialTxCrossPresets(
  isShop: boolean,
): TxCrossPreset<CommercialTxAggregateDim>[] {
  const presets: TxCrossPreset<CommercialTxAggregateDim>[] = [
    { id: "dong_year", label: "동 × 연도", row: "dong", col: "contract_year" },
    { id: "dong_zone", label: "동 × 용도지역", row: "dong", col: "zone_type" },
    { id: "zone_year", label: "용도지역 × 연도", row: "zone_type", col: "contract_year" },
    { id: "road_year", label: "도로폭 × 연도", row: "road_width", col: "contract_year" },
  ];
  if (!isShop) {
    presets.push({
      id: "area_year",
      label: "면적구간 × 연도",
      row: "area_bucket",
      col: "contract_year",
    });
  }
  return presets;
}

export function commercialTxDimensionValue(
  item: CommercialTransactionRow,
  dim: CommercialTxAggregateDim,
): string {
  switch (dim) {
    case "dong":
      return commercialTxDongCell(item);
    case "zone_type":
      return item.zone_type?.trim() || "—";
    case "building_use":
      return item.building_use?.trim() || "—";
    case "road_width":
      return commercialTxRoadWidth(item);
    case "area_bucket":
      return item.area_bucket_label?.trim() || "—";
    case "contract_year":
      return txContractYearLabel(item);
    default:
      return "—";
  }
}

export function commercialTxDrillDownKey(
  dim: CommercialTxAggregateDim,
): CommercialTxSortKey {
  if (dim === "contract_year") return "contract_date";
  return dim;
}

export function commercialTxUnitPrice(item: CommercialTransactionRow): number | null {
  return item.unit_price ?? null;
}

export function commercialTxArea(item: CommercialTransactionRow): number | null {
  return item.gross_area ?? null;
}
