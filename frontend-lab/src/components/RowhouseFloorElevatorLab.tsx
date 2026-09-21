import { useState } from "react";
import clsx from "clsx";
import runJson from "../../../docs/lab/rowhouse_floor_elevator_screen.json";
import ExpHelp, { type ExpHelpDoc } from "./ExpHelp";
import LabResume from "./LabResume";

type Choice = { id: string; label: string; selected: boolean; why: string };
type Answer = { q: string; a: string; evidence: string };
type NextItem = { id: string; status: string; title: string; ask: string; gate: string };
type Fit = {
  ok: boolean;
  n: number;
  n_buildings: number;
  gamma_mid?: number | null;
  gamma_top?: number | null;
  p_mid?: number | null;
  p_top?: number | null;
  pct_mid?: number | null;
  pct_top?: number | null;
  dir_mid?: string;
  dir_top?: string;
  theta_mid?: number | null;
  theta_top?: number | null;
  pct_theta_mid?: number | null;
  pct_theta_top?: number | null;
  p_theta_mid?: number | null;
  p_theta_top?: number | null;
  dir_theta_mid?: string;
  dir_theta_top?: string;
  n_elev_yes?: number;
  n_elev_no?: number;
  r2?: number | null;
  reason?: string;
};
type Delta = {
  n_mid?: number;
  n_top?: number;
  n_pos_mid?: number;
  n_neg_mid?: number;
  share_pos_mid?: number | null;
  median_delta_mid?: number | null;
  mean_delta_mid?: number | null;
  ci_lo_mid?: number | null;
  ci_hi_mid?: number | null;
  n_pos_top?: number;
  n_neg_top?: number;
  share_pos_top?: number | null;
  median_delta_top?: number | null;
  ci_lo_top?: number | null;
  ci_hi_top?: number | null;
};
type Phase1 = {
  pooled: Fit;
  by_n: Record<string, Fit>;
  by_type: Record<string, Fit>;
  by_max_floor: Record<string, Fit>;
  by_subtype?: Record<string, Fit>;
  building_delta: Delta;
  type_agree_mid?: string;
  type_agree_top?: string;
  n_agree_mid?: string;
  n_agree_top?: string;
  n_sig_mid?: string[];
  n_sig_top?: string[];
  type_sig_mid?: string[];
  type_sig_top?: string[];
  sign_disagree_mid?: boolean;
  sign_disagree_top?: boolean;
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
  n_csv_rows?: number;
  summary: {
    n_buildings_scanned: number;
    n_eligible: number;
    n_ident_45: number;
    n_ge_50: number;
    n_sensitivity?: Record<string, number>;
    by_type: Record<string, TypeCounts>;
    elevator_attached?: boolean;
  };
  phase1?: Phase1;
  elevator?: {
    n_yes?: number;
    n_no?: number;
    n_unknown?: number;
    n_mixed?: number;
    n_pnu?: number;
    n_pnu_hit?: number;
    snapshot?: string;
    sample?: { floors_above?: number; ride?: number; emgen?: number; purpose_detail?: string }[];
    csv?: string;
  };
  phase2b?: {
    pooled: Fit;
    by_max_floor?: Record<string, Fit>;
    by_type?: Record<string, Fit>;
    n_yes?: number;
    n_no?: number;
  };
  phase2a?: {
    balance?: {
      n_ident45?: number;
      n_yes?: number;
      n_no?: number;
      n_unknown?: number;
      n_cells?: number;
      n_cells_both?: number;
      level_ok?: boolean;
      rows?: { age_band: string; floor: string; region_type: string; yes: number; no: number; unk: number }[];
    };
    level?: { ok?: boolean; delta?: number | null; pct?: number | null; p?: number | null; dir?: string; n?: number; n_buildings?: number };
    level_skipped?: string;
  };
  phase3?: {
    n_eligible?: number;
    n_known?: number;
    n_yes?: number;
    n_no?: number;
    pooled?: Fit;
    by_max_floor?: Record<string, Fit>;
    by_cap?: Record<string, Fit>;
    by_age?: Record<string, Fit>;
    by_n?: Record<string, Fit>;
    by_purpose?: Record<string, Fit>;
    purpose_n?: Record<string, number>;
    agree_theta_top?: string;
    agree_theta_mid?: string;
    agree_slices_top?: string[];
    sketch?: {
      base?: number;
      no?: { "1"?: number; mid?: number | null; top?: number | null };
      yes?: { "1"?: number; mid?: number | null; top?: number | null };
      note?: string;
    };
  };
  phase3_csv?: string;
  answers: Answer[];
  next: NextItem[];
  limits: string[];
  resume?: { next_id: string; title: string; say: string; do_not: string; how: string };
};

const run = runJson as Run;

type Tab = "verdict" | "screen" | "phase1" | "phase2b" | "phase2a" | "phase3" | "next";
const TABS: { id: Tab; label: string }[] = [
  { id: "verdict", label: "판정" },
  { id: "screen", label: "0차 표" },
  { id: "phase1", label: "1차 FE" },
  { id: "phase2b", label: "2b 기울기" },
  { id: "phase2a", label: "2a 균형" },
  { id: "phase3", label: "3 구성" },
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
const FLOOR_KO: Record<string, string> = { "4": "4층", "5": "5층", "6plus": "6층+(참고)" };
const CAP_KO: Record<string, string> = { capital: "수도권(서울·경기·인천)", noncapital: "비수도권" };
const AGE_C_KO: Record<string, string> = { old: "노후(–2004)", new: "신축(2005+)" };
const AGE_KO: Record<string, string> = {
  "2015p": "2015+",
  "2005_14": "2005–14",
  "1995_04": "1995–04",
  pre1995: "–1994",
  na: "연식미상",
};

function dirKo(d?: string) {
  if (d === "plus") return "가산";
  if (d === "minus") return "감가";
  if (d === "ns") return "유의하지 않음";
  if (d === "split") return "갈림";
  if (d === "na") return "추정 실패";
  return d ?? "—";
}

function pct(v?: number | null) {
  if (v == null) return "—";
  return `${(v * 100).toLocaleString("ko-KR", { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`;
}

function pval(v?: number | null) {
  if (v == null) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 3 });
}

function FitRows({ rows }: { rows: { label: string; fit: Fit }[] }) {
  return (
    <table className="data w-full text-[11px]">
      <thead>
        <tr>
          <th className="text-left">칸</th>
          <th>건물</th>
          <th>n</th>
          <th className="text-left">중간</th>
          <th>중간 %</th>
          <th>p</th>
          <th className="text-left">최상</th>
          <th>최상 %</th>
          <th>p</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ label, fit }) => (
          <tr key={label}>
            <td className="text-left">{label}</td>
            <td>{fit.n_buildings.toLocaleString("ko-KR")}</td>
            <td>{fit.n.toLocaleString("ko-KR")}</td>
            <td className="text-left">{dirKo(fit.dir_mid)}</td>
            <td>{pct(fit.pct_mid)}</td>
            <td>{pval(fit.p_mid)}</td>
            <td className="text-left">{dirKo(fit.dir_top)}</td>
            <td>{pct(fit.pct_top)}</td>
            <td>{pval(fit.p_top)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ThetaRows({ rows }: { rows: { label: string; fit: Fit }[] }) {
  return (
    <table className="data w-full text-[11px]">
      <thead>
        <tr>
          <th className="text-left">칸</th>
          <th>유</th>
          <th>무</th>
          <th className="text-left">θ 중간</th>
          <th>%</th>
          <th>p</th>
          <th className="text-left">θ 최상</th>
          <th>%</th>
          <th>p</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ label, fit }) => (
          <tr key={label}>
            <td className="text-left">{label}</td>
            <td>{(fit.n_elev_yes ?? 0).toLocaleString("ko-KR")}</td>
            <td>{(fit.n_elev_no ?? 0).toLocaleString("ko-KR")}</td>
            <td className="text-left">{dirKo(fit.dir_theta_mid)}</td>
            <td>{pct(fit.pct_theta_mid)}</td>
            <td>{pval(fit.p_theta_mid)}</td>
            <td className="text-left">{dirKo(fit.dir_theta_top)}</td>
            <td>{pct(fit.pct_theta_top)}</td>
            <td>{pval(fit.p_theta_top)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function idx(v?: number | null) {
  if (v == null) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
}

const HELP: ExpHelpDoc = {
  title: "연립·다세대 층·승강기",
  blurb: "층 효과는 건물 안(FE)에서, 승강기는 건물 사이에서 봅니다. 제품 층 식은 바꾸지 않습니다.",
  method: {
    paras: [
      "종속은 ln(만원/㎡)입니다. 화면 회귀 탭의 금액 OLS를 본식으로 쓰지 않습니다.",
      "MVP 칸은 1층 / 중간(2~최고−1) / 최상입니다. 아파트 상대층(저 30%·고 70%)이 아닙니다.",
      "실험 1은 건물 FE + 층 더미 + ln(면적) + 시점입니다. 연식과 시점을 같이 넣지 않습니다. 승강기는 넣지 않습니다.",
      "실험 3은 같은 적격 풀을 체급·연식·수도권(서울·경기·인천)으로만 가릅니다. 계수로 다시 고르지 않습니다.",
    ],
  },
  limits: { paras: run.limits?.length ? run.limits : ["0차 표. 승강기 미부착."] },
  meaning: {
    paras: [
      "승강기 주효과는 FE와 공선입니다. 기울기(층×승강기)만 FE로 읽고, 수준은 4~5층 건물 사이로 읽습니다.",
      "한 단지 p값은 파일럿입니다. 전국 한 %가 아닙니다.",
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

export default function RowhouseFloorElevatorLab() {
  const [tab, setTab] = useState<Tab>("verdict");
  const s = run.summary;
  const p1 = run.phase1;
  const p2b = run.phase2b;
  const p2a = run.phase2a;
  const p3 = run.phase3;
  const elev = run.elevator;
  const scanned = s.n_buildings_scanned ?? 0;
  const eligible = s.n_eligible ?? 0;

  return (
    <div className="max-w-[96rem] mx-auto p-4 space-y-3">
      <div className="flex items-start gap-1">
        <p className="text-[11px] text-slate-500 dark:text-slate-400">
          연구 전용. 창 {run.window_years}년
          {run.period_start ? ` · ${run.period_start} ~ ${run.period_end}` : ""} · {run.date} 스냅샷.
          제품 층 식은 바꾸지 않습니다. 스캔 {scanned.toLocaleString("ko-KR")} · 적격{" "}
          {eligible.toLocaleString("ko-KR")}
          {s.elevator_attached ? " · 승강기 부착" : " · 승강기 미부착"}
          {p1 ? ` · 1차 FE ${dirKo(p1.type_agree_mid)}` : ""}.
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

      <div className="text-[12px] space-y-3">
        {tab === "verdict" && (
          <>
            {run.resume && <LabResume resume={run.resume} />}
            <p className="font-medium">{run.verdict.label}</p>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">선택</th>
                  <th className="text-left">판정</th>
                  <th className="text-left">이유</th>
                </tr>
              </thead>
              <tbody>
                {run.verdict.choices.map((c) => (
                  <tr key={c.id} className={c.selected ? "bg-indigo-50/70 dark:bg-indigo-950/30" : ""}>
                    <td>{c.selected ? "●" : "○"}</td>
                    <td className="text-left">{c.label}</td>
                    <td className="text-left">{c.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {run.answers.map((a) => (
              <div key={a.q}>
                <p className="font-medium">{a.q}</p>
                <p>{a.a}</p>
                <p className="text-[11px] text-slate-500">{a.evidence}</p>
              </div>
            ))}
          </>
        )}

        {tab === "screen" && (
          <>
            <p className="text-[11px] text-slate-500">
              게이트: n≥10 · 1층≥3 · 중간≥3 · 거래 최고층≥4. 단가·γ로 고르지 않음. 4~5층은 실험 2a 식별 창.
            </p>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">민감도</th>
                  <th>적격 건물</th>
                </tr>
              </thead>
              <tbody>
                {["10", "20", "30", "50"].map((t) => (
                  <tr key={t}>
                    <td className="text-left">n≥{t} (기본 게이트 통과분 안)</td>
                    <td>{(s.n_sensitivity?.[t] ?? 0).toLocaleString("ko-KR")}</td>
                  </tr>
                ))}
                <tr>
                  <td className="text-left">4~5층 식별 창</td>
                  <td>{(s.n_ident_45 ?? 0).toLocaleString("ko-KR")}</td>
                </tr>
                <tr>
                  <td className="text-left">n≥50 (제품 효용지수 스모크 후보)</td>
                  <td>{(s.n_ge_50 ?? 0).toLocaleString("ko-KR")}</td>
                </tr>
              </tbody>
            </table>
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th className="text-left">유형</th>
                  <th>적격</th>
                  <th>4~5층</th>
                  <th>n≥50</th>
                </tr>
              </thead>
              <tbody>
                {TYPE_ORDER.map((id) => {
                  const t = s.by_type?.[id];
                  if (!t) return null;
                  return (
                    <tr key={id}>
                      <td className="text-left">{TYPE_KO[id] ?? id}</td>
                      <td>{t.eligible.toLocaleString("ko-KR")}</td>
                      <td>{t.ident_45.toLocaleString("ko-KR")}</td>
                      <td>{t.n_ge_50.toLocaleString("ko-KR")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="text-[11px] text-slate-500">
              비교가능 목록 {run.n_csv_rows?.toLocaleString("ko-KR") ?? "—"}행 · {run.cells_csv ?? "rowhouse_floor_elevator_screen.csv"}
            </p>
          </>
        )}

        {tab === "phase1" && (
          <>
            {!p1 ? (
              <p className="text-[11px] text-slate-500">실험 1 스냅샷 없음. backend에서 러너를 재실행합니다.</p>
            ) : (
              <>
                <p className="text-[11px] text-slate-500">
                  ln(단가)=건물FE+중간+최상+ln(면적)+반기. 연식 없음. 승강기 없음. 유형 합의 중간={dirKo(p1.type_agree_mid)} ·
                  최상={dirKo(p1.type_agree_top)}
                  {p1.n_sig_mid ? ` · 중간 유의 n≥${p1.n_sig_mid.join(",")}` : ""}
                  {p1.sign_disagree_mid ? " 건물 중위 Δ와 FE 중간 부호가 갈립니다." : ""}
                </p>
                <FitRows
                  rows={[
                    { label: "풀 (n≥10)", fit: p1.pooled },
                    ...["10", "20", "30", "50"].map((t) => ({
                      label: `n≥${t}`,
                      fit: p1.by_n?.[t] ?? { ok: false, n: 0, n_buildings: 0 },
                    })),
                  ]}
                />
                <FitRows
                  rows={TYPE_ORDER.map((id) => ({
                    label: TYPE_KO[id] ?? id,
                    fit: p1.by_type?.[id] ?? { ok: false, n: 0, n_buildings: 0 },
                  }))}
                />
                <FitRows
                  rows={["4", "5", "6plus"].map((id) => ({
                    label: FLOOR_KO[id] ?? id,
                    fit: p1.by_max_floor?.[id] ?? { ok: false, n: 0, n_buildings: 0 },
                  }))}
                />
                {p1.by_subtype && Object.keys(p1.by_subtype).length > 0 && (
                  <FitRows
                    rows={Object.entries(p1.by_subtype).map(([id, fit]) => ({
                      label: id,
                      fit,
                    }))}
                  />
                )}
                <table className="data w-full text-[11px]">
                  <thead>
                    <tr>
                      <th className="text-left">건물 중위 Δ (1층 대비)</th>
                      <th>건물</th>
                      <th>가산</th>
                      <th>감가</th>
                      <th>중위</th>
                      <th>95% CI</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="text-left">중간</td>
                      <td>{(p1.building_delta.n_mid ?? 0).toLocaleString("ko-KR")}</td>
                      <td>{(p1.building_delta.n_pos_mid ?? 0).toLocaleString("ko-KR")}</td>
                      <td>{(p1.building_delta.n_neg_mid ?? 0).toLocaleString("ko-KR")}</td>
                      <td>{pct(p1.building_delta.median_delta_mid)}</td>
                      <td>
                        {pct(p1.building_delta.ci_lo_mid)} ~ {pct(p1.building_delta.ci_hi_mid)}
                      </td>
                    </tr>
                    <tr>
                      <td className="text-left">최상</td>
                      <td>{(p1.building_delta.n_top ?? 0).toLocaleString("ko-KR")}</td>
                      <td>{(p1.building_delta.n_pos_top ?? 0).toLocaleString("ko-KR")}</td>
                      <td>{(p1.building_delta.n_neg_top ?? 0).toLocaleString("ko-KR")}</td>
                      <td>{pct(p1.building_delta.median_delta_top)}</td>
                      <td>
                        {pct(p1.building_delta.ci_lo_top)} ~ {pct(p1.building_delta.ci_hi_top)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </>
            )}
          </>
        )}

        {tab === "phase2b" && (
          <>
            {!p2b ? (
              <p className="text-[11px] text-slate-500">실험 2b 스냅샷 없음.</p>
            ) : (
              <>
                <p className="text-[11px] text-slate-500">
                  FE 유지 · 승강기 주효과 없음. θ는 승강기 있는 건물의 층 기울기 차이. 유 {p2b.n_yes ?? 0} · 무 {p2b.n_no ?? 0}
                  {elev ? ` · 표제부 ${elev.snapshot ?? ""} 승용[45]·비상[46]` : ""}.
                </p>
                <table className="data w-full text-[11px]">
                  <thead>
                    <tr>
                      <th className="text-left">칸</th>
                      <th>유</th>
                      <th>무</th>
                      <th className="text-left">θ 중간</th>
                      <th>%</th>
                      <th>p</th>
                      <th className="text-left">θ 최상</th>
                      <th>%</th>
                      <th>p</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { label: "풀", fit: p2b.pooled },
                      ...["4", "5", "6plus"].map((id) => ({
                        label: FLOOR_KO[id] ?? id,
                        fit: p2b.by_max_floor?.[id] ?? { ok: false, n: 0, n_buildings: 0 },
                      })),
                      ...TYPE_ORDER.map((id) => ({
                        label: TYPE_KO[id] ?? id,
                        fit: p2b.by_type?.[id] ?? { ok: false, n: 0, n_buildings: 0 },
                      })),
                    ].map(({ label, fit }) => (
                      <tr key={label}>
                        <td className="text-left">{label}</td>
                        <td>{(fit.n_elev_yes ?? 0).toLocaleString("ko-KR")}</td>
                        <td>{(fit.n_elev_no ?? 0).toLocaleString("ko-KR")}</td>
                        <td className="text-left">{dirKo(fit.dir_theta_mid)}</td>
                        <td>{pct(fit.pct_theta_mid)}</td>
                        <td>{pval(fit.p_theta_mid)}</td>
                        <td className="text-left">{dirKo(fit.dir_theta_top)}</td>
                        <td>{pct(fit.pct_theta_top)}</td>
                        <td>{pval(fit.p_theta_top)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </>
        )}

        {tab === "phase2a" && (
          <>
            {!p2a?.balance ? (
              <p className="text-[11px] text-slate-500">실험 2a 균형 표 없음.</p>
            ) : (
              <>
                <p className="text-[11px] text-slate-500">
                  4~5층만. FE 없음. 유 {p2a.balance.n_yes} · 무 {p2a.balance.n_no} · 미상 {p2a.balance.n_unknown} ·
                  양쪽 칸 {p2a.balance.n_cells_both}/{p2a.balance.n_cells}
                  {p2a.level_skipped ? " · δ 생략(균형 미달)" : ""}
                  {p2a.level?.ok ? ` · δ ${dirKo(p2a.level.dir)} ${pct(p2a.level.pct)} (인과 아님)` : ""}.
                </p>
                <table className="data w-full text-[11px]">
                  <thead>
                    <tr>
                      <th className="text-left">연식대</th>
                      <th className="text-left">층</th>
                      <th className="text-left">유형</th>
                      <th>유</th>
                      <th>무</th>
                      <th>미상</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(p2a.balance.rows ?? []).map((r) => (
                      <tr key={`${r.age_band}|${r.floor}|${r.region_type}`}>
                        <td className="text-left">{AGE_KO[r.age_band] ?? r.age_band}</td>
                        <td className="text-left">{FLOOR_KO[r.floor] ?? r.floor}</td>
                        <td className="text-left">{TYPE_KO[r.region_type] ?? r.region_type}</td>
                        <td>{r.yes.toLocaleString("ko-KR")}</td>
                        <td>{r.no.toLocaleString("ko-KR")}</td>
                        <td>{r.unk.toLocaleString("ko-KR")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </>
        )}

        {tab === "phase3" && (
          <>
            {!p3 ? (
              <p className="text-[11px] text-slate-500">실험 3 스냅샷 없음.</p>
            ) : (
              <>
                <p className="text-[11px] text-slate-500">
                  같은 적격 {p3.n_eligible ?? 0} · 승강기 기지 {p3.n_known ?? 0} (유 {p3.n_yes ?? 0} · 무 {p3.n_no ?? 0}).
                  계수로 다시 고르지 않음. θ 최상 합의={dirKo(p3.agree_theta_top)} · 중간={dirKo(p3.agree_theta_mid)}
                  {p3.agree_slices_top?.length ? ` · 칸 ${p3.agree_slices_top.join(", ")}` : ""}.
                </p>
                <p className="text-[11px] font-medium">랩 스케치 (1층=100, 제품 아님)</p>
                <table className="data w-full text-[11px]">
                  <thead>
                    <tr>
                      <th className="text-left">층</th>
                      <th>승강기 없음</th>
                      <th>승강기 있음</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="text-left">1층</td>
                      <td>{idx(p3.sketch?.no?.[1] ?? 100)}</td>
                      <td>{idx(p3.sketch?.yes?.[1] ?? 100)}</td>
                    </tr>
                    <tr>
                      <td className="text-left">중간</td>
                      <td>{idx(p3.sketch?.no?.mid)}</td>
                      <td>{idx(p3.sketch?.yes?.mid)}</td>
                    </tr>
                    <tr>
                      <td className="text-left">최상</td>
                      <td>{idx(p3.sketch?.no?.top)}</td>
                      <td>{idx(p3.sketch?.yes?.top)}</td>
                    </tr>
                  </tbody>
                </table>
                <p className="text-[11px] text-slate-500">{p3.sketch?.note}</p>
                <ThetaRows
                  rows={[
                    { label: "풀", fit: p3.pooled ?? { ok: false, n: 0, n_buildings: 0 } },
                    ...["4", "5", "6plus"].map((id) => ({
                      label: FLOOR_KO[id] ?? id,
                      fit: p3.by_max_floor?.[id] ?? { ok: false, n: 0, n_buildings: 0 },
                    })),
                    ...(["capital", "noncapital"] as const).map((id) => ({
                      label: CAP_KO[id] ?? id,
                      fit: p3.by_cap?.[id] ?? { ok: false, n: 0, n_buildings: 0 },
                    })),
                    ...(["old", "new"] as const).map((id) => ({
                      label: AGE_C_KO[id] ?? id,
                      fit: p3.by_age?.[id] ?? { ok: false, n: 0, n_buildings: 0 },
                    })),
                    ...["10", "20", "30", "50"].map((t) => ({
                      label: `n≥${t}`,
                      fit: p3.by_n?.[t] ?? { ok: false, n: 0, n_buildings: 0 },
                    })),
                    ...Object.entries(p3.by_purpose ?? {}).map(([id, fit]) => ({
                      label: id,
                      fit,
                    })),
                  ]}
                />
                {p3.purpose_n && Object.keys(p3.purpose_n).length > 0 && (
                  <p className="text-[11px] text-slate-500">
                    표제부 용도 건물 수{" "}
                    {Object.entries(p3.purpose_n)
                      .map(([k, n]) => `${k} ${n}`)
                      .join(" · ")}
                    . 원장 housing_subtype은 쓰지 않음.
                  </p>
                )}
              </>
            )}
          </>
        )}

        {tab === "next" && (
          <>
            {run.resume && <LabResume resume={run.resume} />}
            <p className="text-[11px] text-slate-500">
              재실행은 backend에서{" "}
              <code className="font-mono">python -m app.rowhouse_lab.floor_elevator_screen</code>. 숫자는
              스냅샷을 덮고, 판정 문장은 유지합니다.
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
                    <td className="text-left">{item.title}</td>
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
