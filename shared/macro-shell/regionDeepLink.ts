export type RegionDeepLinkLevel =
  | "sido"
  | "sigungu"
  | "eupmyeondong"
  | "beopjungri"
  | "city";

export type RegionDeepLinkApp = "land" | "built" | "collective" | "rent" | "profile";

export type RegionDeepLink = {
  regionLevel: RegionDeepLinkLevel;
  regionCode: string;
};

const LEVELS = new Set<string>(["sido", "sigungu", "eupmyeondong", "beopjungri", "city"]);

const APP_BASE: Record<RegionDeepLinkApp, string> = {
  land: "/land/",
  built: "/built/",
  collective: "/collective/residential/",
  rent: "/rent/",
  profile: "/profile/",
};

export function parseRegionDeepLink(search = typeof window === "undefined" ? "" : window.location.search): RegionDeepLink | null {
  const qs = new URLSearchParams(search);
  const level = (qs.get("region_level") || "").trim();
  const code = (qs.get("region_code") || "").trim();
  if (!LEVELS.has(level) || !code) return null;
  return { regionLevel: level as RegionDeepLinkLevel, regionCode: code };
}

export function buildAppDeepLink(
  app: RegionDeepLinkApp,
  params: { regionLevel: string; regionCode: string },
): string {
  const qs = new URLSearchParams({
    region_level: params.regionLevel,
    region_code: params.regionCode,
  });
  return `${APP_BASE[app]}?${qs.toString()}`;
}

export type RegionNameRow = {
  sido_name: string;
  sigungu_name: string;
  eupmyeondong_name: string;
  beopjungri_name: string;
};

export async function fetchRegionNameRow(
  level: string,
  code: string,
): Promise<RegionNameRow | null> {
  const params = new URLSearchParams({ limit: "1" });
  if (level === "beopjungri") params.set("beopjungri_code", code);
  else if (level === "eupmyeondong") params.set("eupmyeondong_code", code);
  else if (level === "sigungu" || level === "city") params.set("sigungu_code", code);
  else return null;
  const res = await fetch(`/api/free/v2/regions?${params.toString()}`);
  if (!res.ok) return null;
  const rows = (await res.json()) as RegionNameRow[];
  return rows[0] ?? null;
}

export function matchNamedOption(options: readonly string[], name: string): string | undefined {
  const n = name.trim();
  if (!n) return undefined;
  if (options.includes(n)) return n;
  return options.find((o) => o === n || o.endsWith(n) || o.includes(n));
}
