import { useEffect, useMemo, useRef, useState } from "react";
import { StatsGlossaryHelp } from "@ch2/stats-glossary";
import type { NationalRankTuple, NationalRanksResponse, RegionLevel } from "../types";
import NationalScatter from "./NationalScatter";
import {
  dedupeRegionLabel,
  formatAmountCompact,
  formatAmountPerCapita,
  formatInt,
  formatPopMan,
} from "../utils/format";

type RankTab = "amount" | "count" | "per_capita";

interface RankRow {
  code: string;
  name: string;
  population: number | null;
  amount_3y: number;
  count_3y: number;
  rank_amount: number;
  rank_count: number;
  rank_per_capita: number | null;
}

const ROW_H = 30;
const COLS = "grid-cols-[2.6rem_minmax(0,1fr)_2.75rem_4.35rem]";

const GRAIN_LABEL: Record<RegionLevel, string> = {
  sido: "시도",
  city: "시",
  sigungu: "시군구",
  eupmyeondong: "읍면동",
  beopjungri: "리",
};

const TABS: { id: RankTab; label: string }[] = [
  { id: "amount", label: "시장 규모" },
  { id: "count", label: "거래 활동" },
  { id: "per_capita", label: "인구 대비" },
];

function parseRow(t: NationalRankTuple): RankRow {
  return {
    code: String(t[0]),
    name: dedupeRegionLabel(String(t[1])),
    population: t[2] == null ? null : Number(t[2]),
    amount_3y: Number(t[3] ?? 0),
    count_3y: Number(t[4] ?? 0),
    rank_amount: Number(t[5]),
    rank_count: Number(t[6]),
    rank_per_capita: t[7] == null ? null : Number(t[7]),
  };
}

function sortRows(rows: RankRow[], tab: RankTab): RankRow[] {
  if (tab === "amount") return [...rows].sort((a, b) => a.rank_amount - b.rank_amount || a.code.localeCompare(b.code));
  if (tab === "count") return [...rows].sort((a, b) => a.rank_count - b.rank_count || a.code.localeCompare(b.code));
  const ranked = rows.filter((r) => r.rank_per_capita != null);
  const rest = rows.filter((r) => r.rank_per_capita == null);
  ranked.sort((a, b) => (a.rank_per_capita ?? 0) - (b.rank_per_capita ?? 0) || a.code.localeCompare(b.code));
  rest.sort((a, b) => a.name.localeCompare(b.name, "ko"));
  return [...ranked, ...rest];
}

function rankOf(row: RankRow, tab: RankTab): number | null {
  if (tab === "amount") return row.rank_amount;
  if (tab === "count") return row.rank_count;
  return row.rank_per_capita;
}

function valueOf(row: RankRow, tab: RankTab): string {
  if (tab === "amount") return formatAmountCompact(row.amount_3y);
  if (tab === "count") return `${formatInt(row.count_3y)}건`;
  return formatAmountPerCapita(row.amount_3y, row.population);
}

function formatRankNum(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR");
}

function formatRankOrd(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${formatRankNum(n)}위`;
}

interface Props {
  data: NationalRanksResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  focusCode: string;
  focusName: string;
}

export default function NationalRankCard({ data, isLoading, isError, focusCode, focusName }: Props) {
  const [tab, setTab] = useState<RankTab>("amount");
  const [query, setQuery] = useState("");
  const [openSuggest, setOpenSuggest] = useState(false);
  const [highlightCode, setHighlightCode] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [listH, setListH] = useState(360);
  const [scrollTop, setScrollTop] = useState(0);

  const rows = useMemo(() => (data?.rows ?? []).map(parseRow), [data]);
  const sorted = useMemo(() => sortRows(rows, tab), [rows, tab]);
  const focus = useMemo(() => rows.find((r) => r.code === focusCode) ?? null, [rows, focusCode]);

  const q = query.trim();
  const suggestions = useMemo(() => {
    if (q.length < 1) return [];
    const lower = q.toLowerCase();
    return sorted
      .filter((r) => r.name.toLowerCase().includes(lower) || r.code.includes(q))
      .slice(0, 8);
  }, [q, sorted]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setListH(el.clientHeight));
    ro.observe(el);
    setListH(el.clientHeight);
    return () => ro.disconnect();
  }, [data]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpenSuggest(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    if (!highlightCode) return;
    const t = window.setTimeout(() => setHighlightCode(null), 2800);
    return () => window.clearTimeout(t);
  }, [highlightCode]);

  function scrollToCode(code: string) {
    const el = listRef.current;
    if (!el) return;
    const idx = sorted.findIndex((r) => r.code === code);
    if (idx < 0) return;
    const top = Math.max(0, idx * ROW_H - el.clientHeight / 3);
    el.scrollTop = top;
    setScrollTop(top);
  }

  useEffect(() => {
    const target = highlightCode || focusCode;
    if (!target) return;
    const id = window.requestAnimationFrame(() => scrollToCode(target));
    return () => window.cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sorted, focusCode, highlightCode]);

  function jumpTo(code: string) {
    setHighlightCode(code);
    setOpenSuggest(false);
  }

  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - 4);
  const visible = Math.ceil(listH / ROW_H) + 8;
  const slice = sorted.slice(start, start + visible);
  const grain = data ? GRAIN_LABEL[data.region_level] ?? data.region_level : "";
  const valueHead =
    tab === "amount" ? "3년 거래액" : tab === "count" ? "3년 건수" : "인구당 거래액";

  return (
    <div className="card flex flex-col p-3.5 xl:sticky xl:top-3">
      <div className="flex items-center gap-1.5">
        <h2 className="text-base font-semibold">전국 지역 순위</h2>
        <StatsGlossaryHelp termId="national_rank" size="sm" />
      </div>
      <p className="mt-0.5 text-[11px] leading-snug text-slate-500 dark:text-slate-400">
        최근 {data?.window_years ?? 3}년 · {grain || "지역"} 기준
        {data ? ` · ${data.universe_n.toLocaleString("ko-KR")}곳` : ""}
        {data?.as_of_month ? ` · ${data.as_of_month.slice(0, 7)}` : ""}
      </p>

      <div className="mt-2 flex gap-0.5 rounded-md bg-slate-100 p-0.5 text-[11px] dark:bg-slate-900/50">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={
              tab === t.id
                ? "flex-1 rounded px-1 py-1 font-medium bg-white shadow-sm dark:bg-slate-700"
                : "flex-1 rounded px-1 py-1 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
            }
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="relative mt-2" ref={boxRef}>
        <input
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpenSuggest(true);
          }}
          onFocus={() => setOpenSuggest(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && suggestions[0]) {
              e.preventDefault();
              jumpTo(suggestions[0].code);
            }
          }}
          placeholder="지역 이름 · 해당 순위로 이동"
          className="w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-900"
        />
        {openSuggest && suggestions.length > 0 && (
          <ul className="absolute z-20 mt-1 max-h-40 w-full overflow-auto rounded-md border border-slate-200 bg-white text-xs shadow-md dark:border-slate-600 dark:bg-slate-800">
            {suggestions.map((s) => (
              <li key={s.code}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between px-2 py-1.5 text-left hover:bg-slate-50 dark:hover:bg-slate-700"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => jumpTo(s.code)}
                >
                  <span className="truncate">{s.name}</span>
                  <span className="ml-2 shrink-0 text-[10px] text-slate-400">{formatRankNum(rankOf(s, tab))}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className={`mt-2 grid ${COLS} gap-x-1 px-0.5 text-[10px] font-medium text-slate-500 dark:text-slate-400`}>
        <div>순위</div>
        <div>지역</div>
        <div className="text-right">인구</div>
        <div className="text-right">{valueHead}</div>
      </div>

      <div
        ref={listRef}
        className="relative mt-1 max-h-[22.5rem] overflow-y-auto text-xs"
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      >
        {isLoading && <div className="p-4 text-center text-slate-400">순위를 불러오는 중…</div>}
        {isError && <div className="p-4 text-center text-slate-400">순위 마트가 없습니다.</div>}
        {!isLoading && !isError && data && (
          <div style={{ height: sorted.length * ROW_H, position: "relative" }}>
            {slice.map((row, i) => {
              const idx = start + i;
              const isFocus = row.code === focusCode;
              const isHi = row.code === highlightCode;
              return (
                <div
                  key={row.code}
                  style={{ top: idx * ROW_H, height: ROW_H }}
                  className={`absolute left-0 right-0 grid ${COLS} items-center gap-x-1 px-0.5 ${
                    isHi
                      ? "bg-amber-100 dark:bg-amber-900/40"
                      : isFocus
                        ? "bg-slate-100 dark:bg-slate-700/50"
                        : idx % 2
                          ? "bg-slate-50/70 dark:bg-slate-900/20"
                          : ""
                  }`}
                >
                  <div className="tabular-nums text-slate-500">{formatRankNum(rankOf(row, tab))}</div>
                  <div className="truncate" title={row.name}>
                    {row.name}
                  </div>
                  <div className="text-right tabular-nums text-slate-500">{formatPopMan(row.population)}</div>
                  <div className="truncate text-right tabular-nums">{valueOf(row, tab)}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {focus && (
        <>
          <div className="mt-1 border-t border-dashed border-slate-300 dark:border-slate-600" />
          <div className={`grid ${COLS} items-center gap-x-1 bg-amber-50 px-0.5 py-1 text-xs font-medium dark:bg-amber-900/25`}>
            <div className="tabular-nums">{formatRankNum(rankOf(focus, tab))}</div>
            <div className="truncate" title={focus.name}>
              {focus.name}
              <span className="ml-0.5 text-[9px] font-normal text-amber-700 dark:text-amber-300">현재</span>
            </div>
            <div className="text-right tabular-nums">{formatPopMan(focus.population)}</div>
            <div className="truncate text-right tabular-nums">{valueOf(focus, tab)}</div>
          </div>
        </>
      )}

      {!isLoading && !isError && data && (
        <NationalScatter rows={rows} tab={tab} focusCode={focusCode} onPick={jumpTo} />
      )}

      <p className="mt-2 text-[11px] leading-relaxed text-slate-600 dark:text-slate-300">
        <span className="font-medium">{focusName || focus?.name || focusCode}의 전국 위치</span>
        <br />
        거래액 {formatRankOrd(focus?.rank_amount)} · 건수 {formatRankOrd(focus?.rank_count)} · 인구 대비{" "}
        {formatRankOrd(focus?.rank_per_capita)}
      </p>
    </div>
  );
}
