/** 집합 상업·업무 자산유형 — 단일·복수(콤마) 또는 all */

import type { CommercialAssetType } from "../types";
import { COMMERCIAL_ASSET_LABELS } from "../types";

export type CommercialAssetKind = CommercialAssetType;

export const COMMERCIAL_ASSET_KINDS: CommercialAssetKind[] = [
  "collective_shop",
  "collective_factory",
];

export const COMMERCIAL_KIND_LABELS: Record<CommercialAssetKind, string> = {
  ...COMMERCIAL_ASSET_LABELS,
};

export function parseCommercialAssetKinds(
  assetType: string | undefined | null,
): CommercialAssetKind[] {
  if (!assetType || assetType === "all") return [...COMMERCIAL_ASSET_KINDS];
  const parts = assetType.split(/[,|]/).map((s) => s.trim()).filter(Boolean);
  const out: CommercialAssetKind[] = [];
  for (const p of parts) {
    if ((COMMERCIAL_ASSET_KINDS as string[]).includes(p) && !out.includes(p as CommercialAssetKind)) {
      out.push(p as CommercialAssetKind);
    }
  }
  return out.length ? out : ["collective_shop"];
}

export function encodeCommercialAssetKinds(kinds: CommercialAssetKind[]): string {
  const ordered = COMMERCIAL_ASSET_KINDS.filter((k) => kinds.includes(k));
  if (ordered.length === 0) return "collective_shop";
  if (ordered.length === COMMERCIAL_ASSET_KINDS.length) return "all";
  return ordered.join(",");
}

export function isMultiCommercialAsset(assetType: string | undefined | null): boolean {
  if (!assetType) return false;
  if (assetType === "all") return true;
  return parseCommercialAssetKinds(assetType).length >= 2;
}

export function toggleCommercialAssetKind(
  prev: CommercialAssetKind[],
  kind: CommercialAssetKind,
): CommercialAssetKind[] {
  if (prev.includes(kind)) {
    if (prev.length <= 1) return prev;
    return prev.filter((k) => k !== kind);
  }
  return COMMERCIAL_ASSET_KINDS.filter((k) => k === kind || prev.includes(k));
}

export function commercialEncodedAssetTypeLabel(assetType: string): string {
  if (assetType === "all") return "2유형";
  const kinds = parseCommercialAssetKinds(assetType);
  if (kinds.length === 1) return COMMERCIAL_KIND_LABELS[kinds[0]];
  return kinds.map((k) => COMMERCIAL_KIND_LABELS[k]).join("·");
}
