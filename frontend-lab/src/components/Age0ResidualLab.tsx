import { useState } from "react";
import clsx from "clsx";
import runJson from "../../../docs/lab/age0_residual_run.json";
import ExpHelp, { type ExpHelpDoc } from "./ExpHelp";
import LabResume from "./LabResume";

type Boot = { mean: number; ci95: number[] | null };
type Summary = {
  n: number;
  mean_residual_rate_age0?: number;
  median_residual_rate_age0?: number;
  underpred_share_age0?: number;
  mean_y_over_yhat0_minus_1?: number;
  median_y_over_yhat0_minus_1?: number;
  mean_y?: number;
  mean_yhat0?: number;
  bootstrap_mean_residual_rate_age0_pct?: Boot;
  bootstrap_mean_premium_vs_age0_pct?: Boot;
};
type Sido = {
  addr1: string;
  ok: boolean;
  n_0_3?: number;
  n_0_1?: number;
  n_fit?: number;
  mean_residual_rate_age0?: number | null;
  underpred_share_age0?: number | null;
  mean_y_over_yhat0_minus_1?: number | null;
  ci_residual_age0?: number[] | null;
};
type NextItem = { id: string; status: string; title: string; ask: string; gate: string };
type Answer = { q: string; a: string; evidence: string };
type Choice = { id: string; label: string; selected: boolean; why: string; note?: string };

type Run = {
  date: string;
  decision: string;
  method: { note: string; as_of_label: string; fit_scope: string; grain: string };
  daejeon: { n_fit: number; summary_0_1: Summary; summary_0_3: Summary };
  national: {
    n_fit_total: number;
    sido_sign: { n_sidos_with_new: number; n_mean_residual_positive: number; n_mean_residual_negative: number };
    age_counts: { "0_1": number; "0_3": number; "4_plus": number };
    summary_0_1: Summary;
    summary_0_3: Summary;
  };
  sidos: Sido[];
  verdict: { code: string; label: string; choices: Choice[] };
  answers: Answer[];
  next: NextItem[];
  limits: string[];
  resume?: { next_id: string; title: string; say: string; do_not: string; how: string };
};

const run = runJson as Run;

type Tab = "verdict" | "national" | "sido" | "next";
const TABS: { id: Tab; label: string }[] = [
  { id: "verdict", label: "판정" },
  { id: "national", label: "전국·대전" },
  { id: "sido", label: "시도" },
  { id: "next", label: "다음 실험" },
];

const HELP: ExpHelpDoc = {
  title: "연식=0 잔차",
  blurb: "재고 지역회귀에 연식=0을 넣었을 때 실제 신축과의 격차입니다. ŷ에 k%를 더하지 않습니다.",
  method: {
    paras: [
      "단지 1행, 창 5년 중앙값, log OLS, 세대수·최고층·연식·주차. 시도마다 1회 적합 후 잔차를 스택합니다.",
      "잔차율 = (실제 − 예측) / 실제. 과소예측 = 실제 > 연식=0 예측.",
    ],
  },
  limits: { paras: run.limits },
  meaning: {
    paras: [
      "잔차율이 음수면 연식=0 예측이 실제보다 큽니다. 전국 공통 신축 프리미엄을 더할 근거가 아닙니다.",
      "서울과 경기처럼 부호가 갈리면 입지가 연식 슬라이스보다 큽니다.",
    ],
  },
};

function pct(n: number | null | undefined, d = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(d)}%`;
}

function ci(v: number[] | null | undefined) {
  if (!v || v.length !== 2) return "";
  return ` [${pct(v[0])} , ${pct(v[1])}]`;
}

function statusLabel(s: string) {
  if (s === "planned") return "예정";
  if (s === "blocked") return "금지";
  if (s === "done") return "완료";
  return s;
}

function SumRow({ label, s }: { label: string; s: Summary }) {
  const boot = s.bootstrap_mean_residual_rate_age0_pct;
  return (
    <tr>
      <td className="text-left">{label}</td>
      <td>{s.n.toLocaleString("ko-KR")}</td>
      <td>
        {pct(s.mean_residual_rate_age0)}
        <span className="text-slate-400">{ci(boot?.ci95)}</span>
      </td>
      <td>{pct(s.median_residual_rate_age0)}</td>
      <td>{pct(s.underpred_share_age0, 0)}</td>
      <td>{pct(s.mean_y_over_yhat0_minus_1)}</td>
    </tr>
  );
}

export default function Age0ResidualLab() {
  const [tab, setTab] = useState<Tab>("verdict");
  const n = run.national;

  return (
    <div className="max-w-[96rem] mx-auto p-4 space-y-3">
      <div className="flex items-start gap-1">
        <p className="text-[11px] text-slate-500 dark:text-slate-400">
          연구 전용. {run.method.as_of_label} · {run.method.fit_scope} · {run.date} 스냅샷. 예측식에 신축 프리미엄을
          더하지 않습니다.{" "}
          <a className="underline underline-offset-2" href="?tool=builder">
            시공사 효과
          </a>
          {" · "}
          <a className="underline underline-offset-2" href="?tool=newapt">
            신규아파트 M2
          </a>
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
                연식=0은 재고 식의 0년 슬라이스입니다. 전국 0~3년 잔차율 평균 {pct(n.summary_0_3.mean_residual_rate_age0)}{" "}
                {ci(n.summary_0_3.bootstrap_mean_residual_rate_age0_pct?.ci95)} · 과소예측 비중{" "}
                {pct(n.summary_0_3.underpred_share_age0, 0)}.
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

        {tab === "national" && (
          <>
            <p className="text-[11px] text-slate-500">
              {run.method.note} {run.method.grain}. 잔차율 (y−ŷ0)/y. 적합 n={n.n_fit_total.toLocaleString("ko-KR")} ·
              0~3년 {n.age_counts["0_3"].toLocaleString("ko-KR")} · 0~1년 {n.age_counts["0_1"].toLocaleString("ko-KR")}.
              시도 {n.sido_sign.n_sidos_with_new}곳 중 평균 잔차 + {n.sido_sign.n_mean_residual_positive} / −{" "}
              {n.sido_sign.n_mean_residual_negative}.
            </p>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">표본</th>
                  <th>n</th>
                  <th>잔차율 평균 (연식=0)</th>
                  <th>중앙</th>
                  <th>과소예측 비중</th>
                  <th>y/ŷ0−1 평균</th>
                </tr>
              </thead>
              <tbody>
                <SumRow label="전국 0~3년" s={n.summary_0_3} />
                <SumRow label="전국 0~1년" s={n.summary_0_1} />
                <SumRow label="대전 0~3년" s={run.daejeon.summary_0_3} />
                <SumRow label="대전 0~1년" s={run.daejeon.summary_0_1} />
              </tbody>
            </table>
            <p className="text-[11px] text-slate-500">
              대전은 시 전체 1회 적합(n_fit={run.daejeon.n_fit}). 전국은 시도별 식을 스택한 값이라 대전과 표본이
              겹칩니다.
            </p>
          </>
        )}

        {tab === "sido" && (
          <>
            <p className="text-[11px] text-slate-500">0~3년. 잔차율 양수 = 연식=0이 과소예측(실제가 더 비쌈).</p>
            <div className="overflow-x-auto">
              <table className="data w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="text-left">시도</th>
                    <th>n 0~3</th>
                    <th>잔차율 평균</th>
                    <th>과소예측 비중</th>
                    <th>y/ŷ0−1</th>
                  </tr>
                </thead>
                <tbody>
                  {run.sidos.map((s) => (
                    <tr
                      key={s.addr1}
                      className={clsx(
                        (s.mean_residual_rate_age0 ?? 0) > 5 && "bg-indigo-50/70 dark:bg-indigo-950/30",
                        (s.mean_residual_rate_age0 ?? 0) < -5 && "bg-amber-50/70 dark:bg-amber-950/20",
                      )}
                    >
                      <td className="text-left">{s.addr1}</td>
                      <td>{(s.n_0_3 ?? 0).toLocaleString("ko-KR")}</td>
                      <td>
                        {pct(s.mean_residual_rate_age0)}
                        <span className="text-slate-400">{ci(s.ci_residual_age0)}</span>
                      </td>
                      <td>{pct(s.underpred_share_age0, 0)}</td>
                      <td>{pct(s.mean_y_over_yhat0_minus_1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {tab === "next" && (
          <>
            {run.resume && <LabResume resume={run.resume} />}
            <p className="text-[11px] text-slate-500">
              재실행은 backend에서{" "}
              <code className="font-mono">python -m app.collective.regional_regression.age0_residual_lab</code>. 숫자는
              스냅샷을 덮고, 판정 문장은 사람이 고칩니다.
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
