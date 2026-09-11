import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import snapshotChungbukJson from "../../../docs/lab/recommend_twin_bench_run.json";
import snapshotGyeonggiJson from "../../../docs/lab/recommend_twin_bench_run_gyeonggi.json";
import ExpHelp, { type ExpHelpDoc } from "./ExpHelp";
import LabResume from "./LabResume";
import {
  fetchBenchCases,
  fetchProfileTwins,
  runRecommendTwinBench,
  type AssetType,
  type BenchColumn,
  type BenchResult,
} from "../api/recommendTwinBenchClient";

const HELP: ExpHelpDoc = {
  title: "모형추천 Twin 벤치",
  blurb: "제품 Macro와 같은 엔진으로 Local / Twin1 / Twin2를 비교합니다. 실험 Twin은 1위만 씁니다. 제품 식은 바꾸지 않습니다.",
  method: {
    paras: [
      "읍면동 초점. Twin1은 Local 식 고정, Twin2는 같은 1위 표본에서 예측형 식을 다시 고릅니다. +더미는 Twin 표본에만 동 절편을 엽니다. 경기는 일반구 산하 동을 넣지 않습니다.",
      "시나리오: 연면적 120 · 대지 250 · 연식 10 · 도로 12미터미만 · 용도 기준범주. 더미 예측은 초점 동 절편.",
    ],
  },
  limits: {
    paras: [
      "Local CV와 Twin CV는 시험 표본이 다릅니다. 한 줄 우열로 읽지 않습니다.",
      "1위가 게이트에서 떨어지면 Twin 열은 비웁니다. 2위를 승격하지 않습니다.",
    ],
  },
  meaning: {
    paras: [
      "Twin1 vs Twin2는 같은 1위 표본에서 식만 다릅니다. +더미는 절편 오염을 줄이는지 봅니다.",
      "점추정·CI·PI는 통계적 참고값이며 개별 적정가가 아닙니다.",
    ],
  },
};

type SnapCol = {
  n?: number | null;
  search_cv_mape?: number | null;
  confirm_cv_mape?: number | null;
  y_hat?: number | null;
  skipped_reason?: string | null;
  predict_skipped_reason?: string | null;
};
type SnapRow = {
  case_id: string;
  label?: string;
  asset_type: AssetType;
  region_code: string;
  rank1_region_code?: string | null;
  rank1_skipped_reason?: string | null;
  error?: string;
  columns?: Record<string, SnapCol>;
};
type SnapSummary = {
  n_cases?: number;
  n_ok?: number;
  n_error?: number;
  n_twin_rank1?: number;
  n_twin1_confirm_lt_local?: number;
  n_twin2_confirm_lt_twin1?: number;
};
type Basin = "chungbuk" | "gyeonggi";
type Snapshot = {
  status?: string;
  date?: string;
  basin?: string;
  resume?: { next_id: string; title: string; say: string; do_not: string; how: string };
  summary?: Record<string, SnapSummary>;
  reading?: { notes?: string[] };
  rows?: SnapRow[];
};

const SNAPSHOTS: Record<Basin, Snapshot> = {
  chungbuk: snapshotChungbukJson as Snapshot,
  gyeonggi: snapshotGyeonggiJson as Snapshot,
};
const BASIN_KO: Record<Basin, string> = { chungbuk: "충북", gyeonggi: "경기" };
const ASSET_KO: Record<AssetType, string> = {
  commercial: "상업",
  factory: "공업",
  detached: "단독",
};

function caseBasin(c: { sido_prefix?: string | null; basin?: string | null; region_code: string }): Basin {
  if (c.basin === "gyeonggi" || c.sido_prefix === "41" || c.region_code.startsWith("41")) return "gyeonggi";
  return "chungbuk";
}

function fmtCv(v?: number | null) {
  return v == null ? "—" : `${v.toFixed(1)}%`;
}
function fmtN(v?: number | null) {
  return v == null ? "—" : String(v);
}
function fmtPrice(v?: number | null) {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${Math.round(v).toLocaleString("ko-KR")}`;
}

function ColCell({ col, row }: { col: BenchColumn; row: "n" | "search" | "confirm" | "pred" | "ci" | "pi" | "vars" }) {
  if (col.skipped_reason) {
    return <td className="py-1 pr-2 text-slate-400 text-[11px]">{row === "n" ? col.skipped_reason : "—"}</td>;
  }
  if (row === "n") return <td className="py-1 pr-2 tabular-nums">{fmtN(col.n)}</td>;
  if (row === "search") return <td className="py-1 pr-2 tabular-nums">{fmtCv(col.search_cv_mape)}</td>;
  if (row === "confirm") return <td className="py-1 pr-2 tabular-nums">{fmtCv(col.confirm_cv_mape)}</td>;
  if (row === "vars") {
    return (
      <td className="py-1 pr-2 text-[11px]">
        {col.response_scale ?? "—"} · {(col.blocks ?? []).join(" · ") || "—"}
      </td>
    );
  }
  if (col.predict_skipped_reason) {
    return <td className="py-1 pr-2 text-slate-400 text-[11px]">{row === "pred" ? col.predict_skipped_reason : "—"}</td>;
  }
  if (row === "pred") return <td className="py-1 pr-2 tabular-nums">{fmtPrice(col.y_hat)}</td>;
  if (row === "ci") {
    return (
      <td className="py-1 pr-2 tabular-nums text-[11px]">
        {fmtPrice(col.ci_lower)} ~ {fmtPrice(col.ci_upper)}
      </td>
    );
  }
  return (
    <td className="py-1 pr-2 tabular-nums text-[11px]">
      {fmtPrice(col.pi_lower)} ~ {fmtPrice(col.pi_upper)}
    </td>
  );
}

export default function RecommendTwinBenchLab() {
  const [basin, setBasin] = useState<Basin>("gyeonggi");
  const [assetType, setAssetType] = useState<AssetType>("commercial");
  const [windowYears, setWindowYears] = useState(5);
  const [regionCode, setRegionCode] = useState("41220320");
  const [result, setResult] = useState<BenchResult | null>(null);
  const snapshot = SNAPSHOTS[basin];
  const resume = snapshot.resume ?? {
    next_id: "product-follow",
    title: "스냅샷을 읽고 제품 반영 여부를 결정한다",
    say: "실험 Twin은 1위만. 읍면동 초점. 일반구·시군구 초점은 없습니다.",
    do_not: "전국 전수, 기본 통계 식 덮기, 제품 Twin1을 1위로 축소.",
    how: "관리자 ?tool=recommend-twin.",
  };

  const casesQ = useQuery({
    queryKey: ["recommend-twin-bench-cases"],
    queryFn: fetchBenchCases,
    staleTime: 10 * 60 * 1000,
  });
  const cases = useMemo(
    () => (casesQ.data ?? []).filter((c) => c.asset_type === assetType && caseBasin(c) === basin),
    [casesQ.data, assetType, basin],
  );

  useEffect(() => {
    if (!cases.length) return;
    if (!cases.some((c) => c.region_code === regionCode)) {
      setRegionCode(cases[0].region_code);
    }
  }, [cases, regionCode]);

  const runM = useMutation({
    mutationFn: async () => {
      const twinProfile = assetType === "commercial" ? "built_commercial" : "general";
      const twins = await fetchProfileTwins(regionCode.trim(), {
        windowYears,
        twinProfile,
      });
      return runRecommendTwinBench({
        asset_type: assetType,
        region_code: regionCode.trim(),
        window_years: windowYears,
        profile_twin_neighbors: twins.neighbors,
        profile_version: twins.profile_version,
        profile_as_of_month: twins.profile_as_of_month,
        profile_window_years: twins.profile_window_years,
      });
    },
    onSuccess: (data) => setResult(data),
  });

  const download = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `recommend_twin_bench_${result.region_code}_${result.asset_type}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-4 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">모형추천 Twin 벤치</h2>
          <p className="text-slate-600 dark:text-slate-300 mt-1">
            Local · Twin1 · Twin2 × 지역더미 전후. 실험 Twin은 쌍둥이 1위만. 제품 식은 그대로입니다.
          </p>
        </div>
        <ExpHelp doc={HELP} />
      </div>
      <LabResume resume={resume} />
      <SnapshotPanel filter={assetType} snapshot={snapshot} basin={basin} />

      <div className="flex flex-wrap items-end gap-2 rounded border border-amber-200 dark:border-amber-900 p-3 bg-amber-50/40 dark:bg-amber-950/20">
        <label className="text-xs">
          권역
          <select
            className="mt-0.5 block border rounded px-2 py-1 bg-white dark:bg-slate-900"
            value={basin}
            onChange={(e) => setBasin(e.target.value as Basin)}
          >
            <option value="gyeonggi">경기 · 읍면동 · 일반구 제외</option>
            <option value="chungbuk">충북</option>
          </select>
        </label>
        <label className="text-xs">
          유형
          <select
            className="mt-0.5 block border rounded px-2 py-1 bg-white dark:bg-slate-900"
            value={assetType}
            onChange={(e) => setAssetType(e.target.value as AssetType)}
          >
            <option value="commercial">상업</option>
            <option value="factory">공업</option>
            <option value="detached">단독다가구</option>
          </select>
        </label>
        <label className="text-xs">
          창
          <select
            className="mt-0.5 block border rounded px-2 py-1 bg-white dark:bg-slate-900"
            value={windowYears}
            onChange={(e) => setWindowYears(Number(e.target.value))}
          >
            <option value={3}>3년</option>
            <option value={5}>5년</option>
            <option value={7}>7년</option>
          </select>
        </label>
        <label className="text-xs">
          샘플
          <select
            className="mt-0.5 block border rounded px-2 py-1 bg-white dark:bg-slate-900 min-w-[14rem]"
            value={cases.some((c) => c.region_code === regionCode) ? regionCode : ""}
            onChange={(e) => {
              if (e.target.value) setRegionCode(e.target.value);
            }}
          >
            <option value="">직접 입력</option>
            {cases.map((c) => (
              <option key={c.case_id} value={c.region_code}>
                {c.label} ({c.region_code}
                {c.tx_n != null ? ` · n=${c.tx_n}` : ""})
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          읍면동 코드
          <input
            className="mt-0.5 block border rounded px-2 py-1 bg-white dark:bg-slate-900 w-32"
            value={regionCode}
            onChange={(e) => setRegionCode(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="px-3 py-1.5 rounded bg-amber-800 text-white disabled:opacity-50"
          disabled={runM.isPending || regionCode.trim().length < 8}
          onClick={() => runM.mutate()}
        >
          {runM.isPending ? "계산 중…" : "이 동 실행"}
        </button>
        <button type="button" className="px-3 py-1.5 rounded border disabled:opacity-50" disabled={!result} onClick={download}>
          JSON
        </button>
      </div>

      {runM.isError && (
        <p className="text-red-600">{(runM.error as Error).message || "벤치 실패"}</p>
      )}

      {result && (
        <div className="space-y-2">
          <p className="text-xs text-slate-500">
            {result.region_code} · {result.asset_type} · 창 {result.window_years ?? "—"}년 · Twin 1위{" "}
            {result.rank1_region_code ?? result.rank1_skipped_reason ?? "—"}
            {result.local_obs?.n
              ? ` · Local 거래 n=${result.local_obs.n} 평균 ${fmtPrice(result.local_obs.mean)} P50 ${fmtPrice(result.local_obs.p50)}`
              : ""}
          </p>
          <div className="overflow-x-auto rounded border border-slate-200 dark:border-slate-700">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="text-slate-500 border-b border-slate-200 dark:border-slate-700">
                  <th className="py-1.5 px-2 font-medium"> </th>
                  {result.columns.map((c) => (
                    <th key={c.id} className="py-1.5 pr-2 font-medium">
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["n", "n"],
                    ["search", "탐색 CV"],
                    ["confirm", "확인 CV"],
                    ["vars", "식"],
                    ["pred", "시나리오 ŷ"],
                    ["ci", "평균 95% CI"],
                    ["pi", "예측구간"],
                  ] as const
                ).map(([key, label]) => (
                  <tr key={key} className="border-b border-slate-100 dark:border-slate-800">
                    <td className="py-1 px-2 text-slate-500">{label}</td>
                    {result.columns.map((c) => (
                      <ColCell key={c.id} col={c} row={key} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            시나리오 연면적 120 · 대지 250 · 연식 10 · 도로 12미터미만 · 용도 기준범주. 숫자는 한 줄로 우열 가리지
            않습니다. 제품 Macro Twin1도 1위 + 지역 더미입니다. 이 표는 더미 on/off를 나란히 봅니다.
          </p>
        </div>
      )}
    </div>
  );
}

function SnapCv({ col }: { col?: SnapCol }) {
  if (!col || col.skipped_reason) return <span className="text-slate-400">—</span>;
  return (
    <span className="tabular-nums">
      {fmtCv(col.search_cv_mape)} / {fmtCv(col.confirm_cv_mape)}
    </span>
  );
}

function SnapshotPanel({
  filter,
  snapshot,
  basin,
}: {
  filter: AssetType;
  snapshot: Snapshot;
  basin: Basin;
}) {
  const rows = (snapshot.rows ?? []).filter((r) => r.asset_type === filter);
  const sum = snapshot.summary?.[filter];
  if (!rows.length && snapshot.status !== "experimental" && snapshot.status !== "running") {
    return null;
  }
  return (
    <div className="space-y-2 rounded border border-slate-200 dark:border-slate-700 p-3">
      <p className="text-xs text-slate-500">
        {BASIN_KO[basin]} 샘플 스냅샷 {snapshot.date ?? ""} · {snapshot.status === "running" ? "계산 중" : "창 5년"}
        {basin === "gyeonggi" ? " · 읍면동만 · 일반구 산하 제외" : ""}
        {sum
          ? ` · ${sum.n_ok ?? 0}/${sum.n_cases ?? 0}동 · Twin 1위 ${sum.n_twin_rank1 ?? 0} · Twin1 확인 CV가 Local보다 낮은 동 ${sum.n_twin1_confirm_lt_local ?? 0}`
          : ""}
      </p>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-400">이 유형 행이 아직 없습니다.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[11px] border-collapse">
            <thead>
              <tr className="text-slate-500 border-b border-slate-200 dark:border-slate-700">
                <th className="py-1 pr-2 font-medium">동</th>
                <th className="py-1 pr-2 font-medium">Twin 1위</th>
                <th className="py-1 pr-2 font-medium">Local 탐색/확인</th>
                <th className="py-1 pr-2 font-medium">Twin1</th>
                <th className="py-1 pr-2 font-medium">Twin1+더미</th>
                <th className="py-1 pr-2 font-medium">Twin2</th>
                <th className="py-1 pr-2 font-medium">Twin2+더미</th>
                <th className="py-1 pr-2 font-medium">Local ŷ</th>
                <th className="py-1 pr-2 font-medium">Twin1 ŷ</th>
                <th className="py-1 font-medium">Twin2 ŷ</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const cols = r.columns || {};
                return (
                  <tr key={r.case_id} className="border-b border-slate-100 dark:border-slate-800">
                    <td className="py-1 pr-2">
                      {r.label || r.region_code}
                      <span className="block text-slate-400">{r.region_code}</span>
                    </td>
                    <td className="py-1 pr-2 text-slate-500">
                      {r.error ? r.error : r.rank1_region_code || r.rank1_skipped_reason || "—"}
                    </td>
                    <td className="py-1 pr-2">
                      <SnapCv col={cols.local} />
                    </td>
                    <td className="py-1 pr-2">
                      <SnapCv col={cols.twin1} />
                    </td>
                    <td className="py-1 pr-2">
                      <SnapCv col={cols.twin1_dummy} />
                    </td>
                    <td className="py-1 pr-2">
                      <SnapCv col={cols.twin2} />
                    </td>
                    <td className="py-1 pr-2">
                      <SnapCv col={cols.twin2_dummy} />
                    </td>
                    <td className="py-1 pr-2 tabular-nums">{fmtPrice(cols.local?.y_hat)}</td>
                    <td className="py-1 pr-2 tabular-nums">{fmtPrice(cols.twin1?.y_hat)}</td>
                    <td className="py-1 tabular-nums">{fmtPrice(cols.twin2?.y_hat)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-[11px] text-slate-500">
        {ASSET_KO[filter]} 픽스처. 확인 CV가 낮을수록 오차가 작습니다. 한 줄 우열로 읽지 않습니다.
      </p>
      {filter === "commercial" && snapshot.reading?.notes?.length ? (
        <ul className="text-[11px] text-slate-600 dark:text-slate-300 list-disc pl-4 space-y-0.5">
          {snapshot.reading.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
