import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_08, INSIGHT_08_SNAP, formatPeriodRange } from "../copy/insight08";

function Prose({ lines }: { lines: readonly string[] }) {
  return (
    <div className="space-y-2">
      {lines.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </div>
  );
}

const snap = INSIGHT_08_SNAP;
const copy = INSIGHT_08;

export default function Insight08() {
  const periodLabel = formatPeriodRange(snap.periodStart, snap.periodEnd);
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const aiContext = {
    app: "insight" as const,
    panel: "Insight08",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: snap.asOfMonth,
      period_start: snap.periodStart,
      period_end: snap.periodEnd,
      n_eligible: snap.eligible,
    },
    explain: {
      spec_id: "insight_08",
      spec_version: "1",
      title: copy.listTitle,
      summary: copy.lead,
      limitations: [...copy.limits],
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
            {copy.see.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s1Title}</h3>
          <p>{copy.s1Lead}</p>
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5 dark:border-slate-600 dark:bg-slate-800/60">
            <ul className="list-disc ml-5 space-y-1">
              {copy.s1Gates.map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ul>
          </div>
          <p>{copy.s1Keep}</p>
          <p className="text-slate-600 dark:text-slate-300">{copy.s1Note}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h3>
          <p>{copy.s2Lead}</p>
          <table className="data w-full text-[13px]">
            <thead>
              <tr>
                <th className="text-left">지역</th>
                <th>저층</th>
                <th>중층</th>
                <th>고층</th>
                <th>최상층</th>
              </tr>
            </thead>
            <tbody>
              {snap.profile.map((row) => (
                <tr key={row.tier}>
                  <td>{row.tier}</td>
                  <td>{row.low}</td>
                  <td>{row.mid}</td>
                  <td>{row.high}</td>
                  <td>{row.top}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-slate-600 dark:text-slate-300">1층은 100입니다. {copy.s2Note}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h3>
          <table className="data w-full max-w-md text-[13px]">
            <thead>
              <tr>
                <th className="text-left">최고층</th>
                <th>최상층 가운데값</th>
                <th>단지 수</th>
              </tr>
            </thead>
            <tbody>
              {snap.height.map((row) => (
                <tr key={row.band}>
                  <td>{row.band}</td>
                  <td>{row.top}</td>
                  <td>{row.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Prose lines={copy.s3} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s4Title}</h3>
          <p>{copy.s4Lead}</p>
          <table className="data w-full text-[13px]">
            <thead>
              <tr>
                <th className="text-left">식</th>
                <th>비도시 최상</th>
                <th>광역시 최상</th>
                <th>기타 도시 최상</th>
                <th className="text-left">높이</th>
              </tr>
            </thead>
            <tbody>
              {snap.joint.map((row) => (
                <tr key={row.spec}>
                  <td>{row.spec}</td>
                  <td>{row.nonurban}</td>
                  <td>{row.metroCity}</td>
                  <td>{row.other}</td>
                  <td className="text-left">{row.height}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Prose lines={copy.s4After} />
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
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.otTitle}</h3>
          <Prose lines={copy.ot} />
          <table className="data w-full text-[13px]">
            <thead>
              <tr>
                <th className="text-left">최고층</th>
                <th>오피스텔 고층</th>
                <th>아파트 고층</th>
                <th>차이</th>
                <th>오피스텔 최상/고층</th>
                <th>아파트 최상/고층</th>
                <th>차이</th>
              </tr>
            </thead>
            <tbody>
              {snap.officetel.map((row) => (
                <tr key={row.band}>
                  <td>{row.band}</td>
                  <td>{row.highOff}</td>
                  <td>{row.highApt}</td>
                  <td>{row.highDiff}</td>
                  <td>{row.topOff}</td>
                  <td>{row.topApt}</td>
                  <td>{row.topDiff}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-slate-600 dark:text-slate-300">저층 = 100. 차이는 오피스텔 − 아파트. 최상/고층 100은 고층과 같다는 뜻입니다.</p>
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
