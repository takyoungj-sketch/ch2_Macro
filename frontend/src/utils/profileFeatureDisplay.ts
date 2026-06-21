import {
  getProfileFeatureSpec,
  MIN_RELIABLE_PROFILE_COUNT,
  PROFILE_CATEGORIES,
  PROFILE_FEATURE_SPECS,
  type ProfileFeatureCategoryId,
  type ProfileFeatureSpec,
  type ProfileValueKind,
} from "../constants/profileFeatureCatalog";

export interface SampleReliability {
  stars: number;
  label: string;
  warn?: string;
  reliable: boolean;
}

export interface ParsedProfileFeature {
  key: string;
  value: number;
  spec: ProfileFeatureSpec;
  formatted: string;
  countForReliability: number | null;
  reliability: SampleReliability | null;
}

export interface ProfileFeatureGroup {
  categoryId: ProfileFeatureCategoryId;
  categoryLabel: string;
  features: ParsedProfileFeature[];
}

export function sampleReliability(count: number | null | undefined): SampleReliability {
  if (count == null || count <= 0) {
    return { stars: 0, label: "—", warn: "데이터 없음", reliable: false };
  }
  if (count >= 50) {
    return { stars: 5, label: "★★★★★", reliable: true };
  }
  if (count >= MIN_RELIABLE_PROFILE_COUNT) {
    return { stars: 3, label: "★★★☆☆", reliable: true };
  }
  if (count >= 5) {
    return { stars: 2, label: "★★☆☆☆", warn: "표본 주의", reliable: false };
  }
  return { stars: 1, label: "★☆☆☆☆", warn: "표본 부족", reliable: false };
}

export function formatProfileValue(kind: ProfileValueKind, value: number, unit?: string): string {
  switch (kind) {
    case "count":
      return `${Math.round(value).toLocaleString("ko-KR")}건`;
    case "money_sqm":
      return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 1 })} 만원/㎡`;
    case "population":
      return `${Math.round(value).toLocaleString("ko-KR")}명`;
    case "density":
      return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 1 })} ${unit ?? "명/km²"}`;
    case "ratio":
      return `${(value * 100).toFixed(1)}%`;
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    default:
      return value.toLocaleString("ko-KR", { maximumFractionDigits: 4 });
  }
}

function inferSpecForUnknownKey(key: string): ProfileFeatureSpec {
  if (key.startsWith("ratio_")) {
    return {
      key,
      category: "composition",
      labelKo: key,
      valueKind: "ratio",
      sourceTable: "land_upper_stats_v2",
      sortOrder: 999,
    };
  }
  if (key.includes("_count")) {
    return {
      key,
      category: "other",
      labelKo: key,
      valueKind: "count",
      sortOrder: 999,
    };
  }
  return {
    key,
    category: "other",
    labelKo: key,
    valueKind: "number",
    sortOrder: 999,
  };
}

export function parseProfileFeatures(
  features: Record<string, number>
): ParsedProfileFeature[] {
  const knownKeys = new Set(PROFILE_FEATURE_SPECS.map((s) => s.key));
  const allKeys = [
    ...PROFILE_FEATURE_SPECS.map((s) => s.key).filter((k) => k in features),
    ...Object.keys(features).filter((k) => !knownKeys.has(k)),
  ];

  return allKeys
    .map((key) => {
      const raw = features[key];
      const num = typeof raw === "number" ? raw : Number(raw);
      if (!Number.isFinite(num)) return null;
      const spec = getProfileFeatureSpec(key) ?? inferSpecForUnknownKey(key);
      const countForReliability =
        spec.valueKind === "count"
          ? num
          : spec.countKey != null && features[spec.countKey] != null
            ? Number(features[spec.countKey])
            : null;
      const reliability =
        spec.valueKind === "count" || spec.countKey
          ? sampleReliability(countForReliability)
          : null;
      return {
        key,
        value: num,
        spec,
        formatted: formatProfileValue(spec.valueKind, num, spec.unit),
        countForReliability,
        reliability,
      };
    })
    .filter((x): x is ParsedProfileFeature => x != null);
}

export function groupProfileFeatures(parsed: ParsedProfileFeature[]): ProfileFeatureGroup[] {
  const byCat = new Map<ProfileFeatureCategoryId, ParsedProfileFeature[]>();
  for (const p of parsed) {
    const list = byCat.get(p.spec.category) ?? [];
    list.push(p);
    byCat.set(p.spec.category, list);
  }

  return PROFILE_CATEGORIES.filter((c) => byCat.has(c.id))
    .map((c) => ({
      categoryId: c.id,
      categoryLabel: c.labelKo,
      features: (byCat.get(c.id) ?? []).sort(
        (a, b) => a.spec.sortOrder - b.spec.sortOrder || a.key.localeCompare(b.key)
      ),
    }))
    .filter((g) => g.features.length > 0);
}

export function filterProfileFeatures(
  parsed: ParsedProfileFeature[],
  query: string
): ParsedProfileFeature[] {
  const q = query.trim().toLowerCase();
  if (!q) return parsed;
  return parsed.filter(
    (p) =>
      p.key.toLowerCase().includes(q) ||
      p.spec.labelKo.toLowerCase().includes(q) ||
      (p.spec.sourceDomain?.toLowerCase().includes(q) ?? false) ||
      (p.spec.category.toLowerCase().includes(q) ?? false)
  );
}

export function getFeatureValue(
  features: Record<string, number>,
  key: string
): number | null {
  const v = features[key];
  if (v == null || !Number.isFinite(Number(v))) return null;
  return Number(v);
}

/** 요약 카드용 간단 해석 */
export interface ProfileInsights {
  regionCharacter: string;
  landMarketRank: string | null;
  apartmentActivity: string | null;
  topComposition: string | null;
  cautionLines: string[];
}

export function buildProfileInsights(features: Record<string, number>): ProfileInsights {
  const cautionLines: string[] = [];

  const aptCount = getFeatureValue(features, "apartment_count");
  const landResCount = getFeatureValue(features, "land_residential_count");
  const landComCount = getFeatureValue(features, "land_commercial_count");
  const landIndCount = getFeatureValue(features, "land_industrial_count");

  if (landResCount != null && landResCount < MIN_RELIABLE_PROFILE_COUNT) {
    cautionLines.push(`토지(주거) 거래 ${landResCount}건 — 단가 해석 주의`);
  }
  if (aptCount != null && aptCount < MIN_RELIABLE_PROFILE_COUNT) {
    cautionLines.push(`아파트 거래 ${aptCount}건 — 시장 지표 주의`);
  }

  const resRatio = getFeatureValue(features, "ratio_residential_zone");
  const comRatio = getFeatureValue(features, "ratio_commercial_zone");
  let regionCharacter = "혼합 지역";
  if (resRatio != null && comRatio != null) {
    if (resRatio > 0.45 && resRatio > comRatio) regionCharacter = "주거 중심";
    else if (comRatio > 0.25 && comRatio > resRatio) regionCharacter = "상업·업무 성격";
    else if ((getFeatureValue(features, "ratio_agri_zone") ?? 0) > 0.35) {
      regionCharacter = "농림·외곽 성격";
    }
  }

  const landMeans = [
    { label: "주거", mean: getFeatureValue(features, "land_residential_mean"), n: landResCount },
    { label: "상업", mean: getFeatureValue(features, "land_commercial_mean"), n: landComCount },
    { label: "공업", mean: getFeatureValue(features, "land_industrial_mean"), n: landIndCount },
  ].filter((x) => x.mean != null && x.n != null && x.n > 0);
  landMeans.sort((a, b) => (b.mean ?? 0) - (a.mean ?? 0));
  const landMarketRank =
    landMeans.length >= 2
      ? landMeans.map((x) => x.label).join(" > ")
      : landMeans.length === 1
        ? `${landMeans[0]!.label} 거래 위주`
        : null;

  let apartmentActivity: string | null = null;
  if (aptCount != null) {
    if (aptCount >= 500) apartmentActivity = "매우 활발";
    else if (aptCount >= 100) apartmentActivity = "활발";
    else if (aptCount >= MIN_RELIABLE_PROFILE_COUNT) apartmentActivity = "보통";
    else apartmentActivity = "저조";
  }

  const compEntries = [
    ["주거 용도", getFeatureValue(features, "ratio_residential_zone")],
    ["상업 용도", getFeatureValue(features, "ratio_commercial_zone")],
    ["대지", getFeatureValue(features, "ratio_land_danji")],
    ["전·답", getFeatureValue(features, "ratio_land_rice")],
    ["임야", getFeatureValue(features, "ratio_land_forest")],
  ].filter(([, v]) => v != null) as [string, number][];
  compEntries.sort((a, b) => b[1] - a[1]);
  const topComposition =
    compEntries.length > 0
      ? `${compEntries[0]![0]} ${(compEntries[0]![1] * 100).toFixed(0)}%`
      : null;

  return {
    regionCharacter,
    landMarketRank,
    apartmentActivity,
    topComposition,
    cautionLines,
  };
}
