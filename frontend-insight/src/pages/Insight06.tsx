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

function share(part: number | null | undefined, total: number | undefined): string {
  if (part == null || !total) return "—";
  return `${Math.round((part / total) * 100)}%`;
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
  const daeAdj = snap.adjusted.find((r) => r.id === "nonurban_dae");
  const jarokN = nok?.detail?.match(/\d+/)?.[0];
  const greenSame = pct(nok?.p50) === pct(gye?.p50);
  const closeText = `같은 동네의 도로라도 무엇과 비교하느냐에 따라 가격 비율은 크게 달랐습니다. 주거지역 대지와 비교하면 가운데 값은 ${pct(ju?.p50)}, ${
    greenSame
      ? `녹지·계획관리지역 대지와 비교하면 ${pct(nok?.p50)}`
      : `녹지지역 대지와 비교하면 ${pct(nok?.p50)}, 계획관리지역 대지와 비교하면 ${pct(gye?.p50)}`
  }, 밭·논과 비교하면 각각 ${pct(jeon?.p50)}, ${pct(dap?.p50)}였습니다. 따라서 도로는 토지 가격의 3분의 1이라는 하나의 기준만으로, 이번 자료의 실제 거래가격을 설명하기는 어려웠습니다. 동네별 차이도 상당히 컸습니다.`;
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
      summary: closeText,
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
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">
            같은 동네에서 도로로 등록된 땅의 ㎡당 가격은, 주거지역 대지의 {pct(ju?.p50)}, 녹지지역 대지의{" "}
            {pct(nok?.p50)}, 계획관리지역 대지의 {pct(gye?.p50)} 수준이었습니다. 밭은 {pct(jeon?.p50)}, 논은{" "}
            {pct(dap?.p50)}였습니다. 흔히 말하는 3분의 1이 모든 경우에 나타난 것은 아닙니다.
          </p>
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
          <p>
            예를 들어 같은 읍·면·동의 주거지역에서, 도로 거래와 대지 거래가 각각 {snap.min_n}건 이상 있는 경우를
            골랐습니다. 건수가 적은 동네를 빼려고 고른 기준이고, 3분의 1에 가까운 동네를 고른 기준이 아닙니다. 지분
            거래는 빼었습니다. 기간은 {periodLabel}입니다.
          </p>
          <p>그 동네에서 도로 거래의 ㎡당 가격 가운데 값을 구하고, 대지 거래의 가운데 값을 구했습니다.</p>
          <p>그리고 도로의 가운데 값 ÷ 대지의 가운데 값을 계산했습니다.</p>
          <p>
            이런 계산을 읍·면·동마다, 비교할 땅마다 반복했습니다. 아래의 {pct(ju?.p50)}, {pct(nok?.p50)} 같은 숫자는
            전국 도로 가격을 전국 대지 가격으로 나눈 값이 아닙니다. 동네별로 만든 가격 비율을 다시 모아, 그 가운데 값을
            구한 것입니다.
          </p>
          <p>{copy.s1Third}</p>
          <p>
            <Term id="insight_jimok_road">지목 도로</Term>
            {copy.s1JimokRest}
          </p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h3>
          <p>{copy.s2Lead}</p>
          <p>
            {ju?.n.toLocaleString("ko-KR")}개 동네의 비율을 낮은 순서로 세웠을 때, 가운데 값이 {pct(ju?.p50)}였습니다.
            낮은 쪽 25%의 경계는 {pct(ju?.p25)}, 높은 쪽 25%의 경계는 {pct(ju?.p75)}였습니다. 동네에 따라 도로와 대지의
            가격 차이가 상당히 컸습니다. 3분의 1보다 낮은 동네는 {ju?.n_below_third?.toLocaleString("ko-KR")}개(
            {share(ju?.n_below_third, ju?.n)})입니다.
          </p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h3>
          <p>{copy.s3Lead}</p>
          <p>
            녹지지역은 {nok?.n.toLocaleString("ko-KR")}개 동네에서 비교했습니다. 가운데 값은 {pct(nok?.p50)}였고, 이
            가운데 {jarokN ?? "—"}개가 자연녹지였습니다. 계획관리지역은 {gye?.n.toLocaleString("ko-KR")}개 동네이고,
            가운데 값은 {pct(gye?.p50)}였습니다.
          </p>
          <p>
            3분의 1보다 낮은 동네는 녹지 {nok?.n_below_third?.toLocaleString("ko-KR")}개(
            {share(nok?.n_below_third, nok?.n)}), 계획관리 {gye?.n_below_third?.toLocaleString("ko-KR")}개(
            {share(gye?.n_below_third, gye?.n)})입니다.
          </p>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s4Title}</h3>
          <p>{copy.s4Lead}</p>
          <p>
            예를 들어 도로가 50만 원/㎡라고 해 봅시다. 대지가 100만 원이면 도로는 대지의 <strong>50%</strong>입니다.
            밭이 70만 원이면 도로는 밭의 <strong>71%</strong>가 됩니다. 이 50만 원, 100만 원, 70만 원은 표의 숫자가
            아니라, 비율이 왜 달라지는지 보이려는 예시입니다.
          </p>
          <p>{copy.s4After}</p>
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
          <p className="text-slate-600 dark:text-slate-300">
            표에 넣지 않은 묶음:{" "}
            {snap.thin
              .map((row) => `${row.label} ${row.n.toLocaleString("ko-KR")}곳, 가운데 ${pct(row.p50)}`)
              .join(" · ")}
            . 칸이 적어 위 표와 같은 줄로 읽지 않습니다.
          </p>
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
            <p>
              예를 들어 도시 밖 대지는 단순 비교에서는 {pct(daeAdj?.median)}였지만, 땅 크기·접한 길의 폭·계약 연도의
              차이를 함께 고려하면 {pct(daeAdj?.factor)}로 낮아졌습니다. 밭·논도 단순 비교보다 낮아졌고, 대지보다 높은
              순서는 남았습니다.
            </p>
            <p className="text-slate-600 dark:text-slate-300">{copy.s5Note}</p>
          </section>
        ) : null}

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.patternsTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            <li>주거지역 대지와 비교하면 도로 가격 비율의 가운데 값은 {pct(ju?.p50)}로, 3분의 1보다 높았습니다.</li>
            <li>
              녹지지역·계획관리지역 대지와 비교하면 가운데 값은{" "}
              {greenSame ? `모두 ${pct(nok?.p50)}` : `${pct(nok?.p50)}, ${pct(gye?.p50)}`}로 주거지역보다 낮았습니다.
            </li>
            <li>밭·논과 비교하면 각각 {pct(jeon?.p50)}, {pct(dap?.p50)}로 더 높았습니다.</li>
            <li>
              동네마다 차이가 매우 컸습니다. 도로는 항상 대지 가격의 3분의 1이라는 하나의 숫자로 설명하기는 어렵습니다.
            </li>
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.limitsTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.limits.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p>{closeText}</p>
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
