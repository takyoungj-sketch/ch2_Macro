import { useMemo } from "react";
import {
  buildProfileInsights,
  groupProfileFeatures,
  parseProfileFeatures,
  type ParsedProfileFeature,
} from "../../utils/profileFeatureDisplay";

function MetricBlock({ feature }: { feature: ParsedProfileFeature }) {
  const isCount = feature.spec.valueKind === "count";
  const dimmed =
    !isCount && feature.reliability != null && !feature.reliability.reliable;

  return (
    <div className={dimmed ? "opacity-70" : undefined}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">{feature.spec.labelKo}</span>
        {feature.reliability && !isCount ? (
          <span className="text-[10px] text-slate-400" title={feature.reliability.warn}>
            {feature.reliability.label}
          </span>
        ) : null}
      </div>
      <p
        className={
          isCount
            ? "text-lg font-bold tabular-nums text-slate-900 dark:text-slate-50"
            : "text-base font-semibold tabular-nums text-slate-800 dark:text-slate-100"
        }
      >
        {feature.formatted}
      </p>
      {isCount && feature.reliability ? (
        <p className="text-[11px] mt-0.5">
          <span className="text-slate-500">{feature.reliability.label}</span>
          {feature.reliability.warn ? (
            <span className="ml-1 text-amber-700 dark:text-amber-400">⚠ {feature.reliability.warn}</span>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}

function pickCategoryFeatures(
  groups: ReturnType<typeof groupProfileFeatures>,
  categoryId: string
): ParsedProfileFeature[] {
  return groups.find((g) => g.categoryId === categoryId)?.features ?? [];
}

export default function ProfileSummaryPanel({
  features,
}: {
  features: Record<string, number>;
}) {
  const parsed = useMemo(() => parseProfileFeatures(features), [features]);
  const groups = useMemo(() => groupProfileFeatures(parsed), [parsed]);

  const landDomains = [
    { countKey: "land_residential_count", meanKey: "land_residential_mean", title: "주거용지" },
    { countKey: "land_commercial_count", meanKey: "land_commercial_mean", title: "상업용지" },
    { countKey: "land_industrial_count", meanKey: "land_industrial_mean", title: "공업용지" },
  ] as const;

  const landBlocks = landDomains
    .map(({ countKey, meanKey, title }) => {
      const countF = parsed.find((p) => p.key === countKey);
      const meanF = parsed.find((p) => p.key === meanKey);
      if (!countF && !meanF) return null;
      return { title, countF, meanF };
    })
    .filter(Boolean);

  const aptFeatures = pickCategoryFeatures(groups, "apartment_market");
  const popFeatures = pickCategoryFeatures(groups, "population");
  const compFeatures = pickCategoryFeatures(groups, "composition");

  return (
    <div className="space-y-5">
      {popFeatures.length > 0 ? (
        <section className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 mb-3">■ 인구</h3>
          <div className="grid sm:grid-cols-2 gap-4">
            {popFeatures.map((f) => (
              <MetricBlock key={f.key} feature={f} />
            ))}
          </div>
        </section>
      ) : null}

      {landBlocks.length > 0 ? (
        <section className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 mb-3">■ 토지 시장</h3>
          <div className="space-y-4">
            {landBlocks.map((block) =>
              block ? (
                <div
                  key={block.title}
                  className="rounded-lg bg-slate-50 dark:bg-slate-900/50 px-3 py-2.5 space-y-2"
                >
                  <p className="text-xs font-semibold text-violet-700 dark:text-violet-300">
                    {block.title}
                  </p>
                  <div className="grid sm:grid-cols-2 gap-3">
                    {block.countF ? <MetricBlock feature={block.countF} /> : null}
                    {block.meanF ? <MetricBlock feature={block.meanF} /> : null}
                  </div>
                </div>
              ) : null
            )}
          </div>
        </section>
      ) : null}

      {aptFeatures.length > 0 ? (
        <section className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 mb-3">■ 아파트 시장</h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {aptFeatures.map((f) => (
              <MetricBlock key={f.key} feature={f} />
            ))}
          </div>
        </section>
      ) : null}

      {compFeatures.length > 0 ? (
        <section className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 mb-3">■ 거래 구성</h3>
          <div className="grid sm:grid-cols-2 gap-3">
            {compFeatures.map((f) => (
              <MetricBlock key={f.key} feature={f} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
