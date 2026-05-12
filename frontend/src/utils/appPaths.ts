/** React Router basename과 동일한 Vite BASE_URL 기준 비교 페이지 경로 */
export function resolveCompareHref(): string {
  const raw = import.meta.env.BASE_URL;
  if (!raw || raw === "/") return "/compare";
  const base = raw.endsWith("/") ? raw.slice(0, -1) : raw;
  return `${base}/compare`;
}
