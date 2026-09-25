import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { formatPeriodRange } from "../copy/insight08";
import { INSIGHT_10, INSIGHT_10_SNAP } from "../copy/insight10";

function Prose({ lines }: { lines: readonly string[] }) {
  return (
    <div className="space-y-2">
      {lines.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </div>
  );
}

const snap = INSIGHT_10_SNAP;
const copy = INSIGHT_10;

export default function Insight10() {
  const periodLabel = formatPeriodRange(snap.periodStart, snap.periodEnd);
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const aiContext = {
    app: "insight" as const,
    panel: "Insight10",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: snap.asOfMonth,
      period_start: snap.periodStart,
      period_end: snap.periodEnd,
      n_roads_first: snap.roadsFirst,
      n_roads_area: snap.roadsArea,
    },
    explain: {
      spec_id: "insight_10",
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
        </header>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.summaryTitle}</h3>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">{copy.lead}</p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.seeTitle}</h3>
          <Prose lines={copy.intro} />
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.see.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <section className="space-y-10">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.bodyTitle}</h3>

        <section className={prose}>
          <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s1Title}</h4>
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
          <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h4>
          <p>{copy.s2Lead}</p>
          <table className="data w-full max-w-lg text-[13px]">
            <thead>
              <tr>
                <th className="text-left">구분</th>
                <th>클러스터별 동일가중 가운데값<br />(1층=100)</th>
                <th>전체 거래 수 가중 가운데값<br />(1층=100)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>2층 상대가격지수</td>
                <td>{snap.first.equal}</td>
                <td>{snap.first.weighted}</td>
              </tr>
            </tbody>
          </table>
          <p className="text-slate-600 dark:text-slate-300">
            사분위 {snap.first.p25}–{snap.first.p75}. 도로 클러스터 {snap.roadsFirst.toLocaleString("ko-KR")}곳.
          </p>
          <table className="data w-full max-w-lg text-[13px]">
            <thead>
              <tr>
                <th className="text-left">1층 거래</th>
                <th>클러스터별 동일가중 가운데값<br />(1층=100)</th>
                <th>전체 거래 수 가중 가운데값<br />(1층=100)</th>
                <th>클러스터 수</th>
              </tr>
            </thead>
            <tbody>
              {snap.n1.map((row) => (
                <tr key={row.band}>
                  <td>{row.band}</td>
                  <td>{row.equal}</td>
                  <td>{row.weighted}</td>
                  <td>{row.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-slate-600 dark:text-slate-300">{copy.s2Note}</p>
        </section>

        <section className={prose}>
          <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h4>
          <p>{copy.s3Lead}</p>
          <table className="data w-full max-w-lg text-[13px]">
            <thead>
              <tr>
                <th className="text-left">구분</th>
                <th>클러스터별 동일가중 가운데값<br />(1층=100)</th>
                <th>전체 거래 수 가중 가운데값<br />(1층=100)</th>
                <th>p25–p75</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>2층 상대가격지수<br />(연면적 ±20%)</td>
                <td>{snap.area.equal}</td>
                <td>{snap.area.weighted}</td>
                <td>
                  {snap.area.p25}–{snap.area.p75}
                </td>
              </tr>
            </tbody>
          </table>
          <p className="text-slate-600 dark:text-slate-300">도로 클러스터 {snap.roadsArea}곳. 1층 = 100.</p>
          <Prose lines={copy.s3} />
        </section>

        <section className={prose}>
          <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s4Title}</h4>
          <p>{copy.s4Lead}</p>
          <table className="data w-full max-w-lg text-[13px]">
            <thead>
              <tr>
                <th className="text-left">가중 방식</th>
                <th>회귀 결과<br />(1층=100)</th>
                <th>95% 신뢰구간</th>
              </tr>
            </thead>
            <tbody>
              {snap.controlled.map((row) => (
                <tr key={row.weight}>
                  <td>{row.weight}</td>
                  <td>{row.index}</td>
                  <td>
                    {row.lo}–{row.hi}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Prose lines={copy.s4} />
        </section>

        <section className={prose}>
          <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.patternsTitle}</h4>
          <ol className="list-decimal ml-5 space-y-2">
            {copy.patterns.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ol>
        </section>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.limitsTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.limits.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.closeTitle}</h3>
          <Prose lines={copy.close} />
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
