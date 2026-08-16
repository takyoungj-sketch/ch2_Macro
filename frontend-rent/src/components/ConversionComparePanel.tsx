import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchConversionCompare, fetchConversionValidate, fetchRbDistribution } from "../api/client";
import {
  CONVERSION_METHOD_LABELS,
  assetTypeLabel,
  type RentAssetType,
  type StatsWindowYears,
  type ValidateMethodKey,
} from "../types";

const VALIDATE_METHODS: { key: ValidateMethodKey; label: string }[] = [
  { key: "mean_simple", label: "단순평균" },
  { key: "mean_weighted", label: "n가중" },
  { key: "ols_origin", label: "원점회귀" },
  { key: "ols_weighted", label: "가중회귀" },
];

const SPLITS: { key: "in_sample_sigungu" | "in_sample_dong" | "holdout_sigungu" | "holdout_dong"; label: string }[] = [
  { key: "in_sample_sigungu", label: "동일기간 · 시군구" },
  { key: "in_sample_dong", label: "동일기간 · 읍면동" },
  { key: "holdout_sigungu", label: "hold-out · 시군구" },
  { key: "holdout_dong", label: "hold-out · 읍면동" },
];

const METHOD_KEYS = [
  "r_mean_simple",
  "r_mean_weighted",
  "r_ols_origin",
  "r_ols_weighted",
] as const;

function fmtR(v: number | null | undefined) {
  if (v == null) return "—";
  return `${v.toFixed(2)}%`;
}

function fmtNum(v: number | null | undefined, digits = 2) {
  if (v == null) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export default function ConversionComparePanel({
  addr1,
  assetKinds,
  initialTab = "rates",
  onClose,
  layout = "modal",
}: {
  addr1: string;
  assetKinds: RentAssetType[];
  initialTab?: "rates" | "validate" | "rbdist";
  onClose: () => void;
  layout?: "modal" | "page";
}) {
  const [tab, setTab] = useState<"rates" | "validate" | "rbdist">(initialTab);
  const [windowFilter, setWindowFilter] = useState<StatsWindowYears | 0>(0);
  const validateQ = useQuery({
    queryKey: ["rent-conv-validate"],
    queryFn: fetchConversionValidate,
    enabled: tab === "validate",
  });
  const rbDistQ = useQuery({
    queryKey: ["rent-rb-dist"],
    queryFn: fetchRbDistribution,
    enabled: tab === "rbdist",
  });
  const compareQ = useQuery({
    queryKey: ["rent-conv-compare", addr1, assetKinds],
    queryFn: () =>
      fetchConversionCompare({
        addr1,
        assetTypes: assetKinds.filter((k) => k !== "detached"),
      }),
    enabled: Boolean(addr1),
  });

  const rows = useMemo(() => {
    const all = compareQ.data?.items ?? [];
    if (!windowFilter) return all;
    return all.filter((r) => r.window_years === windowFilter);
  }, [compareQ.data, windowFilter]);

  const shell =
    layout === "page"
      ? "w-full max-w-6xl mx-auto p-4 space-y-3"
      : "fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 p-4 overflow-y-auto";
  const inner = layout === "page" ? "card p-4 space-y-3" : "card w-full max-w-6xl my-6 p-4 space-y-3";

  return (
    <div className={shell}>
      <div className={inner}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">전환율 실험</h2>
            <p className="text-xs text-slate-500">
              {addr1} · 연구 종료. 목록 적용은 단순평균(확정). 검증·분포는 서울 1회 리포트.
            </p>
          </div>
          <button type="button" className="text-sm text-slate-500" onClick={onClose}>
            닫기
          </button>
        </div>
        <div className="flex gap-2 text-xs">
          <button
            type="button"
            className={clsx(
              "rounded border px-2 py-1",
              tab === "rates" ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950" : "border-slate-300",
            )}
            onClick={() => setTab("rates")}
          >
            4방안 r
          </button>
          <button
            type="button"
            className={clsx(
              "rounded border px-2 py-1",
              tab === "validate" ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950" : "border-slate-300",
            )}
            onClick={() => setTab("validate")}
          >
            검증 결과
          </button>
          <button
            type="button"
            className={clsx(
              "rounded border px-2 py-1",
              tab === "rbdist" ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950" : "border-slate-300",
            )}
            onClick={() => setTab("rbdist")}
          >
            r_b 분포
          </button>
        </div>
        {tab === "validate" && (
          <div className="space-y-3">
            {validateQ.isLoading && <p className="text-sm text-slate-400">불러오는 중…</p>}
            {validateQ.error && (
              <p className="text-sm text-red-600">검증 리포트가 없습니다. validate_conversion.py 를 실행하세요.</p>
            )}
            {validateQ.data && (
              <>
                <p className="text-[11px] text-slate-500">
                  {validateQ.data.addr1} · as_of {validateQ.data.as_of} · 반전세 환산 vs 전세 P50
                  (만원/㎡). hold-out은 마지막 1년.
                </p>
                {["3", "5", "7"].map((w) => {
                  const block = validateQ.data!.windows[w];
                  if (!block) return null;
                  return (
                    <div key={w} className="space-y-1">
                      <h3 className="text-sm font-semibold">
                        {w}년 창 ({block.period[0]} ~ {block.period[1]})
                      </h3>
                      <div className="overflow-x-auto">
                        <table className="data">
                          <thead>
                            <tr>
                              <th>구분</th>
                              <th>칸</th>
                              <th>방법</th>
                              <th>MAE</th>
                              <th>MAPE</th>
                              <th>Median AE</th>
                            </tr>
                          </thead>
                          <tbody>
                            {SPLITS.map((sp) =>
                              VALIDATE_METHODS.map((m, i) => {
                                const s = block[sp.key].summary[m.key];
                                return (
                                  <tr key={`${sp.key}|${m.key}`}>
                                    {i === 0 && (
                                      <td rowSpan={4} className="text-[10px] align-middle">
                                        {sp.label}
                                        <div className="text-slate-400">{block[sp.key].n_cells}칸</div>
                                      </td>
                                    )}
                                    {i === 0 && (
                                      <td rowSpan={4} className="num align-middle">
                                        {s.cells}
                                      </td>
                                    )}
                                    <td className={m.key === "mean_simple" ? "font-semibold text-indigo-700 dark:text-indigo-300" : undefined}>
                                      {m.label}
                                    </td>
                                    <td className="num">{fmtNum(s.mae_median)}</td>
                                    <td className="num">{fmtNum(s.mape_median)}%</td>
                                    <td className="num">{fmtNum(s.median_ae_median)}</td>
                                  </tr>
                                );
                              }),
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        )}
        {tab === "rbdist" && (
          <div className="space-y-3">
            {rbDistQ.isLoading && <p className="text-sm text-slate-400">불러오는 중…</p>}
            {rbDistQ.error && (
              <p className="text-sm text-red-600">
                분포 리포트가 없습니다. report_rb_distribution.py 를 실행하세요.
              </p>
            )}
            {rbDistQ.data && (
              <>
                <p className="text-[11px] text-slate-500">
                  {rbDistQ.data.addr1} · as_of {rbDistQ.data.as_of} · 게이트 통과 칸의 건물 r_b.
                  안정 MAD&lt;0.8·|평균−중앙|≤0.5 / 약간 MAD&lt;1.5·갭≤1.0 / 그 외 매우불안정.
                  진단만 — 방법 교체 없음.
                </p>
                {(["sigungu", "dong", "all"] as const).map((lv) => {
                  const b = rbDistQ.data!.bands[lv];
                  if (!b) return null;
                  return (
                    <p key={lv} className="text-xs">
                      {lv === "sigungu" ? "시군구" : lv === "dong" ? "읍면동" : "전체"}{" "}
                      안정 {b.stable.n}({b.stable.pct}%) · 약간 {b.mild.n}({b.mild.pct}%) · 매우불안정{" "}
                      {b.unstable.n}({b.unstable.pct}%)
                    </p>
                  );
                })}
                <div className="overflow-x-auto max-h-[28rem]">
                  <table className="data">
                    <thead>
                      <tr>
                        <th>권</th>
                        <th>동</th>
                        <th>유형</th>
                        <th>창</th>
                        <th>n</th>
                        <th>평균</th>
                        <th>중앙</th>
                        <th>MAD</th>
                        <th>평균−중앙</th>
                        <th>min~max</th>
                        <th>띠</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rbDistQ.data.cells
                        .filter((c) => c.band !== "stable")
                        .map((c) => (
                          <tr key={`${c.level}|${c.addr2}|${c.addr3}|${c.asset_type}|${c.window_years}`}>
                            <td className="text-[10px]">
                              {c.level === "dong" ? "동" : "시군구"} {c.addr2}
                            </td>
                            <td className="text-[10px]">{c.addr3 || "—"}</td>
                            <td className="text-[10px] text-center">{assetTypeLabel(c.asset_type)}</td>
                            <td className="num">{c.window_years}년</td>
                            <td className="num">{c.n}</td>
                            <td className="num">{fmtNum(c.mean)}</td>
                            <td className="num">{fmtNum(c.median)}</td>
                            <td className="num">{fmtNum(c.mad)}</td>
                            <td className="num">{fmtNum(c.mean_minus_median)}</td>
                            <td className="num text-[10px]">
                              {fmtNum(c.min)}~{fmtNum(c.max)}
                            </td>
                            <td className={c.band === "unstable" ? "text-amber-700" : undefined}>
                              {c.band === "unstable" ? "매우불안정" : "약간"}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-[10px] text-slate-400">
                  안정 칸은 숨김. 매우불안정이 소수면 추가 게이트만 검토.
                </p>
              </>
            )}
          </div>
        )}
        {tab === "rates" && (
        <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {([0, 3, 5, 7] as const).map((w) => (
            <button
              key={w}
              type="button"
              className={clsx(
                "rounded border px-2 py-1",
                windowFilter === w
                  ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950"
                  : "border-slate-300 dark:border-slate-600",
              )}
              onClick={() => setWindowFilter(w)}
            >
              {w === 0 ? "창 전체" : `${w}년`}
            </button>
          ))}
        </div>
        {compareQ.isLoading && <p className="text-sm text-slate-400">불러오는 중…</p>}
        {compareQ.error && (
          <p className="text-sm text-red-600">비교 마트를 불러오지 못했습니다.</p>
        )}
        {compareQ.data && (
          <div className="overflow-x-auto">
            <table className="data">
              <thead>
                <tr>
                  <th>시군구</th>
                  <th>유형</th>
                  <th>창</th>
                  <th>식별건물</th>
                  <th>전세n</th>
                  <th>반전세n</th>
                  {METHOD_KEYS.map((k) => (
                    <th key={k} className={k === "r_mean_simple" ? "text-indigo-600" : undefined}>
                      {CONVERSION_METHOD_LABELS[k]}
                    </th>
                  ))}
                  <th>게이트</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.addr2}|${r.asset_type}|${r.window_years}`}>
                    <td>{r.addr2.trim() ? r.addr2 : "시 전체"}</td>
                    <td className="text-[10px] text-center">{assetTypeLabel(r.asset_type)}</td>
                    <td className="num">{r.window_years}년</td>
                    <td className="num">{r.n_buildings.toLocaleString("ko-KR")}</td>
                    <td className="num">{r.n_jeonse.toLocaleString("ko-KR")}</td>
                    <td className="num">{r.n_mixed.toLocaleString("ko-KR")}</td>
                    <td className="num font-semibold text-indigo-700 dark:text-indigo-300">
                      {fmtR(r.r_mean_simple)}
                    </td>
                    <td className="num">{fmtR(r.r_mean_weighted)}</td>
                    <td className="num">{fmtR(r.r_ols_origin)}</td>
                    <td className="num">{fmtR(r.r_ols_weighted)}</td>
                    <td className="text-center text-[10px]">
                      {r.gate_passed ? "통과" : "미달"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && (
              <p className="text-xs text-slate-400 p-3">해당 조건의 전환율 행이 없습니다.</p>
            )}
          </div>
        )}
        </div>
        )}
      </div>
    </div>
  );
}
