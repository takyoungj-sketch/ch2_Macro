import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchTwinLabExperiment,
  fetchTwinLabExperiments,
  type TwinLabExperiment,
  type TwinLabRegionRow,
  type TwinLabVersionKey,
} from "../api/twinLabClient";

type TabId = "overview" | "compare" | "region";

const VERSION_ORDER: TwinLabVersionKey[] = ["r0", "r1", "t1", "rt", "v0", "v1", "v2", "v3", "v2x"];

const VERSION_LABELS: Partial<Record<TwinLabVersionKey, string>> = {
  r0: "R0 Local",
  r1: "R1 참고(식별불가)",
  t1: "T1 +Twin",
  rt: "RT +지역+Twin",
  v0: "V0",
  v1: "V1",
  v2: "V2",
  v3: "V3",
  v2x: "V2x",
};

function versionLabel(v: TwinLabVersionKey, exp?: TwinLabExperiment): string {
  if (exp?.v2_twin_profile === "region_features" && v === "v0") return "R0 Local";
  if (exp?.v2_twin_profile === "region_features" && v === "v2") return "R1 +지역";
  return VERSION_LABELS[v] || v;
}

function downloadComparisonCsv(exp: TwinLabExperiment, versions: TwinLabVersionKey[]) {
  const hasRt = versions.includes("rt");
  const header = hasRt
    ? [
        "case_id",
        "region_label",
        "sample_group",
        "winner",
        "r0_cv",
        "t1_cv",
        "rt_cv",
        "rt_lift_vs_r0",
        "region_selected",
        "rt_blocks",
        "pool_id",
        "n_local",
        "n_pool",
        "region_tier",
      ]
    : [
        "case_id",
        "region_label",
        "region_code",
        "sample_group",
        "n_v0",
        ...versions.map((v) => `${v}_cv_mape`),
        "v1_lift_rel",
        "v2_lift_rel",
        "winner",
      ];
  const lines = [header.join(",")];
  for (const r of exp.regions ?? []) {
    if (hasRt) {
      const rt = r.versions.rt;
      const sel = (rt?.region_blocks_selected ?? []).join(";");
      const blocks = (rt?.blocks ?? []).join("+");
      lines.push(
        [
          r.case_id,
          `"${(r.region_label || "").replace(/"/g, '""')}"`,
          r.sample_group ?? "",
          r.winner ?? "",
          r.versions.r0?.cv_mape ?? "",
          r.versions.t1?.cv_mape ?? "",
          rt?.cv_mape ?? "",
          rt?.lift_rel ?? "",
          `"${sel}"`,
          `"${blocks}"`,
          rt?.pool_id ?? "",
          rt?.n_local ?? "",
          rt?.n_pool ?? "",
          rt?.region_tier ?? exp.region_feature_tier ?? "",
        ].join(","),
      );
      continue;
    }
    const cols = [
      r.case_id,
      `"${(r.region_label || "").replace(/"/g, '""')}"`,
      r.region_code ?? "",
      r.sample_group ?? "",
      r.versions.v0?.n ?? "",
      ...versions.map((v) => r.versions[v]?.cv_mape ?? ""),
      r.versions.v1?.lift_rel ?? "",
      r.versions.v2?.lift_rel ?? "",
      r.winner ?? "",
    ];
    lines.push(cols.join(","));
  }
  const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${exp.experiment_id}_comparison.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

function num(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toFixed(digits);
}

function VersionBlock({
  title,
  ver,
  versionKey,
}: {
  title: string;
  ver: TwinLabRegionRow["versions"][string] | undefined;
  versionKey?: TwinLabVersionKey | string;
}) {
  if (!ver) {
    return (
      <div className="rounded-lg border border-slate-200 dark:border-slate-600 p-3 text-xs text-slate-400">
        {title}: 데이터 없음
      </div>
    );
  }
  if (ver.error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-950/40 p-3 text-xs text-red-700 dark:text-red-300">
        {title}: {ver.error}
      </div>
    );
  }
  const twins = ver.twins ?? [];
  const formulaBlocks = ver.blocks ?? [];
  // 식에 실제로 들어간 region만 "채택"으로 표시 (후보/오표기 방지)
  const regionSelected = (ver.region_blocks_selected ?? []).filter((b) =>
    formulaBlocks.includes(b),
  );
  const regionInPool = ver.region_blocks_candidate ?? ver.region_blocks_in_pool ?? [];
  const isR1 = versionKey === "r1";
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 p-3 space-y-2 text-xs">
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="font-semibold text-slate-800 dark:text-slate-100">{title}</h4>
        <span className="tabular-nums text-blue-700 dark:text-blue-300 font-semibold">
          CV-MAPE {num(ver.cv_mape)}%
        </span>
      </div>
      {isR1 && (
        <p className="text-[11px] text-amber-800 dark:text-amber-200/90 bg-amber-50 dark:bg-amber-950/40 rounded px-2 py-1">
          고정 지역프로필 + 단일동 Local이면 region_*는 상수 → 식별불가. R1≡R0는
          ‘효과 없음’이 아니라 통계적으로 정상. 전국 확대·승패 판정에 쓰지 않음.
        </p>
      )}
      {ver.lift_rel != null && (
        <p className="text-slate-600 dark:text-slate-300">
          Lift {pct(ver.lift_rel)} · Δ {num(ver.delta_pp)}%p
          {ver.hit != null && (
            <span className={ver.hit ? " text-emerald-600" : " text-amber-600"}>
              {ver.hit ? " · hit" : " · miss"}
            </span>
          )}
        </p>
      )}
      <p className="text-slate-500 dark:text-slate-400">
        n={ver.n ?? "—"}
        {ver.n_local != null && <> · Local {ver.n_local}</>}
        {ver.n_pool != null && ver.n_pool !== ver.n_local && <> · Pool {ver.n_pool}</>}
        {(ver.n_twins != null ? ver.n_twins : twins.length) > 0 && (
          <> · Twin {ver.n_twins ?? twins.length}</>
        )}
        {" · "}scale={ver.response_scale ?? "—"}
      </p>
      {formulaBlocks.length > 0 && (
        <p className="text-[11px] text-slate-600 dark:text-slate-300 break-all">
          식 블록: {formulaBlocks.join(" + ")}
        </p>
      )}
      {!isR1 && (regionSelected.length > 0 || regionInPool.length > 0) ? (
        <p className="text-[11px] text-emerald-700 dark:text-emerald-300/90 break-all">
          지역변수
          {regionSelected.length > 0
            ? ` 채택: ${regionSelected.join(", ")}`
            : " 채택 없음"}
          {regionInPool.length > 0 ? ` · 후보: ${regionInPool.join(", ")}` : null}
          {ver.region_tier ? ` · tier=${ver.region_tier}` : null}
        </p>
      ) : null}
      {twins.length > 0 && (
        <ol className="list-decimal list-inside space-y-0.5 text-slate-700 dark:text-slate-200">
          {twins.map((t, i) => (
            <li key={`${t.region_code}-${i}`}>
              {t.label || t.region_code}
              {t.similarity != null && (
                <span className="text-slate-400 ml-1">
                  (sim {Number(t.similarity).toFixed(2)})
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export default function TwinExperimentLab({
  onClose,
  closeLabel = "제품 UI로",
}: {
  onClose?: () => void;
  closeLabel?: string;
}) {
  const [tab, setTab] = useState<TabId>("overview");
  const [experimentId, setExperimentId] = useState<string>("");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  const [kpiGroup, setKpiGroup] = useState<string>("all");

  const listQ = useQuery({
    queryKey: ["twin-lab", "list"],
    queryFn: fetchTwinLabExperiments,
  });

  const items = listQ.data?.items ?? [];
  const activeId = experimentId || items[0]?.experiment_id || "pilot-commercial-demo";

  const expQ = useQuery({
    queryKey: ["twin-lab", "exp", activeId],
    queryFn: () => fetchTwinLabExperiment(activeId),
    enabled: Boolean(activeId),
  });

  const exp: TwinLabExperiment | undefined = expQ.data;
  const regions = exp?.regions ?? [];
  const versions = useMemo(() => {
    const vs = (exp?.versions ?? VERSION_ORDER).filter((v) =>
      VERSION_ORDER.includes(v as TwinLabVersionKey),
    ) as TwinLabVersionKey[];
    return vs.length ? vs : (["v0", "v1", "v2"] as TwinLabVersionKey[]);
  }, [exp?.versions]);

  const sampleGroups = useMemo(() => {
    const keys = Object.keys(exp?.kpis_by_sample_group ?? {});
    if (keys.length) {
      const ordered = ["all", "dev", "holdout", "pilot", "primary", "control"];
      return [
        ...ordered.filter((k) => keys.includes(k)),
        ...keys.filter((k) => !ordered.includes(k)).sort(),
      ];
    }
    return ["all"];
  }, [exp?.kpis_by_sample_group]);

  const activeKpis = useMemo(() => {
    const byGroup = exp?.kpis_by_sample_group?.[kpiGroup];
    if (byGroup) return byGroup;
    if (kpiGroup === "all") return exp?.kpis;
    return exp?.kpis_by_sample_group?.all ?? exp?.kpis;
  }, [exp?.kpis, exp?.kpis_by_sample_group, kpiGroup]);

  const selected =
    regions.find((r) => r.case_id === selectedCaseId) ||
    regions[0] ||
    null;

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-900 text-slate-800 dark:text-slate-100">
      <header className="border-b border-amber-300/60 bg-amber-50 dark:bg-amber-950/40 dark:border-amber-800 px-4 py-3">
        <div className="max-w-6xl mx-auto flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200">
              R&amp;D · 비공개 · 쌍둥이 로직 보강
            </p>
            <h1 className="text-lg font-bold text-slate-900 dark:text-slate-50">
              CH2 Macro 쌍둥이 로직 보강
            </h1>
            <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-0.5">
              Twin Experiment Lab · V0 Local 대비 Twin lift · 제품 UI와 분리 ·{" "}
              <code className="text-[10px]">?lab=twin</code>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="text-xs border border-slate-300 dark:border-slate-600 rounded px-2 py-1.5 bg-white dark:bg-slate-800"
              value={activeId}
              onChange={(e) => {
                setExperimentId(e.target.value);
                setSelectedCaseId(null);
              }}
            >
              {items.length === 0 && (
                <option value="pilot-commercial-demo">pilot-commercial-demo</option>
              )}
              {items.map((it) => (
                <option key={it.experiment_id} value={it.experiment_id}>
                  {it.experiment_id}
                  {it.asset_type ? ` · ${it.asset_type}` : ""}
                  {it.n_regions != null ? ` (${it.n_regions})` : ""}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!expQ.data}
              onClick={() => {
                if (!expQ.data) return;
                const vs = ((expQ.data.versions ?? ["v0", "v1", "v2"]) as TwinLabVersionKey[]).filter(
                  (v) => VERSION_ORDER.includes(v),
                );
                downloadComparisonCsv(expQ.data, vs.length ? vs : ["v0", "v1", "v2"]);
              }}
              className="text-xs px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 hover:bg-slate-50 disabled:opacity-40"
            >
              CSV 내보내기
            </button>
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="text-xs px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-600 hover:bg-white/80"
              >
                {closeLabel}
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-4 space-y-4">
        {(listQ.isError || expQ.isError) && (
          <p className="text-sm text-red-600">
            Lab API 오류 — 백엔드 `/api/built/lab/twin-experiments` 와 토큰을 확인하세요.
          </p>
        )}
        {expQ.isLoading && (
          <p className="text-xs text-slate-500">실험 불러오는 중…</p>
        )}

        {exp && (
          <>
            <div className="flex flex-wrap gap-2 text-[11px] text-slate-600 dark:text-slate-300">
              <span className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600">
                유형 {exp.asset_type}
              </span>
              <span className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600">
                {exp.period_years}년 · {exp.contract_year_from}–{exp.contract_year_to}
              </span>
              <span className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600">
                scope {exp.region_scope} · {exp.anchor_basin}
              </span>
              <span className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600">
                {exp.n_regions ?? regions.length} regions · {exp.source}
              </span>
            </div>

            <div
              className="inline-flex rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5 gap-0.5"
              role="tablist"
            >
              {(
                [
                  ["overview", "성능 요약"],
                  ["compare", "지역별 비교"],
                  ["region", "지역 상세"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  className={clsx(
                    "px-3 py-1.5 text-xs rounded transition-colors",
                    tab === id
                      ? "bg-white dark:bg-slate-700 shadow-sm font-medium"
                      : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200",
                  )}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>

            {tab === "overview" && (
              <section className="rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 overflow-hidden">
                <div className="px-4 py-2 border-b border-slate-100 dark:border-slate-700 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold">버전별 KPI (V0 = Local baseline)</span>
                  {sampleGroups.length > 1 && (
                    <div className="inline-flex rounded border border-slate-200 dark:border-slate-600 p-0.5 gap-0.5">
                      {sampleGroups.map((g) => (
                        <button
                          key={g}
                          type="button"
                          className={clsx(
                            "px-2 py-0.5 text-[10px] rounded",
                            kpiGroup === g
                              ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
                              : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200",
                          )}
                          onClick={() => setKpiGroup(g)}
                        >
                          {g}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-900/50 text-slate-500">
                        <th className="text-left px-3 py-2">지표</th>
                        {versions.map((v) => (
                          <th key={v} className="text-right px-3 py-2 uppercase">
                            {versionLabel(v, exp)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(
                        [
                          ["Median CV-MAPE", "median_cv_mape", "mape"],
                          ["Median Lift", "median_lift_rel", "pct"],
                          ["Hit Rate", "hit_rate", "pct"],
                          ["Worsened", "worsened_rate", "pct"],
                          ["n regions", "n_regions", "int"],
                        ] as const
                      ).map(([label, key, kind]) => (
                        <tr key={key} className="border-t border-slate-100 dark:border-slate-700">
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{label}</td>
                          {versions.map((v) => {
                            const cell = activeKpis?.[v]?.[key];
                            let text = "—";
                            if (typeof cell === "number") {
                              if (kind === "pct") text = pct(cell);
                              else if (kind === "mape") text = `${num(cell)}%`;
                              else text = String(cell);
                            }
                            return (
                              <td key={v} className="px-3 py-2 text-right tabular-nums font-medium">
                                {(v === "v0" || v === "r0") && kind === "pct" ? "—" : text}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {versions.includes("r1") && (
                  <p className="px-4 py-2 text-[10px] text-amber-900 dark:text-amber-100 bg-amber-50 dark:bg-amber-950/40 border-t border-amber-100 dark:border-amber-900">
                    R1(고정 프로필·단일동)은 region_*가 상수라 식별불가 → R1≡R0는 정상. 승패·전국
                    확대 판정은 R0 / T1 / RT만 사용. 지역특성 검증의 본무대는 RT.
                  </p>
                )}
                {exp.region_adoption?.selected_counts &&
                  Object.keys(exp.region_adoption.selected_counts).length > 0 && (
                    <p className="px-4 py-2 text-[10px] text-slate-600 dark:text-slate-300 border-t border-slate-100 dark:border-slate-700">
                      RT region 채택 빈도
                      {exp.region_feature_tier ? ` (tier=${exp.region_feature_tier})` : ""}
                      :{" "}
                      {Object.entries(exp.region_adoption.selected_counts)
                        .map(([k, n]) => `${k}×${n}`)
                        .join(" · ")}
                      {exp.region_adoption.rt_better_than_t1 != null && (
                        <> · RT&gt;T1 {exp.region_adoption.rt_better_than_t1}건</>
                      )}
                    </p>
                  )}
                {exp.notes && (
                  <p className="px-4 py-2 text-[10px] text-slate-600 dark:text-slate-300 bg-slate-50/80 dark:bg-slate-900/40 border-t border-slate-100 dark:border-slate-700">
                    {exp.notes}
                  </p>
                )}
                {exp.pool_ablation_v2 &&
                  Object.values(exp.pool_ablation_v2).some((r) => (r?.n_regions ?? 0) > 0) && (
                  <div className="px-4 py-3 border-t border-slate-100 dark:border-slate-700">
                    <p className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 mb-2">
                      V2 고정 pool ablation (엔진 best와 별도)
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-[11px]">
                        <thead>
                          <tr className="text-slate-500">
                            <th className="text-left py-1">pool</th>
                            <th className="text-right py-1">n</th>
                            <th className="text-right py-1">median lift</th>
                            <th className="text-right py-1">hit</th>
                            <th className="text-right py-1">worsened</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(exp.pool_ablation_v2).map(([pid, row]) => (
                            <tr key={pid} className="border-t border-slate-100 dark:border-slate-700">
                              <td className="py-1 font-mono">{pid}</td>
                              <td className="py-1 text-right tabular-nums">{row?.n_regions ?? "—"}</td>
                              <td className="py-1 text-right tabular-nums">{pct(row?.median_lift_rel)}</td>
                              <td className="py-1 text-right tabular-nums">{pct(row?.hit_rate)}</td>
                              <td className="py-1 text-right tabular-nums">{pct(row?.worsened_rate)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </section>
            )}

            {tab === "compare" && (
              <section className="rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 overflow-hidden">
                <div className="overflow-x-auto max-h-[70vh]">
                  <table className="w-full text-[11px]">
                    <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900 z-10">
                      <tr className="text-slate-500">
                        <th className="text-left px-2 py-2">읍면동</th>
                        <th className="text-left px-2 py-2">군</th>
                        <th className="text-right px-2 py-2">
                          {versions.includes("r0") ? "n(R0)" : "n(V0)"}
                        </th>
                        {versions.map((v) => (
                          <th key={v} className="text-right px-2 py-2 uppercase">
                            {versionLabel(v, exp)} MAPE
                          </th>
                        ))}
                        <th className="text-right px-2 py-2">
                          {versions.includes("rt") ? "RT Lift" : "V2 Lift"}
                        </th>
                        <th className="text-left px-2 py-2">승자</th>
                      </tr>
                    </thead>
                    <tbody>
                      {regions.map((r) => (
                        <tr
                          key={r.case_id}
                          className="border-t border-slate-100 dark:border-slate-700 hover:bg-blue-50/50 dark:hover:bg-slate-700/50 cursor-pointer"
                          onClick={() => {
                            setSelectedCaseId(r.case_id);
                            setTab("region");
                          }}
                        >
                          <td className="px-2 py-1.5 font-medium">
                            {r.region_label}
                            <span className="block text-[10px] text-slate-400 font-normal">
                              {r.region_code}
                            </span>
                          </td>
                          <td className="px-2 py-1.5 text-[10px] text-slate-500">
                            {r.sample_group ?? "—"}
                          </td>
                          <td className="px-2 py-1.5 text-right tabular-nums">
                            {r.versions.r0?.n ?? r.versions.v0?.n ?? "—"}
                          </td>
                          {versions.map((v) => (
                            <td key={v} className="px-2 py-1.5 text-right tabular-nums">
                              {num(r.versions[v]?.cv_mape)}
                            </td>
                          ))}
                          <td className="px-2 py-1.5 text-right tabular-nums text-blue-700 dark:text-blue-300">
                            {pct(r.versions.rt?.lift_rel ?? r.versions.v2?.lift_rel)}
                          </td>
                          <td className="px-2 py-1.5 uppercase text-slate-600 dark:text-slate-300">
                            {r.winner ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {tab === "region" && selected && (
              <section className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <label className="text-xs text-slate-500">지역</label>
                  <select
                    className="text-xs border border-slate-300 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-800"
                    value={selected.case_id}
                    onChange={(e) => setSelectedCaseId(e.target.value)}
                  >
                    {regions.map((r) => (
                      <option key={r.case_id} value={r.case_id}>
                        {r.region_label}
                      </option>
                    ))}
                  </select>
                  <span className="text-[11px] text-slate-400">
                    {selected.admin_level} · {selected.role} · winner {selected.winner}
                  </span>
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {versions.map((v) => (
                    <VersionBlock
                      key={v}
                      title={versionLabel(v, exp)}
                      ver={selected.versions[v]}
                      versionKey={v}
                    />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
