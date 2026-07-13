/** 복합부동산 자산유형 — 단일·복수(콤마) 또는 all */

export type BuiltAssetKind = "commercial" | "factory" | "detached";
/** API에 넘기는 값: 단일 / "a,b" / "all" */
export type AssetType = BuiltAssetKind | "all" | string;

export const BUILT_ASSET_KINDS: BuiltAssetKind[] = ["commercial", "factory", "detached"];

export const ASSET_KIND_LABELS: Record<BuiltAssetKind, string> = {
  commercial: "상업(일반상가)",
  factory: "공장창고",
  detached: "단독다가구",
};

export function parseAssetKinds(assetType: string | undefined | null): BuiltAssetKind[] {
  if (!assetType || assetType === "all") return [...BUILT_ASSET_KINDS];
  const parts = assetType.split(/[,|]/).map((s) => s.trim()).filter(Boolean);
  const out: BuiltAssetKind[] = [];
  for (const p of parts) {
    if ((BUILT_ASSET_KINDS as string[]).includes(p) && !out.includes(p as BuiltAssetKind)) {
      out.push(p as BuiltAssetKind);
    }
  }
  return out.length ? out : ["commercial"];
}

export function encodeAssetKinds(kinds: BuiltAssetKind[]): string {
  const ordered = BUILT_ASSET_KINDS.filter((k) => kinds.includes(k));
  if (ordered.length === 0) return "commercial";
  if (ordered.length === BUILT_ASSET_KINDS.length) return "all";
  return ordered.join(",");
}

export function isUnifiedAsset(assetType: string | undefined | null): boolean {
  if (!assetType) return false;
  if (assetType === "all") return true;
  return parseAssetKinds(assetType).length >= 2;
}

export function isOnlyDetached(assetType: string | undefined | null): boolean {
  const kinds = parseAssetKinds(assetType);
  return kinds.length === 1 && kinds[0] === "detached";
}

export function toggleAssetKind(prev: BuiltAssetKind[], kind: BuiltAssetKind): BuiltAssetKind[] {
  if (prev.includes(kind)) {
    if (prev.length <= 1) return prev;
    return prev.filter((k) => k !== kind);
  }
  return BUILT_ASSET_KINDS.filter((k) => k === kind || prev.includes(k));
}

export function assetTypeLabel(assetType: string): string {
  if (assetType === "all") return "3유형";
  const kinds = parseAssetKinds(assetType);
  if (kinds.length === 1) return ASSET_KIND_LABELS[kinds[0]];
  return kinds.map((k) => ASSET_KIND_LABELS[k].replace(/\(.*\)/, "").trim()).join("·");
}
