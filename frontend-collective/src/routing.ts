/** `/collective/` SPA 하위 경로 — residential | commercial | (landing) */
export function getCollectiveSegment(): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  const pathname = window.location.pathname.replace(/\/$/, "") || "/";
  if (pathname === base || pathname === `${base}/`) {
    return "";
  }
  if (pathname.startsWith(`${base}/`)) {
    return pathname.slice(base.length + 1).split("/")[0] ?? "";
  }
  return "";
}

export function redirectToCollectiveSubpath(subpath: "residential" | "commercial") {
  const base = import.meta.env.BASE_URL.replace(/\/?$/, "/");
  window.location.replace(`${window.location.origin}${base}${subpath}/`);
}
