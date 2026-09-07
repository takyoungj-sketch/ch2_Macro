import { useState } from "react";
import clsx from "clsx";
import runJson from "../../../docs/lab/builder_ident_run.json";
import ExpHelp, { type ExpHelpDoc } from "./ExpHelp";
import LabResume from "./LabResume";

type Resid = {
  mean_pct: number;
  median_pct: number;
  mean_ci95_pct: number[] | null;
  top_region: string | null;
  top_region_share: number | null;
};

type Featured = {
  builder: string;
  n: number;
  n_regions: number;
  land_only_pct: number;
  land_only_ci: number[] | null;
  land_plus_fe_pct: number | null;
  land_plus_fe_ci: number[] | null;
  ratio_fe_over_land: number | null;
  kept_after_fe: boolean;
  resid_A: Resid | null;
  resid_B: Resid | null;
};

type NextItem = { id: string; status: string; title: string; ask: string; gate: string };
type Answer = { q: string; a: string; evidence: string };
type Choice = { id: string; label: string; selected: boolean; why: string; note?: string };

type WithinFeatured = {
  builder: string;
  n: number;
  n_cells: number;
  land_plus_fe_pct: number | null;
  within_pct: number | null;
  within_ci: number[] | null;
  within_gu_median_pct: number | null;
  share_gu_positive: number | null;
  ratio_within_over_fe: number | null;
  kept: boolean;
  within_nonzero?: boolean;
};

type Run = {
  date: string;
  decision: string;
  method: {
    note: string;
    as_of_label: string;
    n_eligible: number;
    n_regions: number;
    min_builder_n: number;
    min_builder_regions: number;
  };
  fit: {
    A_land: { adj_r2: number; mape: number; k: number };
    B_land_fe: { adj_r2: number; mape: number; k: number };
    C_fe: { adj_r2: number; mape: number; k: number };
    D_core: { adj_r2: number; mape: number; k: number };
    delta_adj_r2: {
      B_minus_A_fe_given_land: number;
      C_minus_D_fe_given_no_land: number;
      A_minus_D_land_given_no_fe: number;
      B_minus_C_land_given_fe: number;
    };
  };
  second_stage: {
    A_resid_on_builder: { adj_r2: number };
    A_resid_on_builder_region: { adj_r2: number };
    B_resid_on_builder: { adj_r2: number };
  };
  stability_summary: {
    n_builders_ge30_ge3regions: number;
    median_abs_ratio_fe_over_land: number | null;
    n_sign_and_p05_after_fe: number;
  };
  featured: Featured[];
  verdict: { code: string; label: string; choices: Choice[] };
  answers: Answer[];
  next: NextItem[];
  limits: string[];
  resume?: { next_id: string; title: string; say: string; do_not: string; how: string };
  within_gu?: {
    decision: string;
    method: { n_gu_fit: number; n_gu_skipped: number; n_stacked: number; median_gu_adj_r2: number | null };
    second_stage: { within_resid_on_builder: { adj_r2: number } };
    summary: { n_featured: number; n_kept: number; n_within_nonzero?: number };
    featured: WithinFeatured[];
    verdict?: { label: string; note: string };
  };
};

const run = runJson as Run;

type Tab = "verdict" | "models" | "builders" | "withingu" | "next";
const TABS: { id: Tab; label: string }[] = [
  { id: "verdict", label: "판정" },
  { id: "models", label: "네 모형" },
  { id: "builders", label: "시공사 안정성" },
  { id: "withingu", label: "구 안" },
  { id: "next", label: "다음 실험" },
];

const HELP: ExpHelpDoc = {
  title: "시공사 효과 식별",
  blurb: "지역회귀 현재 정의로 공시지가와 시군구 FE를 같은 표본에서 비교합니다.",
  method: {
    paras: [
      "단지 1행, 창 5년 중앙값, log(만원/㎡). 핵심은 세대수·최고층·연식·주차. 공시지가는 원/㎡ 원값. 시군구 FE.",
      "2단계: 모형 A 잔차 ~ 시공사, 같은 잔차 ~ 시공사+시군구 FE. %는 exp(γ)−1. 기준은 기타(n<30).",
    ],
    bullets: [
      "면적·거래시점은 현재 지역회귀에 없어 넣지 않음",
      "예측식·신축 프리미엄·시공사 보정은 적용하지 않음",
    ],
  },
  limits: {
    paras: run.limits.map((x) => x),
  },
  meaning: {
    paras: [
      "공시만으로 본 시공사 %가 지역 FE 뒤에 남으면 독립 효과 후보입니다. FE 뒤에 0 근처로 가면 입지가 시공사로 보인 경우입니다.",
      "제품 지역회귀는 구 안에서 돌아갑니다. 구 안 잔차는 남지만 전국 FE γ와 부호가 갈려, 전국 공통 γ를 식에 넣지 않습니다 (D-065).",
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

export default function BuilderIdentLab() {
  const [tab, setTab] = useState<Tab>("verdict");
  const d = run.fit.delta_adj_r2;
  const sum = run.stability_summary;

  return (
    <div className="max-w-[96rem] mx-auto p-4 space-y-3">
      <div className="flex items-start gap-1">
        <p className="text-[11px] text-slate-500 dark:text-slate-400">
          연구 전용. {run.method.as_of_label} · n={run.method.n_eligible.toLocaleString("ko-KR")} · 시군구{" "}
          {run.method.n_regions} · {run.date} 스냅샷. D-063·D-065. 집합 메뉴·예측식은 바꾸지 않습니다. 연식=0 신축 잔차는{" "}
          <a className="underline underline-offset-2" href="?tool=age0">
            연식=0 잔차
          </a>
          .
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
                제품 지역회귀·신규아파트 식에 시공사 변수를 넣지 않습니다. 공시지가는 입지의 일부를 흡수하지만 시군구 FE를
                대체하지 않습니다. 구 안 잔차는 남으나 전국 FE와 식별이 불안정합니다 (D-065).
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

        {tab === "models" && (
          <>
            <p className="text-[11px] text-slate-500">{run.method.note}</p>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">모형</th>
                  <th className="text-left">변수</th>
                  <th>k</th>
                  <th>Adj R²</th>
                  <th>MAPE</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="text-left">D</td>
                  <td className="text-left">세대수·층·연식·주차</td>
                  <td>{run.fit.D_core.k}</td>
                  <td>{run.fit.D_core.adj_r2.toFixed(3)}</td>
                  <td>{run.fit.D_core.mape.toFixed(1)}%</td>
                </tr>
                <tr>
                  <td className="text-left">A</td>
                  <td className="text-left">D + 개별공시지가</td>
                  <td>{run.fit.A_land.k}</td>
                  <td>{run.fit.A_land.adj_r2.toFixed(3)}</td>
                  <td>{run.fit.A_land.mape.toFixed(1)}%</td>
                </tr>
                <tr>
                  <td className="text-left">C</td>
                  <td className="text-left">D + 시군구 FE</td>
                  <td>{run.fit.C_fe.k}</td>
                  <td>{run.fit.C_fe.adj_r2.toFixed(3)}</td>
                  <td>{run.fit.C_fe.mape.toFixed(1)}%</td>
                </tr>
                <tr>
                  <td className="text-left">B</td>
                  <td className="text-left">A + 시군구 FE</td>
                  <td>{run.fit.B_land_fe.k}</td>
                  <td>{run.fit.B_land_fe.adj_r2.toFixed(3)}</td>
                  <td>{run.fit.B_land_fe.mape.toFixed(1)}%</td>
                </tr>
              </tbody>
            </table>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">비교</th>
                  <th>Δ Adj R²</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="text-left">A−D 공시 | FE 없음</td>
                  <td>+{d.A_minus_D_land_given_no_fe.toFixed(3)}</td>
                </tr>
                <tr>
                  <td className="text-left">C−D FE | 공시 없음</td>
                  <td>+{d.C_minus_D_fe_given_no_land.toFixed(3)}</td>
                </tr>
                <tr className="bg-indigo-50 dark:bg-indigo-950/40">
                  <td className="text-left">B−A FE | 공시 있음</td>
                  <td>+{d.B_minus_A_fe_given_land.toFixed(3)}</td>
                </tr>
                <tr className="bg-indigo-50 dark:bg-indigo-950/40">
                  <td className="text-left">B−C 공시 | FE 있음</td>
                  <td>+{d.B_minus_C_land_given_fe.toFixed(3)}</td>
                </tr>
              </tbody>
            </table>
            <p className="text-[11px] text-slate-500">
              2단계 Adj R²: A잔차~시공사 {run.second_stage.A_resid_on_builder.adj_r2.toFixed(3)} · A잔차~시공사+FE{" "}
              {run.second_stage.A_resid_on_builder_region.adj_r2.toFixed(3)} · B잔차~시공사{" "}
              {run.second_stage.B_resid_on_builder.adj_r2.toFixed(3)}
            </p>
          </>
        )}

        {tab === "builders" && (
          <>
            <p className="text-[11px] text-slate-500">
              충분 표본 n≥{run.method.min_builder_n} · 시군구≥{run.method.min_builder_regions} ={" "}
              {sum.n_builders_ge30_ge3regions}곳. FE 후에도 부호·p&lt;0.05 = {sum.n_sign_and_p05_after_fe}곳. |FE/공시만|
              중앙값 {sum.median_abs_ratio_fe_over_land ?? "—"}. % = exp(γ)−1 vs 기타.
            </p>
            <div className="overflow-x-auto">
              <table className="data w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="text-left">시공사</th>
                    <th>n</th>
                    <th>시군구</th>
                    <th>공시만</th>
                    <th>공시+지역 FE</th>
                    <th>비율</th>
                    <th className="text-left">유지</th>
                  </tr>
                </thead>
                <tbody>
                  {run.featured.map((s) => (
                    <tr
                      key={s.builder}
                      className={clsx(s.kept_after_fe ? "bg-indigo-50/70 dark:bg-indigo-950/30" : undefined)}
                    >
                      <td className="text-left">{s.builder}</td>
                      <td>{s.n.toLocaleString("ko-KR")}</td>
                      <td>{s.n_regions}</td>
                      <td>
                        {pct(s.land_only_pct)}
                        <span className="text-slate-400">{ci(s.land_only_ci)}</span>
                      </td>
                      <td>
                        {pct(s.land_plus_fe_pct)}
                        <span className="text-slate-400">{ci(s.land_plus_fe_ci)}</span>
                      </td>
                      <td>{s.ratio_fe_over_land == null ? "—" : s.ratio_fe_over_land.toFixed(2)}</td>
                      <td className="text-left">{s.kept_after_fe ? "남음" : "사라짐/반전"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3 className="font-semibold">모형 A·B 평균 잔차 (참고)</h3>
            <p className="text-[11px] text-slate-500">
              평균 잔차는 2단계 기준(기타)과 다릅니다. B는 이미 시군구 FE가 들어간 잔차.
            </p>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">시공사</th>
                  <th>A 평균</th>
                  <th>B 평균</th>
                  <th className="text-left">1위 시군구 (A)</th>
                </tr>
              </thead>
              <tbody>
                {run.featured.map((s) => (
                  <tr key={`r-${s.builder}`}>
                    <td className="text-left">{s.builder}</td>
                    <td>
                      {pct(s.resid_A?.mean_pct)}
                      <span className="text-slate-400">{ci(s.resid_A?.mean_ci95_pct)}</span>
                    </td>
                    <td>
                      {pct(s.resid_B?.mean_pct)}
                      <span className="text-slate-400">{ci(s.resid_B?.mean_ci95_pct)}</span>
                    </td>
                    <td className="text-left">
                      {s.resid_A?.top_region ?? "—"}
                      {s.resid_A?.top_region_share != null
                        ? ` ${(s.resid_A.top_region_share * 100).toFixed(1)}%`
                        : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {tab === "withingu" && run.within_gu && (
          <>
            <section className="rounded border border-amber-200 dark:border-amber-800 bg-amber-50/70 dark:bg-amber-950/30 px-2.5 py-2 space-y-1">
              <p className="font-semibold text-amber-950 dark:text-amber-100">
                {run.within_gu.verdict?.label ?? "구 안 잔차 (D-065)"}
              </p>
              <p>{run.within_gu.verdict?.note}</p>
            </section>
            <p className="text-[11px] text-slate-500">
              구마다 핵심+공시지가 log OLS. 적합 {run.within_gu.method.n_gu_fit}곳 · 스킵{" "}
              {run.within_gu.method.n_gu_skipped}곳 · 스택 {run.within_gu.method.n_stacked.toLocaleString("ko-KR")}단지.
              구 중앙 Adj R² {run.within_gu.method.median_gu_adj_r2 ?? "—"}. 잔차~시공사 Adj R²{" "}
              {run.within_gu.second_stage.within_resid_on_builder.adj_r2.toFixed(3)}. 주요{" "}
              {run.within_gu.summary.n_featured}곳 중 CI 0 제외 {run.within_gu.summary.n_within_nonzero ?? "—"}곳 · 1차와
              부호 유지 {run.within_gu.summary.n_kept}곳. % ≈ exp(평균 로그 잔차)−1.
            </p>
            <div className="overflow-x-auto">
              <table className="data w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="text-left">시공사</th>
                    <th>n</th>
                    <th>구 셀</th>
                    <th>1차 공시+FE</th>
                    <th>구 안</th>
                    <th>구 중앙</th>
                    <th>구 양수</th>
                    <th className="text-left">판정</th>
                  </tr>
                </thead>
                <tbody>
                  {run.within_gu.featured.map((s) => (
                    <tr
                      key={s.builder}
                      className={clsx(
                        s.kept
                          ? "bg-indigo-50/70 dark:bg-indigo-950/30"
                          : s.within_nonzero
                            ? "bg-amber-50/70 dark:bg-amber-950/20"
                            : undefined,
                      )}
                    >
                      <td className="text-left">{s.builder}</td>
                      <td>{s.n.toLocaleString("ko-KR")}</td>
                      <td>{s.n_cells}</td>
                      <td>{pct(s.land_plus_fe_pct)}</td>
                      <td>
                        {pct(s.within_pct)}
                        <span className="text-slate-400">{ci(s.within_ci)}</span>
                      </td>
                      <td>{pct(s.within_gu_median_pct)}</td>
                      <td>
                        {s.share_gu_positive == null ? "—" : `${(s.share_gu_positive * 100).toFixed(0)}%`}
                      </td>
                      <td className="text-left">
                        {s.kept ? "유지" : s.within_nonzero ? "남음·부호 갈림" : "0 포함"}
                      </td>
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
              이 창에서 이어갑니다. 1차 재실행은{" "}
              <code className="font-mono">python -m app.collective.regional_regression.builder_ident_lab</code>
              . 구 안은{" "}
              <code className="font-mono">python -m app.collective.regional_regression.builder_within_gu_lab</code>.
              숫자는 스냅샷을 덮고, 판정 문장은 사람이 고칩니다.
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
                {run.next.map((n) => (
                  <tr
                    key={n.id}
                    className={clsx(n.status === "blocked" && "bg-amber-50 dark:bg-amber-950/30")}
                  >
                    <td className="text-left">{statusLabel(n.status)}</td>
                    <td className="text-left font-medium">{n.title}</td>
                    <td className="text-left">{n.ask}</td>
                    <td className="text-left">{n.gate}</td>
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
