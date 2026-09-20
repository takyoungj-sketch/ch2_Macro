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
type TypeCounts = { cells: number; eligible: number; phase1: number };

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
  verdict: { code: string; label: string; choices: Choice[] };
  answers: Answer[];
  next: NextItem[];
  limits: string[];
  resume?: { next_id: string; title: string; say: string; do_not: string; how: string };
};

const run = runJson as Run;

type Tab = "verdict" | "phase1" | "types" | "next";
const TABS: { id: Tab; label: string }[] = [
  { id: "verdict", label: "판정" },
  { id: "phase1", label: "1차 칸" },
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

const TYPE_ORDER = ["metro_gu", "cap_city", "prov_city", "urban_rural", "gun"];

const HELP: ExpHelpDoc = {
  title: "토지 면적 탄성",
  blurb: "시군구×지목 칸에서 log(단가)~log(면적)의 β입니다. 전국 한 숫자로 대체하지 않습니다. 제품 식은 바꾸지 않습니다.",
  method: {
    paras: [
      "창 5년. 지분 제외. 면적 IQR 없음. 단가만 Raw vs Robust. 모형 A=연도+도로, B=법정동 FE(식별 점검), C=제곱+구간 중위.",
      "선정은 거래량·면적 분포만. 단가·β로 고르지 않습니다. 대·전·답을 한 식에 섞지 않습니다.",
    ],
  },
  limits: { paras: run.limits },
  meaning: {
    paras: [
      "β<0 이면 면적이 클수록 ㎡당 단가가 낮습니다(규모 경제·소필지 할증). β>0 이면 광평 희소 쪽입니다.",
      "A와 B가 갈리면 A를 버리지 않습니다. A는 시장 구성, B는 동 내부입니다.",
    ],
  },
};

function statusLabel(s: string) {
  if (s === "planned") return "예정";
  if (s === "blocked") return "금지";
  if (s === "done") return "완료";
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

function bLabel(b: Fit["B"]): string {
  if (b == null) return "—";
  if (typeof b === "string") return b === "B_skip" ? "skip" : b;
  return fmtBeta(b.beta);
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
          {run.summary.n_eligible.toLocaleString("ko-KR")} · 1차 {run.summary.n_phase1}.
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
              <code className="font-mono">python -m app.land_lab.area_elasticity_screen</code>. 숫자는 스냅샷을 덮고,
              판정 문장은 유지합니다. 전 칸 표는 {run.cells_csv ?? "land_area_elasticity_screen.csv"}.
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
                    className={clsx(item.status === "blocked" && "bg-amber-50 dark:bg-amber-950/30")}
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
