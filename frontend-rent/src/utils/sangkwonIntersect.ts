import booleanIntersects from "@turf/boolean-intersects";
import booleanTouches from "@turf/boolean-touches";
import bbox from "@turf/bbox";
import type { SangkwonHit } from "../types";

export function filterAdminFeaturesByCodes(
  features: GeoJSON.Feature[],
  selectedCodes: string[],
): GeoJSON.Feature[] {
  const wanted = selectedCodes.map((c) => String(c ?? "").trim()).filter(Boolean);
  if (!wanted.length) return [];
  return features.filter((f) => {
    const code = String((f.properties as { ch2_code?: string } | null)?.ch2_code ?? "").trim();
    if (!code) return false;
    return wanted.some((a) => code === a || code.startsWith(a) || a.startsWith(code));
  });
}

/** 행정 폴리곤과 면이 겹치는 상권. 경계만 맞닿은 경우는 제외. */
export function sangkwonHitsForAdmin(
  adminFeatures: GeoJSON.Feature[],
  sangkwonFc: GeoJSON.FeatureCollection | null | undefined,
): SangkwonHit[] {
  if (!sangkwonFc?.features.length || adminFeatures.length === 0) return [];
  const adminBoxes = adminFeatures
    .filter((f) => f.geometry)
    .map((f) => {
      try {
        return { feat: f, box: bbox(f) as [number, number, number, number] };
      } catch {
        return null;
      }
    })
    .filter((x): x is { feat: GeoJSON.Feature; box: [number, number, number, number] } => x != null);
  if (!adminBoxes.length) return [];
  const hits: SangkwonHit[] = [];
  for (const feat of sangkwonFc.features) {
    const name = String(feat.properties?.sec_nm ?? "").trim();
    if (!name || !feat.geometry) continue;
    let skBox: [number, number, number, number];
    try {
      skBox = bbox(feat) as [number, number, number, number];
    } catch {
      continue;
    }
    let score = 0;
    let ok = false;
    for (const admin of adminBoxes) {
      const [aw, as, ae, an] = admin.box;
      const [bw, bs, be, bn] = skBox;
      const w = Math.min(ae, be) - Math.max(aw, bw);
      const h = Math.min(an, bn) - Math.max(as, bs);
      if (w <= 0 || h <= 0) continue;
        try {
          if (!booleanIntersects(feat, admin.feat)) continue;
          if (booleanTouches(feat, admin.feat)) continue;
        } catch {
          continue;
        }
      ok = true;
      score += w * h;
    }
    if (ok) {
      hits.push({
        sec_nm: name,
        sido: String(feat.properties?.sido ?? ""),
        buld_nm: String(feat.properties?.buld_nm ?? ""),
        overlapScore: score,
      });
    }
  }
  hits.sort((a, b) => b.overlapScore - a.overlapScore || a.sec_nm.localeCompare(b.sec_nm, "ko"));
  return hits;
}
