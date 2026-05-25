import { useAppStore } from "../store";
import type { FreeStatsWindowYears } from "../types";
import { normalizeFreeStatsWindowYears } from "../types";

export default function FreeStatsWindowToggle({
  idPrefix = "free-v2",
}: {
  idPrefix?: string;
}) {
  const windowYears = useAppStore((s) => normalizeFreeStatsWindowYears(s.freeStatsWindowYears));
  const setWindowYears = useAppStore((s) => s.setFreeStatsWindowYears);

  const choice = (y: FreeStatsWindowYears, label: string) => {
    const active = windowYears === y;
    return (
      <button
        key={y}
        type="button"
        id={`${idPrefix}-win-${y}`}
        aria-pressed={active}
        onClick={() => setWindowYears(y)}
        className={`px-3 py-1 rounded-md text-[11px] font-semibold transition-colors ${
          active
            ? "bg-white text-blue-700 shadow-sm"
            : "text-slate-500 hover:text-slate-700"
        }`}
      >
        {label}
      </button>
    );
  };

  return (
    <div
      className="flex flex-wrap items-center gap-2"
      role="group"
      aria-label="계약일 기준 롤링 구간"
    >
      <span className="text-[11px] text-slate-500 shrink-0">구간</span>
      <div className="flex gap-0.5 bg-slate-100 rounded-lg p-0.5">
        {choice(3, "3년")}
        {choice(5, "5년")}
      </div>
    </div>
  );
}
