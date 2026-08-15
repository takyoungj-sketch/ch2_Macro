import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runRentRegression, type RentRegressionResult } from "../api/client";

function fmtPct(v: number | null | undefined) {
  if (v == null || !Number.isFinite(v)) return "—";
  return `${v.toFixed(1)}%`;
}

function fmtR2(v: number | null | undefined) {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toFixed(3);
}

export default function RentRegressionPanel({
  buildingKey,
  extraKeys,
  assetType,
}: {
  buildingKey: string;
  extraKeys: string[];
  assetType: string;
}) {
  const [exclusiveArea, setExclusiveArea] = useState(true);
  const [floor, setFloor] = useState(true);
  const [buildingAge, setBuildingAge] = useState(true);
  const [logModel, setLogModel] = useState(false);
  const keys = [buildingKey, ...extraKeys.filter((k) => k !== buildingKey)];

  const runM = useMutation({
    mutationFn: () =>
      runRentRegression({
        buildingKeys: keys,
        assetType,
        exclusiveArea,
        floor,
        buildingAge,
        modelType: logModel ? "log" : "linear",
      }),
  });

  const data: RentRegressionResult | undefined = runM.data;
  const err =
    (runM.error as { response?: { data?: { detail?: string } } } | undefined)?.response?.data
      ?.detail ?? (runM.isError ? "회귀를 실행하지 못했습니다." : null);

  return (
    <div className="space-y-3">
      <p className="text-[10px] text-slate-500">
        전세 보증금(만원) 기준. 면적·층·연식이 보증금에 어떤 방향·크기로 작용하는지 탐색합니다.
        월세·반전세는 포함하지 않습니다. 표본 8건 이상.
        {keys.length > 1 ? ` · 선택 ${keys.length}동 통합` : ""}
      </p>
      <div className="flex flex-wrap gap-3 text-xs">
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={exclusiveArea}
            onChange={(e) => setExclusiveArea(e.target.checked)}
          />
          전용면적
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={floor} onChange={(e) => setFloor(e.target.checked)} />
          층
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={buildingAge}
            onChange={(e) => setBuildingAge(e.target.checked)}
          />
          연식
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={logModel} onChange={(e) => setLogModel(e.target.checked)} />
          로그(% 해석)
        </label>
      </div>
      <button
        type="button"
        className="btn btn-primary text-xs"
        disabled={runM.isPending}
        onClick={() => runM.mutate()}
      >
        {runM.isPending ? "실행 중…" : keys.length > 1 ? "통합 회귀 실행" : "회귀 실행"}
      </button>
      {err && <p className="text-xs text-red-600">{err}</p>}
      {data && (
        <div className="space-y-2 text-xs">
          <p className="text-slate-600 dark:text-slate-300">
            n={data.n.toLocaleString("ko-KR")} · 수정 R² {fmtR2(data.adj_r_squared)} · MAPE{" "}
            {fmtPct(data.mape)}
          </p>
          {data.equation && (
            <p className="rounded border border-slate-200 dark:border-slate-700 px-2 py-1.5 font-mono text-[11px] leading-snug">
              {data.equation}
            </p>
          )}
          {(data.warnings ?? []).map((w) => (
            <p key={w} className="text-[10px] text-amber-700">
              {w}
            </p>
          ))}
          {data.coefficients?.length > 0 && (
            <div className="modal-table-wrap overflow-x-auto">
              <table className="w-full text-xs border-collapse modal-inner-table">
                <thead>
                  <tr>
                    <th className="border px-2 py-1">변수</th>
                    <th className="border px-2 py-1">효과</th>
                    <th className="border px-2 py-1">p</th>
                  </tr>
                </thead>
                <tbody>
                  {data.coefficients.map((c) => (
                    <tr key={c.name}>
                      <td className="border px-2 py-1">{c.label || c.name}</td>
                      <td className="border px-2 py-1">
                        {c.effect_plain ??
                          (c.estimate != null ? c.estimate.toFixed(2) : "—")}
                      </td>
                      <td className="border px-2 py-1 tabular-nums">
                        {(c.p ?? c.p_value) != null
                          ? Number(c.p ?? c.p_value).toFixed(4)
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
