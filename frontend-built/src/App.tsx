import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchAddr2,
  fetchAddr3WithCounts,
  fetchFilterMeta,
  fetchLeafRegions,
  fetchRegionStructure,
  fetchRiRegions,
  fetchScopeSampleFilters,
  fetchTransactions,
  predictRegression,
  runRegression,
} from "./api/client";
import {
  formatAddr2OptionLabel,
  formatScopeAddr2,
  isFlatSidoAddr2,
} from "./utils/flatSidoRegion";
import BuiltTransactionListModal from "./components/BuiltTransactionListModal";
import AiAssistantPanel from "./components/AiAssistantPanel";
import { buildBuiltRegressionContext, buildBuiltPredictionContext } from "./api/aiClient";
import type {
  Addr3Option,
  AssetType,
  CorrelationSeries,
  IqrMultiplier,
  PredictOptions,
  RegionOption,
  RegressionLevelResult,
  RegressionPredictRequest,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionVariableSpec,
  ResponseScale,
  RiPick,
  SampleFilterState,
  ScopeSampleFilterResponse,
} from "./types";
import { EMPTY_SAMPLE_FILTER } from "./types";

function riKey(p: RiPick) {
  return `${p.eup}|${p.ri}`;
}

const ADMIN_LABELS: Record<string, string> = {
  sigungu: "시군구",
  gu: "구",
  eupmyeondong: "읍면동",
  beopjungri: "법정리",
};

const COEF_LABELS: Record<string, string> = {
  const: "상수(절편)",
  gross_area: "연면적",
  land_area: "대지면적",
  building_age: "연식",
  road_code: "도로",
};

const ASSET_TYPE_LABELS: Record<string, string> = {
  commercial: "상업",
  factory: "공장",
  detached: "단독",
};

/** statsmodels 변수명 → 표시용 한글 */
function formatCoefName(name: string, assetType?: AssetType): string {
  if (COEF_LABELS[name]) return COEF_LABELS[name];
  if (name.startsWith("zone_")) return `용도지역·${name.slice(5)}`;
  if (name.startsWith("use_")) {
    const prefix = assetType === "detached" ? "주택유형" : "건축물용도";
    return `${prefix}·${name.slice(4)}`;
  }
  if (name.startsWith("road_")) return `도로조건·${name.slice(5)}`;
  if (name.startsWith("atype_")) {
    const key = name.slice(6);
    return `유형·${ASSET_TYPE_LABELS[key] ?? key}`;
  }
  if (name.startsWith("loc_")) return `지역·${name.slice(4)}`;
  return name;
}

function parseOptionalNum(s: string): number | undefined {
  const t = s.trim();
  if (!t) return undefined;
  const n = Number(t);
  return Number.isFinite(n) ? n : undefined;
}

function sampleFilterToApi(sf: SampleFilterState) {
  return {
    zone_types: sf.zoneTypes.length ? sf.zoneTypes : undefined,
    building_uses: sf.buildingUses.length ? sf.buildingUses : undefined,
    road_width_labels: sf.roadWidthLabels.length ? sf.roadWidthLabels : undefined,
    gross_area_min: parseOptionalNum(sf.gross_area_min),
    gross_area_max: parseOptionalNum(sf.gross_area_max),
    land_area_min: parseOptionalNum(sf.land_area_min),
    land_area_max: parseOptionalNum(sf.land_area_max),
    building_age_min: parseOptionalNum(sf.building_age_min),
    building_age_max: parseOptionalNum(sf.building_age_max),
  };
}

function isEmptySampleFilter(sample: SampleFilterState): boolean {
  return (
    sample.zoneTypes.length === 0 &&
    sample.buildingUses.length === 0 &&
    sample.roadWidthLabels.length === 0 &&
    !sample.gross_area_min.trim() &&
    !sample.gross_area_max.trim() &&
    !sample.land_area_min.trim() &&
    !sample.land_area_max.trim() &&
    !sample.building_age_min.trim() &&
    !sample.building_age_max.trim()
  );
}

function sampleFilterSummary(sample: SampleFilterState): string {
  if (isEmptySampleFilter(sample)) return "전체";
  let n = sample.zoneTypes.length + sample.buildingUses.length + sample.roadWidthLabels.length;
  for (const k of [
    "gross_area_min",
    "gross_area_max",
    "land_area_min",
    "land_area_max",
    "building_age_min",
    "building_age_max",
  ] as const) {
    if (sample[k].trim()) n += 1;
  }
  return `${n}개 조건`;
}

function SampleFilterPanel({
  assetType,
  scope,
  sample,
  onChange,
  filteredTotal,
}: {
  assetType: AssetType;
  scope?: ScopeSampleFilterResponse;
  sample: SampleFilterState;
  onChange: (next: SampleFilterState) => void;
  filteredTotal?: number;
}) {
  const [open, setOpen] = useState(false);
  const useLabel = assetType === "detached" ? "주택유형" : "건축물용도";
  const contHint = (name: string) => scope?.continuous.find((c) => c.name === name);

  const toggle = (key: "zoneTypes" | "buildingUses" | "roadWidthLabels", name: string) => {
    const arr = sample[key];
    onChange({
      ...sample,
      [key]: arr.includes(name) ? arr.filter((x) => x !== name) : [...arr, name],
    });
  };

  const showZone = assetType !== "detached" && assetType !== "all";
  const countLabel =
    filteredTotal != null ? `n=${fmtNum(filteredTotal)}` : scope ? `n=${fmtNum(scope.total)}` : "…";

  const filterBody = (
    <>
      <p className="text-xs text-slate-500">
        미선택 = 전체. 회귀·거래 목록·예측에 동일 적용됩니다.
      </p>

      <div className="grid grid-cols-1 gap-2 text-xs">
        {(
          [
            ["gross_area", "gross_area_min", "gross_area_max"],
            ["land_area", "land_area_min", "land_area_max"],
            ["building_age", "building_age_min", "building_age_max"],
          ] as const
        ).map(([col, minKey, maxKey]) => {
          const hint = contHint(col);
          if (!hint) return null;
          return (
            <div key={col} className="space-y-1">
              <div className="text-slate-600 font-medium">
                {formatCoefName(col, assetType)}
                <span className="text-slate-400 font-normal">
                  {" "}
                  ({fmtNum(hint.min, 0)}~{fmtNum(hint.max, 0)})
                </span>
              </div>
              <div className="flex gap-1 items-center">
                <input
                  className="input py-1"
                  type="number"
                  placeholder="min"
                  value={sample[minKey]}
                  onChange={(e) => onChange({ ...sample, [minKey]: e.target.value })}
                />
                <span className="text-slate-400">~</span>
                <input
                  className="input py-1"
                  type="number"
                  placeholder="max"
                  value={sample[maxKey]}
                  onChange={(e) => onChange({ ...sample, [maxKey]: e.target.value })}
                />
              </div>
            </div>
          );
        })}
      </div>

      {(showZone && (scope?.zone_types?.length ?? 0) > 0) ||
      (scope?.building_uses?.length ?? 0) > 0 ||
      (scope?.road_width_labels?.length ?? 0) > 0 ? (
        <div className="space-y-2 pt-1">
          <p className="text-xs font-medium text-slate-600">범주(더미) 변수</p>
          {showZone && (scope?.zone_types?.length ?? 0) > 0 && (
            <RegionChipPanel
              compact
              collapsible
              title="용도지역"
              hint="선택한 용도지역 거래만 포함"
              selected={sample.zoneTypes}
              options={scope!.zone_types}
              onToggle={(n) => toggle("zoneTypes", n)}
              onSelectAll={() => onChange({ ...sample, zoneTypes: scope!.zone_types.map((z) => z.name) })}
              onClear={() => onChange({ ...sample, zoneTypes: [] })}
            />
          )}

          {(scope?.building_uses?.length ?? 0) > 0 && (
            <RegionChipPanel
              compact
              collapsible
              title={useLabel}
              hint={`선택한 ${useLabel}만 포함`}
              selected={sample.buildingUses}
              options={scope!.building_uses}
              onToggle={(n) => toggle("buildingUses", n)}
              onSelectAll={() => onChange({ ...sample, buildingUses: scope!.building_uses.map((u) => u.name) })}
              onClear={() => onChange({ ...sample, buildingUses: [] })}
            />
          )}

          {(scope?.road_width_labels?.length ?? 0) > 0 && (
            <RegionChipPanel
              compact
              collapsible
              title="도로조건"
              hint="선택한 도로조건 거래만 포함"
              selected={sample.roadWidthLabels}
              options={scope!.road_width_labels}
              onToggle={(n) => toggle("roadWidthLabels", n)}
              onSelectAll={() =>
                onChange({ ...sample, roadWidthLabels: scope!.road_width_labels.map((u) => u.name) })
              }
              onClear={() => onChange({ ...sample, roadWidthLabels: [] })}
            />
          )}
        </div>
      ) : null}

      <button
        type="button"
        className="btn btn-ghost text-xs"
        onClick={() => onChange({ ...EMPTY_SAMPLE_FILTER })}
      >
        표본 필터 초기화
      </button>
    </>
  );

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-xs bg-slate-50 hover:bg-slate-100 transition-colors"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="font-medium text-slate-800">표본 필터</span>
        <span className="text-slate-500 shrink-0 text-right">
          {sampleFilterSummary(sample)} · {countLabel}
          <span className="ml-1.5 inline-block w-3 text-center">{open ? "▾" : "▸"}</span>
        </span>
      </button>
      {open && <div className="p-3 space-y-3 border-t border-slate-200 bg-white">{filterBody}</div>}
    </div>
  );
}

function defaultPredictInputs(opts?: PredictOptions | null): Record<string, string> {
  const out: Record<string, string> = {};
  for (const c of opts?.continuous ?? []) {
    const lo = c.min ?? 0;
    const hi = c.max ?? lo;
    out[c.name] = String(Math.round((lo + hi) / 2));
  }
  if (opts?.zone_types?.length) {
    out.zone_type = opts.zone_reference ?? opts.zone_types[0];
  }
  if (opts?.building_uses?.length) {
    out.building_use = opts.building_use_reference ?? opts.building_uses[0];
  }
  if (opts?.road_width_labels?.length) {
    out.road_width_label = opts.road_width_reference ?? opts.road_width_labels[0];
  }
  if (opts?.asset_types?.length) {
    out.predict_asset_type = opts.asset_type_reference ?? opts.asset_types[0];
  }
  if (opts?.region_leaves?.length) {
    out.region_leaf = opts.region_reference ?? opts.region_leaves[0];
  }
  return out;
}

function PredictPanel({
  regData,
  regBody,
  vars,
  assetType,
  regionLabel,
}: {
  regData: RegressionRunResponse;
  regBody: RegressionRunRequest;
  vars: RegressionVariableSpec;
  assetType: AssetType;
  regionLabel: string;
}) {
  const levels = useMemo(() => {
    const all = [regData.primary, ...regData.comparisons];
    return all.filter((l) => l.n >= 10 && l.coefficients.length > 0 && l.predict_options);
  }, [regData]);

  const [adminLevel, setAdminLevel] = useState<string>("sigungu");
  const selected = levels.find((l) => l.admin_level === adminLevel) ?? levels[0];
  const [inputs, setInputs] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!levels.length) return;
    const best = [...levels].sort((a, b) => b.n - a.n)[0];
    setAdminLevel(best.admin_level);
    setInputs(defaultPredictInputs(best.predict_options));
  }, [regData, levels]);

  useEffect(() => {
    if (!selected?.predict_options) return;
    setInputs(defaultPredictInputs(selected.predict_options));
  }, [adminLevel, selected?.predict_options]);

  const predictM = useMutation({ mutationFn: predictRegression });

  const aiPredictionContext = useMemo(() => {
    if (!predictM.data || !selected) return null;
    return buildBuiltPredictionContext(predictM.data, {
      regionLabel: selected.scope_label ?? regionLabel,
      assetType,
      regressionN: selected.n,
      adjR2: selected.adj_r_squared,
    });
  }, [predictM.data, selected, regionLabel, assetType]);

  if (!levels.length) return null;

  const opts = selected?.predict_options;

  const runPredict = () => {
    const body: RegressionPredictRequest = {
      ...regBody,
      admin_level: adminLevel as RegressionPredictRequest["admin_level"],
    };
    for (const c of opts?.continuous ?? []) {
      const raw = inputs[c.name];
      if (raw === "" || raw == null) return;
      body[c.name as keyof RegressionPredictRequest] = Number(raw) as never;
    }
    if (vars.zone_type_dummy && inputs.zone_type) body.zone_type = inputs.zone_type;
    if (vars.building_use_dummy && inputs.building_use) body.building_use = inputs.building_use;
    if (vars.road_width_dummy && inputs.road_width_label) body.road_width_label = inputs.road_width_label;
    if (vars.asset_type_dummy && inputs.predict_asset_type) body.predict_asset_type = inputs.predict_asset_type;
    if (vars.region_leaf_dummy && adminLevel === "eupmyeondong" && inputs.region_leaf) {
      body.region_leaf = inputs.region_leaf;
    }
    predictM.mutate(body);
  };

  return (
    <div className="card space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-sm">예측 계산</h2>
          <p className="text-xs text-slate-500 mt-1">
            탐색용 OLS — 개별 거래 95% 예측구간(PI). n이 작으면 구간이 매우 넓습니다.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {aiPredictionContext && <AiAssistantPanel context={aiPredictionContext} />}
          <button
            type="button"
            className="btn btn-primary shrink-0"
            onClick={runPredict}
            disabled={predictM.isPending}
          >
            {predictM.isPending ? "계산 중…" : "예측"}
          </button>
        </div>
      </div>

      <div className="flex flex-nowrap items-end gap-2 text-xs overflow-x-auto pb-0.5">
        <label className="space-y-1 shrink-0">
          <span className="text-slate-500 block whitespace-nowrap">scope</span>
          <select
            className="input !w-[11rem] py-1 text-xs"
            value={adminLevel}
            onChange={(e) => setAdminLevel(e.target.value)}
          >
            {levels.map((l) => (
              <option key={l.admin_level} value={l.admin_level}>
                {ADMIN_LABELS[l.admin_level] ?? l.admin_level} (n={l.n})
              </option>
            ))}
          </select>
        </label>

        {(opts?.continuous ?? []).map((c) => (
          <label key={c.name} className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap" title={c.min != null && c.max != null ? `${c.min}~${c.max}` : undefined}>
              {formatCoefName(c.name, assetType)}
            </span>
            <input
              className="input !w-[8.5rem] py-1 text-xs"
              type="number"
              title={c.min != null && c.max != null ? `${fmtNum(c.min, 0)}~${fmtNum(c.max, 0)}` : undefined}
              value={inputs[c.name] ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, [c.name]: e.target.value }))}
            />
          </label>
        ))}

        {vars.zone_type_dummy && (opts?.zone_types?.length ?? 0) > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">용도지역</span>
            <select
              className="input !w-[11rem] py-1 text-xs"
              value={inputs.zone_type ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, zone_type: e.target.value }))}
            >
              {opts!.zone_types.map((z) => (
                <option key={z} value={z}>
                  {z}
                  {z === opts!.zone_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.building_use_dummy && (opts?.building_uses?.length ?? 0) > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">
              {assetType === "detached" ? "주택유형" : "건축물용도"}
            </span>
            <select
              className="input !w-[11rem] py-1 text-xs"
              value={inputs.building_use ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, building_use: e.target.value }))}
            >
              {opts!.building_uses.map((u) => (
                <option key={u} value={u}>
                  {u}
                  {u === opts!.building_use_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.road_width_dummy && (opts?.road_width_labels?.length ?? 0) > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">도로조건</span>
            <select
              className="input !w-[11rem] py-1 text-xs"
              value={inputs.road_width_label ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, road_width_label: e.target.value }))}
            >
              {opts!.road_width_labels.map((u) => (
                <option key={u} value={u}>
                  {u}
                  {u === opts!.road_width_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.asset_type_dummy && (opts?.asset_types?.length ?? 0) > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">유형</span>
            <select
              className="input !w-[11rem] py-1 text-xs"
              value={inputs.predict_asset_type ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, predict_asset_type: e.target.value }))}
            >
              {opts!.asset_types.map((u) => (
                <option key={u} value={u}>
                  {ASSET_TYPE_LABELS[u] ?? u}
                  {u === opts!.asset_type_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {vars.region_leaf_dummy &&
          adminLevel === "eupmyeondong" &&
          (opts?.region_leaves?.length ?? 0) > 0 && (
          <label className="space-y-1 shrink-0">
            <span className="text-slate-500 block whitespace-nowrap">지역</span>
            <select
              className="input !w-[11rem] py-1 text-xs"
              value={inputs.region_leaf ?? ""}
              onChange={(e) => setInputs((prev) => ({ ...prev, region_leaf: e.target.value }))}
            >
              {(opts?.region_leaves ?? []).map((u) => (
                <option key={u} value={u}>
                  {u}
                  {u === opts?.region_reference ? " (기준)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {selected?.scope_label && (
        <p className="text-xs text-slate-500">모형: {selected.scope_label}</p>
      )}

      {predictM.isError && (
        <p className="text-sm text-red-600">{(predictM.error as Error).message ?? "예측 실패"}</p>
      )}

      {predictM.data && (
        <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 space-y-2 text-sm">
          <div>
            <span className="text-slate-500 text-xs">예상 금액</span>
            <div className="text-xl font-bold">{fmtNum(Math.round(predictM.data.y_hat))}만원</div>
          </div>
          <div className="text-xs space-y-1">
            <div>
              <span className="font-medium">95% 예측구간 (개별 거래)</span>{" "}
              {fmtNum(Math.round(predictM.data.pi_lower))} ~ {fmtNum(Math.round(predictM.data.pi_upper))}만원
            </div>
            <div className="text-slate-500">
              95% 평균 신뢰구간 {fmtNum(Math.round(predictM.data.ci_lower))} ~{" "}
              {fmtNum(Math.round(predictM.data.ci_upper))}만원
            </div>
          </div>
          {predictM.data.warnings.map((w: string) => (
            <p key={w} className="text-xs badge-warn">
              {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

const ASSET_LABELS: Record<AssetType, string> = {
  all: "통합(3유형)",
  commercial: "상업(일반상가)",
  factory: "공장창고",
  detached: "단독다가구",
};

const DEFAULT_VARS_BY_TYPE: Record<AssetType, RegressionVariableSpec> = {
  all: {
    gross_area: true,
    land_area: true,
    building_age: true,
    road_width_dummy: true,
    road_code: false,
    zone_type_dummy: true,
    building_use_dummy: true,
    asset_type_dummy: true,
    region_leaf_dummy: false,
  },
  commercial: {
    gross_area: true,
    land_area: true,
    building_age: true,
    road_width_dummy: true,
    road_code: false,
    zone_type_dummy: true,
    building_use_dummy: true,
    asset_type_dummy: false,
    region_leaf_dummy: false,
  },
  factory: {
    gross_area: true,
    land_area: true,
    building_age: true,
    road_width_dummy: true,
    road_code: false,
    zone_type_dummy: true,
    building_use_dummy: true,
    asset_type_dummy: false,
    region_leaf_dummy: false,
  },
  detached: {
    gross_area: true,
    land_area: true,
    building_age: true,
    road_width_dummy: true,
    road_code: false,
    zone_type_dummy: false,
    building_use_dummy: true,
    asset_type_dummy: false,
    region_leaf_dummy: false,
  },
};

function fmtNum(n?: number | null, digits = 0) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** e 표기 없이 고정 소수 — p값·계수 등 */
function fmtDecimal(n?: number | null, digits = 5) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

/** 회귀 계수 — 정수 */
function fmtCoefInt(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return Math.round(n).toLocaleString("ko-KR");
}

function ScatterMini({
  points,
  label,
  r,
}: {
  points: { x: number; y: number }[];
  label: string;
  r?: number | null;
}) {
  if (!points.length) return null;
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const pad = 8;
  const w = 220;
  const h = 120;
  const sx = (x: number) => pad + ((x - minX) / (maxX - minX || 1)) * (w - pad * 2);
  const sy = (y: number) => h - pad - ((y - minY) / (maxY - minY || 1)) * (h - pad * 2);

  return (
    <div className="card">
      <div className="text-xs font-semibold mb-1">
        {label} vs 금액 {r != null && <span className="text-slate-500">r={fmtDecimal(r, 5)}</span>}
      </div>
      <svg width={w} height={h} className="bg-slate-50 rounded border border-slate-100">
        {points.map((p, i) => (
          <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r={2} fill="#64748b" opacity={0.5} />
        ))}
      </svg>
    </div>
  );
}

function RegionChipPanel({
  title,
  hint,
  selected,
  options,
  formatLabel,
  onToggle,
  onSelectAll,
  onClear,
  compact = false,
  collapsible = false,
}: {
  title: string;
  hint: string;
  selected: string[];
  options: { id?: string; name: string; count: number }[];
  formatLabel?: (o: { name: string; count: number }) => string;
  onToggle: (name: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
  compact?: boolean;
  collapsible?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const label = formatLabel ?? ((o) => o.name);
  const summary =
    selected.length > 0
      ? `${selected.length}개 선택`
      : options.length
        ? `전체 · ${options.length}종`
        : "항목 없음";

  const chipArea = (
    <div className={clsx("flex flex-wrap gap-2 overflow-y-auto border border-slate-100 rounded p-2", compact ? "max-h-36" : "max-h-44")}>
      {options.map((o) => (
        <label
          key={o.id ?? o.name}
          className={clsx(
            "flex items-center gap-1.5 text-xs px-2 py-1 rounded border cursor-pointer",
            selected.includes(o.name)
              ? "bg-slate-800 text-white border-slate-800"
              : "bg-white text-slate-700 border-slate-200 hover:border-slate-400",
          )}
        >
          <input
            type="checkbox"
            className="sr-only"
            checked={selected.includes(o.name)}
            onChange={() => onToggle(o.name)}
          />
          {label(o)}
          <span className={clsx("opacity-70", selected.includes(o.name) && "text-slate-300")}>
            ({fmtNum(o.count)})
          </span>
        </label>
      ))}
      {options.length === 0 && <span className="text-xs text-slate-400">항목 없음</span>}
    </div>
  );

  if (collapsible) {
    return (
      <div className="border border-slate-200 rounded-lg overflow-hidden">
        <button
          type="button"
          className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-xs bg-slate-50 hover:bg-slate-100 transition-colors"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          <span className="font-medium text-slate-800">{title}</span>
          <span className="text-slate-500 shrink-0">
            {summary}
            <span className="ml-1.5 inline-block w-3 text-center">{open ? "▾" : "▸"}</span>
          </span>
        </button>
        {open && (
          <div className="p-2 space-y-2 border-t border-slate-200 bg-white">
            <p className="text-xs text-slate-500">{hint}</p>
            <div className="flex gap-2">
              <button type="button" className="btn btn-ghost text-xs" onClick={onSelectAll} disabled={!options.length}>
                전체 선택
              </button>
              <button type="button" className="btn btn-ghost text-xs" onClick={onClear} disabled={!selected.length}>
                선택 해제
              </button>
            </div>
            {chipArea}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={compact ? "space-y-2" : "card space-y-2"}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <h2 className="font-semibold text-sm">
          {title}{" "}
          <span className="text-slate-500 font-normal">({selected.length}개 선택)</span>
        </h2>
        <div className="flex gap-2">
          <button type="button" className="btn btn-ghost" onClick={onSelectAll} disabled={!options.length}>
            전체 선택
          </button>
          <button type="button" className="btn btn-ghost" onClick={onClear} disabled={!selected.length}>
            선택 해제
          </button>
        </div>
      </div>
      <p className="text-xs text-slate-500 mb-2">{hint}</p>
      {chipArea}
    </div>
  );
}

function levelCardTitle(result: RegressionLevelResult): string {
  const sl = result.scope_label?.trim();
  if (!sl) return ADMIN_LABELS[result.admin_level] ?? result.admin_level;
  if (sl.endsWith(" 시군구")) return sl.slice(0, -" 시군구".length);
  if (sl.endsWith(" 읍면동")) return sl.slice(0, -" 읍면동".length);
  if (sl.endsWith(" 읍·면")) return sl.slice(0, -" 읍·면".length);
  return sl;
}

function LevelCard({ result, assetType }: { result: RegressionLevelResult; assetType: AssetType }) {
  return (
    <div className="card space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold text-sm">{levelCardTitle(result)}</h3>
          <p className="text-xs text-slate-500 mt-0.5">{ADMIN_LABELS[result.admin_level] ?? result.admin_level}</p>
        </div>
        <span className="text-xs text-slate-500">n={fmtNum(result.n)}</span>
      </div>
      {result.warning && <p className="text-xs badge-warn">{result.warning}</p>}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>R² {fmtDecimal(result.r_squared, 5)}</div>
        <div>Adj R² {fmtDecimal(result.adj_r_squared, 5)}</div>
        <div title="in-sample · 금액(만원) 원척도">
          MAPE {result.mape != null ? `${fmtDecimal(result.mape, 2)}%` : "—"}
        </div>
        <div>유의 변수 {result.significant_count}개</div>
        <div>F p {fmtDecimal(result.f_p_value, 5)}</div>
      </div>
      {result.coefficients.length > 0 && (
        <div className="table-wrap max-h-48">
          <table className="data w-full">
            <thead>
              <tr>
                <th>변수</th>
                <th>계수</th>
                <th>SE</th>
                <th>t</th>
                <th>p</th>
              </tr>
            </thead>
            <tbody>
              {result.coefficients.map((c) => (
                <tr key={c.name}>
                  <td>{formatCoefName(c.name, assetType)}</td>
                  <td>{fmtCoefInt(c.estimate)}</td>
                  <td>{fmtCoefInt(c.std_err)}</td>
                  <td>{fmtDecimal(c.t_value, 2)}</td>
                  <td className={clsx(c.p_value != null && c.p_value < 0.05 && "badge-sig")}>
                    {fmtDecimal(c.p_value, 5)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(result.vif?.length ?? 0) > 0 && (
        <div className="text-xs space-y-1">
          <div className="font-semibold text-slate-600">다중공선성 (VIF · 연속변수)</div>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {result.vif!.map((v) => (
              <span
                key={v.name}
                className={clsx(
                  v.vif != null && v.vif >= 10 && "text-red-600 font-medium",
                  v.vif != null && v.vif >= 5 && v.vif < 10 && "text-amber-700",
                )}
              >
                {formatCoefName(v.name, assetType)} {v.vif != null ? fmtDecimal(v.vif, 2) : "—"}
              </span>
            ))}
          </div>
          <p className="text-slate-400">VIF≥10 주의 · ≥5 참고</p>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [assetType, setAssetType] = useState<AssetType>("commercial");
  const [addr1, setAddr1] = useState("");
  const [addr2, setAddr2] = useState("");
  const [guList, setGuList] = useState<string[]>([]);
  const [leafList, setLeafList] = useState<string[]>([]);
  const [riList, setRiList] = useState<RiPick[]>([]);
  const [yearFrom, setYearFrom] = useState<number | "">("");
  const [yearTo, setYearTo] = useState<number | "">("");
  const [txModalOpen, setTxModalOpen] = useState(false);
  const [vars, setVars] = useState<RegressionVariableSpec>(DEFAULT_VARS_BY_TYPE.commercial);
  const [excludeOutliers, setExcludeOutliers] = useState(false);
  const [iqrMultiplier, setIqrMultiplier] = useState<IqrMultiplier>(3);
  const [sampleFilter, setSampleFilter] = useState<SampleFilterState>(EMPTY_SAMPLE_FILTER);
  const [useRollingWindow, setUseRollingWindow] = useState(true);
  const [windowYears, setWindowYears] = useState<3 | 5>(3);
  const [responseScale, setResponseScale] = useState<ResponseScale>("linear");

  const metaQ = useQuery({
    queryKey: ["built-meta"],
    queryFn: fetchFilterMeta,
    retry: 2,
    staleTime: 60_000,
  });
  const asOfMonth = metaQ.data?.as_of_month ?? undefined;

  useEffect(() => {
    setVars(DEFAULT_VARS_BY_TYPE[assetType]);
    setSampleFilter(EMPTY_SAMPLE_FILTER);
  }, [assetType]);

  useEffect(() => {
    setSampleFilter(EMPTY_SAMPLE_FILTER);
  }, [addr1, addr2, guList, leafList, riList, yearFrom, yearTo, useRollingWindow, windowYears]);

  useEffect(() => {
    if (leafList.length < 2) {
      setVars((v) => (v.region_leaf_dummy ? { ...v, region_leaf_dummy: false } : v));
    }
  }, [leafList.length]);

  const rollingParams = useMemo(
    () =>
      useRollingWindow && asOfMonth
        ? { as_of_month: asOfMonth, window_years: windowYears }
        : {},
    [useRollingWindow, asOfMonth, windowYears],
  );
  const sampleApiParams = useMemo(() => sampleFilterToApi(sampleFilter), [sampleFilter]);
  const regionChipScopeParams = useMemo(
    () => ({
      contract_year_from: yearFrom === "" ? undefined : yearFrom,
      contract_year_to: yearTo === "" ? undefined : yearTo,
      ...rollingParams,
      ...sampleApiParams,
    }),
    [yearFrom, yearTo, rollingParams, sampleApiParams],
  );
  const addr2Q = useQuery({
    queryKey: ["addr2", addr1, assetType],
    queryFn: () => fetchAddr2(addr1, assetType),
    enabled: !!addr1,
  });

  useEffect(() => {
    if (!addr1 || addr2) return;
    const opts = addr2Q.data ?? [];
    if (opts.length === 1 && isFlatSidoAddr2(opts[0])) {
      setAddr2(opts[0]!);
    }
  }, [addr1, addr2, addr2Q.data]);
  const structureQ = useQuery({
    queryKey: ["region-structure", addr1, addr2, assetType],
    queryFn: () => fetchRegionStructure(addr1, addr2, assetType),
    enabled: !!addr1 && !!addr2,
  });
  const hasIntermediate = structureQ.data?.has_intermediate ?? false;
  const intermediateLabel = structureQ.data?.intermediate_label ?? "구";
  const leafLevel = structureQ.data?.leaf_level ?? "addr3";
  const useAddr4Leaf = leafLevel === "addr4";

  const guQ = useQuery({
    queryKey: ["gu", addr1, addr2, assetType, regionChipScopeParams],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType, regionChipScopeParams),
    enabled: !!addr1 && !!addr2 && useAddr4Leaf,
  });

  const flatLeafQ = useQuery({
    queryKey: ["flat-leaf", addr1, addr2, assetType, regionChipScopeParams],
    queryFn: () => fetchAddr3WithCounts(addr1, addr2, assetType, regionChipScopeParams),
    enabled: !!addr1 && !!addr2 && !useAddr4Leaf,
  });

  const leafQ = useQuery({
    queryKey: ["leaf", addr1, addr2, assetType, guList, regionChipScopeParams],
    queryFn: () => fetchLeafRegions(addr1, addr2, guList, assetType, regionChipScopeParams),
    enabled: !!addr1 && !!addr2 && useAddr4Leaf,
  });

  const riQ = useQuery({
    queryKey: ["ri", addr1, addr2, assetType, leafLevel, guList, leafList, regionChipScopeParams],
    queryFn: () =>
      fetchRiRegions(addr1, addr2, {
        leafLevel,
        addr3List: useAddr4Leaf ? (guList.length ? guList : undefined) : leafList,
        addr4List: useAddr4Leaf ? leafList : undefined,
        assetType,
        scope: regionChipScopeParams,
      }),
    enabled: !!addr1 && !!addr2 && leafList.length > 0 && structureQ.isSuccess,
  });

  const visibleLeafOptions = useMemo(() => {
    if (!useAddr4Leaf) {
      return (flatLeafQ.data ?? []).map((o: Addr3Option) => ({ ...o, id: o.name, parent: null }));
    }
    const opts = leafQ.data ?? [];
    const filtered = !guList.length ? opts : opts.filter((o) => o.parent && guList.includes(o.parent));
    return filtered.map((o) => ({ ...o, id: `${o.parent ?? ""}|${o.name}` }));
  }, [useAddr4Leaf, flatLeafQ.data, leafQ.data, guList]);

  useEffect(() => {
    if (!useAddr4Leaf) return;
    const allowed = new Set(visibleLeafOptions.map((o) => o.name));
    setLeafList((prev) => prev.filter((n) => allowed.has(n)));
  }, [useAddr4Leaf, visibleLeafOptions]);

  useEffect(() => {
    const allowed = new Set(
      (riQ.data ?? [])
        .filter((o) => o.parent)
        .map((o) => `${o.parent}|${o.name}`),
    );
    setRiList((prev) => prev.filter((p) => allowed.has(riKey(p))));
  }, [riQ.data]);

  useEffect(() => {
    if (!leafList.length) setRiList([]);
  }, [leafList]);

  const toggleGu = (name: string) => {
    setGuList((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]));
  };

  const toggleLeaf = (name: string) => {
    setLeafList((prev) => (prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]));
  };

  const toggleRi = (pick: RiPick) => {
    const key = riKey(pick);
    setRiList((prev) =>
      prev.some((p) => riKey(p) === key) ? prev.filter((p) => riKey(p) !== key) : [...prev, pick],
    );
  };

  const regressionMode = useMemo(() => {
    if (riList.length > 0) return "three_way" as const;
    if (leafList.length > 0) return "two_way" as const;
    return "sigungu_only" as const;
  }, [riList.length, leafList.length]);

  const inferredGuList = useMemo(() => {
    const fromParent = visibleLeafOptions
      .filter((o) => leafList.includes(o.name) && o.parent)
      .map((o) => o.parent as string);
    return [...new Set([...guList, ...fromParent])];
  }, [guList, leafList, visibleLeafOptions]);

  const regionFilterParams = useMemo(() => {
    const addr4Mode = useAddr4Leaf || inferredGuList.length > 0;
    if (addr4Mode) {
      return {
        leaf_level: "addr4" as const,
        addr3_list: inferredGuList.length ? inferredGuList : undefined,
        addr4_list: leafList.length ? leafList : undefined,
      };
    }
    return {
      leaf_level: "addr3" as const,
      addr3_list: leafList.length ? leafList : undefined,
    };
  }, [useAddr4Leaf, inferredGuList, leafList]);

  const scopeBaseParams = useMemo(
    () => ({
      asset_type: assetType,
      addr1: addr1 || undefined,
      addr2: addr2 || undefined,
      ...regionFilterParams,
      ri_pick: riList.length ? riList.map(riKey) : undefined,
      contract_year_from: yearFrom === "" ? undefined : yearFrom,
      contract_year_to: yearTo === "" ? undefined : yearTo,
      ...rollingParams,
    }),
    [assetType, addr1, addr2, regionFilterParams, riList, yearFrom, yearTo, rollingParams],
  );

  const scopeFilterQ = useQuery({
    queryKey: ["scope-filters", scopeBaseParams],
    queryFn: () =>
      fetchScopeSampleFilters({
        asset_type: scopeBaseParams.asset_type,
        addr1: scopeBaseParams.addr1,
        addr2: scopeBaseParams.addr2,
        addr3_list: scopeBaseParams.addr3_list,
        addr4_list: scopeBaseParams.addr4_list,
        ri_pick: scopeBaseParams.ri_pick,
        contract_year_from: scopeBaseParams.contract_year_from,
        contract_year_to: scopeBaseParams.contract_year_to,
        as_of_month: scopeBaseParams.as_of_month,
        window_years: scopeBaseParams.window_years,
      }),
  });

  const txExportParams = useMemo(
    () => ({
      ...scopeBaseParams,
      ...sampleApiParams,
    }),
    [scopeBaseParams, sampleApiParams],
  );

  const txCountQ = useQuery({
    queryKey: ["built-tx-count", txExportParams],
    queryFn: () => fetchTransactions({ ...txExportParams, page: 1, page_size: 1 }),
  });

  const regBody: RegressionRunRequest = useMemo(
    () => ({
      asset_type: assetType,
      addr1: addr1 || undefined,
      addr2: addr2 || undefined,
      ...regionFilterParams,
      ri_list: riList.length ? riList : undefined,
      contract_year_from: yearFrom === "" ? undefined : yearFrom,
      contract_year_to: yearTo === "" ? undefined : yearTo,
      ...rollingParams,
      ...sampleApiParams,
      variables: vars,
      response_scale: responseScale,
      exclude_outliers_iqr: excludeOutliers,
      outlier_iqr_multiplier: iqrMultiplier,
    }),
    [
      assetType,
      addr1,
      addr2,
      regionFilterParams,
      riList,
      yearFrom,
      yearTo,
      rollingParams,
      sampleApiParams,
      vars,
      responseScale,
      excludeOutliers,
      iqrMultiplier,
    ],
  );

  const regM = useMutation({ mutationFn: runRegression });

  const aiRegionLabel = useMemo(() => {
    if (regM.data?.primary?.scope_label) return regM.data.primary.scope_label;
    const parts = [addr1, formatScopeAddr2(addr2, addr1), ...guList, ...leafList].filter(Boolean);
    return parts.join(" ") || "선택 지역";
  }, [regM.data, addr1, addr2, guList, leafList]);

  const aiRegressionContext = useMemo(() => {
    if (!regM.data) return null;
    return buildBuiltRegressionContext(regM.data, {
      regionLabel: aiRegionLabel,
      assetType,
    });
  }, [regM.data, aiRegionLabel, assetType]);

  const addr2ScopeLabel = formatScopeAddr2(addr2, addr1) || addr1;

  const regressionSummaryText = useMemo(() => {
    if (regressionMode === "sigungu_only") {
      return addr2 ? `${addr2ScopeLabel} 시군구 단일 회귀` : "시군구 단일 회귀";
    }
    if (regressionMode === "two_way") {
      if (regM.data?.comparisons.length) {
        const upper = levelCardTitle(regM.data.primary);
        const lower = regM.data.comparisons[0]
          ? levelCardTitle(regM.data.comparisons[0])
          : `선택 읍·면·동 ${leafList.length}개`;
        return `2-way: ${upper} vs ${lower}`;
      }
      if (useAddr4Leaf || inferredGuList.length > 0) {
        const guHint =
          inferredGuList.length > 0
            ? inferredGuList.join(", ")
            : guList.length
              ? guList.join(", ")
              : "선택 동 상위";
        return `2-way: ${intermediateLabel}(${guHint}) vs 선택 읍·면·동 ${leafList.length}개`;
      }
      return `2-way: 시군구(${addr2ScopeLabel}) vs 선택 읍·면·동 ${leafList.length}개`;
    }
    if (regressionMode === "three_way") {
      const topLabel =
        regM.data?.primary?.scope_label && useAddr4Leaf
          ? `${intermediateLabel} · ${regM.data.primary.scope_label}`
          : useAddr4Leaf
            ? intermediateLabel
            : "시군구";
      return `3-way: ${topLabel} · 상위 읍·면(${[...new Set(riList.map((p) => p.eup))].join(", ")}) · 리 ${riList.length}개`;
    }
    return "";
  }, [
    regressionMode,
    addr2,
    addr2ScopeLabel,
    useAddr4Leaf,
    inferredGuList,
    intermediateLabel,
    guList,
    leafList.length,
    riList,
    regM.data,
  ]);

  const years = metaQ.data?.contract_years ?? [];

  const txModalSummary = useMemo(() => {
    const parts = [ASSET_LABELS[assetType]];
    if (addr1) parts.push(addr1);
    if (addr2) parts.push(formatScopeAddr2(addr2, addr1));
    if (useRollingWindow && asOfMonth) parts.push(`롤링 ${windowYears}년 · ${asOfMonth}`);
    return parts.join(" · ");
  }, [assetType, addr1, addr2, useRollingWindow, asOfMonth, windowYears]);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className="bg-slate-900 text-white px-6 py-4 shrink-0">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs text-slate-400 mb-1">
              <a href="/" className="hover:text-white">
                CH2 Macro
              </a>
              {" · "}
              <a href="/land/" className="hover:text-white">
                토지
              </a>
              {" · 복합부동산"}
              <span className="ml-2 text-amber-300/90 text-[10px] font-medium uppercase tracking-wide">
                beta
              </span>
            </p>
            <h1 className="text-lg font-bold">복합부동산 통계</h1>
            <p className="text-sm text-slate-300 mt-1">
              상업·공장·단독다가구 일반(非집합) — 거래 탐색·OLS 회귀 ·{" "}
              <a href="/collective/commercial/" className="underline hover:text-white">
                집합상가·공장
              </a>
              은 별도
            </p>
          </div>
        </div>
      </header>

      <main className="flex flex-1 min-h-0 overflow-hidden">
        {/* 왼쪽: 유형·지역·표본 필터 */}
        <aside className="layout-sidebar p-4 space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-800 mb-3">유형 · 지역</h2>
            {metaQ.isError && (
              <div className="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
                <p>지역·연도 목록을 불러오지 못했습니다. 새로고침(Ctrl+Shift+R) 후 다시 시도해 주세요.</p>
                <button
                  type="button"
                  className="mt-1 underline"
                  onClick={() => metaQ.refetch()}
                >
                  다시 불러오기
                </button>
              </div>
            )}
            {metaQ.isLoading && !metaQ.data && (
              <p className="mb-3 text-xs text-slate-500">지역 목록 불러오는 중…</p>
            )}
            <div className="space-y-3">
              <label className="text-xs space-y-1 block">
                <span className="text-slate-500">유형</span>
                <select
                  className="input"
                  value={assetType}
                  onChange={(e) => {
                    setAssetType(e.target.value as AssetType);
                  }}
                >
                  {(metaQ.data?.asset_types ?? (Object.keys(ASSET_LABELS) as AssetType[])).map((t) => (
                    <option key={t} value={t}>
                      {ASSET_LABELS[t as AssetType] ?? t}
                    </option>
                  ))}
                </select>
              </label>
              <div className="space-y-2 rounded border border-slate-200 p-2">
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={useRollingWindow}
                    onChange={(e) => {
                      setUseRollingWindow(e.target.checked);
                    }}
                  />
                  <span>롤링 창 (contract_date)</span>
                </label>
                {useRollingWindow && (
                  <div className="flex gap-2 text-xs">
                    <label className="flex items-center gap-1">
                      <input
                        type="radio"
                        name="window-years"
                        checked={windowYears === 3}
                        onChange={() => {
                          setWindowYears(3);
                        }}
                      />
                      3년
                    </label>
                    <label className="flex items-center gap-1">
                      <input
                        type="radio"
                        name="window-years"
                        checked={windowYears === 5}
                        onChange={() => {
                          setWindowYears(5);
                        }}
                      />
                      5년
                    </label>
                    {asOfMonth && (
                      <span className="text-slate-500 ml-auto">기준 {asOfMonth}</span>
                    )}
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <label className="text-xs space-y-1 block">
                  <span className="text-slate-500">연도(from)</span>
                  <select
                    className="input"
                    value={yearFrom}
                    onChange={(e) => setYearFrom(e.target.value ? Number(e.target.value) : "")}
                  >
                    <option value="">—</option>
                    {years.map((y: number) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs space-y-1 block">
                  <span className="text-slate-500">연도(to)</span>
                  <select
                    className="input"
                    value={yearTo}
                    onChange={(e) => setYearTo(e.target.value ? Number(e.target.value) : "")}
                  >
                    <option value="">—</option>
                    {years.map((y: number) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="text-xs space-y-1 block">
                <span className="text-slate-500">시도</span>
                <select
                  className="input"
                  value={addr1}
                  disabled={metaQ.isLoading && !metaQ.data}
                  onChange={(e) => {
                    setAddr1(e.target.value);
                    setAddr2("");
                    setGuList([]);
                    setLeafList([]);
                    setRiList([]);
                  }}
                >
                  <option value="">전국</option>
                  {(metaQ.data?.addr1_list ?? []).map((a: string) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
                {metaQ.isLoading && !metaQ.data && (
                  <span className="text-slate-400 text-[11px]">시도 목록 불러오는 중…</span>
                )}
                {metaQ.isSuccess && !(metaQ.data?.addr1_list?.length) && (
                  <span className="text-amber-700 text-[11px]">시도 목록이 비어 있습니다.</span>
                )}
              </label>
              <label className="text-xs space-y-1 block">
                <span className="text-slate-500">시군구</span>
                <select
                  className="input"
                  value={addr2}
                  disabled={!addr1}
                  onChange={(e) => {
                    setAddr2(e.target.value);
                    setGuList([]);
                    setLeafList([]);
                    setRiList([]);
                  }}
                >
                  <option value="">전체</option>
                  {(addr2Q.data ?? []).map((a) => (
                    <option key={a} value={a}>
                      {formatAddr2OptionLabel(a)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {addr2 && hasIntermediate && (
            <RegionChipPanel
              compact
              title={`${intermediateLabel} 선택`}
              hint={`미선택 시 ${addr2ScopeLabel} 전체.`}
              selected={guList}
              options={guQ.data ?? []}
              onToggle={toggleGu}
              onSelectAll={() => {
                setGuList((guQ.data ?? []).map((o) => o.name));
              }}
              onClear={() => {
                setGuList([]);
              }}
            />
          )}

          {addr2 && (
            <RegionChipPanel
              compact
              title="읍면동 선택"
              hint={
                structureQ.isLoading
                  ? "지역 구조 확인 중…"
                  : hasIntermediate
                    ? `${intermediateLabel} 선택 후 좁힐 수 있습니다.`
                    : `미선택 시 ${addr2ScopeLabel} 전체.`
              }
              selected={leafList}
              options={visibleLeafOptions}
              formatLabel={(o) => {
                const parent = (o as RegionOption).parent;
                return parent ? `${parent} · ${o.name}` : o.name;
              }}
              onToggle={toggleLeaf}
              onSelectAll={() => {
                setLeafList(visibleLeafOptions.map((o) => o.name));
              }}
              onClear={() => {
                setLeafList([]);
                setRiList([]);
              }}
            />
          )}

          {addr2 && !structureQ.isLoading && structureQ.isError && (
            <p className="text-xs text-red-600">읍·면·동 목록을 불러오지 못했습니다.</p>
          )}

          {addr2 && (flatLeafQ.isLoading || leafQ.isLoading) && !visibleLeafOptions.length && (
            <p className="text-xs text-slate-400">읍·면·동 목록 불러오는 중…</p>
          )}

          {addr2 && leafList.length > 0 && (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold text-sm">
                  법정리 선택{" "}
                  <span className="text-slate-500 font-normal">({riList.length}개 선택)</span>
                </h2>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={!(riQ.data ?? []).length}
                    onClick={() => {
                      setRiList(
                        (riQ.data ?? [])
                          .filter((o) => o.parent)
                          .map((o) => ({ eup: o.parent!, ri: o.name })),
                      );
                    }}
                  >
                    전체 선택
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={!riList.length}
                    onClick={() => {
                      setRiList([]);
                    }}
                  >
                    선택 해제
                  </button>
                </div>
              </div>
              <p className="text-xs text-slate-500">
                미선택 시 읍·면·동 단위 2-way 비교. 리 선택 시 3-way(시군구 · 상위 읍·면 · 리).
              </p>
              <div className="flex flex-wrap gap-2 overflow-y-auto border border-slate-100 rounded p-2 max-h-36">
                {(riQ.data ?? []).map((o) => {
                  const pick: RiPick = { eup: o.parent ?? "", ri: o.name };
                  const selected = riList.some((p) => riKey(p) === riKey(pick));
                  return (
                    <label
                      key={riKey(pick)}
                      className={clsx(
                        "flex items-center gap-1.5 text-xs px-2 py-1 rounded border cursor-pointer",
                        selected
                          ? "bg-slate-800 text-white border-slate-800"
                          : "bg-white text-slate-700 border-slate-200 hover:border-slate-400",
                      )}
                    >
                      <input
                        type="checkbox"
                        className="sr-only"
                        checked={selected}
                        onChange={() => toggleRi(pick)}
                      />
                      {o.parent ? `${o.parent} · ${o.name}` : o.name}
                      <span className={clsx("opacity-70", selected && "text-slate-300")}>
                        ({fmtNum(o.count)})
                      </span>
                    </label>
                  );
                })}
                {riQ.isLoading && <span className="text-xs text-slate-400">불러오는 중…</span>}
                {!riQ.isLoading && !(riQ.data ?? []).length && (
                  <span className="text-xs text-slate-400">하위 리 없음</span>
                )}
              </div>
            </div>
          )}

          <div className="border-t border-slate-200 pt-4">
            <SampleFilterPanel
              assetType={assetType}
              scope={scopeFilterQ.data}
              sample={sampleFilter}
              onChange={(next) => {
                setSampleFilter(next);
              }}
              filteredTotal={txCountQ.data?.total}
            />
            {scopeFilterQ.isLoading && (
              <p className="text-xs text-slate-400 mt-2">필터 옵션 불러오는 중…</p>
            )}
          </div>
        </aside>

        {/* 오른쪽: 회귀 분석 */}
        <div className="layout-main">
          <section className="px-4 py-4 pb-8 shrink-0">
            <div className="card space-y-2">
              <div className="flex items-start justify-between gap-3 sticky top-0 bg-white z-10 py-1 -mx-1 px-1">
                <div className="min-w-0">
                  <h2 className="font-semibold text-sm">회귀 실험 (종속: 금액 만원)</h2>
                  <p className="text-xs text-slate-500 mt-1">{regressionSummaryText}</p>
                </div>
                <div className="flex flex-wrap gap-2 shrink-0">
                  {regM.data && aiRegressionContext && (
                    <AiAssistantPanel context={aiRegressionContext} />
                  )}
                  <button
                    type="button"
                    className="btn btn-ghost shrink-0"
                    onClick={() => setTxModalOpen(true)}
                  >
                    거래목록
                    {txCountQ.data?.total != null && (
                      <span className="ml-1 text-slate-500 font-normal">
                        ({fmtNum(txCountQ.data.total)})
                      </span>
                    )}
                  </button>
                  <button
                    className="btn btn-primary shrink-0"
                    onClick={() => regM.mutate(regBody)}
                    disabled={
                      regM.isPending || (!!addr2 && leafList.length > 0 && !structureQ.isSuccess)
                    }
                    title={
                      !!addr2 && leafList.length > 0 && !structureQ.isSuccess
                        ? "지역 구조 확인 중… 잠시 후 다시 시도하세요."
                        : undefined
                    }
                  >
                    {regM.isPending ? "계산 중…" : "통계분석"}
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs">
                {(
                  [
                    ["gross_area", "연면적"],
                    ["land_area", "대지면적"],
                    ["building_age", "연식"],
                    ["road_width_dummy", "도로조건 더미"],
                    ...(assetType !== "detached"
                      ? ([["zone_type_dummy", "용도지역 더미"]] as const)
                      : []),
                    [
                      "building_use_dummy",
                      assetType === "detached" ? "주택유형 더미" : "건축물용도 더미",
                    ],
                    ...(assetType === "all" ? ([["asset_type_dummy", "유형 더미"]] as const) : []),
                    ...(leafList.length >= 2
                      ? ([["region_leaf_dummy", "지역(읍·면·동) 더미"]] as const)
                      : []),
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      checked={vars[key as keyof RegressionVariableSpec]}
                      onChange={(e) =>
                        setVars((v) => ({ ...v, [key]: e.target.checked }))
                      }
                    />
                    {label}
                  </label>
                ))}
                {vars.region_leaf_dummy && (
                  <span className="text-slate-500 w-full">
                    읍·면·동 풀링 회귀(하위 scope)에만 적용. 시군구·구 단일 회귀에는 넣지 않습니다.
                  </span>
                )}
                <label className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={responseScale === "log"}
                    onChange={(e) => setResponseScale(e.target.checked ? "log" : "linear")}
                  />
                  log(금액) semi-log
                </label>
                <label className="flex items-center gap-1">
                  <input type="checkbox" checked={excludeOutliers} onChange={(e) => setExcludeOutliers(e.target.checked)} />
                  IQR 금액 이상치 제외
                </label>
                {excludeOutliers &&
                  ([1.5, 2, 3] as const).map((k) => (
                    <label key={k} className="flex items-center gap-1">
                      <input
                        type="radio"
                        name="iqr-k"
                        checked={iqrMultiplier === k}
                        onChange={() => setIqrMultiplier(k)}
                      />
                      IQR×{k}
                    </label>
                  ))}
              </div>
              {regM.isError && (
                <p className="text-sm text-red-600">{(regM.error as Error).message ?? "회귀 실패"}</p>
              )}
              {regM.data && (
                <div className="space-y-2 pt-1">
                  <div
                    className={clsx(
                      "grid gap-2",
                      regressionMode === "sigungu_only" && "md:grid-cols-1",
                      regressionMode === "two_way" && "md:grid-cols-2",
                      regressionMode === "three_way" && "md:grid-cols-3",
                    )}
                  >
                    <LevelCard result={regM.data.primary} assetType={assetType} />
                    {regM.data.comparisons.map((c: RegressionLevelResult, i: number) => (
                      <LevelCard key={`${c.admin_level}-${i}`} result={c} assetType={assetType} />
                    ))}
                  </div>
                  {regM.data.correlations.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs text-slate-500">
                        상관·산점도 —{" "}
                        {ADMIN_LABELS[regM.data.correlation_admin_level ?? "sigungu"]}
                        {regM.data.correlation_scope_label
                          ? ` · ${regM.data.correlation_scope_label}`
                          : ""}
                        {regM.data.correlation_n != null ? ` (n=${fmtNum(regM.data.correlation_n)})` : ""}
                      </p>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {regM.data.correlations.map((s: CorrelationSeries) => (
                          <ScatterMini key={s.variable} points={s.points} label={s.label} r={s.pearson_r} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>

          {regM.data && (
            <section className="px-4 pb-4 pt-0">
              <PredictPanel
                regData={regM.data}
                regBody={regBody}
                vars={vars}
                assetType={assetType}
                regionLabel={aiRegionLabel}
              />
            </section>
          )}
        </div>
      </main>

      <BuiltTransactionListModal
        open={txModalOpen}
        onClose={() => setTxModalOpen(false)}
        assetType={assetType}
        exportParams={txExportParams}
        summary={txModalSummary}
      />
    </div>
  );
}
