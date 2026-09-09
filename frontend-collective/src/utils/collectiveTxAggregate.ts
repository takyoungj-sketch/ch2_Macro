import type { AssetType, CollectiveTransactionRow } from "../types";
import {
  collectiveTxDongCell,
  formatCollectiveDealType,
  type CollectiveTxSortKey,
} from "./collectiveTxDisplay";
import {
  txContractYearLabel,
  type TxAggregateDimSpec,
  type TxCrossPreset,
} from "./txAggregate";

export type CollectiveTxAggregateDim =
  | "building"
  | "dong"
  | "floor"
  | "deal_type"
  | "contract_year"
  | "buyer_type"
  | "seller_type";

export function collectiveTxAggregateDimensions(
  assetType: AssetType,
  showBuilding: boolean,
): TxAggregateDimSpec<CollectiveTxAggregateDim>[] {
  const dongLabel = assetType === "presale" ? "권리" : "동";
  const dims: TxAggregateDimSpec<CollectiveTxAggregateDim>[] = [];
  if (showBuilding) {
    dims.push({ id: "building", label: "단지", hint: "코호트 단지별 비교" });
  }
  dims.push(
    { id: "dong", label: dongLabel, hint: "동(또는 분양 권리)별 비교" },
    { id: "floor", label: "층" },
    { id: "deal_type", label: "거래유형" },
    { id: "contract_year", label: "계약연도" },
    { id: "buyer_type", label: "매수" },
    { id: "seller_type", label: "매도" },
  );
  return dims;
}

export function collectiveTxCrossPresets(
  assetType: AssetType,
  showBuilding: boolean,
): TxCrossPreset<CollectiveTxAggregateDim>[] {
  const dongLabel = assetType === "presale" ? "권리" : "동";
  const presets: TxCrossPreset<CollectiveTxAggregateDim>[] = [
    { id: "dong_year", label: `${dongLabel} × 연도`, row: "dong", col: "contract_year" },
    { id: "dong_deal", label: `${dongLabel} × 거래유형`, row: "dong", col: "deal_type" },
    { id: "dong_floor", label: `${dongLabel} × 층`, row: "dong", col: "floor" },
  ];
  if (showBuilding) {
    presets.unshift({
      id: "bldg_year",
      label: "단지 × 연도",
      row: "building",
      col: "contract_year",
    });
  }
  return presets;
}

export function collectiveTxDimensionValue(
  item: CollectiveTransactionRow,
  dim: CollectiveTxAggregateDim,
  assetType: AssetType,
): string {
  switch (dim) {
    case "building":
      return item.display_name?.trim() || "—";
    case "dong":
      return collectiveTxDongCell(item, assetType);
    case "floor":
      return item.floor == null ? "—" : String(item.floor);
    case "deal_type":
      return formatCollectiveDealType(item.deal_type);
    case "contract_year":
      return txContractYearLabel(item);
    case "buyer_type":
      return item.buyer_type?.trim() || "—";
    case "seller_type":
      return item.seller_type?.trim() || "—";
    default:
      return "—";
  }
}

export function collectiveTxDrillDownKey(
  dim: CollectiveTxAggregateDim,
): CollectiveTxSortKey {
  if (dim === "contract_year") return "contract_date";
  return dim;
}

export function collectiveTxUnitPrice(item: CollectiveTransactionRow): number | null {
  return item.unit_price ?? null;
}

export function collectiveTxArea(item: CollectiveTransactionRow): number | null {
  return item.exclusive_area ?? null;
}
