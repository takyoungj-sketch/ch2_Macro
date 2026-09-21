import { type ReactNode } from "react";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_03, INSIGHT_03_SNAP, fmtPct1, formatPeriodRange } from "../copy/insight03";

function Term({ id, children }: { id: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-0.5 align-middle">
      {children}
      <StatsGlossaryHelp termId={id} size="xs" />
    </span>
  );
}

function Prose({ lines }: { lines: string[] }) {
  return (
    <div className="space-y-2">
      {lines.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </div>
  );
}

const snap = INSIGHT_03_SNAP;
const copy = INSIGHT_03;

export default function Insight03() {
  const periodLabel = formatPeriodRange(snap.periodStart, snap.periodEnd);
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const aiContext = {
    app: "insight" as const,
    panel: "Insight03",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: snap.asOfMonth,
      period_start: snap.periodStart,
      period_end: snap.periodEnd,
      n_eligible: snap.eligible,
      n_known: snap.known,
      pct_theta_top: snap.pctThetaTop,
      pct_delta_level: snap.pctDeltaLevel,
    },
    explain: {
      spec_id: "insight_03",
      spec_version: "1",
      title: copy.listTitle,
      summary: copy.lead,
      limitations: copy.limits,
    },
  };

  return (
    <>
      <PublishAiContext context={aiContext} />
      <article className="max-w-4xl mx-auto px-4 py-8 space-y-10 pb-16">
        <p>
          <a href="/insight/" className="text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">
            ← 질문 목록
          </a>
        </p>

        <header className="space-y-3">
          <h2 className="text-xl font-bold leading-snug">{copy.listTitle}</h2>
          <p className="text-sm text-slate-500">
            {copy.listSub}
            <span className="mx-1.5 text-slate-300">·</span>
            {periodLabel}
          </p>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">{copy.lead}</p>
          <div className={prose}>
            <Prose lines={copy.intro} />
          </div>
        </header>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.seeTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            <li>
              <Term id="insight_within_building">같은 건물 안 비교</Term>
              입니다. {copy.see[0]}
            </li>
            <li>{copy.see[1]}</li>
            <li>{copy.see[2]}</li>
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s1Title}</h3>
          <p>{copy.s1Lead}</p>
          <p>{copy.s1Body}</p>
          <ul className="list-disc ml-5 space-y-1">
            {copy.s1Gates.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
          <p className="text-slate-600 dark:text-slate-300">{copy.s1Note}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h3>
          <Prose lines={copy.s2} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h3>
          <p>{copy.s3Lead}</p>
          <p>
            {copy.s3ThetaLabel}: {fmtPct1(snap.pctThetaTop)}
          </p>
          <p className="text-slate-600 dark:text-slate-300">{copy.s3ThetaHint}</p>
          <table className="data w-full max-w-md text-[13px]">
            <thead>
              <tr>
                <th className="text-left">층</th>
                <th>승강기 없음</th>
                <th>승강기 있음</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="text-left">
                  <Term id="insight_floor_index_100">1층</Term>
                </td>
                <td>100</td>
                <td>100</td>
              </tr>
              <tr>
                <td className="text-left">중간층</td>
                <td>{snap.sketch.no.mid}</td>
                <td>{snap.sketch.yes.mid}</td>
              </tr>
              <tr>
                <td className="text-left">최상층</td>
                <td>{snap.sketch.no.top}</td>
                <td>{snap.sketch.yes.top}</td>
              </tr>
            </tbody>
          </table>
          <p className="text-slate-600 dark:text-slate-300">{copy.sketchCaption}</p>
          <p className="text-[11px] text-slate-500">{copy.sketchRound}</p>
          <Prose lines={copy.s3After} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s4Title}</h3>
          <p>{copy.s4Lead}</p>
          <table className="data w-full max-w-md text-[13px]">
            <thead>
              <tr>
                <th className="text-left">구분</th>
                <th>최상층 승강기 효과</th>
              </tr>
            </thead>
            <tbody>
              {snap.groups.map((row) => (
                <tr key={row.label}>
                  <td className="text-left">{row.label}</td>
                  <td>{fmtPct1(row.pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>{copy.s4Close}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s5Title}</h3>
          <p className="font-medium">{copy.s5Lead}</p>
          <Prose lines={copy.s5} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.patternsTitle}</h3>
          <ol className="list-decimal ml-5 space-y-2">
            {copy.patterns.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ol>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.limitsTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.limits.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <p>{copy.close}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.nextTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.next.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.relatedTitle}</h3>
          <Prose lines={copy.related} />
          <p>
            <a href={copy.relatedHref} className="text-slate-800 underline dark:text-slate-200">
              {copy.relatedLink}
            </a>
          </p>
        </section>
      </article>
    </>
  );
}
