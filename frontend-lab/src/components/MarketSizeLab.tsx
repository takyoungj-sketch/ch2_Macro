import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchMarketSizeLab,
  type SizeCorr,
  type SizeLevel,
  type SizeMetric,
  type SizePair,
  type SizeScatterPoint,
} from "../api/marketSizeClient";
import ExpHelp, { type ExpHelpDoc } from "./ExpHelp";
import { SIZE_HELP } from "./marketSizeHelp";

const LEVELS: { id: SizeLevel; label: string }[] = [
  { id: "sigungu", label: "시군구" },
  { id: "eupmyeondong", label: "읍면동" },
  { id: "beopjungri", label: "리" },
];

function fmtR(r: number | null | undefined): string {
  if (r == null || Number.isNaN(r)) return "—";
  const sign = r > 0 ? "+" : "";
  return `${sign}${r.toFixed(2)}`;
}

function pairKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

function metricBlock(p: SizePair, metric: SizeMetric): SizeCorr {
  return metric === "amount" ? p.amount : p.count;
}

function shareBlock(p: SizePair, metric: SizeMetric): { n: number; r: number | null } {
  return metric === "amount" ? p.share_amount : p.share_count;
}

function olsLine(xs: number[], ys: number[]): { a: number; b: number } | null {
  const n = xs.length;
  if (n < 2 || n !== ys.length) return null;
  const mx = xs.reduce((s, v) => s + v, 0) / n;
  const my = ys.reduce((s, v) => s + v, 0) / n;
  let num = 0;
  let dx = 0;
  for (let i = 0; i < n; i++) {
    const vx = xs[i] - mx;
    num += vx * (ys[i] - my);
    dx += vx * vx;
  }
  if (dx <= 0) return null;
  const b = num / dx;
  return { a: my - b * mx, b };
}

function SizeScatter({
  points,
  a,
  b,
  metric,
}: {
  points: SizeScatterPoint[];
  a: string;
  b: string;
  metric: SizeMetric;
}) {
  const w = 520;
  const h = 340;
  const pad = { l: 48, r: 12, t: 12, b: 36 };
  if (points.length < 2) {
    return <p className="text-sm text-slate-500">점이 부족합니다.</p>;
  }
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const dx = maxX - minX || 1;
  const dy = maxY - minY || 1;
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const toX = (v: number) => pad.l + ((v - minX) / dx) * innerW;
  const toY = (v: number) => pad.t + (1 - (v - minY) / dy) * innerH;
  const fit = olsLine(xs, ys);
  const unit = metric === "amount" ? "로그 거래액" : "로그 건수";
  const x0 = minX;
  const x1 = maxX;
  const y0 = fit ? fit.a + fit.b * x0 : 0;
  const y1 = fit ? fit.a + fit.b * x1 : 0;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full max-w-[34rem] h-auto text-slate-400">
      <rect
        x={pad.l}
        y={pad.t}
        width={innerW}
        height={innerH}
        fill="transparent"
        className="stroke-slate-200 dark:stroke-slate-700"
      />
      {fit && (
        <line
          x1={toX(x0)}
          y1={toY(y0)}
          x2={toX(x1)}
          y2={toY(y1)}
          className="stroke-amber-600 dark:stroke-amber-400"
          strokeWidth={1.5}
        />
      )}
      {points.map((p) => (
        <circle
          key={p.code}
          cx={toX(p.x)}
          cy={toY(p.y)}
          r={2.2}
          className="fill-slate-500/55 dark:fill-slate-300/50"
        >
          <title>
            {p.name} · {a} {p.x_raw.toLocaleString("ko-KR")} · {b} {p.y_raw.toLocaleString("ko-KR")}
          </title>
        </circle>
      ))}
      <text x={w / 2} y={h - 8} textAnchor="middle" className="fill-current text-[10px]">
        {a} ({unit})
      </text>
      <text
        x={14}
        y={h / 2}
        textAnchor="middle"
        transform={`rotate(-90 14 ${h / 2})`}
        className="fill-current text-[10px]"
      >
        {b} ({unit})
      </text>
    </svg>
  );
}

type Scored = { p: SizePair; r: number; rPop: number | null; n: number };

export default function MarketSizeLab() {
  const [level, setLevel] = useState<SizeLevel>("sigungu");
  const [metric, setMetric] = useState<SizeMetric>("amount");
  const [togetherMin, setTogetherMin] = useState(0.5);
  const [adjTogetherMin, setAdjTogetherMin] = useState(0.4);
  const [oppositeMax, setOppositeMax] = useState(-0.3);
  const [weakAbs, setWeakAbs] = useState(0.2);
  const [showShare, setShowShare] = useState(false);
  const [showAllPairs, setShowAllPairs] = useState(false);
  const [picked, setPicked] = useState<{ a: string; b: string } | null>({ a: "아파트", b: "상가" });

  const q = useQuery({
    queryKey: ["lab-market-size", level, picked?.a, picked?.b, metric],
    queryFn: () =>
      fetchMarketSizeLab({
        regionLevel: level,
        scatterA: picked?.a,
        scatterB: picked?.b,
        scatterMetric: metric,
      }),
  });

  const buckets = useMemo(() => {
    const pairs = q.data?.pairs ?? [];
    const scored: Scored[] = pairs
      .map((p) => {
        const b = metricBlock(p, metric);
        return { p, r: b.r, rPop: b.r_pop ?? null, n: b.n };
      })
      .filter((x): x is Scored => x.r != null);
    const together = scored.filter((x) => x.r >= togetherMin).sort((a, b) => b.r - a.r);
    const adjTogether = scored
      .filter((x) => x.rPop != null && x.rPop >= adjTogetherMin)
      .sort((a, b) => (b.rPop ?? 0) - (a.rPop ?? 0));
    const opposite = scored
      .filter((x) => x.rPop != null && x.rPop <= oppositeMax)
      .sort((a, b) => (a.rPop ?? 0) - (b.rPop ?? 0));
    const weak = scored
      .filter((x) => x.rPop != null && Math.abs(x.rPop) < weakAbs)
      .sort((a, b) => Math.abs(a.rPop ?? 0) - Math.abs(b.rPop ?? 0));
    return { together, adjTogether, opposite, weak };
  }, [q.data, metric, togetherMin, adjTogetherMin, oppositeMax, weakAbs]);

  const popRows = useMemo(() => {
    const rows = q.data?.population_axis ?? [];
    return [...rows].sort((a, b) => {
      const ra = (metric === "amount" ? a.amount.r : a.count.r) ?? -999;
      const rb = (metric === "amount" ? b.amount.r : b.count.r) ?? -999;
      return rb - ra;
    });
  }, [q.data, metric]);

  const pickedBlock = useMemo(() => {
    if (!picked || !q.data) return null;
    const hit = q.data.pairs.find((p) => pairKey(p.a, p.b) === pairKey(picked.a, picked.b));
    return hit ? metricBlock(hit, metric) : null;
  }, [q.data, picked, metric]);

  const err = q.isError ? ((q.error as { message?: string })?.message ?? "불러오지 못했습니다") : null;
  const sampled =
    !!q.data?.scatter && q.data.scatter.points.length < q.data.scatter.n_positive;
  const visiblePricePairs = useMemo(
    () => (q.data?.price_pairs ?? []).filter((p) => p.price.n > 0),
    [q.data],
  );
  const hasWithinVolume = useMemo(() => {
    const pairs = q.data?.pairs ?? [];
    return pairs.some((p) => {
      const w = metric === "amount" ? p.within_amount : p.within_count;
      return (w?.n_parents ?? 0) > 0;
    });
  }, [q.data, metric]);
  const hasWithinPrice = useMemo(
    () => visiblePricePairs.some((p) => (p.within_price.n_parents ?? 0) > 0),
    [visiblePricePairs],
  );
  const missingPriceTypes =
    q.data?.price_missing_types ??
    (q.data?.price_types ?? []).filter((t) => !visiblePricePairs.some((p) => p.a === t || p.b === t));
  const withinEmpty =
    level === "sigungu"
      ? "시군구 화면에는 내부 비교가 없습니다. 읍면동 또는 리를 고르면 표가 나옵니다."
      : "이 체급에서 시군구당 하위지역 3곳 이상인 내부 비교가 없습니다.";

  return (
    <div className="max-w-6xl mx-auto px-4 py-4 space-y-4 pb-10">
      <div className="flex items-start gap-2">
        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          같은 행정 체급의 지역을 대상으로 유형별 3년 거래규모의 <strong>로그 Pearson r</strong>을 계산합니다.
          ① 거래 있음 비율 → ② 시군구 내부(읍·리) → ③ ㎡당 P50(인구 보정 없음) → ④ 단가의 시군구 내부.
          시계열 동조·순수한 상관이 아닙니다. 각 창의 <strong>?</strong>에 실험 방법·한계·의미가 있습니다.
        </p>
        <ExpHelp doc={SIZE_HELP.overview} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center text-xs text-slate-500">
          체급
          <ExpHelp doc={SIZE_HELP.grain} size="xs" />
        </span>
        {LEVELS.map((lv) => (
          <button
            key={lv.id}
            type="button"
            className={clsx(
              "rounded-md border px-2.5 py-1 text-xs font-semibold",
              level === lv.id
                ? "border-amber-600 bg-amber-50 text-amber-950 dark:border-amber-400 dark:bg-amber-950 dark:text-amber-100"
                : "border-slate-300 text-slate-600 dark:border-slate-600 dark:text-slate-300",
            )}
            onClick={() => setLevel(lv.id)}
          >
            {lv.label}
          </button>
        ))}
        <span className="ml-2 inline-flex items-center gap-1">
          <span className="text-xs text-slate-500">규모</span>
          <ExpHelp doc={SIZE_HELP.metric} size="xs" />
          <div className="inline-flex rounded border border-slate-300 dark:border-slate-600 p-0.5">
          <button
            type="button"
            className={clsx(
              "px-2 py-0.5 text-[11px] rounded",
              metric === "amount" ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900" : "text-slate-600",
            )}
            onClick={() => setMetric("amount")}
          >
            거래금액
          </button>
          <button
            type="button"
            className={clsx(
              "px-2 py-0.5 text-[11px] rounded",
              metric === "count" ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900" : "text-slate-600",
            )}
            onClick={() => setMetric("count")}
          >
            거래건수
          </button>
          </div>
        </span>
        <label className="text-[11px] text-slate-500 flex items-center gap-1 ml-2">
          <input type="checkbox" checked={showShare} onChange={(e) => setShowShare(e.target.checked)} />
          비중 r (비교용)
        </label>
      </div>

      <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
        <label className="flex items-center gap-1">
          함께 큼 로그 r ≥
          <input
            type="number"
            step="0.05"
            className="w-16 rounded border px-1 py-0.5 dark:bg-slate-800 dark:border-slate-600"
            value={togetherMin}
            onChange={(e) => setTogetherMin(Number(e.target.value))}
          />
        </label>
        <label className="flex items-center gap-1">
          보정 후 함께 ≥
          <input
            type="number"
            step="0.05"
            className="w-16 rounded border px-1 py-0.5 dark:bg-slate-800 dark:border-slate-600"
            value={adjTogetherMin}
            onChange={(e) => setAdjTogetherMin(Number(e.target.value))}
          />
        </label>
        <label className="flex items-center gap-1">
          약함 |보정 r| &lt;
          <input
            type="number"
            step="0.05"
            className="w-16 rounded border px-1 py-0.5 dark:bg-slate-800 dark:border-slate-600"
            value={weakAbs}
            onChange={(e) => setWeakAbs(Number(e.target.value))}
          />
        </label>
        <label className="flex items-center gap-1">
          반대 보정 r ≤
          <input
            type="number"
            step="0.05"
            className="w-16 rounded border px-1 py-0.5 dark:bg-slate-800 dark:border-slate-600"
            value={oppositeMax}
            onChange={(e) => setOppositeMax(Number(e.target.value))}
          />
        </label>
      </div>

      {q.isLoading && <p className="text-sm text-slate-500">같은 결 전국 벡터를 읽고 있습니다…</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      {q.data && (
        <p className="text-[11px] text-slate-500">
          {q.data.as_of_month} · {q.data.profile_version} · 창 {q.data.window_years}년 · 유니버스{" "}
          {q.data.universe_n.toLocaleString("ko-KR")}곳
          {q.data.dropped_dong ? ` · 리가 아닌 …00 ${q.data.dropped_dong}곳 제외` : ""}
          {q.data.added_city ? ` · 일반구 있는 시 ${q.data.added_city}곳 포함` : ""} · 사용{" "}
          {q.data.n.toLocaleString("ko-KR")}곳 · 행을 누르면 산점도
        </p>
      )}

      {q.data && (
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
          <Bucket
            title="함께 큰 유형"
            help={SIZE_HELP.together}
            empty="문턱을 넘는 로그 r 쌍이 없습니다."
            rows={buckets.together.slice(0, 5)}
            mode="log"
            metric={metric}
            showShare={showShare}
            picked={picked}
            onPick={setPicked}
          />
          <Bucket
            title="인구 보정 후에도 함께 큰"
            help={SIZE_HELP.adjTogether}
            empty="보정 r 문턱을 넘는 쌍이 없습니다."
            rows={buckets.adjTogether.slice(0, 5)}
            mode="adj"
            metric={metric}
            showShare={showShare}
            picked={picked}
            onPick={setPicked}
          />
          <Bucket
            title="관계가 약한 유형"
            help={SIZE_HELP.weak}
            empty="보정 r이 문턱 안인 쌍이 없습니다."
            rows={buckets.weak.slice(0, 5)}
            mode="adj"
            metric={metric}
            showShare={showShare}
            picked={picked}
            onPick={setPicked}
          />
          <Bucket
            title="반대로 나타나는 유형"
            help={SIZE_HELP.opposite}
            empty="보정 r이 문턱 이하 음수인 쌍이 없습니다."
            rows={buckets.opposite.slice(0, 5)}
            mode="adj"
            metric={metric}
            showShare={showShare}
            picked={picked}
            onPick={setPicked}
          />
        </div>
      )}

      {q.data?.scatter && picked && (
        <section className="card p-4">
          <h2 className="text-sm font-semibold inline-flex items-center">
            산점도 · {picked.a} × {picked.b}
            <ExpHelp doc={SIZE_HELP.scatter} />
          </h2>
          <p className="mt-1 text-sm tabular-nums">
            로그 r {fmtR(pickedBlock?.r)} · n {(pickedBlock?.n ?? 0).toLocaleString("ko-KR")} · 인구 보정 r{" "}
            {fmtR(pickedBlock?.r_pop)}
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            양축 로그. 노란 선은 표시 점의 최소제곱. 양쪽 거래가 있는 점만. 표시{" "}
            {q.data.scatter.points.length.toLocaleString("ko-KR")} / 양수 {q.data.scatter.n_positive.toLocaleString("ko-KR")}곳
            {sampled ? " (표본 — 회귀선도 표본 기준)" : ""}
          </p>
          <div className="mt-3">
            <SizeScatter points={q.data.scatter.points} a={q.data.scatter.a} b={q.data.scatter.b} metric={metric} />
          </div>
        </section>
      )}

      {q.data && (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700">
            <h2 className="text-sm font-semibold inline-flex items-center">
              인구 ↔ 유형별 거래규모
              <ExpHelp doc={SIZE_HELP.popAxis} />
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="data w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left">유형</th>
                  <th>로그 r</th>
                  <th>n</th>
                </tr>
              </thead>
              <tbody>
                {popRows.map((row) => {
                  const block = metric === "amount" ? row.amount : row.count;
                  return (
                    <tr key={row.type}>
                      <td className="text-left">{row.type}</td>
                      <td className="tabular-nums">{fmtR(block.r)}</td>
                      <td className="tabular-nums">{block.n.toLocaleString("ko-KR")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {q.data && (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1 min-w-0">
              <span className="text-sm font-semibold">28쌍 전체</span>
              <ExpHelp doc={SIZE_HELP.allPairs} />
              <span className="ml-1 text-[11px] text-slate-500">실험용 원표 · 계산은 전부</span>
            </span>
            <button
              type="button"
              className="shrink-0 text-[11px] text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
              onClick={() => setShowAllPairs((v) => !v)}
            >
              {showAllPairs ? "접기" : "펴기"}
            </button>
          </div>
          {showAllPairs && (
            <div className="overflow-x-auto border-t border-slate-100 dark:border-slate-700">
              <table className="data w-full text-xs">
                <thead>
                  <tr>
                    <th className="text-left">쌍</th>
                    <th>로그 r</th>
                    <th>n</th>
                    <th>인구 보정 r</th>
                    {showShare && <th>비중 r</th>}
                  </tr>
                </thead>
                <tbody>
                  {[...q.data.pairs]
                    .sort((a, b) => (metricBlock(b, metric).r ?? -9) - (metricBlock(a, metric).r ?? -9))
                    .map((p) => {
                      const block = metricBlock(p, metric);
                      const share = shareBlock(p, metric);
                      const active = picked && pairKey(picked.a, picked.b) === pairKey(p.a, p.b);
                      return (
                        <tr
                          key={`${p.a}-${p.b}`}
                          className={clsx("cursor-pointer", active && "bg-amber-50 dark:bg-amber-950/40")}
                          onClick={() => setPicked({ a: p.a, b: p.b })}
                        >
                          <td className="text-left">
                            {p.a} × {p.b}
                          </td>
                          <td className="tabular-nums">{fmtR(block.r)}</td>
                          <td className="tabular-nums">{block.n.toLocaleString("ko-KR")}</td>
                          <td className="tabular-nums">{fmtR(block.r_pop)}</td>
                          {showShare && <td className="tabular-nums">{fmtR(share.r)}</td>}
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {q.data?.presence && (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700">
            <h2 className="text-sm font-semibold inline-flex items-center">
              ① 거래 있음 비율 (n 붕괴)
              <ExpHelp doc={SIZE_HELP.presence} />
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              3년 거래액 &gt; 0인 곳. 핵심 4유형(토지·상가·단독·아파트) 모두 있음 {q.data.core4_n?.toLocaleString("ko-KR")}곳
              / {q.data.n.toLocaleString("ko-KR")}
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="data w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left">유형</th>
                  <th>있음</th>
                  <th>비율</th>
                </tr>
              </thead>
              <tbody>
                {q.data.presence.map((row) => (
                  <tr key={row.type}>
                    <td className="text-left">{row.type}</td>
                    <td className="tabular-nums">{row.n_pos.toLocaleString("ko-KR")}</td>
                    <td className="tabular-nums">{(row.pct * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {q.data && (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700">
            <h2 className="text-sm font-semibold inline-flex items-center">
              ② 시군구 내부 거래규모
              <ExpHelp doc={SIZE_HELP.withinVolume} />
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              같은 시군구 5자리 안에서 로그 규모를 뺀 뒤 Pearson. 시군구당 양쪽 거래 있는 하위지역 3곳 이상.
            </p>
          </div>
          {hasWithinVolume ? (
          <div className="overflow-x-auto">
            <table className="data w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left">쌍</th>
                  <th>내부 r</th>
                  <th>내부 인구보정 r</th>
                  <th>시군구</th>
                  <th>n</th>
                </tr>
              </thead>
              <tbody>
                {[...q.data.pairs]
                  .map((p) => ({ p, w: metric === "amount" ? p.within_amount : p.within_count }))
                  .filter((x) => x.w && x.w.r != null)
                  .sort((a, b) => (b.w!.r ?? -9) - (a.w!.r ?? -9))
                  .map(({ p, w }) => (
                    <tr key={`w-${p.a}-${p.b}`}>
                      <td className="text-left">
                        {p.a} × {p.b}
                      </td>
                      <td className="tabular-nums">{fmtR(w!.r)}</td>
                      <td className="tabular-nums">{fmtR(w!.r_pop)}</td>
                      <td className="tabular-nums">{w!.n_parents ?? "—"}</td>
                      <td className="tabular-nums">{w!.n.toLocaleString("ko-KR")}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          ) : (
            <p className="px-4 py-3 text-xs text-slate-500">{withinEmpty}</p>
          )}
        </section>
      )}

      {q.data?.price_pairs && (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700">
            <h2 className="text-sm font-semibold inline-flex items-center">
              ③ ㎡당 P50 상관 (인구 보정 없음)
              <ExpHelp doc={SIZE_HELP.unitPrice} />
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">{q.data.price_note}</p>
            {missingPriceTypes.length > 0 && (
              <p className="text-[11px] text-slate-500 mt-0.5">
                이 체급에 ㎡당 마트가 없는 유형: {missingPriceTypes.join(" · ")}. 표에서 뺐습니다.
                규모 실험의 같은 이름과 섞어 읽지 마세요.
              </p>
            )}
          </div>
          {visiblePricePairs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="data w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left">쌍</th>
                  <th>로그 r</th>
                  <th>n</th>
                </tr>
              </thead>
              <tbody>
                {[...visiblePricePairs]
                  .sort((a, b) => (b.price.r ?? -9) - (a.price.r ?? -9))
                  .map((p) => (
                    <tr key={`pr-${p.a}-${p.b}`}>
                      <td className="text-left">
                        {p.a} × {p.b}
                      </td>
                      <td className="tabular-nums">{fmtR(p.price.r)}</td>
                      <td className="tabular-nums">{p.price.n.toLocaleString("ko-KR")}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          ) : (
            <p className="px-4 py-3 text-xs text-slate-500">이 체급에서 양쪽 단가가 있는 쌍이 없습니다.</p>
          )}
        </section>
      )}

      {q.data?.price_pairs && (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700">
            <h2 className="text-sm font-semibold inline-flex items-center">
              ④ 시군구 내부 ㎡당 P50
              <ExpHelp doc={SIZE_HELP.withinPrice} />
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">인구 보정 없음. 시군구당 양쪽 단가 있는 하위지역 3곳 이상.</p>
            {missingPriceTypes.length > 0 && (
              <p className="text-[11px] text-slate-500 mt-0.5">
                {missingPriceTypes.join(" · ")} 단가는 이 체급 마트가 없어 내부표에도 없습니다.
              </p>
            )}
          </div>
          {hasWithinPrice ? (
          <div className="overflow-x-auto">
            <table className="data w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left">쌍</th>
                  <th>내부 r</th>
                  <th>시군구</th>
                  <th>n</th>
                </tr>
              </thead>
              <tbody>
                {visiblePricePairs
                  .filter((p) => p.within_price.r != null)
                  .sort((a, b) => (b.within_price.r ?? -9) - (a.within_price.r ?? -9))
                  .map((p) => (
                    <tr key={`wp-${p.a}-${p.b}`}>
                      <td className="text-left">
                        {p.a} × {p.b}
                      </td>
                      <td className="tabular-nums">{fmtR(p.within_price.r)}</td>
                      <td className="tabular-nums">{p.within_price.n_parents ?? "—"}</td>
                      <td className="tabular-nums">{p.within_price.n.toLocaleString("ko-KR")}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          ) : (
            <p className="px-4 py-3 text-xs text-slate-500">{withinEmpty}</p>
          )}
        </section>
      )}
    </div>
  );
}

function Bucket({
  title,
  help,
  empty,
  rows,
  mode,
  metric,
  showShare,
  picked,
  onPick,
}: {
  title: string;
  help: ExpHelpDoc;
  empty: string;
  rows: Scored[];
  mode: "log" | "adj";
  metric: SizeMetric;
  showShare: boolean;
  picked: { a: string; b: string } | null;
  onPick: (pair: { a: string; b: string }) => void;
}) {
  return (
    <section className="card p-4">
      <h2 className="text-sm font-semibold inline-flex items-center">
        {title}
        <ExpHelp doc={help} />
      </h2>
      {rows.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">{empty}</p>
      ) : (
        <ol className="mt-2 space-y-1.5">
          {rows.map((row, i) => {
            const share = shareBlock(row.p, metric);
            const active = picked && pairKey(picked.a, picked.b) === pairKey(row.p.a, row.p.b);
            const primary = mode === "log" ? row.r : row.rPop;
            const secondary = mode === "log" ? row.rPop : row.r;
            const secondaryLabel = mode === "log" ? "인구 보정" : "로그";
            return (
              <li key={`${row.p.a}-${row.p.b}`}>
                <button
                  type="button"
                  className={clsx(
                    "w-full rounded px-2 py-1.5 text-left text-xs hover:bg-slate-50 dark:hover:bg-slate-800",
                    active && "bg-amber-50 dark:bg-amber-950/40",
                  )}
                  onClick={() => onPick({ a: row.p.a, b: row.p.b })}
                >
                  <span className="text-slate-400 mr-1">{i + 1}.</span>
                  {row.p.a} × {row.p.b}{" "}
                  <span className="tabular-nums font-semibold">{fmtR(primary)}</span>
                  <span className="text-slate-400"> n={row.n.toLocaleString("ko-KR")}</span>
                  <span className="block text-[10px] text-slate-500 mt-0.5 tabular-nums">
                    {secondaryLabel} {fmtR(secondary)}
                  </span>
                  {showShare && <span className="block text-[10px] text-slate-500">비중 {fmtR(share.r)}</span>}
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
