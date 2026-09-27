import { type ReactNode } from "react";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_06, INSIGHT_06_SNAP, formatPeriodRange } from "../copy/insight06";

function Term({ id, children }: { id: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-0.5 align-middle">
      {children}
      <StatsGlossaryHelp termId={id} size="xs" />
    </span>
  );
}

function pct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

const snap = INSIGHT_06_SNAP;
const copy = INSIGHT_06;
const main = Object.fromEntries(snap.main.map((row) => [row.id, row]));

export default function Insight06() {
  const periodLabel = formatPeriodRange(snap.period_start, snap.period_end);
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const ju = main.ju;
  const nok = main.nok;
  const gye = main.gye;
  const jeon = main.nonurban_jeon;
  const dap = main.nonurban_dap;
  const show = [ju, nok, gye, jeon, dap].filter(Boolean);
  const aiContext = {
    app: "insight" as const,
    panel: "Insight06",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: snap.as_of_month,
      period_start: snap.period_start,
      period_end: snap.period_end,
      min_n: snap.min_n,
      ju_n: ju?.n,
      ju_p50: ju?.p50,
      nok_n: nok?.n,
      nok_p50: nok?.p50,
      gye_n: gye?.n,
      gye_p50: gye?.p50,
      jeon_n: jeon?.n,
      jeon_p50: jeon?.p50,
      dap_n: dap?.n,
      dap_p50: dap?.p50,
      factor_dae: snap.adjusted.find((r) => r.id === "nonurban_dae")?.factor,
      factor_jeon: snap.adjusted.find((r) => r.id === "nonurban_jeon")?.factor,
      factor_dap: snap.adjusted.find((r) => r.id === "nonurban_dap")?.factor,
    },
    explain: {
      spec_id: "insight_06",
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
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{copy.listSub}</p>
          <p className="text-sm text-slate-500">{periodLabel}</p>
          <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">{copy.lead}</p>
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
          <p>{copy.s1Step1}</p>
          <p>{copy.s1Gate}</p>
          <p>{copy.s1Window}</p>
          <p>{copy.s1Each}</p>
          <p>{copy.s1Formula}</p>
          <p>{copy.s1FormulaTail}</p>
          <p>{copy.s1Repeat}</p>
          <p>{copy.s1NotNational}</p>
          <p>{copy.s1Third}</p>
          <p>
            여기서 말하는 <Term id="insight_jimok_road">지목 도로</Term>는 지목이 도로로 등록된 토지를 뜻합니다.
            대장에 도로로 적혀 있는 땅이라는 의미이며, 평가에서 말하는 도로와 반드시 같은 개념은 아닙니다.
          </p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h3>
          {copy.s2.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h3>
          {copy.s3.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s4Title}</h3>
          {copy.s4.map((line) => (
            <p key={line}>{line}</p>
          ))}
          <p className="text-slate-600 dark:text-slate-300">{copy.tableCaption}</p>
          <div className="overflow-x-auto">
            <table className="data w-full text-[13px] whitespace-nowrap">
              <thead>
                <tr>
                  <th className="text-left">비교한 땅</th>
                  <th>동네 수</th>
                  <th>25%</th>
                  <th>가운데</th>
                  <th>75%</th>
                </tr>
              </thead>
              <tbody>
                {show.map((row) => (
                  <tr key={row.id}>
                    <td className="text-left">
                      {row.label}
                      {row.detail ? (
                        <span className="block text-xs text-slate-500">{row.detail.replace("칸", "개 동네")}</span>
                      ) : null}
                    </td>
                    <td>{row.n.toLocaleString("ko-KR")}</td>
                    <td>{pct(row.p25)}</td>
                    <td>{pct(row.p50)}</td>
                    <td>{pct(row.p75)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>{copy.thinNote}</p>
          <p>{copy.thinAfter}</p>
        </section>

        {snap.adjusted.length > 0 ? (
          <section className={prose}>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s5Title}</h3>
            <p>{copy.s5Before}</p>
            <p>{copy.s5Diff}</p>
            <p>{copy.s5Reg}</p>
            <div className="overflow-x-auto">
              <table className="data w-full text-[13px] whitespace-nowrap">
                <thead>
                  <tr>
                    <th className="text-left">비교</th>
                    <th>단순 비교</th>
                    <th>다른 조건을 고려한 회귀분석</th>
                  </tr>
                </thead>
                <tbody>
                  {snap.adjusted.map((row) => (
                    <tr key={row.id}>
                      <td className="text-left">{row.label}</td>
                      <td>{pct(row.median)}</td>
                      <td>{pct(row.factor)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>{copy.s5Group}</p>
            <p>{copy.s5NotSame}</p>
            <p>{copy.s5Factors}</p>
            <p>{copy.s5Order}</p>
            <p>{copy.s5Note}</p>
            <p>{copy.s5Scope}</p>
          </section>
        ) : null}

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.patternsTitle}</h3>
          {copy.patterns.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.limitsTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.limits.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {copy.close.map((line) => (
            <p key={line}>{line}</p>
          ))}
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
