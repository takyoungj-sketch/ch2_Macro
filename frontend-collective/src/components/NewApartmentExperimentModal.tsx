import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchNewAptExperiment, fetchNewAptRegionCompare, type NewAptCell, type NewAptRegionCompare, type NewAptRegionModel, type NewAptSpecRow } from "../api/newAptClient";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import DraggableModalShell from "./DraggableModalShell";
import { NEW_APT_EXPERIMENT_HELP } from "../utils/residentialAnalysisHelp";

type Tab = "compare" | "region" | "m2" | "cells" | "validate" | "errors";
type CellFilter = "m2" | "holdout" | "no_land" | "outlier_y" | "outlier_ape" | "all";

const TABS: { id: Tab; label: string }[] = [
  { id: "compare", label: "비교표" },
  { id: "region", label: "충북 확장" },
  { id: "m2", label: "M2 잠정식" },
  { id: "cells", label: "학습 테이블" },
  { id: "validate", label: "검증" },
  { id: "errors", label: "오차 패턴" },
];

function fmt(n: number | null | undefined, d = 2) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", { maximumFractionDigits: d });
}

function specLabel(row: NewAptSpecRow) {
  const loc =
    row.location === "land"
      ? "토지"
      : row.location === "sigungu"
        ? "구시세"
        : row.location === "both"
          ? "구+토지"
          : row.location === "gu_fe"
            ? "구FE"
            : row.location === "gu_fe_land"
              ? "구FE+토지"
              : row.location === "sido_fe"
                ? "광역FE"
                : row.location === "sido_fe_land"
                  ? "광역FE+토지"
                  : "연도만";
  const track = row.track === "main" ? "본선" : row.track === "diag_b" ? "진단B" : "진단C";
  return `${track} ${row.product} · ${loc}`;
}

function coefLabel(name: string) {
  if (name === "const") return "절편";
  if (name === "ln_land_p50") return "ln(토지P50)";
  if (name === "ln_households") return "ln(세대수)";
  if (name === "max_floor") return "최고층";
  if (name === "parking_per_household") return "세대당 주차";
  if (name.startsWith("vintage_")) return `vintage ${name.slice("vintage_".length)}`;
  if (name.startsWith("yr_")) return `연도 ${name.slice(3)}`;
  if (name.startsWith("builder_")) return `시공사 ${name.slice("builder_".length)}`;
  if (name.startsWith("struct_")) return `구조 ${name.slice("struct_".length)}`;
  if (name.startsWith("sido_")) return `광역 ${name.slice(5)}`;
  if (name.startsWith("gu_")) return `시군구 ${name.slice(3)}`;
  return name;
}

function focusTxt(model: NewAptRegionModel, name: string) {
  const f = model.focus?.[name];
  if (f?.coef == null) return "—";
  const mag = Math.abs(f.coef).toFixed(3);
  return `${f.sign ?? ""}${mag}`;
}

function actionLabel(action: string) {
  if (action === "data_fix") return "데이터 수정";
  if (action === "later_variable") return "나중 변수";
  if (action === "ignore_old_stock") return "노후 — 변수 금지";
  return "경고만";
}

function bucketLabel(bucket: string) {
  if (bucket === "data") return "데이터";
  if (bucket === "structure") return "구조";
  if (bucket === "extra") return "모델 외";
  if (bucket === "market") return "시점";
  return bucket;
}

function zoneLabel(code: string) {
  const map: Record<string, string> = {
    exact: "정확",
    majority: "다수",
    priority_tie: "동수→우선",
    missing: "없음",
    coarse_only: "도시지역만",
  };
  return map[code] ?? code;
}

export default function NewApartmentExperimentModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("compare");
  const [sample, setSample] = useState<"A-1-land" | "A-2-land">("A-1-land");
  const [cellFilter, setCellFilter] = useState<CellFilter>("m2");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 40;

  const query = useQuery({
    queryKey: ["new-apt-experiment", "30"],
    queryFn: () => fetchNewAptExperiment("30"),
    staleTime: 5 * 60_000,
  });
  const regionQuery = useQuery({
    queryKey: ["new-apt-region-compare"],
    queryFn: fetchNewAptRegionCompare,
    staleTime: 5 * 60_000,
    enabled: tab === "region",
  });
  const data = query.data;
  const rows = (data?.comparison.table ?? []).filter((r) => r.sample === sample);

  const filteredCells = useMemo(() => {
    let list: NewAptCell[] = data?.cells ?? [];
    if (cellFilter === "m2") list = list.filter((c) => c.in_m2);
    if (cellFilter === "holdout") list = list.filter((c) => c.in_holdout && c.in_m2);
    if (cellFilter === "no_land") list = list.filter((c) => c.land_p50 == null);
    if (cellFilter === "outlier_y") list = list.filter((c) => c.outlier_y);
    if (cellFilter === "outlier_ape") list = list.filter((c) => c.outlier_ape);
    const needle = q.trim().toLowerCase();
    if (needle) {
      list = list.filter((c) =>
        [c.display_name, c.sigungu_name, c.zone_compact, c.uqa_label, c.builder_group]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(needle),
      );
    }
    return list;
  }, [data, cellFilter, q]);

  const pageCount = Math.max(1, Math.ceil(filteredCells.length / pageSize));
  const pageRows = filteredCells.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <DraggableModalShell
      open
      onClose={onClose}
      titleId="new-apt-experiment-title"
      title="신규아파트 실험"
      subtitle={
        <>
          대전 M2는 잠정 기준식 · 충북 복제·전이 실험 · 분양가 단정 아님
          <AnalysisHelpPanel explain={NEW_APT_EXPERIMENT_HELP} className="ml-1" />
        </>
      }
      allowFullscreen
      allowFontScale
      resizable
      defaultWidth={960}
      defaultHeight={720}
      minWidth={640}
      minHeight={480}
      headerExtra={
        <div className="flex flex-wrap gap-0.5 rounded-md border modal-tab-bar p-0.5" role="tablist">
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
      }
    >
      <div className="text-xs text-slate-700 dark:text-slate-200 space-y-3">
        {query.isLoading && tab !== "region" && <p className="text-slate-500">학습표·검증을 계산하는 중… (약 10초)</p>}
        {query.isError && tab !== "region" && (
          <p className="text-red-600">
            {(query.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              "실험 결과를 불러오지 못했습니다. 대전 마트가 있는지 확인하세요."}
          </p>
        )}
        {data && tab === "compare" && (
          <>
            <div className="flex flex-wrap gap-2 items-center">
              <label className="flex items-center gap-1">
                표본
                <select
                  className="input py-0.5 text-xs"
                  value={sample}
                  onChange={(e) => setSample(e.target.value as "A-1-land" | "A-2-land")}
                >
                  <option value="A-1-land">A-1 전체 연식</option>
                  <option value="A-2-land">A-2 신축 5년</option>
                </select>
              </label>
              <p className="text-[11px] text-slate-500">
                토지 조인 {fmt(data.land_join.land_join_pct, 1)}% ({data.land_join.n_land.toLocaleString("ko-KR")}/
                {data.land_join.n_cells.toLocaleString("ko-KR")}) · 얇은 셀 n&lt;15 {data.land_join.n_thin_land} · 동 안
                CV {fmt(data.land_dispersion.land_cv_mean_within_eup, 2)} / 대전 {fmt(data.land_dispersion.land_cv_daejeon, 2)}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="data w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="text-left">식</th>
                    <th className="text-right">n</th>
                    <th className="text-right">Adj R²</th>
                    <th className="text-right">hold-out MAPE</th>
                    <th className="text-right">토지 β</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={`${r.track}-${r.product}-${r.location}-${i}`} className={clsx(r.is_baseline && "bg-indigo-50 dark:bg-indigo-950/40")}>
                      <td>
                        {specLabel(r)}
                        {r.is_baseline && <span className="ml-1 text-indigo-600 font-semibold">기준</span>}
                      </td>
                      <td className="text-right tabular-nums">{r.n_train.toLocaleString("ko-KR")}</td>
                      <td className="text-right tabular-nums">{fmt(r.adj_r_squared, 3)}</td>
                      <td className="text-right tabular-nums">{r.holdout_mape == null ? "—" : `${fmt(r.holdout_mape, 1)}%`}</td>
                      <td className="text-right tabular-nums">{fmt(r.land_coef, 3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="list-disc pl-4 text-[11px] text-slate-500 space-y-0.5">
              {data.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </>
        )}

        {tab === "region" && (
          <RegionComparePanel
            loading={regionQuery.isLoading}
            error={
              regionQuery.isError
                ? ((regionQuery.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                  "충북 마트를 먼저 만드세요. pipeline/build_new_apartment_dataset.py --sido-code 43 --replace")
                : null
            }
            data={regionQuery.data}
          />
        )}

        {data && tab === "m2" && (
          <>
            <p className="text-[11px] text-slate-500">{data.baseline_role}</p>
            <p className="font-mono text-[11px] leading-relaxed break-all bg-slate-50 dark:bg-slate-800/60 rounded px-2 py-1.5">
              {data.m2.equation || "—"}
            </p>
            <p>
              n={data.m2.n_train.toLocaleString("ko-KR")} · Adj R² {fmt(data.m2.adj_r_squared, 3)} · hold-out MAPE{" "}
              {data.m2.holdout_mape == null ? "—" : `${fmt(data.m2.holdout_mape, 1)}%`} · MAE {fmt(data.m2.holdout_mae, 1)} 만원/㎡
            </p>
            {data.m2.warnings?.length ? (
              <p className="text-amber-700 dark:text-amber-300">{data.m2.warnings.join(" · ")}</p>
            ) : null}
            <div className="overflow-x-auto max-h-80">
              <table className="data w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="text-left">변수</th>
                    <th className="text-right">계수</th>
                    <th className="text-left">읽기</th>
                    <th className="text-right">SE</th>
                    <th className="text-right">t</th>
                    <th className="text-right">p</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.m2.coefficients ?? []).map((c) => (
                    <tr key={c.name}>
                      <td>{coefLabel(c.name)}</td>
                      <td className="text-right tabular-nums">{fmt(c.coef, 4)}</td>
                      <td>{c.plain ?? "—"}</td>
                      <td className="text-right tabular-nums">{fmt(c.se, 4)}</td>
                      <td className="text-right tabular-nums">{fmt(c.t, 2)}</td>
                      <td className="text-right tabular-nums">{fmt(c.p, 4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {data && tab === "cells" && (
          <>
            <div className="flex flex-wrap gap-2 items-center">
              <select
                className="input py-0.5 text-xs"
                value={cellFilter}
                onChange={(e) => {
                  setCellFilter(e.target.value as CellFilter);
                  setPage(0);
                }}
              >
                <option value="m2">M2 학습 셀</option>
                <option value="holdout">신축 hold-out</option>
                <option value="no_land">토지 미조인</option>
                <option value="outlier_y">Y IQR 이상치</option>
                <option value="outlier_ape">잔차 {data.cell_summary.ape_outlier_threshold}%+</option>
                <option value="all">전체 셀</option>
              </select>
              <input
                className="input py-0.5 text-xs w-40"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(0);
                }}
                placeholder="단지명·구…"
              />
              <span className="text-[11px] text-slate-500">
                {filteredCells.length.toLocaleString("ko-KR")}행 · 이상치 Y {data.cell_summary.n_outlier_y} · APE{" "}
                {data.cell_summary.n_outlier_ape} · 토지없음 {data.land_join.n_missing_land}
              </span>
            </div>
            <p className="text-[11px] text-slate-500">{data.land_join.note}</p>
            <div className="overflow-x-auto">
              <table className="data w-full text-[10px]">
                <thead>
                  <tr>
                    <th className="text-left">단지</th>
                    <th>연도</th>
                    <th>구</th>
                    <th className="text-right">실제</th>
                    <th className="text-right">M2</th>
                    <th className="text-right">APE%</th>
                    <th className="text-right">토지P50</th>
                    <th>용도</th>
                    <th>조인</th>
                    <th className="text-right">세대</th>
                    <th className="text-right">층</th>
                    <th className="text-right">주차</th>
                    <th>vintage</th>
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((c) => (
                    <tr
                      key={`${c.building_key}-${c.calendar_year}`}
                      className={clsx(
                        c.outlier_ape && "bg-amber-50 dark:bg-amber-950/30",
                        c.in_holdout && "outline outline-1 outline-indigo-300/60",
                      )}
                    >
                      <td className="max-w-[9rem] truncate" title={c.display_name ?? c.building_key}>
                        {c.display_name ?? c.building_key.slice(0, 8)}
                        {c.in_holdout ? <span className="ml-0.5 text-indigo-600">H</span> : null}
                      </td>
                      <td>{c.calendar_year ?? "—"}</td>
                      <td>{c.sigungu_name ?? "—"}</td>
                      <td className="text-right tabular-nums">{fmt(c.y, 0)}</td>
                      <td className="text-right tabular-nums">{fmt(c.yhat, 0)}</td>
                      <td className="text-right tabular-nums">{fmt(c.ape, 1)}</td>
                      <td className="text-right tabular-nums">{fmt(c.land_p50, 0)}</td>
                      <td title={c.uqa_label ?? undefined}>{c.zone_compact ?? "—"}</td>
                      <td>{zoneLabel(c.zone_resolution)}</td>
                      <td className="text-right tabular-nums">{c.households ?? "—"}</td>
                      <td className="text-right tabular-nums">{c.max_floor ?? "—"}</td>
                      <td className="text-right tabular-nums">{fmt(c.parking_per_household, 2)}</td>
                      <td>{c.vintage ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center gap-2 text-[11px]">
              <button type="button" className="btn py-0.5 px-2" disabled={page <= 0} onClick={() => setPage((p) => p - 1)}>
                이전
              </button>
              <span>
                {page + 1} / {pageCount}
              </span>
              <button
                type="button"
                className="btn py-0.5 px-2"
                disabled={page + 1 >= pageCount}
                onClick={() => setPage((p) => p + 1)}
              >
                다음
              </button>
            </div>
          </>
        )}

        {data && tab === "validate" && (
          <>
            <section>
              <h3 className="font-semibold mb-1">랜덤 신축 hold-out</h3>
              <p>
                {data.validation.random_new_buildings.label} · MAPE{" "}
                {data.validation.random_new_buildings.mape == null
                  ? "—"
                  : `${fmt(data.validation.random_new_buildings.mape, 1)}%`}{" "}
                · MAE {fmt(data.validation.random_new_buildings.mae, 1)} 만원/㎡ · 단지{" "}
                {data.validation.random_new_buildings.n_hold_buildings ?? "—"} · 셀{" "}
                {data.validation.random_new_buildings.n_hold ?? "—"}
              </p>
            </section>
            <section>
              <h3 className="font-semibold mb-1">구 통째 hold-out (Leave-one-구-out)</h3>
              <p className="text-[11px] text-slate-500 mb-1">
                한 구를 빼고 나머지로 M2를 학습한 뒤 그 구를 예측. 가중 MAPE {fmt(data.validation.leave_one_gu_pooled_mape, 1)}%
              </p>
              <table className="data w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="text-left">구</th>
                    <th className="text-right">학습 n</th>
                    <th className="text-right">검증 n</th>
                    <th className="text-right">MAPE</th>
                    <th className="text-right">MAE</th>
                  </tr>
                </thead>
                <tbody>
                  {data.validation.leave_one_gu.map((r) => (
                    <tr key={r.group}>
                      <td>{r.label ?? r.group}</td>
                      <td className="text-right tabular-nums">{r.n_train.toLocaleString("ko-KR")}</td>
                      <td className="text-right tabular-nums">{r.n_hold.toLocaleString("ko-KR")}</td>
                      <td className="text-right tabular-nums">{r.mape == null ? r.reason ?? "—" : `${fmt(r.mape, 1)}%`}</td>
                      <td className="text-right tabular-nums">{fmt(r.mae, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <section>
              <h3 className="font-semibold mb-1">연도 통째 hold-out</h3>
              <p className="text-[11px] text-slate-500 mb-1">{data.validation.year_holdout_note}</p>
              <table className="data w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="text-left">연도</th>
                    <th className="text-right">학습 n</th>
                    <th className="text-right">검증 n</th>
                    <th className="text-right">MAPE</th>
                    <th className="text-right">MAE</th>
                  </tr>
                </thead>
                <tbody>
                  {data.validation.leave_one_year.map((r) => (
                    <tr
                      key={r.group}
                      className={clsx(
                        data.validation.latest_year?.group === r.group && "bg-indigo-50 dark:bg-indigo-950/40",
                      )}
                    >
                      <td>
                        {r.label ?? r.group}
                        {data.validation.latest_year?.group === r.group ? (
                          <span className="ml-1 text-indigo-600">최근</span>
                        ) : null}
                      </td>
                      <td className="text-right tabular-nums">{r.n_train.toLocaleString("ko-KR")}</td>
                      <td className="text-right tabular-nums">{r.n_hold.toLocaleString("ko-KR")}</td>
                      <td className="text-right tabular-nums">{r.mape == null ? r.reason ?? "—" : `${fmt(r.mape, 1)}%`}</td>
                      <td className="text-right tabular-nums">{fmt(r.mae, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        )}

        {data && tab === "errors" && data.error_audit && (
          <>
            {data.error_audit.decision && (
              <section className="rounded border border-indigo-200 dark:border-indigo-800 bg-indigo-50/60 dark:bg-indigo-950/30 px-2.5 py-2 space-y-1">
                <p className="font-semibold text-indigo-900 dark:text-indigo-200">
                  {data.error_audit.decision.verdict}
                </p>
                <p>{data.error_audit.decision.next_step}</p>
                <p className="text-[11px] text-slate-500">{data.error_audit.decision.builder_vs_brand}</p>
              </section>
            )}
            {data.error_audit.large_new_watch && (
              <section>
                <h3 className="font-semibold mb-1">신축 대단지 과소예측 누적</h3>
                <p className="text-[11px] text-slate-500 mb-1">
                  {data.error_audit.large_new_watch.pattern} · 시공사/브랜드 후보지. 한 구·한 시공사에 몰리면 레이어를 열지
                  않습니다.
                </p>
                <table className="data w-full text-[11px] mb-2">
                  <thead>
                    <tr>
                      <th className="text-right">단지</th>
                      <th className="text-right">시공사</th>
                      <th className="text-right">브랜드</th>
                      <th className="text-right">구</th>
                      <th className="text-right">평균 APE</th>
                      <th className="text-right">과소예측</th>
                      <th>레이어 개방</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="text-right tabular-nums">{data.error_audit.large_new_watch.n_buildings}</td>
                      <td className="text-right tabular-nums">{data.error_audit.large_new_watch.n_builders}</td>
                      <td className="text-right tabular-nums">{data.error_audit.large_new_watch.n_brands}</td>
                      <td className="text-right tabular-nums">{data.error_audit.large_new_watch.n_sigungu}</td>
                      <td className="text-right tabular-nums">
                        {data.error_audit.large_new_watch.mean_ape == null
                          ? "—"
                          : `${fmt(data.error_audit.large_new_watch.mean_ape, 1)}%`}
                      </td>
                      <td className="text-right tabular-nums">
                        {data.error_audit.large_new_watch.direction_underpred_pct == null
                          ? "—"
                          : `${fmt(data.error_audit.large_new_watch.direction_underpred_pct, 0)}%`}
                      </td>
                      <td>{data.error_audit.large_new_watch.ready_for_builder_layer ? "검토" : "아직"}</td>
                    </tr>
                  </tbody>
                </table>
                {data.error_audit.large_new_watch.history.length > 0 && (
                  <p className="text-[11px] text-slate-500 mb-1">
                    누적:{" "}
                    {data.error_audit.large_new_watch.history
                      .map((h) => `${h.as_of} ${h.n_buildings}단지`)
                      .join(" → ")}
                  </p>
                )}
                {data.error_audit.large_new_watch.members.length > 0 && (
                  <table className="data w-full text-[10px]">
                    <thead>
                      <tr>
                        <th className="text-left">단지</th>
                        <th>구</th>
                        <th className="text-right">APE</th>
                        <th className="text-right">세대</th>
                        <th>시공사</th>
                        <th>브랜드</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.error_audit.large_new_watch.members.map((m) => (
                        <tr key={m.building_key}>
                          <td className="max-w-[10rem] truncate">
                            {m.display_name ?? m.building_key.slice(0, 8)}
                            {m.in_holdout ? <span className="ml-0.5 text-indigo-600">H</span> : null}
                          </td>
                          <td>{m.sigungu_name ?? "—"}</td>
                          <td className="text-right tabular-nums">{fmt(m.median_ape, 1)}</td>
                          <td className="text-right tabular-nums">{m.households ?? "—"}</td>
                          <td className="max-w-[7rem] truncate">{m.builder_group ?? "—"}</td>
                          <td className="max-w-[7rem] truncate">{m.brand ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            )}
            {data.error_audit.data_fix_sensitivity && (
              <section>
                <h3 className="font-semibold mb-1">데이터 정제 비교 (본체 유지)</h3>
                <p className="text-[11px] text-slate-500 mb-1">{data.error_audit.data_fix_sensitivity.note}</p>
                <p>
                  {data.error_audit.data_fix_sensitivity.label} · 제외 셀{" "}
                  {data.error_audit.data_fix_sensitivity.n_dropped.toLocaleString("ko-KR")} · hold-out MAPE{" "}
                  {data.error_audit.data_fix_sensitivity.baseline_holdout_mape == null
                    ? "—"
                    : `${fmt(data.error_audit.data_fix_sensitivity.baseline_holdout_mape, 1)}%`}{" "}
                  →{" "}
                  {data.error_audit.data_fix_sensitivity.holdout_mape == null
                    ? "—"
                    : `${fmt(data.error_audit.data_fix_sensitivity.holdout_mape, 1)}%`}
                  {data.error_audit.data_fix_sensitivity.delta_mape != null && (
                    <> (Δ {fmt(data.error_audit.data_fix_sensitivity.delta_mape, 2)})</>
                  )}
                  {data.error_audit.data_fix_sensitivity.delta_mape != null &&
                    data.error_audit.data_fix_sensitivity.delta_mape > 0 && (
                      <span className="ml-1 text-amber-700">· 정제해도 hold-out이 나빠지면 본선 표본을 줄이지 않습니다.</span>
                    )}
                </p>
              </section>
            )}
            <p className="text-[11px] text-slate-500">
              단지 단위(연도 셀 묶음). 검토 {data.error_audit.n_review_buildings}단지 / M2{" "}
              {data.error_audit.n_m2_buildings}단지. 반복은 {data.error_audit.repeat_min}단지 이상.
            </p>
            <ul className="list-disc pl-4 text-[11px] text-slate-500 space-y-0.5">
              {data.error_audit.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
            <h3 className="font-semibold">반복 패턴</h3>
            <div className="overflow-x-auto">
              <table className="data w-full text-[11px]">
                <thead>
                  <tr>
                    <th className="text-left">패턴</th>
                    <th>갈래</th>
                    <th className="text-right">단지</th>
                    <th className="text-right">hold-out</th>
                    <th className="text-right">신축학습</th>
                    <th className="text-right">노후</th>
                    <th>반복</th>
                    <th>조치</th>
                  </tr>
                </thead>
                <tbody>
                  {data.error_audit.patterns
                    .filter((p) => p.n_buildings > 0)
                    .map((p) => (
                      <tr
                        key={p.tag}
                        className={clsx(
                          p.action === "later_variable" && "bg-indigo-50 dark:bg-indigo-950/40",
                          p.action === "data_fix" && "bg-amber-50 dark:bg-amber-950/30",
                        )}
                      >
                        <td>{p.label}</td>
                        <td>{bucketLabel(p.bucket)}</td>
                        <td className="text-right tabular-nums">{p.n_buildings}</td>
                        <td className="text-right tabular-nums">{p.n_holdout}</td>
                        <td className="text-right tabular-nums">{p.n_new_train}</td>
                        <td className="text-right tabular-nums">{p.n_old}</td>
                        <td>{p.repeat ? "예" : "—"}</td>
                        <td>{actionLabel(p.action)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            <h3 className="font-semibold">검토 단지 (APE 큰 순)</h3>
            <div className="overflow-x-auto max-h-64">
              <table className="data w-full text-[10px]">
                <thead>
                  <tr>
                    <th className="text-left">단지</th>
                    <th>구</th>
                    <th>표본</th>
                    <th className="text-right">중앙APE</th>
                    <th className="text-right">최대</th>
                    <th>방향</th>
                    <th>태그</th>
                  </tr>
                </thead>
                <tbody>
                  {data.error_audit.buildings.slice(0, 40).map((b) => (
                    <tr key={b.building_key}>
                      <td className="max-w-[10rem] truncate">{b.display_name ?? b.building_key.slice(0, 8)}</td>
                      <td>{b.sigungu_name ?? "—"}</td>
                      <td>
                        {b.in_holdout ? "hold-out" : b.is_new ? "신축학습" : "노후학습"}
                      </td>
                      <td className="text-right tabular-nums">{fmt(b.median_ape, 1)}</td>
                      <td className="text-right tabular-nums">{fmt(b.max_ape, 1)}</td>
                      <td>{b.direction === "underpred" ? "실거래↑" : "모형↑"}</td>
                      <td className="max-w-[14rem] truncate">{b.tags.join(", ") || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </DraggableModalShell>
  );
}

function RegionComparePanel({
  loading,
  error,
  data,
}: {
  loading: boolean;
  error: string | null;
  data: NewAptRegionCompare | undefined;
}) {
  if (loading) return <p className="text-slate-500">대전·충북 M2와 대전 hold-out 고정 전이를 계산하는 중…</p>;
  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return null;
  const verdict = data.transfer.verdict;
  const overall = data.transfer.misleading_overall;
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-slate-500">{data.baseline_role}</p>
      <p className="text-[11px] text-slate-500">
        대전 셀 {data.samples.daejeon?.n_cells?.toLocaleString("ko-KR") ?? "—"} · 충북 셀{" "}
        {data.samples.chungbuk?.n_cells?.toLocaleString("ko-KR") ?? "—"} · 토지 조인{" "}
        {fmt(data.samples.daejeon?.land_join_pct, 1)}% / {fmt(data.samples.chungbuk?.land_join_pct, 1)}%
      </p>
      <div
        className={clsx(
          "rounded px-2 py-1.5 text-[11px]",
          verdict.code === "improves"
            ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
            : verdict.code === "worsens"
              ? "bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
              : "bg-slate-50 text-slate-700 dark:bg-slate-800/60 dark:text-slate-200",
        )}
      >
        {verdict.summary} 통합 채택={data.adopt_pooled ? "예" : "아니오"}
      </div>
      <h3 className="font-semibold">대전 고정 테스트</h3>
      <div className="overflow-x-auto">
        <table className="data w-full text-[11px]">
          <thead>
            <tr>
              <th className="text-left">학습</th>
              <th className="text-left">테스트</th>
              <th className="text-right">MAPE</th>
              <th className="text-right">n hold</th>
            </tr>
          </thead>
          <tbody>
            {data.transfer.rows.map((r) => (
              <tr key={r.model_id} className={clsx(r.model_id === "C_sido" && "bg-indigo-50 dark:bg-indigo-950/40")}>
                <td>{r.train}</td>
                <td>{r.test}</td>
                <td className="text-right tabular-nums">{r.mape == null ? "—" : `${fmt(r.mape, 1)}%`}</td>
                <td className="text-right tabular-nums">{r.n_hold ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {overall && (
        <p className="text-[11px] text-slate-500">
          {overall.label}: {overall.mape == null ? "—" : `${fmt(overall.mape, 1)}%`} · {overall.note}
        </p>
      )}
      <h3 className="font-semibold">A / B / C 계수</h3>
      <div className="overflow-x-auto">
        <table className="data w-full text-[11px]">
          <thead>
            <tr>
              <th className="text-left">모형</th>
              <th className="text-left">목적</th>
              <th className="text-right">n</th>
              <th className="text-right">Adj R²</th>
              <th className="text-right">hold MAPE</th>
              <th className="text-right">토지</th>
              <th className="text-right">세대수</th>
              <th className="text-right">층</th>
              <th className="text-right">주차</th>
            </tr>
          </thead>
          <tbody>
            {data.models.map((m) => (
              <tr key={m.id} className={clsx(m.is_baseline && "bg-indigo-50 dark:bg-indigo-950/40")}>
                <td>
                  {m.id} {m.region}
                  {m.is_baseline ? <span className="ml-1 text-indigo-600 font-semibold">잠정</span> : null}
                </td>
                <td className="max-w-[12rem]">{m.purpose}</td>
                <td className="text-right tabular-nums">{m.n_train.toLocaleString("ko-KR")}</td>
                <td className="text-right tabular-nums">{fmt(m.adj_r_squared, 3)}</td>
                <td className="text-right tabular-nums">
                  {m.holdout_mape == null ? "—" : `${fmt(m.holdout_mape, 1)}%`}
                  <span className="block text-[10px] text-slate-400">{m.hold_scope}</span>
                </td>
                <td className="text-right tabular-nums">{focusTxt(m, "ln_land_p50")}</td>
                <td className="text-right tabular-nums">{focusTxt(m, "ln_households")}</td>
                <td className="text-right tabular-nums">{focusTxt(m, "max_floor")}</td>
                <td className="text-right tabular-nums">{focusTxt(m, "parking_per_household")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="list-disc pl-4 text-[11px] text-slate-500 space-y-0.5">
        {data.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
        {data.next_steps.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </div>
  );
}
