import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_07, INSIGHT_07_WEIGHTS } from "../copy/insight07";

const copy = INSIGHT_07;

export default function Insight07() {
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const aiContext = {
    app: "insight" as const,
    panel: "Insight07",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      algorithm: 21,
      profile_version: "v2.1-national",
      window_years: 3,
      weight_population: 0.15,
      weight_market_mix: 0.35,
      weight_land: 0.3,
      weight_apartment: 0.2,
    },
    explain: {
      spec_id: "insight_07",
      spec_version: "1",
      title: copy.listTitle,
      summary: copy.listSub,
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
          <h2 className="text-xl font-bold leading-snug inline-flex items-center gap-1">
            {copy.listTitle}
            <StatsGlossaryHelp termId="twin_region" size="sm" />
          </h2>
          <p className="text-sm text-slate-500">{copy.listSub}</p>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">{copy.lead}</p>
          <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">{copy.leadNext}</p>
        </header>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.seeTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.see.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s1Title}</h3>
          <p>{copy.s1Body}</p>
          <p>{copy.s1Scope}</p>
          <p>{copy.s1Pop}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h3>
          <p>{copy.s2Lead}</p>
          <div className="overflow-x-auto">
            <table className="data w-full text-[13px]">
              <thead>
                <tr>
                  <th className="text-left">항목</th>
                  <th>가중치</th>
                  <th className="text-left">보는 것</th>
                </tr>
              </thead>
              <tbody>
                {INSIGHT_07_WEIGHTS.map((row) => (
                  <tr key={row.label}>
                    <td className="text-left">{row.label}</td>
                    <td>{row.weight}</td>
                    <td className="text-left">{row.looks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h3>
          <p>{copy.s3Pop}</p>
          <p>{copy.s3Mix}</p>
          <p>{copy.s3Land}</p>
          <p>{copy.s3Apt}</p>
          <p>{copy.s3Rep}</p>
          <p>{copy.s3Clamp}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s4Title}</h3>
          <p>{copy.s4Body}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.limitsTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.limits.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.checkTitle}</h3>
          <p className="font-medium text-slate-900 dark:text-slate-50">{copy.checkedTitle}</p>
          <p>{copy.checked}</p>
          <p className="font-medium text-slate-900 dark:text-slate-50">{copy.toCheckTitle}</p>
          <p>{copy.toCheck}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.nextTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.next.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.relatedTitle}</h3>
          <p>{copy.related}</p>
          <p>
            <a href={copy.relatedHref} className="text-sky-800 dark:text-sky-300 underline">
              {copy.relatedLink}
            </a>
          </p>
        </section>
      </article>
    </>
  );
}
