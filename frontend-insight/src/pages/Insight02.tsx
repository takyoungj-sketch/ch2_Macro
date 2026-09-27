import { useEffect, useMemo, useState, type ReactNode } from "react";
import clsx from "clsx";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import CorrHeatmap, { fmtSigned } from "../components/CorrHeatmap";
import SizeScatter from "../components/SizeScatter";
import {
  fetchInsight02,
  fetchInsight02Scatter,
  insight02AiFacts,
  type Insight02Pair,
  type Insight02Response,
  type Insight02ScatterResponse,
} from "../api/insightClient";
import { INSIGHT_02, formatAsOfMonth, pairLabel } from "../copy/insight02";

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

function pairKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

function findPair(pairs: Insight02Pair[], a: string, b: string): Insight02Pair | undefined {
  const k = pairKey(a, b);
  return pairs.find((p) => pairKey(p.a, p.b) === k);
}

function Seg({
  options,
  value,
  onChange,
}: {
  options: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="inline-flex rounded border border-slate-300 dark:border-slate-600 p-0.5">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          className={clsx(
            "px-2 py-0.5 text-[11px] rounded",
            value === o.id
              ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
              : "text-slate-600 dark:text-slate-300",
          )}
          onClick={() => onChange(o.id)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export default function Insight02() {
  const [data, setData] = useState<Insight02Response | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [popMode, setPopMode] = useState<"raw" | "pop">("raw");
  const [picked, setPicked] = useState<{ a: string; b: string }>({ a: "상가", b: "아파트" });
  const [pricePicked, setPricePicked] = useState<{ a: string; b: string } | null>(null);
  const [sizeScatter, setSizeScatter] = useState<Insight02ScatterResponse | null>(null);
  const [priceScatter, setPriceScatter] = useState<Insight02ScatterResponse | null>(null);
  const [scatterErr, setScatterErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetchInsight02()
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

  useEffect(() => {
    let live = true;
    setSizeScatter(null);
    setScatterErr(null);
    fetchInsight02Scatter(picked.a, picked.b, "amount")
      .then((d) => {
        if (live) setSizeScatter(d);
      })
      .catch((e: { message?: string }) => {
        if (live) setScatterErr(e?.message || "산점도를 불러오지 못했습니다.");
      });
    return () => {
      live = false;
    };
  }, [picked.a, picked.b]);

  useEffect(() => {
    if (!pricePicked) {
      setPriceScatter(null);
      return;
    }
    let live = true;
    setPriceScatter(null);
    fetchInsight02Scatter(pricePicked.a, pricePicked.b, "price")
      .then((d) => {
        if (live) setPriceScatter(d);
      })
      .catch(() => {
        if (live) setPriceScatter(null);
      });
    return () => {
      live = false;
    };
  }, [pricePicked?.a, pricePicked?.b]);

  const aiContext = useMemo(() => {
    return {
      app: "insight" as const,
      panel: "Insight02",
      purpose: "statistics" as const,
      scope: { region_label: "전국" },
      facts: data ? insight02AiFacts(data) : {},
      explain: {
        spec_id: "insight_02",
        spec_version: "1",
        title: INSIGHT_02.listTitle,
        summary: INSIGHT_02.intro[0],
        limitations: INSIGHT_02.limits,
      },
    };
  }, [data]);

  const types = data?.types?.length ? data.types : [];
  const priceTypes = data?.price_types?.length ? data.price_types : [];
  const asOf = formatAsOfMonth(data?.as_of);
  const years = data?.window_years ?? 3;

  const getSizeR = (a: string, b: string): number | null => {
    const p = data ? findPair(data.pairs, a, b) : undefined;
    if (!p) return null;
    return popMode === "pop" ? (p.amount.r_pop ?? null) : p.amount.r;
  };

  const getPriceR = (a: string, b: string): number | null => {
    const k = pairKey(a, b);
    const hit = data?.price_pairs.find((p) => pairKey(p.a, p.b) === k);
    return hit?.r ?? null;
  };

  const sizeHit = data ? findPair(data.pairs, picked.a, picked.b) : undefined;
  const sizeBlock = sizeHit?.amount ?? null;

  const priceHit = pricePicked
    ? data?.price_pairs.find((p) => pairKey(p.a, p.b) === pairKey(pricePicked.a, pricePicked.b))
    : undefined;

  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";

  const pickSize = (a: string, b: string) => {
    setPicked({ a, b });
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
          <h2 className="text-xl font-bold leading-snug">{INSIGHT_02.listTitle}</h2>
          <p className="text-sm text-slate-500">
            {INSIGHT_02.listSub}
          </p>
          <p className="text-sm text-slate-500">
            최근 {years}년 · 전국 · 시·군·구
            {asOf ? ` · 기준월 ${asOf}` : ""}
            {data ? ` · n=${data.n}` : ""}
          </p>
          <div className={prose}>
            <Prose lines={INSIGHT_02.intro} />
            <p>{INSIGHT_02.basis}</p>
            <p>
              <Term id="pearson_r">상관계수</Term>는 두 변수가 함께 움직이는 정도를 나타내고,{" "}
              <Term id="insight_cross">시·군·구</Term> 단위는 분석의 공간 단위입니다.{" "}
              <Term id="insight_pop_adj">인구 보정</Term>은 지역의 인구 규모 때문에 생길 수 있는 관계를 줄여서 보는
              방법입니다.
            </p>
          </div>
        </header>

        {err && <p className="text-sm text-red-600">{err}</p>}
        {!data && !err && (
          <p className="text-sm text-slate-500">숫자를 불러오는 중입니다. 처음이면 조금 걸릴 수 있습니다.</p>
        )}

        <section className="space-y-3">
          <h3 className="text-base font-semibold">① {INSIGHT_02.heatmapTitle}</h3>
          <div className={prose}>
            <Prose lines={INSIGHT_02.s1Before} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Seg
              options={[
                { id: "raw", label: INSIGHT_02.heatmapRaw },
                { id: "pop", label: INSIGHT_02.heatmapPop },
              ]}
              value={popMode}
              onChange={(id) => setPopMode(id as "raw" | "pop")}
            />
          </div>
          {data ? (
            <div className="card p-3">
              <CorrHeatmap types={types} getR={getSizeR} selected={picked} onSelect={pickSize} />
            </div>
          ) : null}
          <div className={prose}>
            <p className="font-medium text-slate-900 dark:text-slate-50">{INSIGHT_02.s1ExampleTitle}</p>
            <Prose lines={INSIGHT_02.s1Example} />
          </div>

          <div className="card p-4 space-y-3">
            <p className="text-sm font-medium">{pairLabel(picked.a, picked.b)}</p>
            {sizeBlock ? (
              <p className="text-sm tabular-nums text-slate-700 dark:text-slate-200">
                원래 {fmtSigned(sizeBlock.r)}
                <span className="mx-2 text-slate-400">→</span>
                인구 보정 {fmtSigned(sizeBlock.r_pop)}
                <span className="ml-2 text-xs text-slate-500">n={sizeBlock.n}</span>
              </p>
            ) : null}
            {scatterErr ? <p className="text-sm text-red-600">{scatterErr}</p> : null}
            {sizeScatter ? (
              <SizeScatter
                points={sizeScatter.points}
                a={sizeScatter.a}
                b={sizeScatter.b}
                xLabel="로그 거래액"
                yLabel="로그 거래액"
              />
            ) : !scatterErr ? (
              <p className="text-sm text-slate-500">산점도를 불러오는 중입니다.</p>
            ) : null}
            <p className="text-xs text-slate-500">{INSIGHT_02.scatterCaptionAmount}</p>
          </div>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold">② {INSIGHT_02.patternTitle}</h3>
          <p>{INSIGHT_02.patternLead}</p>
          <p className="font-medium text-slate-900 dark:text-slate-50">{INSIGHT_02.surviveTitle}</p>
          <p>{INSIGHT_02.surviveLead}</p>
          <ul className="list-disc ml-5 space-y-1">
            {INSIGHT_02.survivePairs.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <Prose lines={INSIGHT_02.surviveAfter} />
          <p className="font-medium text-slate-900 dark:text-slate-50">{INSIGHT_02.apparentTitle}</p>
          <p>{INSIGHT_02.apparentLead}</p>
          <ul className="list-disc ml-5 space-y-1">
            {INSIGHT_02.apparentPairs.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <Prose lines={INSIGHT_02.apparentAfter} />
          <p className="font-medium text-slate-900 dark:text-slate-50">{INSIGHT_02.reverseTitle}</p>
          <p>{INSIGHT_02.reverseLead}</p>
          <ul className="list-disc ml-5 space-y-1">
            {INSIGHT_02.reversePairs.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <Prose lines={INSIGHT_02.reverseAfter} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold">③ {INSIGHT_02.contrastTitle}</h3>
          <Prose lines={INSIGHT_02.s3} />
          <table className="data w-full max-w-md text-[13px]">
            <thead>
              <tr>
                <th className="text-left">유형</th>
                <th>거래규모</th>
                <th>거래건수</th>
              </tr>
            </thead>
            <tbody>
              {INSIGHT_02.s3Rows.map((row) => (
                <tr key={row.pair}>
                  <td className="text-left">{row.pair}</td>
                  <td>{row.amount}</td>
                  <td>{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Prose lines={INSIGHT_02.s3After} />
        </section>

        <section className="space-y-3">
          <h3 className="text-base font-semibold">④ {INSIGHT_02.priceTitle}</h3>
          <div className={prose}>
            <p>
              이번에는 거래규모가 아니라 시·군·구별 유형의 <Term id="insight_p50">㎡당 가격 중위값(P50)</Term>을
              비교했습니다.
            </p>
            <Prose lines={INSIGHT_02.s4.slice(1, 5)} />
            <p>{INSIGHT_02.s4[5]}</p>
            <ul className="list-disc ml-5 space-y-1">
              {INSIGHT_02.s4High.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
          {data ? (
            <div className="card p-3">
              <CorrHeatmap
                types={[...priceTypes]}
                getR={getPriceR}
                selected={pricePicked}
                onSelect={(a, b) => setPricePicked({ a, b })}
              />
            </div>
          ) : null}
          <p className="text-xs text-slate-500">{INSIGHT_02.priceCaption}</p>
          {pricePicked && priceHit ? (
            <div className="card p-4 space-y-3">
              <p className="text-sm font-medium">{pairLabel(pricePicked.a, pricePicked.b)}</p>
              <p className="text-sm tabular-nums">
                {fmtSigned(priceHit.r)}
                <span className="ml-2 text-xs text-slate-500">n={priceHit.n}</span>
              </p>
              {priceScatter ? (
                <SizeScatter
                  points={priceScatter.points}
                  a={priceScatter.a}
                  b={priceScatter.b}
                  xLabel="로그 ㎡당 중앙값"
                  yLabel="로그 ㎡당 중앙값"
                />
              ) : null}
              <p className="text-xs text-slate-500">{INSIGHT_02.scatterCaptionPrice}</p>
            </div>
          ) : null}
          <div className={prose}>
            <Prose lines={INSIGHT_02.s4After} />
          </div>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold">⑤ {INSIGHT_02.withinTitle}</h3>
          <Prose lines={INSIGHT_02.within} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold">{INSIGHT_02.patternsTitle}</h3>
          <ol className="list-decimal ml-5 space-y-2">
            {INSIGHT_02.patterns.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ol>
          <Prose lines={INSIGHT_02.patternsAfter} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold">{INSIGHT_02.limitsTitle}</h3>
          <ul className="list-disc pl-5 space-y-1">
            {INSIGHT_02.limits.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <Prose lines={INSIGHT_02.close} />
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold">{INSIGHT_02.nextTitle}</h3>
          <ul className="list-disc pl-5 space-y-1">
            {INSIGHT_02.next.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>

        <section className={prose}>
          <h3 className="text-base font-semibold">{INSIGHT_02.relatedTitle}</h3>
          <Prose lines={INSIGHT_02.related} />
          <p>
            <a href={INSIGHT_02.relatedHref} className="text-slate-800 underline dark:text-slate-200">
              {INSIGHT_02.relatedLink}
            </a>
          </p>
        </section>
      </article>
    </>
  );
}
