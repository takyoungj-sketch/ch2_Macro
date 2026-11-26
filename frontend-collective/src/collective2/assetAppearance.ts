/** 집합2 유형 색. 공개 화면은 이 값을 받지 않는다. */

export type CollectiveAssetKind =
  | "apartment"
  | "rowhouse"
  | "officetel"
  | "presale"
  | "collective_shop"
  | "collective_factory";

export type AssetAppearance = {
  label: string;
  ink: string;
  glow: string;
};

export const ASSET_APPEARANCE: Record<CollectiveAssetKind, AssetAppearance> = {
  apartment: { label: "아파트", ink: "#854D0E", glow: "#FDE68A" },
  rowhouse: { label: "연립·다세대", ink: "#3F6212", glow: "#BEF264" },
  officetel: { label: "오피스텔", ink: "#6D28D9", glow: "#C4B5FD" },
  presale: { label: "분양권", ink: "#9D174D", glow: "#F9A8D4" },
  collective_shop: { label: "집합상가", ink: "#075985", glow: "#7DD3FC" },
  collective_factory: { label: "집합공장", ink: "#115E59", glow: "#5EEAD4" },
};

export function appearanceFor(assetType: string | null | undefined): AssetAppearance | undefined {
  if (!assetType || !(assetType in ASSET_APPEARANCE)) return undefined;
  return ASSET_APPEARANCE[assetType as CollectiveAssetKind];
}

export function assetColorVars(assetType: string | null | undefined): Record<string, string> | undefined {
  const look = appearanceFor(assetType);
  if (!look) return undefined;
  return { "--asset-ink": look.ink, "--asset-glow": look.glow };
}
