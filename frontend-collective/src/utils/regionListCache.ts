export const REGION_LIST_STALE_MS = 60 * 60 * 1000;

export const PREFETCH_SIDO_FIRST = ["서울특별시", "경기도", "인천광역시", "충청북도"];

export function orderedSidoPrefetchList(sidos: string[]): string[] {
  const first = PREFETCH_SIDO_FIRST.filter((s) => sidos.includes(s));
  const rest = sidos.filter((s) => !PREFETCH_SIDO_FIRST.includes(s));
  return [...first, ...rest];
}

export function mergeRegionChipOptions<T extends { name: string; parent?: string | null; count: number }>(
  names: T[] | undefined,
  counted: T[] | undefined,
): T[] {
  if (!names?.length) return counted ?? [];
  if (!counted?.length) return names;
  const key = (o: T) => `${o.parent ?? ""}|${o.name}`;
  const map = new Map(counted.map((c) => [key(c), c]));
  return names.map((n) => map.get(key(n)) ?? n);
}
