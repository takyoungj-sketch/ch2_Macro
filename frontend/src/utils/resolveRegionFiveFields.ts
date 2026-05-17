import type { RegionItem } from "../types";

function compact(s: string): string {
  return String(s ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
}

/** 빈 문자열 조각이면 해당 조건 무시 */
function includesLoose(haystack: string, needle: string): boolean {
  const n = needle.trim();
  if (!n) return true;
  const h = compact(haystack);
  const q = compact(n);
  if (!q) return true;
  return h.includes(q);
}

/** 흔한 약칭 → 법정 시도 명칭(코드 참조표 기준에 맞춤) */
const SIDO_CANON_FROM_ABBR = new Map<string, string>(
  Object.entries({
    충북: "충청북도",
    충남: "충청남도",
    경북: "경상북도",
    경남: "경상남도",
    전북: "전북특별자치도",
    전남: "전라남도",
    강원: "강원특별자치도",
    제주: "제주특별자치도",
    서울: "서울특별시",
    부산: "부산광역시",
    대구: "대구광역시",
    인천: "인천광역시",
    광주: "광주광역시",
    대전: "대전광역시",
    울산: "울산광역시",
    세종: "세종특별자치시",
    경기: "경기도",
  })
);

function matchSido(sidoName: string, q: string): boolean {
  if (!q.trim()) return true;
  if (includesLoose(sidoName, q)) return true;
  const cq = compact(q);
  const canon = SIDO_CANON_FROM_ABBR.get(cq);
  if (!canon) return false;
  return compact(sidoName) === compact(canon);
}

/** 쉼표·슬래시 등으로 여러 지명 입력 시 OR 조합 (복대동, 가경동) */
function splitNameTokens(raw: string): string[] {
  return raw
    .split(/[,，/|]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export type RegionFiveFields = readonly [string, string, string, string, string];

export function resolveBeopjungriFromFiveFields(
  regions: RegionItem[],
  parts: RegionFiveFields
): { codes: string[]; sampleLabel?: string } {
  const p1 = String(parts[0] ?? "").trim();
  const p2 = String(parts[1] ?? "").trim();
  const p3 = String(parts[2] ?? "").trim();
  const p4 = String(parts[3] ?? "").trim();
  const p5 = String(parts[4] ?? "").trim();

  if (!(p1 || p2 || p3 || p4 || p5)) {
    return { codes: [], sampleLabel: undefined };
  }

  const raw4 = p4;
  const raw5 = p5;

  /** ④⑤는 쉼표로 여러 이름 → 하나라도 읍면동/법정리명과 맞으면 포함 */
  const tokens4 = splitNameTokens(raw4);
  const tokens5 = splitNameTokens(raw5);

  const cand = regions.filter((r) => {
    if (!matchSido(r.sido_name, p1)) return false;
    const sigu = r.sigungu_name ?? "";
    if (!includesLoose(sigu, p2)) return false;
    if (!includesLoose(sigu, p3)) return false;

    const eup = r.eupmyeondong_name ?? "";
    const beop = r.beopjungri_name ?? "";

    if (tokens5.length > 0) {
      if (!tokens5.some((t) => includesLoose(beop, t))) return false;
      if (tokens4.length > 0 && !tokens4.some((t) => includesLoose(eup, t))) return false;
      return true;
    }

    if (tokens4.length > 0) {
      return tokens4.some((t) => includesLoose(eup, t) || includesLoose(beop, t));
    }

    return true;
  });

  const codes = [...new Set(cand.map((r) => String(r.beopjungri_code).trim()))].sort((a, b) =>
    a.localeCompare(b, "ko-KR")
  );

  const sampleLabel =
    cand.length > 0
      ? `${cand[0].sido_name} ${cand[0].sigungu_name} ${cand[0].eupmyeondong_name} ${cand[0].beopjungri_name}`
      : undefined;

  return { codes, sampleLabel };
}
