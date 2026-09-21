import { useState } from "react";
import clsx from "clsx";
import runJson from "../../../docs/lab/land_area_elasticity_screen.json";
import ExpHelp, { type ExpHelpDoc } from "./ExpHelp";
import LabResume from "./LabResume";

type Coef = { beta?: number | null; se?: number | null; p?: number | null; n?: number; r2?: number };
type Turning = { area_star?: number | null; in_range?: boolean; beta2_sig?: boolean };
type Fit = {
  sido_name: string;
  sigungu_name: string;
  sigungu_code: string;
  land_category: string;
  region_type: string;
  n_raw?: number;
  n_tier?: string;
  A?: Coef | null;
  A_robust?: Coef | null;
  B?: Coef | string;
  C?: { turning?: Turning; status?: string } | null;
};
type Cell = {
  sido_name: string;
  sigungu_name: string;
  sigungu_code: string;
  land_category: string;
  region_type: string;
  n: number;
  p90_p50?: number | null;
  eligible: boolean;
  b_preview?: string;
};
type NextItem = { id: string; status: string; title: string; ask: string; gate: string };
type Answer = { q: string; a: string; evidence: string };
type Choice = { id: string; label: string; selected: boolean; why: string; note?: string };
type Dir = "lower" | "neutral" | "higher" | "skip";
type Arm = {
  delta_mean?: number | null;
  delta_median?: number | null;
  ci_lo?: number | null;
  ci_hi?: number | null;
  direction?: Dir;
  reason?: string;
};
type Phase2Row = {
  sido_name: string;
  sigungu_name: string;
  sigungu_code: string;
  land_category: string;
  region_type: string;
  n: number;
  n_tiny: number;
  n_body: number;
  n_large: number;
  n_below_floor: number;
  tiny_aux?: boolean;
  large?: Arm | null;
  tiny?: Arm | null;
};
type DirCounts = { lower: number; neutral: number; higher: number; n: number; comparable?: number; tiny_aux?: number; delta_median_p50?: number | null; share_ci_excl_0?: number | null };
type Phase2 = {
  n_eligible: number;
  n_comparable: number;
  n_tiny_aux: number;
  n_skip: number;
  skip_reasons?: Record<string, number>;
  large: DirCounts;
  tiny: DirCounts;
  by_type: Record<string, DirCounts>;
  by_category: Record<string, DirCounts>;
};
type TypeCounts = { cells: number; eligible: number; phase1: number };
type Comp = {
  n: number;
  median_n?: number | null;
  median_p90_p50?: number | null;
  median_population?: number | null;
  median_unit_price?: number | null;
  median_urban_share?: number | null;
  share_dae?: number | null;
  share_farm?: number | null;
  by_type?: Record<string, number>;
  by_category?: Record<string, number>;
};
type WithinVs = { same?: number; to_neutral?: number; opposite?: number; skip?: number };
type FocusRow = {
  sido_name: string;
  sigungu_name: string;
  land_category: string;
  region_type: string;
  direction_cell?: Dir;
  delta_median_cell?: number | null;
  direction_within?: Dir;
  delta_median_within?: number | null;
  ci_lo_within?: number | null;
  ci_hi_within?: number | null;
  within_vs_cell?: string;
  n_dongs_both?: number;
  urban_share?: number | null;
  population?: number | null;
};
type CrossCell = {
  n: number;
  lower: number;
  neutral: number;
  higher: number;
  share_lower?: number | null;
  share_higher?: number | null;
};
type Phase3 = {
  n_cells: number;
  pop_year?: number;
  composition: { lower: Comp; neutral: Comp; higher: Comp };
  tiny_by_type: Record<string, DirCounts>;
  by_type_category?: Record<string, Record<string, CrossCell>>;
  within_dong: { n_ok: number; n_skip: number; vs_cell: Record<string, WithinVs> };
  higher_or_metro: FocusRow[];
};

type Run = {
  date: string;
  status: string;
  as_of_month: string;
  period_start: string;
  period_end: string;
  window_years: number;
  product_change: boolean;
  cells_csv?: string;
  summary: {
    n_cells: number;
    n_eligible: number;
    n_phase1: number;
    by_type: Record<string, TypeCounts>;
  };
  phase1: Cell[];
  phase1_fits: Fit[];
  phase1_fit_summary: {
    n_fits: number;
    beta_a_median: number | null;
    share_negative: number | null;
    raw_robust_sign_match: number | null;
    turning_in_range_given_sig: number | null;
  };
  phase2?: Phase2;
  phase2_rows?: Phase2Row[];
  phase2_csv?: string;
  phase3?: Phase3;
  phase3_csv?: string;
  verdict: { code: string; label: string; choices: Choice[] };
  answers: Answer[];
  next: NextItem[];
  limits: string[];
  resume?: { next_id: string; title: string; say: string; do_not: string; how: string };
};

const run = runJson as Run;

type Tab = "verdict" | "phase1" | "phase2" | "phase3" | "types" | "next";
const TABS: { id: Tab; label: string }[] = [
  { id: "verdict", label: "판정" },
  { id: "phase1", label: "1차 칸" },
  { id: "phase2", label: "2차 단가" },
  { id: "phase3", label: "3차 구성" },
  { id: "types", label: "유형" },
  { id: "next", label: "다음 실험" },
];

const TYPE_KO: Record<string, string> = {
  metro_gu: "대도시 구",
  cap_city: "수도권 시",
  prov_city: "지방 시",
  urban_rural: "도농복합시",
  gun: "군",
};
const CAT_ORDER = ["대", "전", "답"];

const TYPE_ORDER = ["metro_gu", "cap_city", "prov_city", "urban_rural", "gun"];

const HELP: ExpHelpDoc = {
  title: "토지 면적 탄성",
  blurb: "시군구×지목 칸에서 log(단가)~log(면적)의 β입니다. 전국 한 숫자로 대체하지 않습니다. 제품 식은 바꾸지 않습니다.",
  method: {
    paras: [
      "창 5년. 지분 제외. 면적 IQR 없음. 1차 단가만 Raw vs Robust. 모형 A=연도+도로, B=법정동 FE(식별 점검), C=제곱+구간 중위.",
      "2차는 369칸 OLS가 아니다. 적격칸을 모집단으로, 몸통 n≥30·광평 n≥20인 칸만 중위 단가 차이+CI. 평균은 보조. 초소형은 보조열.",
      "선정은 거래량·면적 분포만. 단가·β·Δ로 고르지 않습니다. 대·전·답을 한 식에 섞지 않습니다.",
      "3차는 구성·같은 동·유형×지목 교차표다. 4차 회귀가 아니다. 랩을 닫고 차후에 용도지역 분할부터 잇는다.",
    ],
  },
  limits: { paras: run.limits },
  meaning: {
    paras: [
      "β<0 이면 면적이 클수록 ㎡당 단가가 낮습니다(규모 경제·소필지 할증). β>0 이면 광평 희소 쪽입니다.",
      "높게=도시체급×대지, 전·답은 체급 불문 낮게. 대지면 광평이 비싸다로 읽지 않습니다. 전국 −19.9%는 헤드라인이 아닙니다.",
    ],
  },
};

function statusLabel(s: string) {
  if (s === "planned") return "예정";
  if (s === "blocked") return "금지";
  if (s === "done") return "완료";
  if (s === "parked") return "보류";
  return s;
}

function fmtBeta(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(3)}`;
}

function pct(v: number | null | undefined, d = 0) {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(d)}%`;
}

function betaTone(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "";
  if (v > 0.05) return "bg-indigo-50/70 dark:bg-indigo-950/30";
  if (v < -0.05) return "bg-amber-50/70 dark:bg-amber-950/20";
  return "";
}

function fmtPct(v: number | null | undefined, d = 1) {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(d)}%`;
}

function dirKo(d: Dir | undefined) {
  if (d === "lower") return "낮게 관측";
  if (d === "higher") return "높게 관측";
  if (d === "neutral") return "중립";
  if (d === "skip") return "skip";
  return "—";
}

function dirTone(d: Dir | undefined) {
  if (d === "lower") return "bg-amber-50/70 dark:bg-amber-950/20";
  if (d === "higher") return "bg-indigo-50/70 dark:bg-indigo-950/30";
  return "";
}

function bLabel(b: Fit["B"]): string {
  if (b == null) return "—";
  if (typeof b === "string") return b === "B_skip" ? "skip" : b;
  return fmtBeta(b.beta);
}

function Phase2Panel({ run }: { run: Run }) {
  const p2 = run.phase2;
  const rows = run.phase2_rows ?? [];
  if (!p2) {
    return <p className="text-[11px] text-slate-500">2차 스냅샷이 없습니다. backend에서 area_elasticity_gap 을 실행합니다.</p>;
  }
  const lg = p2.large;
  const ordered = [...rows].sort((a, b) => {
    const ta = TYPE_ORDER.indexOf(a.region_type);
    const tb = TYPE_ORDER.indexOf(b.region_type);
    if (ta !== tb) return ta - tb;
    return `${a.sido_name}${a.sigungu_name}${a.land_category}`.localeCompare(
      `${b.sido_name}${b.sigungu_name}${b.land_category}`,
      "ko",
    );
  });
  return (
    <>
      <p className="text-[11px] text-slate-500">
        369는 모집단. 비교가능 = 몸통 n≥30 · 광평 n≥20. 판정은 중위 Δ + 95% CI. 평균은 보조. 초소형은 보조열. 단가·Δ로
        칸을 고르지 않음.
      </p>
      <section className="rounded border border-slate-200 dark:border-slate-600 px-2.5 py-2 space-y-1">
        <p>
          적격 {p2.n_eligible.toLocaleString("ko-KR")} → 비교가능 {p2.n_comparable.toLocaleString("ko-KR")} · 미달{" "}
          {p2.n_skip.toLocaleString("ko-KR")} · 초소형 보조열 {p2.n_tiny_aux.toLocaleString("ko-KR")}
        </p>
        <p>
          광평 vs 몸통: 낮게 {lg.lower} · 중립 {lg.neutral} · 높게 {lg.higher} · 중위 Δ {fmtPct(lg.delta_median_p50)} ·
          CI가 0 밖 {pct(lg.share_ci_excl_0)}
        </p>
        <p>
          초소형 vs 몸통(보조): 낮게 {p2.tiny.lower} · 중립 {p2.tiny.neutral} · 높게 {p2.tiny.higher} · 중위 Δ{" "}
          {fmtPct(p2.tiny.delta_median_p50)}
        </p>
      </section>
      <p className="text-[11px] font-medium">유형 × 광평 방향 (3차 표의 뼈대. 구성 통계는 3차)</p>
      <table className="data w-full text-[11px]">
        <thead>
          <tr>
            <th className="text-left">유형</th>
            <th>비교가능</th>
            <th>낮게 관측</th>
            <th>중립</th>
            <th>높게 관측</th>
          </tr>
        </thead>
        <tbody>
          {TYPE_ORDER.map((id) => {
            const t = p2.by_type[id];
            if (!t) return null;
            return (
              <tr key={id}>
                <td className="text-left">{TYPE_KO[id] ?? id}</td>
                <td>{t.comparable ?? t.n}</td>
                <td>{t.lower}</td>
                <td>{t.neutral}</td>
                <td>{t.higher}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-[11px] font-medium">지목 × 광평 방향</p>
      <table className="data w-full text-[11px]">
        <thead>
          <tr>
            <th className="text-left">지목</th>
            <th>비교가능</th>
            <th>낮게 관측</th>
            <th>중립</th>
            <th>높게 관측</th>
          </tr>
        </thead>
        <tbody>
          {["대", "전", "답", "임야"].map((cat) => {
            const t = p2.by_category[cat];
            if (!t) return null;
            return (
              <tr key={cat}>
                <td className="text-left">{cat}</td>
                <td>{t.comparable ?? t.n}</td>
                <td>{t.lower}</td>
                <td>{t.neutral}</td>
                <td>{t.higher}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="overflow-x-auto">
        <table className="data w-full text-[11px]">
          <thead>
            <tr>
              <th className="text-left">유형</th>
              <th className="text-left">시군구</th>
              <th className="text-left">지목</th>
              <th>n</th>
              <th>몸통</th>
              <th>광평</th>
              <th>Δ중위</th>
              <th>Δ평균</th>
              <th className="text-left">95% CI</th>
              <th className="text-left">광평</th>
              <th className="text-left">초소형</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((r) => {
              const d = r.large?.direction;
              return (
                <tr key={`${r.sigungu_code}-${r.land_category}`} className={dirTone(d)}>
                  <td className="text-left">{TYPE_KO[r.region_type] ?? r.region_type}</td>
                  <td className="text-left">
                    {r.sido_name} {r.sigungu_name}
                  </td>
                  <td className="text-left">{r.land_category}</td>
                  <td>{r.n.toLocaleString("ko-KR")}</td>
                  <td>{r.n_body}</td>
                  <td>{r.n_large}</td>
                  <td>{fmtPct(r.large?.delta_median)}</td>
                  <td>{fmtPct(r.large?.delta_mean)}</td>
                  <td className="text-left">
                    {r.large?.ci_lo == null ? "—" : `${fmtPct(r.large.ci_lo)} ~ ${fmtPct(r.large.ci_hi)}`}
                  </td>
                  <td className="text-left">{dirKo(d)}</td>
                  <td className="text-left">
                    {r.tiny_aux ? `${dirKo(r.tiny?.direction)} ${fmtPct(r.tiny?.delta_median)}` : "skip"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

function num(v: number | null | undefined, d = 0) {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: d });
}

function Phase3Panel({ run }: { run: Run }) {
  const p3 = run.phase3;
  if (!p3) {
    return (
      <p className="text-[11px] text-slate-500">
        3차 스냅샷이 없습니다. backend에서 area_elasticity_where 를 실행합니다.
      </p>
    );
  }
  const dirs: { id: "lower" | "neutral" | "higher"; label: string }[] = [
    { id: "lower", label: "광평 낮게" },
    { id: "neutral", label: "중립" },
    { id: "higher", label: "광평 높게" },
  ];
  const vs = p3.within_dong.vs_cell || {};
  const focus = [...(p3.higher_or_metro || [])].sort((a, b) => {
    const ta = TYPE_ORDER.indexOf(a.region_type);
    const tb = TYPE_ORDER.indexOf(b.region_type);
    if (ta !== tb) return ta - tb;
    return `${a.sido_name}${a.sigungu_name}`.localeCompare(`${b.sido_name}${b.sigungu_name}`, "ko");
  });
  return (
    <>
      <p className="text-[11px] text-slate-500">
        2차 비교가능 {p3.n_cells}칸 전부. |Δ|·단가로 다시 고르지 않음. 인구 연말 {p3.pop_year ?? "—"}. 칸 중위 단가는
        구성 기술통계이지 선정 기준이 아님. 같은 동 점검은 몸통·광평이 같이 있는 동만. 교차표는 3차 랩 마감이며 4차 회귀가
        아님.
      </p>
      <p className="text-[11px] font-medium">방향 그룹 구성 (그룹 안 중위)</p>
      <table className="data w-full text-[11px]">
        <thead>
          <tr>
            <th className="text-left">그룹</th>
            <th>칸</th>
            <th>거래 n</th>
            <th>P90/P50</th>
            <th>인구</th>
            <th>칸 중위단가</th>
            <th>도시계 거래</th>
            <th>대지 비율</th>
            <th>전·답 비율</th>
          </tr>
        </thead>
        <tbody>
          {dirs.map(({ id, label }) => {
            const c = p3.composition[id];
            return (
              <tr key={id}>
                <td className="text-left">{label}</td>
                <td>{c.n}</td>
                <td>{num(c.median_n, 0)}</td>
                <td>{c.median_p90_p50 != null ? c.median_p90_p50.toFixed(2) : "—"}</td>
                <td>{num(c.median_population, 0)}</td>
                <td>{num(c.median_unit_price, 1)}</td>
                <td>{pct(c.median_urban_share)}</td>
                <td>{pct(c.share_dae)}</td>
                <td>{pct(c.share_farm)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {p3.by_type_category ? (
        <>
          <p className="text-[11px] font-medium">유형 × 지목 × 광평 방향 (3차 랩 마감)</p>
          <p className="text-[11px] text-slate-500">
            높게=도시체급×대지, 전·답은 체급 불문 낮게. 대지면 광평이 비싸다로 읽지 않음.
          </p>
          <table className="data w-full text-[11px]">
            <thead>
              <tr>
                <th className="text-left">유형</th>
                <th className="text-left">지목</th>
                <th>칸</th>
                <th>낮게</th>
                <th>중립</th>
                <th>높게</th>
                <th>높게 비율</th>
              </tr>
            </thead>
            <tbody>
              {TYPE_ORDER.flatMap((id) => {
                const slot = p3.by_type_category?.[id];
                if (!slot) return [];
                return CAT_ORDER.filter((cat) => slot[cat]).map((cat) => {
                  const c = slot[cat];
                  return (
                    <tr key={`${id}-${cat}`}>
                      <td className="text-left">{TYPE_KO[id] ?? id}</td>
                      <td className="text-left">{cat}</td>
                      <td>{c.n}</td>
                      <td>{c.lower}</td>
                      <td>{c.neutral}</td>
                      <td>{c.higher}</td>
                      <td>{pct(c.share_higher)}</td>
                    </tr>
                  );
                });
              })}
            </tbody>
          </table>
        </>
      ) : null}
      <p className="text-[11px] font-medium">초소형 방향 × 유형 (보조. 광평 표와 섞지 않음)</p>
      <table className="data w-full text-[11px]">
        <thead>
          <tr>
            <th className="text-left">유형</th>
            <th>보조열</th>
            <th>낮게</th>
            <th>중립</th>
            <th>높게</th>
          </tr>
        </thead>
        <tbody>
          {TYPE_ORDER.map((id) => {
            const t = p3.tiny_by_type[id];
            if (!t) return null;
            return (
              <tr key={id}>
                <td className="text-left">{TYPE_KO[id] ?? id}</td>
                <td>{t.n}</td>
                <td>{t.lower}</td>
                <td>{t.neutral}</td>
                <td>{t.higher}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-[11px] font-medium">
        같은 동 안 광평 vs 몸통 · 가능 {p3.within_dong.n_ok} · skip {p3.within_dong.n_skip}
      </p>
      <table className="data w-full text-[11px]">
        <thead>
          <tr>
            <th className="text-left">2차 방향</th>
            <th>동 안 같음</th>
            <th>동 안 중립</th>
            <th>동 안 반대</th>
            <th>동 가드 skip</th>
          </tr>
        </thead>
        <tbody>
          {dirs.map(({ id, label }) => {
            const v = vs[id] || {};
            return (
              <tr key={id}>
                <td className="text-left">{label}</td>
                <td>{v.same ?? 0}</td>
                <td>{v.to_neutral ?? 0}</td>
                <td>{v.opposite ?? 0}</td>
                <td>{v.skip ?? 0}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-[11px] font-medium">대도시 구 · 광평 높게 칸 (입지 점검)</p>
      <div className="overflow-x-auto">
        <table className="data w-full text-[11px]">
          <thead>
            <tr>
              <th className="text-left">유형</th>
              <th className="text-left">시군구</th>
              <th className="text-left">지목</th>
              <th className="text-left">칸 방향</th>
              <th>칸 Δ</th>
              <th className="text-left">동 안</th>
              <th>동 안 Δ</th>
              <th>도시계</th>
              <th>인구</th>
            </tr>
          </thead>
          <tbody>
            {focus.map((r) => (
              <tr
                key={`${r.sido_name}-${r.sigungu_name}-${r.land_category}`}
                className={dirTone(r.direction_cell)}
              >
                <td className="text-left">{TYPE_KO[r.region_type] ?? r.region_type}</td>
                <td className="text-left">
                  {r.sido_name} {r.sigungu_name}
                </td>
                <td className="text-left">{r.land_category}</td>
                <td className="text-left">{dirKo(r.direction_cell)}</td>
                <td>{fmtPct(r.delta_median_cell)}</td>
                <td className="text-left">{dirKo(r.direction_within)}</td>
                <td>{fmtPct(r.delta_median_within)}</td>
                <td>{pct(r.urban_share)}</td>
                <td>{num(r.population, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function LandAreaElasticityLab() {
  const [tab, setTab] = useState<Tab>("verdict");
  const s = run.phase1_fit_summary;
  const fitsByKey = new Map(
    run.phase1_fits.map((f) => [`${f.sigungu_code}|${f.land_category}`, f]),
  );

  return (
    <div className="max-w-[96rem] mx-auto p-4 space-y-3">
      <div className="flex items-start gap-1">
        <p className="text-[11px] text-slate-500 dark:text-slate-400">
          연구 전용. 창 {run.window_years}년 · {run.period_start} ~ {run.period_end} · {run.date} 스냅샷. 제품 토지
          회귀식은 바꾸지 않습니다. 칸 {run.summary.n_cells.toLocaleString("ko-KR")} · 적격{" "}
          {run.summary.n_eligible.toLocaleString("ko-KR")} · 1차 {run.summary.n_phase1}
          {run.phase2 ? ` · 2차 비교가능 ${run.phase2.n_comparable.toLocaleString("ko-KR")}` : ""}
          {run.status === "paused" ? " · 1–3차 정리 · 차후 이어서" : ""}.
        </p>
        <ExpHelp doc={HELP} size="xs" />
      </div>

      <div
        className="flex flex-wrap gap-0.5 rounded-md border border-slate-200 dark:border-slate-600 p-0.5 w-fit"
        role="tablist"
      >
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={clsx(
              "px-2.5 py-1 text-[11px] font-medium rounded",
              tab === id
                ? "bg-indigo-600 text-white"
                : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700",
            )}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="text-xs text-slate-700 dark:text-slate-200 space-y-3">
        {tab === "verdict" && (
          <>
            {run.resume && <LabResume resume={run.resume} />}
            <section className="rounded border border-amber-200 dark:border-amber-800 bg-amber-50/70 dark:bg-amber-950/30 px-2.5 py-2 space-y-1">
              <p className="font-semibold text-amber-950 dark:text-amber-100">{run.verdict.label}</p>
              <p>
                1차 24칸 β_A 중위 {fmtBeta(s.beta_a_median)} · 음수 {pct(s.share_negative)} · Raw/Robust 부호 일치{" "}
                {pct(s.raw_robust_sign_match)} · turning 범위 안(유의 시) {pct(s.turning_in_range_given_sig)}.
              </p>
              {run.phase2 && (
                <p>
                  2차 비교가능 {run.phase2.n_comparable}칸 · 광평 낮게 {run.phase2.large.lower} · 중립{" "}
                  {run.phase2.large.neutral} · 높게 {run.phase2.large.higher} · 중위 Δ {fmtPct(run.phase2.large.delta_median_p50)}
                  . 초소형 보조 중위 Δ {fmtPct(run.phase2.tiny.delta_median_p50)}.
                </p>
              )}
              {run.phase3 && (
                <p>
                  3차 낮게 칸은 전·답 {pct(run.phase3.composition.lower.share_farm)} · 높게 칸은 대지{" "}
                  {pct(run.phase3.composition.higher.share_dae)}. 같은 동 안 반대 뒤집힘 0. 대도시 광평 높게 12칸은 동
                  안에서도 유지.
                </p>
              )}
            </section>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">선택지</th>
                  <th className="text-left">채택</th>
                  <th className="text-left">근거</th>
                </tr>
              </thead>
              <tbody>
                {run.verdict.choices.map((c) => (
                  <tr key={c.id} className={clsx(c.selected && "bg-indigo-50 dark:bg-indigo-950/40")}>
                    <td className="text-left">{c.label}</td>
                    <td className="text-left">{c.selected ? (c.note ?? "예") : "아니오"}</td>
                    <td className="text-left">{c.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">질문</th>
                  <th className="text-left">답</th>
                  <th className="text-left">근거</th>
                </tr>
              </thead>
              <tbody>
                {run.answers.map((a) => (
                  <tr key={a.q}>
                    <td className="text-left">{a.q}</td>
                    <td className="text-left font-medium">{a.a}</td>
                    <td className="text-left">{a.evidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "phase1" && (
          <>
            <p className="text-[11px] text-slate-500">
              유형 안 스펙트럼(P90/P50·꼬리) 우선. 단가·β로 고르지 않음. 노랑=β&lt;−0.05, 보라=β&gt;+0.05.
            </p>
            <div className="overflow-x-auto">
              <table className="data w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="text-left">유형</th>
                    <th className="text-left">시군구</th>
                    <th className="text-left">지목</th>
                    <th>n</th>
                    <th>P90/P50</th>
                    <th>β_A</th>
                    <th>Robust</th>
                    <th>B</th>
                    <th className="text-left">turning</th>
                  </tr>
                </thead>
                <tbody>
                  {run.phase1.map((c) => {
                    const f = fitsByKey.get(`${c.sigungu_code}|${c.land_category}`);
                    const beta = f?.A?.beta ?? null;
                    const turn = f?.C?.turning;
                    let turnLabel = "—";
                    if (turn?.beta2_sig && turn.in_range && turn.area_star != null) {
                      turnLabel = `${turn.area_star}㎡`;
                    } else if (turn?.beta2_sig) {
                      turnLabel = "범위 밖";
                    }
                    return (
                      <tr key={`${c.sigungu_code}-${c.land_category}`} className={betaTone(beta)}>
                        <td className="text-left">{TYPE_KO[c.region_type] ?? c.region_type}</td>
                        <td className="text-left">
                          {c.sido_name} {c.sigungu_name}
                        </td>
                        <td className="text-left">{c.land_category}</td>
                        <td>{c.n.toLocaleString("ko-KR")}</td>
                        <td>{c.p90_p50 != null ? c.p90_p50.toFixed(2) : "—"}</td>
                        <td>{fmtBeta(beta)}</td>
                        <td>{fmtBeta(f?.A_robust?.beta)}</td>
                        <td>{bLabel(f?.B)}</td>
                        <td className="text-left">{turnLabel}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        {tab === "phase2" && <Phase2Panel run={run} />}
        {tab === "phase3" && <Phase3Panel run={run} />}

        {tab === "types" && (
          <>
            <p className="text-[11px] text-slate-500">게이트는 유형×지목마다 다릅니다. 전국 공통 1,000㎡ 컷은 없습니다.</p>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">유형</th>
                  <th>칸</th>
                  <th>적격</th>
                  <th>1차</th>
                </tr>
              </thead>
              <tbody>
                {TYPE_ORDER.map((id) => {
                  const t = run.summary.by_type[id];
                  if (!t) return null;
                  return (
                    <tr key={id}>
                      <td className="text-left">{TYPE_KO[id] ?? id}</td>
                      <td>{t.cells.toLocaleString("ko-KR")}</td>
                      <td>{t.eligible.toLocaleString("ko-KR")}</td>
                      <td>{t.phase1}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}

        {tab === "next" && (
          <>
            {run.resume && <LabResume resume={run.resume} />}
            <p className="text-[11px] text-slate-500">
              재실행은 backend에서{" "}
              <code className="font-mono">python -m app.land_lab.area_elasticity_screen</code>
              (1차) · <code className="font-mono">python -m app.land_lab.area_elasticity_gap</code>
              (2차) · <code className="font-mono">python -m app.land_lab.area_elasticity_where</code>
              (3차). 숫자는 스냅샷을 덮고, 판정 문장은 유지합니다. 전 칸 표는{" "}
              {run.cells_csv ?? "land_area_elasticity_screen.csv"}
              {run.phase2_csv ? ` · 2차 ${run.phase2_csv}` : ""}
              {run.phase3_csv ? ` · 3차 ${run.phase3_csv}` : ""}.
            </p>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">상태</th>
                  <th className="text-left">실험</th>
                  <th className="text-left">질문</th>
                  <th className="text-left">게이트</th>
                </tr>
              </thead>
              <tbody>
                {run.next.map((item) => (
                  <tr
                    key={item.id}
                    className={clsx(
                      item.status === "blocked" && "bg-amber-50 dark:bg-amber-950/30",
                      item.status === "parked" && "bg-slate-50 dark:bg-slate-800/40",
                    )}
                  >
                    <td className="text-left">{statusLabel(item.status)}</td>
                    <td className="text-left font-medium">{item.title}</td>
                    <td className="text-left">{item.ask}</td>
                    <td className="text-left">{item.gate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}
