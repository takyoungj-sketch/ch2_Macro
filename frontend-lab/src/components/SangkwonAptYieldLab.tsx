import { useState } from "react";
import snap from "../../../docs/lab/sangkwon_apt_yield.json";

const KINDS: { key: string; label: string }[] = [
  { key: "office", label: "오피스" },
  { key: "mid_retail", label: "중대형 상가" },
  { key: "small_retail", label: "소규모 상가" },
  { key: "strata", label: "집합 상가" },
];

type Zone = {
  income: number | null;
  capital: number | null;
  investment: number | null;
  rent: number | null;
  sale_price: number | null;
  n_income: number;
  n_buildings: number;
  n_dongs?: number;
};

type Row = {
  asset_kind: string;
  sec_nm: string;
  sido: string;
  income: number | null;
  capital: number | null;
  investment: number | null;
  rent: number | null;
  n_investment: number;
  inside: Zone | null;
  near: Zone | null;
  admin: Zone | null;
  overlap: Zone | null;
};

type AptMode = "near" | "admin" | "overlap";

function num(v: number | null | undefined, digits = 2): string {
  if (v == null) return "—";
  return v.toLocaleString("ko-KR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function pearson(xs: number[], ys: number[]): { r: number | null; n: number } {
  const pairs: [number, number][] = [];
  for (let i = 0; i < xs.length; i += 1) {
    if (xs[i] != null && ys[i] != null && Number.isFinite(xs[i]) && Number.isFinite(ys[i])) {
      pairs.push([xs[i], ys[i]]);
    }
  }
  const n = pairs.length;
  if (n < 5) return { r: null, n };
  const mx = pairs.reduce((s, p) => s + p[0], 0) / n;
  const my = pairs.reduce((s, p) => s + p[1], 0) / n;
  let cov = 0;
  let vx = 0;
  let vy = 0;
  for (const [x, y] of pairs) {
    const dx = x - mx;
    const dy = y - my;
    cov += dx * dy;
    vx += dx * dx;
    vy += dy * dy;
  }
  if (vx === 0 || vy === 0) return { r: null, n };
  return { r: cov / Math.sqrt(vx * vy), n };
}

function seriesOf(rows: Row[], mode: AptMode): { label: string; values: (number | null)[] }[] {
  const apt = (row: Row) => (mode === "admin" ? row.admin : mode === "overlap" ? row.overlap : row.inside);
  const base = [
    { label: "상권 소득", values: rows.map((row) => row.income) },
    { label: "상권 자본", values: rows.map((row) => row.capital) },
    { label: "상권 투자", values: rows.map((row) => row.investment) },
    { label: "아파트 소득", values: rows.map((row) => apt(row)?.income ?? null) },
    { label: "아파트 자본", values: rows.map((row) => apt(row)?.capital ?? null) },
    { label: "아파트 소득+자본", values: rows.map((row) => apt(row)?.investment ?? null) },
    { label: "상권 임대료", values: rows.map((row) => row.rent) },
    { label: "아파트 임대료", values: rows.map((row) => apt(row)?.rent ?? null) },
    { label: "아파트 매매가", values: rows.map((row) => apt(row)?.sale_price ?? null) },
  ];
  if (mode === "near") {
    base.push(
      { label: "인근 소득+자본", values: rows.map((row) => row.near?.investment ?? null) },
      { label: "인근 임대료", values: rows.map((row) => row.near?.rent ?? null) },
    );
  }
  return base;
}

function CorrMatrix({ rows, mode }: { rows: Row[]; mode: AptMode }) {
  const series = seriesOf(rows, mode);
  return (
    <div className="space-y-1">
      <p className="text-xs text-slate-500">상관. 빈칸은 그 짝에서만 뺍니다. 짝이 5곳 미만이면 빈칸입니다.</p>
      <div className="overflow-x-auto">
        <table className="data w-full text-[12px] whitespace-nowrap">
          <thead className="sticky top-0 z-10 bg-white dark:bg-slate-900">
            <tr>
              <th className="text-left"> </th>
              {series.map((col) => (
                <th key={col.label}>{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {series.map((row, i) => (
              <tr key={row.label}>
                <td className="text-left">{row.label}</td>
                {series.map((col, j) => {
                  const hit = pearson(row.values as number[], col.values as number[]);
                  return (
                    <td key={col.label} title={hit.n ? `n=${hit.n}` : ""}>
                      {i === j ? "1.00" : num(hit.r)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Table({ rows, mode }: { rows: Row[]; mode: AptMode }) {
  return (
    <div className="max-h-[640px] overflow-auto">
      <table className="data w-full text-[12px] whitespace-nowrap">
        <thead className="sticky top-0 z-10 bg-white dark:bg-slate-900">
          <tr>
            <th className="text-left">상권</th>
            <th>소득</th>
            <th>자본</th>
            <th>투자</th>
            <th>아파트 소득</th>
            <th>아파트 자본</th>
            <th>아파트 소득+자본</th>
            <th>상권 임대료</th>
            <th>아파트 임대료</th>
            <th>아파트 매매가</th>
            {mode === "near" ? (
              <>
                <th>인근 소득+자본</th>
                <th>인근 임대료</th>
              </>
            ) : (
              <th>읍면동 수</th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const zone = mode === "admin" ? row.admin : mode === "overlap" ? row.overlap : row.inside;
            return (
            <tr key={`${row.asset_kind}-${row.sec_nm}`}>
              <td className="text-left">
                {row.sec_nm}
                <span className="ml-1 text-slate-400">{row.sido}</span>
              </td>
              <td>{num(row.income)}</td>
              <td>{num(row.capital)}</td>
              <td>{num(row.investment)}</td>
              <td>{num(zone?.income)}</td>
              <td>{num(zone?.capital)}</td>
              <td>{num(zone?.investment)}</td>
              <td>{num(row.rent, 3)}</td>
              <td>{num(zone?.rent, 3)}</td>
              <td>{num(zone?.sale_price, 1)}</td>
              {mode === "near" ? (
                <>
                  <td>{num(row.near?.investment)}</td>
                  <td>{num(row.near?.rent, 3)}</td>
                </>
              ) : (
                <td>{zone?.n_dongs ?? "—"}</td>
              )}
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function SangkwonAptYieldLab() {
  const rows = snap.rows as Row[];
  const [mode, setMode] = useState<AptMode>("near");
  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6 text-sm leading-relaxed">
      <p>
        2021–2025 연간 값의 단순평균이다. 정렬은 상권 투자수익률 평균이다. 수익률 칸과 가격 칸은 따로 읽는다.
        아파트 자본은 평균 ㎡당 매매가의 전년 대비다. 임대료 단위는 만원/㎡·월이다. 매매가는 만원/㎡이다.
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          className={`rounded border px-3 py-1.5 text-sm ${mode === "near" ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300"}`}
          onClick={() => setMode("near")}
        >
          인근 아파트
        </button>
        <button
          type="button"
          className={`rounded border px-3 py-1.5 text-sm ${mode === "admin" ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300"}`}
          onClick={() => setMode("admin")}
        >
          동일 행정구역 아파트
        </button>
        <button
          type="button"
          className={`rounded border px-3 py-1.5 text-sm ${mode === "overlap" ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300"}`}
          onClick={() => setMode("overlap")}
        >
          경계가 겹치는 읍면동
        </button>
      </div>
      <p className="text-xs text-slate-500">
        {mode === "near"
          ? "아파트 칸은 상권 안입니다. 인근 칸은 경계 밖 약 1km입니다."
          : mode === "overlap"
            ? "아파트 칸은 상권 도형과 읍면동 경계가 면적으로 겹치는 동의 전체 실거래입니다."
            : "아파트 칸은 상권 안 단지의 읍면동이고, 안이 비면 가장 가까운 단지의 읍면동입니다."}
      </p>
      <ul className="text-xs text-slate-600 dark:text-slate-300 list-disc pl-4 space-y-1">
        {snap.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
      {KINDS.map((kind) => {
        const part = rows.filter((row) => row.asset_kind === kind.key);
        return (
          <section key={kind.key} className="space-y-2">
            <h3 className="font-semibold">
              {kind.label} · {part.length}곳
            </h3>
            <Table rows={part} mode={mode} />
            <CorrMatrix rows={part} mode={mode} />
          </section>
        );
      })}
    </div>
  );
}
