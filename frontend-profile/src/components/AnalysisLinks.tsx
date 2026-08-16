import { deepLinkTo } from "../utils/deepLinks";

const LINKS: { app: "land" | "built" | "collective" | "rent"; label: string }[] = [
  { app: "land", label: "토지" },
  { app: "built", label: "복합" },
  { app: "collective", label: "집합" },
  { app: "rent", label: "임대" },
];

export default function AnalysisLinks({
  regionLevel,
  regionCode,
}: {
  regionLevel: string;
  regionCode: string;
}) {
  return (
    <div className="card px-5 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">이 지역 상세분석</span>
        {LINKS.map(({ app, label }) => (
          <a
            key={app}
            href={deepLinkTo(app, { regionLevel, regionCode })}
            className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-indigo-400"
          >
            {label} →
          </a>
        ))}
      </div>
    </div>
  );
}
