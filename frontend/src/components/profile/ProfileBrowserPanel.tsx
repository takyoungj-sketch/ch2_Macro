import { useMemo, useState } from "react";
import {
  filterProfileFeatures,
  groupProfileFeatures,
  parseProfileFeatures,
  type ParsedProfileFeature,
} from "../../utils/profileFeatureDisplay";

function FeatureRow({ feature }: { feature: ParsedProfileFeature }) {
  const isCount = feature.spec.valueKind === "count";
  const dimmed =
    !isCount && feature.reliability != null && !feature.reliability.reliable;

  return (
    <div
      className={`py-2.5 border-b border-slate-100 dark:border-slate-700/80 last:border-0 ${
        dimmed ? "opacity-75" : ""
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="min-w-0 flex-1">
          <p className={`text-sm ${isCount ? "font-bold" : "font-medium"} text-slate-800 dark:text-slate-100`}>
            {feature.spec.labelKo}
          </p>
          <p className="text-[10px] font-mono text-slate-400 truncate">{feature.key}</p>
        </div>
        <div className="text-right shrink-0">
          <p
            className={`tabular-nums ${
              isCount
                ? "text-base font-bold text-slate-900 dark:text-white"
                : "text-sm font-semibold text-slate-700 dark:text-slate-200"
            }`}
          >
            {feature.formatted}
          </p>
          {feature.reliability && (isCount || feature.spec.countKey) ? (
            <p className="text-[10px] text-slate-500 mt-0.5">
              {feature.reliability.label}
              {feature.reliability.warn ? (
                <span className="text-amber-700 dark:text-amber-400 ml-1">⚠ {feature.reliability.warn}</span>
              ) : null}
            </p>
          ) : null}
        </div>
      </div>
      {(feature.spec.sourceTable || feature.spec.sourceDomain) && (
        <p className="text-[10px] text-slate-400 mt-1.5">
          Source: {feature.spec.sourceTable}
          {feature.spec.sourceDomain ? ` · ${feature.spec.sourceDomain}` : ""}
        </p>
      )}
    </div>
  );
}

export default function ProfileBrowserPanel({
  features,
}: {
  features: Record<string, number>;
}) {
  const [query, setQuery] = useState("");

  const parsed = useMemo(() => parseProfileFeatures(features), [features]);
  const filtered = useMemo(() => filterProfileFeatures(parsed, query), [parsed, query]);
  const groups = useMemo(() => groupProfileFeatures(filtered), [filtered]);

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="profile-feature-search" className="sr-only">
          Feature 검색
        </label>
        <input
          id="profile-feature-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="검색: population, apartment, land, industrial …"
          className="w-full rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-800 dark:text-slate-100 placeholder:text-slate-400"
        />
        <p className="text-[10px] text-slate-400 mt-1">
          {filtered.length}/{parsed.length} feature
        </p>
      </div>

      {groups.length === 0 ? (
        <p className="text-sm text-slate-500">검색 결과가 없습니다.</p>
      ) : (
        groups.map((group) => (
          <section
            key={group.categoryId}
            className="rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden"
          >
            <h3 className="text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-3 py-2 border-b border-slate-200 dark:border-slate-700">
              ■ {group.categoryLabel}
            </h3>
            <div className="px-3">
              {group.features.map((f) => (
                <FeatureRow key={f.key} feature={f} />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
