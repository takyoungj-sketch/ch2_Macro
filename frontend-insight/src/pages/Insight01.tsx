import { useEffect, useMemo, useState, type ReactNode } from "react";
import clsx from "clsx";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import {
  DualLine,
  SingleLine,
  addLag,
  fmtCount,
  fmtEokWon,
  fmtManwon,
  fmtPct,
  fmtPp,
  fmtRate,
  toMap,
} from "../components/InsightCharts";
import CorrTable from "../components/CorrTable";
import {
  fetchInsight01,
  insight01AiFacts,
  type Insight01Response,
  type MacroCorr,
  type MacroPairRow,
} from "../api/insightClient";
import { INSIGHT_01, LAG_LABELS, formatPeriodRange } from "../copy/insight01";

function Term({ id, children }: { id: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-0.5 align-middle">
      {children}
      <StatsGlossaryHelp termId={id} size="xs" />
    </span>
  );
}

function unionKeys(...maps: Map<number, number>[]): number[] {
  const s = new Set<number>();
  for (const m of maps) {
    for (const k of m.keys()) s.add(k);
  }
  return [...s].sort((a, b) => a - b);
}

function pairCell(row: MacroPairRow | undefined, key: string): MacroCorr | null {
  if (!row) return null;
  const v = row[key];
  if (v && typeof v === "object" && "r" in v) return v as MacroCorr;
  return null;
}

function fmtSigned(r: number | null | undefined): string {
  if (r == null || Number.isNaN(r)) return "—";
  return r.toFixed(2);
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

export default function Insight01() {
  const [data, setData] = useState<Insight01Response | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lag, setLag] = useState(0);
  const [metric, setMetric] = useState<"count" | "amount">("count");

  useEffect(() => {
    let live = true;
    fetchInsight01()
      .then((d) => {
        if (live) setData(d);
      })
      .catch((e: { message?: string }) => {
        if (live) setErr(e?.message || "불러오지 못했습니다.");
      });
    return () => {
      live = false;
    };
  }, []);

  const aiContext = useMemo(() => {
    return {
      app: "insight" as const,
      panel: "Insight01",
      purpose: "statistics" as const,
      scope: { region_label: "전국" },
      facts: data ? insight01AiFacts(data) : {},
      explain: {
        spec_id: "insight_01",
        spec_version: "1",
        title: INSIGHT_01.listTitle,
        summary: INSIGHT_01.intro[0],
        limitations: INSIGHT_01.limits,
      },
    };
  }, [data]);

  const lags = data?.lags?.length ? data.lags : [0, 1, 3, 6];
  const types = data?.types?.length ? data.types : [];
  const cd = data?.rates?.cd_91;
  const base = data?.rates?.bok_base;
  const total = data?.series?.["합계"];
  const periodLabel = formatPeriodRange(data?.period_start, data?.period_end);

  const totalCountRs = useMemo(() => {
    const row = data?.pairs.find((p) => p.type === "합계");
    return {
      0: pairCell(row, "cd_91_count_lag0")?.r ?? null,
      1: pairCell(row, "cd_91_count_lag1")?.r ?? null,
      3: pairCell(row, "cd_91_count_lag3")?.r ?? null,
      6: pairCell(row, "cd_91_count_lag6")?.r ?? null,
    };
  }, [data]);

  const pattern2 =
    totalCountRs[0] != null && totalCountRs[1] != null && totalCountRs[3] != null && totalCountRs[6] != null
      ? `전체 거래건수의 상관계수는 같은 달 ${fmtSigned(totalCountRs[0])}에서 1개월 뒤 ${fmtSigned(totalCountRs[1])}, 3개월 뒤 ${fmtSigned(totalCountRs[3])}, 6개월 뒤 ${fmtSigned(totalCountRs[6])}로 낮아졌습니다.`
      : "전체 거래건수의 상관계수는 아래 표 1의 합계 행에서 시차가 길어질수록 작아지는 모습을 보입니다.";

  const levelKeys = useMemo(() => {
    if (!data || !cd || !total) return [];
    return unionKeys(toMap(cd.values), toMap(data.m2?.values ?? []), toMap(total.count), toMap(total.amount));
  }, [data, cd, total]);

  const yoyRate = useMemo(() => {
    if (!data || !cd || !total) return null;
    const left = toMap(cd.d_pp);
    const rightRaw = toMap(metric === "count" ? total.yoy_count : total.yoy_amount);
    const right = new Map<number, number>();
    for (const [t] of left) {
      const yv = rightRaw.get(addLag(t, lag));
      if (yv == null) continue;
      right.set(t, yv);
    }
    const keys = [...left.keys()].filter((k) => right.has(k)).sort((a, b) => a - b);
    return { keys, left, right };
  }, [data, cd, total, lag, metric]);

  const yoyM2 = useMemo(() => {
    if (!data?.m2 || !total) return null;
    const left = toMap(data.m2.yoy_pct);
    const rightRaw = toMap(metric === "count" ? total.yoy_count : total.yoy_amount);
    const right = new Map<number, number>();
    for (const [t] of left) {
      const yv = rightRaw.get(addLag(t, lag));
      if (yv == null) continue;
      right.set(t, yv);
    }
    const keys = [...left.keys()].filter((k) => right.has(k)).sort((a, b) => a - b);
    return { keys, left, right };
  }, [data, total, lag, metric]);

  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";

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
          <h2 className="text-xl font-bold leading-snug">{INSIGHT_01.listTitle}</h2>
          <p className="text-sm text-slate-500">
            전국 · 월별
            {periodLabel ? ` · ${periodLabel}` : ""}
          </p>
          <div className={prose}>
            <Prose lines={INSIGHT_01.intro} />
          </div>
        </header>

        {err && <p className="text-sm text-red-600">{err}</p>}
        {!data && !err && (
          <p className="text-sm text-slate-500">숫자를 불러오는 중입니다. 처음이면 조금 걸릴 수 있습니다.</p>
        )}

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">무엇을 확인하나?</h3>
          <p>
            <strong>질문.</strong> {INSIGHT_01.question}
          </p>
          <p>{INSIGHT_01.questionLead}</p>
          <p>
            <strong>분석 대상.</strong> {INSIGHT_01.subjects[0]} {INSIGHT_01.subjects[1]}{" "}
            <Term id="insight_total">전체 거래</Term> · <Term id="insight_amount">거래액</Term>
          </p>
          <div>
            <p>
              <strong>비교 방법.</strong> {INSIGHT_01.methods[0]}{" "}
              <Term id="insight_cd">CD 금리</Term> · <Term id="insight_m2">M2</Term>
            </p>
            <Prose lines={INSIGHT_01.methods.slice(1)} />
          </div>
          <p>
            {INSIGHT_01.corrOnce} <Term id="pearson_r">상관계수</Term> ·{" "}
            <Term id="insight_yoy">전년동월</Term> · <Term id="insight_lag">시차</Term>
          </p>
          <p className="text-slate-500">{INSIGHT_01.confirmRate}</p>
        </section>

        <section className="space-y-3">
          <h3 className="text-base font-semibold flex items-center gap-1">
            시장의 흐름부터 살펴보기
            <Term id="insight_level">수준 그래프</Term>
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-300">{INSIGHT_01.levelLead}</p>
          {cd && levelKeys.length >= 2 ? (
            <div className="space-y-4">
              <div className="card p-3">
                <p className="text-sm font-medium mb-1">금리 (%)</p>
                <SingleLine
                  keys={levelKeys}
                  values={toMap(cd.values)}
                  overlay={base ? toMap(base.values) : undefined}
                  label="시장금리 · CD(91일) (%)"
                  overlayLabel={base ? "기준금리" : undefined}
                  formatY={fmtRate}
                />
              </div>
              <div className="card p-3">
                <p className="text-sm font-medium mb-1">유동성 (조원)</p>
                <SingleLine
                  keys={levelKeys}
                  values={toMap(data?.m2?.values ?? [])}
                  label="M2 평잔 (조원)"
                  formatY={fmtEokWon}
                />
              </div>
              <div className="card p-3">
                <p className="text-sm font-medium mb-1">거래활동 (건/월)</p>
                <SingleLine
                  keys={levelKeys}
                  values={toMap(total?.count ?? [])}
                  label="전국 부동산 거래건수 (건/월)"
                  formatY={fmtCount}
                />
              </div>
              <div className="card p-3">
                <p className="text-sm font-medium mb-1">거래규모 (조원/월)</p>
                <SingleLine
                  keys={levelKeys}
                  values={toMap(total?.amount ?? [])}
                  label="전국 부동산 거래액 (조원/월)"
                  formatY={fmtManwon}
                />
              </div>
            </div>
          ) : null}
          <p className="text-xs text-slate-500">{INSIGHT_01.levelCaption}</p>
        </section>

        <section className="space-y-3">
          <h3 className="text-base font-semibold">변화율로 비교하기</h3>
          <div className={prose}>
            <Prose lines={INSIGHT_01.whyYoy} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded border border-slate-300 dark:border-slate-600 p-0.5">
              {(["count", "amount"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={clsx(
                    "px-2 py-0.5 text-[11px] rounded",
                    metric === m
                      ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
                      : "text-slate-600 dark:text-slate-300",
                  )}
                  onClick={() => setMetric(m)}
                >
                  {m === "count" ? "거래건수" : "거래액"}
                </button>
              ))}
            </div>
            <div className="inline-flex flex-wrap gap-1">
              {lags.map((k) => (
                <button
                  key={k}
                  type="button"
                  className={clsx(
                    "px-2 py-0.5 text-[11px] rounded border",
                    lag === k
                      ? "border-slate-800 bg-slate-800 text-white dark:border-slate-200 dark:bg-slate-200 dark:text-slate-900"
                      : "border-slate-300 text-slate-600 dark:border-slate-600 dark:text-slate-300",
                  )}
                  onClick={() => setLag(k)}
                >
                  {LAG_LABELS[k] ?? `+${k}`}
                </button>
              ))}
            </div>
          </div>
          {yoyRate ? (
            <div className="card p-3 space-y-2">
              <p className="text-sm font-medium">금리 변화와 거래</p>
              <div className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                <Prose lines={INSIGHT_01.chartRate} />
              </div>
              <DualLine
                keys={yoyRate.keys}
                left={yoyRate.left}
                right={yoyRate.right}
                leftLabel="CD 금리 (전년동월, %p)"
                rightLabel={`전체 ${metric === "count" ? "거래건수" : "거래액"} (전년동월, %)`}
                formatLeft={fmtPp}
                formatRight={fmtPct}
              />
            </div>
          ) : null}
          {yoyM2 ? (
            <div className="card p-3 space-y-2">
              <p className="text-sm font-medium">M2 변화와 거래</p>
              <div className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                <Prose lines={INSIGHT_01.chartM2} />
              </div>
              <DualLine
                keys={yoyM2.keys}
                left={yoyM2.left}
                right={yoyM2.right}
                leftLabel="M2 (전년동월, %)"
                rightLabel={`전체 ${metric === "count" ? "거래건수" : "거래액"} (전년동월, %)`}
                formatLeft={fmtPct}
                formatRight={fmtPct}
              />
            </div>
          ) : null}
        </section>

        {data ? (
          <section className="space-y-6">
            <h3 className="text-base font-semibold">숫자로 확인하기</h3>
            <CorrTable
              title="표 1 · 금리 변화 × 거래건수"
              lead={INSIGHT_01.table1}
              pairs={data.pairs}
              types={types}
              lags={lags}
              keyPrefix="cd_91_count"
            />
            <CorrTable
              title="표 2 · 금리 변화 × 거래액"
              lead={INSIGHT_01.table2}
              pairs={data.pairs}
              types={types}
              lags={lags}
              keyPrefix="cd_91_amount"
            />
            <CorrTable
              title="표 3 · M2 변화 × 거래건수"
              lead={INSIGHT_01.table3}
              pairs={data.pairs}
              types={types}
              lags={lags}
              keyPrefix="m2_count"
            />
            <CorrTable
              title="표 4 · M2 변화 × 거래액"
              lead={INSIGHT_01.table4}
              pairs={data.pairs}
              types={types}
              lags={lags}
              keyPrefix="m2_amount"
            />
            <details className="text-sm text-slate-600 dark:text-slate-300">
              <summary className="cursor-pointer">확인용 금리 (국고 3년·기준금리)</summary>
              <div className="mt-3 space-y-4">
                {data.rates.ktb_3y ? (
                  <CorrTable
                    title="국고 3년 × 거래건수"
                    lead="본문의 기준 금리는 CD 91일물입니다. 국고 3년은 같은 방법으로 함께 본 확인용 결과입니다."
                    pairs={data.pairs}
                    types={types}
                    lags={lags}
                    keyPrefix="ktb_3y_count"
                  />
                ) : null}
                {data.rates.bok_base ? (
                  <CorrTable
                    title="기준금리 × 거래건수"
                    lead="기준금리도 같은 방법으로 본 확인용 결과입니다."
                    pairs={data.pairs}
                    types={types}
                    lags={lags}
                    keyPrefix="bok_base_count"
                  />
                ) : null}
              </div>
            </details>
          </section>
        ) : null}

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">분석에서 확인되는 패턴</h3>
          <ol className="list-decimal ml-5 space-y-3">
            {INSIGHT_01.patterns.map((item, i) => (
              <li key={item.title}>
                <p className="font-medium text-slate-800 dark:text-slate-100">{item.title}</p>
                <p className="mt-1">{i === 1 ? pattern2 : item.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">이 분석의 한계</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {INSIGHT_01.limits.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <p>{INSIGHT_01.close}</p>
          <p className="text-xs text-slate-500">{INSIGHT_01.next}</p>
          {INSIGHT_01.relatedHref ? (
            <p>
              <a href={INSIGHT_01.relatedHref} className="text-slate-800 underline dark:text-slate-200">
                {INSIGHT_01.relatedLink}
              </a>
            </p>
          ) : null}
        </section>
      </article>
    </>
  );
}
