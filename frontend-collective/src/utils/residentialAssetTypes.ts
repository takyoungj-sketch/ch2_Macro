/** 집합 주거용 자산유형 — 단일·복수(콤마) 또는 all */

import type { AssetType } from "../types";
import { ASSET_LABELS } from "../types";

export type ResidentialAssetKind = AssetType;

export const RESIDENTIAL_ASSET_KINDS: ResidentialAssetKind[] = [
  "apartment",
  "rowhouse",
  "officetel",
  "presale",
];

export const RESIDENTIAL_KIND_LABELS: Record<ResidentialAssetKind, string> = {
  ...ASSET_LABELS,
};

export function parseResidentialAssetKinds(
  assetType: string | undefined | null,
): ResidentialAssetKind[] {
  if (!assetType || assetType === "all") return [...RESIDENTIAL_ASSET_KINDS];
  const parts = assetType.split(/[,|]/).map((s) => s.trim()).filter(Boolean);
  const out: ResidentialAssetKind[] = [];
  for (const p of parts) {
    if ((RESIDENTIAL_ASSET_KINDS as string[]).includes(p) && !out.includes(p as ResidentialAssetKind)) {
      out.push(p as ResidentialAssetKind);
    }
  }
  return out.length ? out : ["apartment"];
}

export function encodeResidentialAssetKinds(kinds: ResidentialAssetKind[]): string {
  const ordered = RESIDENTIAL_ASSET_KINDS.filter((k) => kinds.includes(k));
  if (ordered.length === 0) return "apartment";
  if (ordered.length === RESIDENTIAL_ASSET_KINDS.length) return "all";
  return ordered.join(",");
}

export function isMultiResidentialAsset(assetType: string | undefined | null): boolean {
  if (!assetType) return false;
  if (assetType === "all") return true;
  return parseResidentialAssetKinds(assetType).length >= 2;
}

export function toggleResidentialAssetKind(
  prev: ResidentialAssetKind[],
  kind: ResidentialAssetKind,
): ResidentialAssetKind[] {
  if (prev.includes(kind)) {
    if (prev.length <= 1) return prev;
    return prev.filter((k) => k !== kind);
  }
  return RESIDENTIAL_ASSET_KINDS.filter((k) => k === kind || prev.includes(k));
}

export function residentialAssetTypeLabel(assetType: string): string {
  if (assetType === "all") return "4유형";
  const kinds = parseResidentialAssetKinds(assetType);
  if (kinds.length === 1) return RESIDENTIAL_KIND_LABELS[kinds[0]];
  return kinds.map((k) => RESIDENTIAL_KIND_LABELS[k]).join("·");
}
