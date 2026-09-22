import { useState, type ReactNode } from "react";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { MIX_TYPE_COLOR, YearMixStack, YearMultiLine, YearSingleLine, yearDomainFromMaps } from "../components/InsightCharts";
import { INSIGHT_05, INSIGHT_05_SNAP } from "../copy/insight05";

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

function toYearMap(pts: { year: number; v: number }[]): Map<number, number> {
  return new Map(pts.map((p) => [p.year, p.v]));
}

function fmtR(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return Number(v.toFixed(2)).toLocaleString("ko-KR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtJo(v: number): string {
  const jo = v / 1000;
  if (Math.abs(jo) < 1e-12) return "0조";
  const digits = Math.abs(jo) >= 100 ? 0 : 1;
  return `${Number(jo.toFixed(digits)).toLocaleString("ko-KR")}조`;
}

const LEVEL_COLOR = {
  re: "#dc2626",
  gdp: "#2563eb",
  m2: "#059669",
  stock: "#d97706",
};

const snap = INSIGHT_05_SNAP;
const copy = INSIGHT_05;

export default function Insight05() {
  const [showTypeGdp, setShowTypeGdp] = useState(false);
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const years = snap.years;
  const reMap = toYearMap(snap.reTotal);
  const gdpLevelMap = toYearMap(snap.gdp);
  const m2LevelMap = toYearMap(snap.m2);
  const stockLevelMap = toYearMap(snap.stock);
  const vsGdpMap = toYearMap(snap.vsGdp);
  const vsM2Map = toYearMap(snap.vsM2);
  const vsStockMap = toYearMap(snap.vsStock);
  const mixTypes = snap.types.filter((t) => t !== "합계");
  const mixAmountMaps = mixTypes.map((t) => toYearMap(snap.mixAmount[t] ?? []));
  const mixStacked = new Map(
    years.map((y) => [y, mixAmountMaps.reduce((sum, m) => sum + (m.get(y) ?? 0), 0)] as const),
  );
  const mixAmtStackDom = yearDomainFromMaps([mixStacked], true);
  const mixAmtLineDom = yearDomainFromMaps(mixAmountMaps, true);
  const mixAmountSeries = mixTypes.map((t, i) => ({
    key: t,
    label: t,
    values: mixAmountMaps[i],
    color: MIX_TYPE_COLOR[t] ?? "#64748b",
  }));
  const levelDom = yearDomainFromMaps([reMap, gdpLevelMap, m2LevelMap, stockLevelMap], true);
  const ratioDom = yearDomainFromMaps([vsGdpMap, vsM2Map, vsStockMap], true);
  const levelSeries = [
    { key: "re", label: copy.sLevelRe, values: reMap, color: LEVEL_COLOR.re },
    { key: "gdp", label: copy.sLevelGdp, values: gdpLevelMap, color: LEVEL_COLOR.gdp },
    { key: "m2", label: copy.sLevelM2, values: m2LevelMap, color: LEVEL_COLOR.m2 },
    { key: "stock", label: copy.sLevelStock, values: stockLevelMap, color: LEVEL_COLOR.stock },
  ];
  const ratioSeries = [
    { key: "vsGdp", label: copy.s2Gdp, values: vsGdpMap, color: LEVEL_COLOR.gdp },
    { key: "vsM2", label: copy.s2M2, values: vsM2Map, color: LEVEL_COLOR.m2 },
    { key: "vsStock", label: copy.s2Stock, values: vsStockMap, color: LEVEL_COLOR.stock },
  ];
  const aiContext = {
    app: "insight" as const,
    panel: "Insight05",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: snap.asOf,
      year_start: snap.yearStart,
      year_end: snap.yearEnd,
      n_years: years.length,
      n_yoy: snap.corr.n_yoy,
      r_yoy_re_gdp: snap.corr.yoy.re_gdp,
      r_yoy_re_m2: snap.corr.yoy.re_m2,
      r_yoy_re_stock: snap.corr.yoy.re_stock,
      unit_ok_2010: snap.smoke["2010"]?.unit_ok ?? false,
      unit_ok_2024: snap.smoke["2024"]?.unit_ok ?? false,
    },
    explain: {
      spec_id: "insight_05",
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
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{copy.listSub}</p>
          <p className="text-sm text-slate-500">
            {copy.listMeta}
            <span className="mx-1.5 text-slate-300">·</span>
            {snap.yearStart}–{snap.yearEnd}
          </p>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">{copy.lead}</p>
          <div className={prose}>
            <Prose lines={copy.intro} />
          </div>
        </header>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s1Title}</h3>
          <Prose lines={copy.s1Body} />
          <p>
            분모의{" "}
            <Term id="insight_nominal_gdp">명목 GDP</Term>,{" "}
            <Term id="insight_m2">시중 돈(M2)</Term>,{" "}
            <Term id="insight_stock_turnover">주식 거래대금</Term>은 각각 다른 질문입니다. 비율은{" "}
            <Term id="insight_turnover_vs_gdp">거래액 / GDP</Term>,{" "}
            <Term id="insight_turnover_vs_m2">거래액 / M2</Term>
            처럼 규모를 비교한 지표로 읽습니다.
          </p>
        </section>

        <section className="space-y-4">
          <div className={prose}>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.sLevelsTitle}</h3>
            <Prose lines={copy.sLevelsLead} />
          </div>
          <YearSingleLine
            years={years}
            values={reMap}
            label={copy.sLevelRe}
            formatY={fmtJo}
            color={LEVEL_COLOR.re}
            domain={levelDom}
            showValues
          />
          <YearSingleLine
            years={years}
            values={gdpLevelMap}
            label={copy.sLevelGdp}
            formatY={fmtJo}
            color={LEVEL_COLOR.gdp}
            domain={levelDom}
            showValues
          />
          <YearSingleLine
            years={years}
            values={m2LevelMap}
            label={copy.sLevelM2}
            formatY={fmtJo}
            color={LEVEL_COLOR.m2}
            domain={levelDom}
            showValues
          />
          <YearSingleLine
            years={years}
            values={stockLevelMap}
            label={copy.sLevelStock}
            formatY={fmtJo}
            color={LEVEL_COLOR.stock}
            domain={levelDom}
            showValues
          />
          <YearMultiLine
            years={years}
            series={levelSeries}
            label={copy.sLevelsTogether}
            formatY={fmtJo}
            domain={levelDom}
            showValues
          />
        </section>

        <section className="space-y-4">
          <div className={prose}>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h3>
            <p>{copy.s2Lead}</p>
            <Prose lines={copy.s2Body} />
          </div>
          <YearSingleLine
            years={years}
            values={vsGdpMap}
            label={copy.s2Gdp}
            color={LEVEL_COLOR.gdp}
            domain={ratioDom}
            showValues
          />
          <YearSingleLine
            years={years}
            values={vsM2Map}
            label={copy.s2M2}
            color={LEVEL_COLOR.m2}
            domain={ratioDom}
            showValues
          />
          <YearSingleLine
            years={years}
            values={vsStockMap}
            label={copy.s2Stock}
            color={LEVEL_COLOR.stock}
            domain={ratioDom}
            showValues
          />
          <YearMultiLine
            years={years}
            series={ratioSeries}
            label={copy.s2Together}
            domain={ratioDom}
            showValues
          />
        </section>

        <section className="space-y-4">
          <div className={prose}>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h3>
            <p>{copy.s3AmountLead}</p>
          </div>
          <YearMixStack
            years={years}
            share={snap.mixAmount}
            label={copy.s3AmountStack}
            formatY={fmtJo}
            domain={mixAmtStackDom}
          />
          <YearMultiLine
            years={years}
            series={mixAmountSeries}
            label={copy.s3AmountLines}
            formatY={fmtJo}
            domain={mixAmtLineDom}
          />
          <div className={prose}>
            <p>
              <Term id="insight_type_mix_year">유형 구성비</Term>. {copy.s3Lead}
            </p>
          </div>
          <YearMixStack years={years} share={snap.mixShare} label={copy.s3ShareLabel} />
        </section>

        <section className="space-y-3">
          <div className={prose}>
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.sCorrTitle}</h3>
            <p>
              <Term id="pearson_r">상관계수 r</Term>. {copy.sCorrLead}
            </p>
          </div>
          <table className="data w-full max-w-lg text-[13px]">
            <thead>
              <tr>
                <th className="text-left">거래액과</th>
                <th>명목 GDP</th>
                <th>시중 돈(M2)</th>
                <th>주식 거래대금</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="text-left">
                  {copy.sCorrLevel} (n={snap.corr.n_level})
                </td>
                <td>{fmtR(snap.corr.level.re_gdp)}</td>
                <td>{fmtR(snap.corr.level.re_m2)}</td>
                <td>{fmtR(snap.corr.level.re_stock)}</td>
              </tr>
              <tr>
                <td className="text-left">
                  {copy.sCorrYoy} (n={snap.corr.n_yoy})
                </td>
                <td>{fmtR(snap.corr.yoy.re_gdp)}</td>
                <td>{fmtR(snap.corr.yoy.re_m2)}</td>
                <td>{fmtR(snap.corr.yoy.re_stock)}</td>
              </tr>
            </tbody>
          </table>
          <p className="text-sm text-slate-600 dark:text-slate-300">{copy.sCorrCaption}</p>
        </section>

        <section className="space-y-3">
          <button
            type="button"
            className="text-sm underline text-slate-700 dark:text-slate-200"
            onClick={() => setShowTypeGdp((v) => !v)}
          >
            {showTypeGdp ? copy.s4Hide : copy.s4Toggle}
          </button>
          {showTypeGdp ? (
            <div className="space-y-4">
              <p className="text-sm text-slate-600 dark:text-slate-300">{copy.s4Lead}</p>
              {snap.types.map((t) => (
                <YearSingleLine
                  key={t}
                  years={years}
                  values={toYearMap(snap.typeVsGdp[t] ?? [])}
                  label={`${t} / GDP`}
                />
              ))}
            </div>
          ) : null}
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
