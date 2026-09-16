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
  type SizeCorr,
} from "../api/insightClient";
import { INSIGHT_02, SIZE_GROUPS, formatAsOfMonth, pairLabel } from "../copy/insight02";

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

type ReadKind = "survive" | "apparent" | "reverse" | "weak" | "missing";

function readKind(block: SizeCorr | null | undefined): ReadKind {
  if (!block || block.r == null) return "missing";
  const r = block.r;
  const rp = block.r_pop;
  if (rp != null && rp <= SIZE_GROUPS.reversePop) return "reverse";
  if (rp != null && rp >= SIZE_GROUPS.survivePop) return "survive";
  if (r >= SIZE_GROUPS.apparentR && (rp == null || rp < SIZE_GROUPS.apparentPop)) return "apparent";
  return "weak";
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
  const kind = readKind(sizeBlock);

  const groups = useMemo(() => {
    const pairs = data?.pairs ?? [];
    const scored = pairs.map((p) => ({ p, block: p.amount })).filter((x) => x.block.r != null);
    const survive = scored
      .filter((x) => x.block.r_pop != null && (x.block.r_pop as number) >= SIZE_GROUPS.survivePop)
      .sort((a, b) => (b.block.r_pop ?? 0) - (a.block.r_pop ?? 0))
      .slice(0, 5);
    const apparent = scored
      .filter(
        (x) =>
          (x.block.r as number) >= SIZE_GROUPS.apparentR &&
          (x.block.r_pop == null || x.block.r_pop < SIZE_GROUPS.apparentPop),
      )
      .sort((a, b) => (b.block.r as number) - (a.block.r as number))
      .slice(0, 5);
    const taken = new Set([...survive, ...apparent].map((x) => pairKey(x.p.a, x.p.b)));
    const reverse = scored
      .filter((x) => !taken.has(pairKey(x.p.a, x.p.b)))
      .filter(
        (x) =>
          (x.block.r_pop != null && (x.block.r_pop as number) <= SIZE_GROUPS.reversePop) ||
          ((x.block.r as number) < 0.35 &&
            (x.block.r_pop == null || Math.abs(x.block.r_pop) < SIZE_GROUPS.apparentPop)),
      )
      .sort((a, b) => (a.block.r_pop ?? 1) - (b.block.r_pop ?? 1))
      .slice(0, 5);
    return { survive, apparent, reverse };
  }, [data]);

  const diverge = useMemo(() => {
    const pairs = data?.pairs ?? [];
    return pairs
      .filter((p) => p.amount.r != null && p.count.r != null)
      .map((p) => ({
        p,
        gap: Math.abs((p.amount.r as number) - (p.count.r as number)),
        signFlip:
          ((p.amount.r as number) > 0.05 && (p.count.r as number) < -0.05) ||
          ((p.amount.r as number) < -0.05 && (p.count.r as number) > 0.05),
      }))
      .filter((x) => x.signFlip || x.gap >= SIZE_GROUPS.divergeAbs)
      .sort((a, b) => b.gap - a.gap)
      .slice(0, 5);
  }, [data]);

  const priceHighlights = useMemo(() => {
    const pairs = data?.pairs ?? [];
    const prices = data?.price_pairs ?? [];
    return prices
      .filter((pp) => pp.r != null && pp.r >= 0.7)
      .map((pp) => {
        const size = findPair(pairs, pp.a, pp.b);
        return { pp, size };
      })
      .filter((x) => x.size?.amount.r_pop != null && (x.size.amount.r_pop as number) < SIZE_GROUPS.apparentPop)
      .sort((a, b) => (b.pp.r as number) - (a.pp.r as number))
      .slice(0, 3);
  }, [data]);

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
          <p className="inline-flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <span className="rounded bg-amber-100 px-2 py-0.5 font-medium text-amber-950 dark:bg-amber-900/40 dark:text-amber-100">
              최근 {years}년
            </span>
            <span className="text-slate-500">전국 · 시군구{asOf ? ` · 기준월 ${asOf}` : ""}</span>
            {data ? <span className="text-slate-500">· n={data.n}</span> : null}
          </p>
          <div className={prose}>
            <Prose lines={INSIGHT_02.intro} />
            <p>
              {INSIGHT_02.basis} <Term id="pearson_r">상관계수</Term> ·{" "}
              <Term id="insight_cross">시군구 단면</Term> · <Term id="insight_pop_adj">인구 보정</Term>
            </p>
          </div>
        </header>

        {err && <p className="text-sm text-red-600">{err}</p>}
        {!data && !err && (
          <p className="text-sm text-slate-500">숫자를 불러오는 중입니다. 처음이면 조금 걸릴 수 있습니다.</p>
        )}

        <section className="space-y-3">
          <h3 className="text-base font-semibold">① {INSIGHT_02.heatmapTitle}</h3>
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
          <p className="text-xs text-slate-500">{INSIGHT_02.heatmapCaption}</p>

          <div className="card p-4 space-y-3">
            <p className="text-sm font-medium">{pairLabel(picked.a, picked.b)}</p>
            {sizeBlock ? (
              <p className="text-sm tabular-nums text-slate-700 dark:text-slate-200">
                {INSIGHT_02.beforeAfter} {fmtSigned(sizeBlock.r)}
                <span className="mx-2 text-slate-400">→</span>
                {INSIGHT_02.afterPop} {fmtSigned(sizeBlock.r_pop)}
                <span className="ml-2 text-xs text-slate-500">n={sizeBlock.n}</span>
              </p>
            ) : null}
            <p className="text-sm text-slate-600 dark:text-slate-300">{INSIGHT_02.reads[kind]}</p>
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

        <section className="space-y-4">
          <h3 className="text-base font-semibold">② {INSIGHT_02.patternTitle}</h3>
          <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">{INSIGHT_02.patternLead}</p>
          {(
            [
              ["survive", INSIGHT_02.surviveTitle, INSIGHT_02.surviveBody, INSIGHT_02.surviveTag, groups.survive],
              ["apparent", INSIGHT_02.apparentTitle, INSIGHT_02.apparentBody, INSIGHT_02.apparentTag, groups.apparent],
              ["reverse", INSIGHT_02.reverseTitle, INSIGHT_02.reverseBody, INSIGHT_02.reverseTag, groups.reverse],
            ] as const
          ).map(([key, title, body, tag, rows]) => (
            <div key={key} className="card p-4 space-y-3">
              <p className="text-sm font-medium">{title}</p>
              <p className="text-sm text-slate-600 dark:text-slate-300">{body}</p>
              {rows.length === 0 ? (
                <p className="text-sm text-slate-500">{INSIGHT_02.emptyGroup}</p>
              ) : (
                <ul className="grid gap-2 sm:grid-cols-2">
                  {rows.map(({ p, block }) => (
                    <li key={`${p.a}|${p.b}`}>
                      <button
                        type="button"
                        className="w-full rounded border border-slate-200 dark:border-slate-600 px-3 py-2 text-left hover:border-slate-400"
                        onClick={() => pickSize(p.a, p.b)}
                      >
                        <p className="text-sm font-medium text-slate-900 dark:text-slate-50">
                          {pairLabel(p.a, p.b)}
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5">{tag}</p>
                        <p className="text-xs tabular-nums text-slate-600 dark:text-slate-300 mt-1">
                          {fmtSigned(block.r)} → {fmtSigned(block.r_pop)}
                        </p>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </section>

        <section className="space-y-3">
          <h3 className="text-base font-semibold">③ {INSIGHT_02.contrastTitle}</h3>
          <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">{INSIGHT_02.contrastLead}</p>
          <p className="text-xs text-slate-500">{INSIGHT_02.contrastHint}</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {diverge.map(({ p }) => (
              <li key={`${p.a}|${p.b}`}>
                <button
                  type="button"
                  className="card w-full p-4 text-left hover:border-slate-400"
                  onClick={() => pickSize(p.a, p.b)}
                >
                  <p className="text-sm font-medium">{pairLabel(p.a, p.b)}</p>
                  <p className="mt-2 text-sm tabular-nums text-slate-700 dark:text-slate-200">
                    규모 {fmtSigned(p.amount.r)}
                  </p>
                  <p className="text-sm tabular-nums text-slate-700 dark:text-slate-200">
                    건수 {fmtSigned(p.count.r)}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-3">
          <h3 className="text-base font-semibold">④ {INSIGHT_02.priceTitle}</h3>
          <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">
            {INSIGHT_02.priceLead} <Term id="insight_p50">㎡당 중앙값</Term>
          </p>
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
          {priceHighlights.length > 0 ? (
            <ul className="grid gap-2 sm:grid-cols-2">
              {priceHighlights.map(({ pp, size }) => (
                <li key={`${pp.a}|${pp.b}`}>
                  <button
                    type="button"
                    className="card w-full p-4 text-left hover:border-slate-400"
                    onClick={() => setPricePicked({ a: pp.a, b: pp.b })}
                  >
                    <p className="text-sm font-medium">{pairLabel(pp.a, pp.b)}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{INSIGHT_02.priceHighlightTag}</p>
                    <p className="text-xs tabular-nums text-slate-600 dark:text-slate-300 mt-1">
                      규모 {fmtSigned(size?.amount.r ?? null)} → {fmtSigned(size?.amount.r_pop ?? null)} · 단가{" "}
                      {fmtSigned(pp.r)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-200">{INSIGHT_02.priceClose}</p>
        </section>

        <details className="card p-4 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
          <summary className="cursor-pointer font-medium text-slate-900 dark:text-slate-50">
            ⑤ {INSIGHT_02.withinTitle}
          </summary>
          <div className="mt-3 space-y-2">
            <p>{INSIGHT_02.withinLead}</p>
            <Prose lines={INSIGHT_02.withinBody} />
          </div>
        </details>

        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">이 분석의 한계</h3>
          <ul className="list-disc pl-5 space-y-1">
            {INSIGHT_02.limits.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p>{INSIGHT_02.close}</p>
          <p className="text-xs text-slate-500">{INSIGHT_02.next}</p>
        </section>
      </article>
    </>
  );
}
