import { useMemo } from "react";
import { useAppStore } from "../store";
import { resolveProfileRegionFromTier } from "../utils/upperTierStats";

/**
 * 신규 독립 지역 프로필 앱(/profile/)으로 이동하는 딥링크 — D-027 §12.
 * 단일 지역(시군구/읍면동/법정동·리 승격)이 해석될 때만 노출.
 */
export default function RegionalProfileLink() {
  const tierSelection = useAppStore((s) => s.tierSelection);
  const target = useMemo(() => resolveProfileRegionFromTier(tierSelection), [tierSelection]);

  if (!target) return null;

  const href = `/profile/?region_level=${target.level}&region_code=${target.code}`;
  return (
    <a
      href={href}
      className="inline-flex shrink-0 items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
    >
      지역 프로필 →
    </a>
  );
}
