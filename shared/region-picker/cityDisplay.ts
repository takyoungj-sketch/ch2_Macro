import { extractCityFirstToken } from "./cityBucket";
import type { RegionNameInfo } from "./types";

/** 의사-시(city) 5자리 버킷의 짧은 이름 — 예: 청주시 */
export function cityShortLabel(name: RegionNameInfo | null, cityCode: string): string {
  if (name) {
    const tok = extractCityFirstToken(name.sigungu_name);
    if (tok) return tok;
  }
  return cityCode;
}

/** 의사-시 전체 라벨 — 예: 충청북도 청주시 */
export function cityFullLabel(name: RegionNameInfo | null, cityCode: string): string {
  if (name) {
    const tok = extractCityFirstToken(name.sigungu_name);
    if (tok) return `${name.sido_name} ${tok}`.trim();
  }
  return cityCode;
}
