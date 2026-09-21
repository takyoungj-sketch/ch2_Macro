import { type ReactNode } from "react";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_04, INSIGHT_04_SNAP, formatPeriodRange, higherShareLabel } from "../copy/insight04";

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

const snap = INSIGHT_04_SNAP;
const copy = INSIGHT_04;

export default function Insight04() {
  const periodLabel = formatPeriodRange(snap.periodStart, snap.periodEnd);
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const aiContext = {
    app: "insight" as const,
    panel: "Insight04",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: snap.asOfMonth,
      period_start: snap.periodStart,
      period_end: snap.periodEnd,
      n_eligible: snap.eligible,
      n_comparable: snap.comparable,
      n_lower: snap.large.lower,
      n_neutral: snap.large.neutral,
      n_higher: snap.large.higher,
    },
    explain: {
      spec_id: "insight_04",
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
              <Term id="insight_same_cell">같은 시군구·같은 지목 안에서</Term> 비교합니다. 같은 시군구·같은 지목
              안에서만 비교하므로 서울 대지와 군 전을 직접 비교하지 않습니다.
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
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5 dark:border-slate-600 dark:bg-slate-800/60">
            <p>
              이 글에서 「<Term id="insight_relative_large">광평</Term>」{copy.largeBoxRest}
            </p>
          </div>
          <p className="text-slate-600 dark:text-slate-300">{copy.s1Note}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h3>
          <p>{copy.s2[0]}</p>
          <table className="data w-full max-w-md text-[13px]">
            <thead>
              <tr>
                <th className="text-left">방향</th>
                <th>비교 그룹 수</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="text-left">낮게</td>
                <td>{snap.large.lower.toLocaleString("ko-KR")}</td>
              </tr>
              <tr>
                <td className="text-left">중립</td>
                <td>{snap.large.neutral.toLocaleString("ko-KR")}</td>
              </tr>
              <tr>
                <td className="text-left">높게</td>
                <td>{snap.large.higher.toLocaleString("ko-KR")}</td>
              </tr>
              <tr>
                <td className="text-left">비교한 그룹</td>
                <td>{snap.comparable.toLocaleString("ko-KR")}</td>
              </tr>
            </tbody>
          </table>
          <p className="text-slate-600 dark:text-slate-300">{copy.s2TableCaption}</p>
          <p>{copy.s2[1]}</p>
          <p>{copy.s2[2]}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h3>
          <p>{copy.s3Lead}</p>
          <p className="text-slate-600 dark:text-slate-300">{copy.s3Legend}</p>
          <table className="data w-full text-[13px]">
            <thead>
              <tr>
                <th className="text-left">유형</th>
                <th className="text-left">지목</th>
                <th>비교 그룹</th>
                <th>낮게</th>
                <th>중립</th>
                <th>높게</th>
                <th>높게 비율</th>
              </tr>
            </thead>
            <tbody>
              {snap.cross.map((row) => (
                <tr key={`${row.type}-${row.jimok}`}>
                  <td className="text-left">{row.type}</td>
                  <td className="text-left">{row.jimok}</td>
                  <td>{row.n}</td>
                  <td>{row.lower}</td>
                  <td>{row.neutral}</td>
                  <td>{row.higher}</td>
                  <td>{higherShareLabel(row.higher, row.n)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Prose lines={copy.s3After} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s4Title}</h3>
          <p>{copy.s4Lead}</p>
          <Prose lines={copy.s4} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s5Title}</h3>
          <p className="font-medium">{copy.s5Lead}</p>
          <p>{copy.s5}</p>
          <details className="text-slate-600 dark:text-slate-300">
            <summary className="cursor-pointer text-sm">{copy.s5DetailLabel}</summary>
            <p className="mt-2">{copy.s5Detail}</p>
          </details>
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
