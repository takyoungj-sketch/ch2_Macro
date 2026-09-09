import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import {
  predictRegionalRegression,
  runRegionalRegression,
  type FunnelStep,
  type RegionalRegressionPredictInputs,
  type RegionalRegressionRunRequest,
  type RegionalRegressionVariables,
  type SampleBreakdown,
  type FittedBuildingRow,
  type NewBuildAge0Gap,
} from "../api/regionalRegressionClient";
import type { StatsWindowYears } from "./StatsWindowToggle";
import CollectiveRegressionEquation from "./CollectiveRegressionEquation";
import DraggableModalShell from "./DraggableModalShell";
import {
  ESTIMATE_COPY,
  MetricWithHelp,
  StatisticalEstimateCaption,
  StatisticalEstimateDisclaimer,
  StatisticalEstimateRangeRow,
} from "@ch2/stats-glossary";
import { ASSET_LABELS } from "../types";
import { parseResidentialAssetKinds } from "../utils/residentialAssetTypes";

type Props = {
  addr1: string;
  addr2: string;
  hasIntermediate: boolean;
  guList: string[];
  leafList: string[];
  regionCodes?: string[];
  regionCodeLevel?: "eupmyeondong" | "beopjungri";
  regionAddrs?: string[];
  windowYears: StatsWindowYears;
  assetType: string;
  onClose: () => void;
};

function regressionKinds(assetType: string) {
  return parseResidentialAssetKinds(assetType).filter((k) => k !== "presale");
}

const VIRTUAL_KEY = "__virtual__";

function emptyPredictInputs(): RegionalRegressionPredictInputs {
  return {};
}

function inputsFromFitted(row: FittedBuildingRow): RegionalRegressionPredictInputs {
  return {
    households: row.households ?? undefined,
    max_floor: row.max_floor ?? undefined,
    building_age: row.building_age ?? undefined,
    parking_per_household: row.parking_per_household ?? undefined,
    assessed_land_price: row.assessed_land_price ?? undefined,
    asset_type: row.asset_type ?? undefined,
    structure_group: row.structure_group ?? undefined,
    builder_group: row.builder_group ?? undefined,
  };
}

const CORE_VARS: Array<[keyof RegionalRegressionVariables, string]> = [
  ["households", "세대수"],
  ["max_floor", "최고층"],
  ["building_age", "연식"],
  ["parking", "세대당 주차"],
];
const WEAK_VARS: Array<[keyof RegionalRegressionVariables, string, string]> = [
  ["structure", "구조", "결측은 미상 더미 · 실측에서 예측 개선 없음"],
  ["builder", "시공사", "결측은 미상 더미 · 단지를 빼지 않음"],
];
const LAND_VAR: [keyof RegionalRegressionVariables, string] = [
  "assessed_land_price",
  "개별공시지가",
];

const MIN_TX_OPTIONS = [5, 3, 2] as const;
type MinTx = (typeof MIN_TX_OPTIONS)[number];

const VAR_DROP_TO_KEY: Record<string, keyof RegionalRegressionVariables> = {
  households_flag: "households",
  households_missing: "households",
  max_floor_flag: "max_floor",
  max_floor_missing: "max_floor",
  building_age_missing: "building_age",
  parking_flag: "parking",
  parking_missing: "parking",
  assessed_land_price_missing: "assessed_land_price",
};

const VAR_KEY_LABEL: Partial<Record<keyof RegionalRegressionVariables, string>> = {
  households: "세대수",
  max_floor: "최고층",
  building_age: "연식",
  parking: "세대당 주차",
  assessed_land_price: "개별공시지가",
};

function funnelStep(sample: SampleBreakdown, code: string): FunnelStep | undefined {
  return (sample.funnel ?? []).find((s) => s.code === code);
}

function missingVarsStillOn(
  vars: RegionalRegressionVariables,
  sample: SampleBreakdown,
): Array<keyof RegionalRegressionVariables> {
  const step = funnelStep(sample, "var_drop");
  if (!step?.n) return [];
  const keys = new Set<keyof RegionalRegressionVariables>();
  for (const r of step.reasons) {
    const k = VAR_DROP_TO_KEY[r.code];
    if (k && vars[k]) keys.add(k);
  }
  return [...keys];
}

function turnOffVars(
  vars: RegionalRegressionVariables,
  keys: Array<keyof RegionalRegressionVariables>,
): RegionalRegressionVariables {
  return { ...vars, ...Object.fromEntries(keys.map((k) => [k, false])) };
}

function fmt(n: number | null | undefined, d = 2) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR", { maximumFractionDigits: d });
}

function fittedKey(row: { building_key: string; asset_type?: string | null }) {
  return row.asset_type ? `${row.building_key}|${row.asset_type}` : row.building_key;
}

function signedPct(n: number) {
  const abs = Math.abs(n).toLocaleString("ko-KR", { maximumFractionDigits: 1 });
  if (n > 0) return `+${abs}%`;
  if (n < 0) return `−${abs}%`;
  return "0%";
}

function NewBuildAge0GapNote({ gap }: { gap: NewBuildAge0Gap }) {
  if (gap.n_0_3 <= 0) {
    return (
      <p>
        이 식 표본에 준공 0~3년 단지가 없어, 연식=0과 실제 신축의 격차율을 계산하지
        못했습니다.
      </p>
    );
  }
  const med = gap.median_residual_pct;
  const dir =
    med == null
      ? ""
      : med > 0
        ? "실제가 더 높음(과소예측)"
        : med < 0
          ? "실제가 더 낮음(과대예측)"
          : "중앙은 일치";
  return (
    <>
      <div>
        같은 식·이 표본의 준공 0~3년 {gap.n_0_3.toLocaleString("ko-KR")}단지
        {gap.n_0_1 > 0 ? ` (0~1년 ${gap.n_0_1.toLocaleString("ko-KR")})` : ""}에 연식만
        0으로 넣으면 실제 대비{" "}
        <MetricWithHelp
          label="중앙 잔차"
          termId="newbuild_age0_gap"
          value={med == null ? "—" : signedPct(med)}
        />
        {dir ? ` · ${dir}` : ""}
        {gap.underpred_share_pct != null
          ? ` · 과소예측 비율 ${fmt(gap.underpred_share_pct, 0)}%`
          : ""}
        {gap.thin ? " · 표본이 적어 참고입니다" : ""}
        .
      </div>
      <p>예측값에 더하는 보정이 아닙니다. 단지마다 편차가 큽니다.</p>
    </>
  );
}

function regionParams(p: Props): Pick<
  RegionalRegressionRunRequest,
  "addr3_list" | "addr4_list" | "region_codes" | "region_code_level" | "region_addrs"
> {
  const addr = p.hasIntermediate
    ? {
        addr3_list: p.guList.length ? p.guList : undefined,
        addr4_list: p.leafList.length ? p.leafList : undefined,
      }
    : { addr3_list: p.leafList.length ? p.leafList : undefined };
  return {
    ...addr,
    region_codes: p.regionCodes?.length ? p.regionCodes : undefined,
    region_code_level: p.regionCodeLevel,
    region_addrs: p.regionAddrs?.length ? p.regionAddrs : undefined,
  };
}

export default function RegionalRegressionModal(props: Props) {
  const kinds = regressionKinds(props.assetType);
  const unified = kinds.length >= 2;
  const [vars, setVars] = useState<RegionalRegressionVariables>({
    households: true,
    max_floor: true,
    building_age: true,
    parking: !unified,
    structure: false,
    builder: false,
    asset_type_dummy: unified,
    assessed_land_price: false,
  });
  const [modelType, setModelType] = useState<"linear" | "log">("log");
  const [weightMode, setWeightMode] = useState<"equal" | "tx">("equal");
  const [minTx, setMinTx] = useState<MinTx>(5);
  const [pickKey, setPickKey] = useState(VIRTUAL_KEY);
  const [inputs, setInputs] = useState<RegionalRegressionPredictInputs>({});

  const body = useMemo<RegionalRegressionRunRequest>(
    () => ({
      addr1: props.addr1,
      addr2: props.addr2,
      ...regionParams(props),
      window_years: props.windowYears,
      asset_type: props.assetType,
      variables: vars,
      model_type: modelType,
      weight_mode: weightMode,
      min_tx: minTx,
    }),
    [
      props.addr1,
      props.addr2,
      props.hasIntermediate,
      props.guList,
      props.leafList,
      props.regionCodes,
      props.regionCodeLevel,
      props.regionAddrs,
      props.windowYears,
      props.assetType,
      vars,
      modelType,
      weightMode,
      minTx,
    ],
  );

  const runM = useMutation({
    mutationFn: (req: RegionalRegressionRunRequest) => runRegionalRegression(req),
  });
  const predM = useMutation({
    mutationFn: () => predictRegionalRegression({ ...body, inputs }),
  });

  const data = runM.data;
  const picked = pickKey !== VIRTUAL_KEY ? data?.fitted.find((r) => fittedKey(r) === pickKey) : undefined;

  function applyTarget(key: string) {
    if (key === VIRTUAL_KEY || !key) {
      setPickKey(VIRTUAL_KEY);
      setInputs(emptyPredictInputs());
      predM.reset();
      return;
    }
    const row = data?.fitted.find((r) => fittedKey(r) === key);
    if (!row) return;
    setPickKey(key);
    setInputs(inputsFromFitted(row));
    predM.reset();
  }

  return (
    <DraggableModalShell
      open
      onClose={props.onClose}
      titleId="regional-regression-title"
      title="지역회귀"
      subtitle={`한 행 = 단지 · 값이 있으면 출처와 무관하게 포함 · 거래 ${minTx}건 미만은 제외`}
      allowFullscreen
      allowFontScale
      resizable
      defaultWidth={920}
      defaultHeight={700}
      minWidth={640}
      minHeight={480}
    >
      <div className="text-xs text-slate-700 dark:text-slate-200 space-y-3">
        <p className="text-[11px] text-slate-500">
          {data?.scope_label ?? `${props.addr1} · ${props.addr2} · ${props.windowYears}년 창`}
          {data?.as_of_month ? ` · 기준 ${data.as_of_month.slice(0, 7)}` : ""}
        </p>

        <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-2">
          <p className="text-xs font-semibold">1. 변수</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1.5">
            {CORE_VARS.map(([key, label]) => (
              <label
                key={key}
                className="flex items-center gap-1"
                title={
                  key === "parking"
                    ? "표제부 단지에는 주차 값이 없어 켜면 빠집니다"
                    : undefined
                }
              >
                <input
                  type="checkbox"
                  checked={vars[key]}
                  onChange={(e) => setVars((v) => ({ ...v, [key]: e.target.checked }))}
                />
                {label}
              </label>
            ))}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1.5 pt-1 border-t border-slate-100 dark:border-slate-700">
            {WEAK_VARS.map(([key, label, hint]) => (
              <label key={key} className="flex items-center gap-1" title={hint}>
                <input
                  type="checkbox"
                  checked={vars[key]}
                  onChange={(e) => setVars((v) => ({ ...v, [key]: e.target.checked }))}
                />
                {label}
                <span className="text-[10px] text-amber-700 dark:text-amber-400">약한 변수</span>
              </label>
            ))}
          </div>
          {unified && (
            <label className="flex items-center gap-1 pt-1" title="기준은 아파트(있으면). 계수는 같은 규모·연식에서 아파트 대비 단가 수준입니다.">
              <input
                type="checkbox"
                checked={vars.asset_type_dummy}
                onChange={(e) => setVars((v) => ({ ...v, asset_type_dummy: e.target.checked }))}
              />
              유형 더미
              <span className="text-[10px] text-slate-500">기준 아파트 · 교차항 없음</span>
            </label>
          )}
          <label
            className="flex items-center gap-1 pt-1 border-t border-slate-100 dark:border-slate-700"
            title="기본 통계에 연결된 최신 대표 필지의 개별공시지가(원/㎡)를 원값으로 사용합니다."
          >
            <input
              type="checkbox"
              checked={vars[LAND_VAR[0]]}
              onChange={(e) => setVars((v) => ({ ...v, [LAND_VAR[0]]: e.target.checked }))}
            />
            {LAND_VAR[1]}
            <span className="text-[10px] text-slate-500">최신 대표 필지 · 원값</span>
          </label>
        </section>

        <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-1.5">
          <p className="text-xs font-semibold">2. 모형</p>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={modelType === "linear"} onChange={() => setModelType("linear")} />
            선형 — 단가(만원/㎡) ~ 변수
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={modelType === "log"} onChange={() => setModelType("log")} />
            log — log(단가) ~ 변수 (% 해석)
          </label>
        </section>

        <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-1.5">
          <p className="text-xs font-semibold">3. 관측치 처리</p>
          <p className="text-[11px] text-slate-600 dark:text-slate-300">
            최소 거래수 — 창 중앙값을 단지 시세로 보기 어려운 단지를 제외합니다. 기본은 5건입니다.
          </p>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {MIN_TX_OPTIONS.map((n) => (
              <label key={n} className="flex items-center gap-1.5">
                <input type="radio" checked={minTx === n} onChange={() => setMinTx(n)} />
                {n}건 미만 제외{n === 5 ? " (기본)" : ""}
              </label>
            ))}
          </div>
          {minTx < 5 && (
            <p className="text-[11px] text-amber-800 dark:text-amber-300 leading-snug">
              {minTx}건까지 넣으면 시세가 얇은 단지가 들어갑니다. 거래수 가중을 권합니다.
            </p>
          )}
          <p className="text-[11px] text-slate-600 dark:text-slate-300">
            구조·시공사 결측은 미상 더미입니다. 세대수·층·연식·주차·공시지가처럼 값이 없는 연속변수만 단지를 뺍니다.
          </p>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={weightMode === "equal"} onChange={() => setWeightMode("equal")} />
            단지 균등
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={weightMode === "tx"} onChange={() => setWeightMode("tx")} />
            거래수 가중
          </label>
          <p className="text-[10px] text-slate-500 leading-snug">
            거래수 가중은 거래가 많은 단지의 대표가격에 더 높은 신뢰도를 부여합니다.
          </p>
        </section>

        <button
          type="button"
          className="btn btn-primary"
          disabled={runM.isPending}
          onClick={() => {
            setPickKey(VIRTUAL_KEY);
            setInputs(emptyPredictInputs());
            predM.reset();
            runM.mutate(body);
          }}
        >
          {runM.isPending ? "적합 중…" : "회귀 실행"}
        </button>

        {runM.isError && (
          <p className="text-red-600">
            {(runM.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              "지역회귀를 실행하지 못했습니다."}
          </p>
        )}

        {data && (
          <>
            {data.warnings.map((w) => (
              <p key={w} className="text-[11px] text-amber-700 dark:text-amber-300 leading-snug">
                {w}
              </p>
            ))}

            {data.n < 20 && (
              <LowSampleHint
                n={data.n}
                vars={vars}
                sample={data.sample}
                minTx={minTx}
                pending={runM.isPending}
                onTurnOffMissing={(keys) => {
                  const nextVars = turnOffVars(vars, keys);
                  setVars(nextVars);
                  setPickKey(VIRTUAL_KEY);
                  setInputs(emptyPredictInputs());
                  predM.reset();
                  runM.mutate({ ...body, variables: nextVars });
                }}
              />
            )}

            <SampleFunnel sample={data.sample} />

            <section className="space-y-2">
              <p className="text-xs font-semibold">5. 성능</p>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                <MetricWithHelp
                  label="학습 n"
                  termId="fit_n"
                  value={data.n.toLocaleString("ko-KR")}
                  title="최종 분석 표본 중 학습에 쓴 단지. Holdout 은 탈락이 아닙니다."
                />
                <div>
                  <div className="text-[10px] text-slate-500">Holdout n</div>
                  <div className="tabular-nums">
                    {data.sample.n_hold > 0 ? data.sample.n_hold.toLocaleString("ko-KR") : "—"}
                  </div>
                </div>
                {data.weight_mode === "tx" && data.n_effective != null && (
                  <div>
                    <div className="text-[10px] text-slate-500">유효 단지</div>
                    <div className="tabular-nums">{fmt(data.n_effective, 1)}</div>
                  </div>
                )}
                <MetricWithHelp label="Adj R²" termId="adj_r_squared" value={fmt(data.adj_r_squared, 3)} />
                <MetricWithHelp
                  label="학습 MAPE"
                  termId="mape"
                  value={data.mape != null ? `${fmt(data.mape, 1)}%` : "—"}
                  title="학습 표본 기준. Holdout 이 없으면 외부 검증이 아닙니다."
                />
                <div>
                  <div className="text-[10px] text-slate-500">Holdout MAPE</div>
                  <div className="tabular-nums">{data.hold_mape != null ? `${fmt(data.hold_mape, 1)}%` : "—"}</div>
                </div>
              </div>
              {data.mape != null && data.sample.n_hold === 0 && (
                <p className="text-[11px] text-amber-800 dark:text-amber-300 leading-snug">
                  표본이 적어 Holdout 검증을 수행하지 않았습니다. MAPE는 학습표본 기준입니다.
                </p>
              )}
            </section>

            {data.blocks.length > 0 && (
              <div className="rounded-md border border-slate-200 dark:border-slate-600 overflow-hidden">
                <table className="data w-full text-[11px]">
                  <thead>
                    <tr>
                      <th className="text-left">블록</th>
                      <th className="text-right">hold MAPE</th>
                      <th className="text-right">핵심 대비</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.blocks.map((b) => (
                      <tr key={b.block} className={clsx(b.weak && "text-amber-800 dark:text-amber-300")}>
                        <td>
                          {b.label}
                          {b.weak ? " (약함)" : ""}
                        </td>
                        <td className="text-right tabular-nums">
                          {b.hold_mape == null ? "—" : `${fmt(b.hold_mape, 1)}%`}
                        </td>
                        <td className="text-right tabular-nums">
                          {b.delta_mape_vs_core == null
                            ? "—"
                            : `${b.delta_mape_vs_core > 0 ? "+" : ""}${fmt(b.delta_mape_vs_core, 1)}%p`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data.blocks
                  .filter((b) => b.note)
                  .map((b) => (
                    <p key={`${b.block}-n`} className="px-2 py-1 text-[10px] text-slate-500">
                      {b.note}
                    </p>
                  ))}
              </div>
            )}

            {data.equation && (
              <div className="space-y-1">
                <div className="text-xs font-semibold">회귀식</div>
                <CollectiveRegressionEquation
                  coefficients={data.coefficients}
                  modelType={data.model_type}
                  equation={data.equation}
                />
                <p className="text-[10px] text-slate-500">
                  적합: {data.weight_mode === "tx" ? "거래수 가중" : "단지 균등"}
                  {data.model_type === "log" ? " · log 단가" : " · 선형 단가"}
                </p>
                <ReferenceCategoriesLine refs={data.reference_categories} />
              </div>
            )}

            {data.coefficients.length > 0 && (
              <details>
                <summary className="cursor-pointer text-slate-600 dark:text-slate-400 font-medium">
                  계수 상세
                </summary>
                <div className="table-wrap max-h-48 mt-1 overflow-auto">
                  <table className="data w-full text-[11px]">
                    <thead>
                      <tr>
                        <th className="text-left">변수</th>
                        <th className="text-left">해석</th>
                        <th className="text-right">p</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.coefficients.map((c) => (
                        <tr key={c.name}>
                          <td>{c.label}</td>
                          <td>{c.effect_plain ?? "—"}</td>
                          <td className="text-right tabular-nums">{c.p == null ? "—" : fmt(c.p, 4)}</td>
                        </tr>
                      ))}
                      {referenceRows(data.reference_categories).map((r) => (
                        <tr key={r.key} className="bg-slate-50 dark:bg-slate-800/40">
                          <td>
                            {r.label}
                            <span className="ml-1 text-[10px] text-indigo-700 dark:text-indigo-300">기준</span>
                          </td>
                          <td>더미에 넣지 않습니다. 다른 {r.kind} 계수는 이 값 대비입니다.</td>
                          <td className="text-right tabular-nums">—</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

            {data.n >= 20 && (
              <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-2">
                <p className="text-xs font-semibold">6. 단지 평균단가 예측 (만원/㎡)</p>
                {data.fitted.length > 0 && (
                  <label className="block space-y-1">
                    <span className="text-slate-500">예측 대상</span>
                    <select
                      className="input"
                      value={pickKey}
                      onChange={(e) => applyTarget(e.target.value)}
                    >
                      <option value={VIRTUAL_KEY}>가상단지 — 변수를 직접 입력</option>
                      {data.fitted.map((r) => (
                        <option key={fittedKey(r)} value={fittedKey(r)}>
                          {r.display_name}
                          {r.asset_type ? ` · ${ASSET_LABELS[r.asset_type as keyof typeof ASSET_LABELS] ?? r.asset_type}` : ""}
                          {" "}
                          (단지 중앙값 {fmt(r.y, 0)} · 적합값 {fmt(r.y_hat, 0)}
                          {r.ape != null ? ` · 오차 ${fmt(r.ape, 1)}%` : ""})
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {pickKey === VIRTUAL_KEY && (
                  <p className="text-[11px] text-slate-500">
                    가상단지입니다. 세대수·최고층·연식 등을 직접 넣은 뒤 예측합니다.
                  </p>
                )}
                {picked && (
                  <p className="text-[11px] text-slate-500">
                    단지 중앙값 {fmt(picked.y, 0)} · 적합값 {fmt(picked.y_hat, 0)}
                    {picked.ape != null ? ` · 오차 ${fmt(picked.ape, 1)}%` : ""}
                    {" "}
                    · 아래 칸은 이 단지 값입니다. 바꿔서 what-if 할 수 있습니다.
                  </p>
                )}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <NumField
                    label="세대수"
                    value={inputs.households}
                    onChange={(n) => setInputs((s) => ({ ...s, households: n }))}
                    disabled={!vars.households}
                  />
                  <NumField
                    label="최고층"
                    value={inputs.max_floor}
                    onChange={(n) => setInputs((s) => ({ ...s, max_floor: n }))}
                    disabled={!vars.max_floor}
                  />
                  <NumField
                    label="연식"
                    value={inputs.building_age}
                    onChange={(n) => setInputs((s) => ({ ...s, building_age: n }))}
                    disabled={!vars.building_age}
                  />
                  <NumField
                    label="세대당 주차"
                    value={inputs.parking_per_household}
                    onChange={(n) => setInputs((s) => ({ ...s, parking_per_household: n }))}
                    disabled={!vars.parking}
                    step="0.1"
                  />
                  {vars.assessed_land_price && (
                    <NumField
                      label="개별공시지가 (원/㎡)"
                      value={inputs.assessed_land_price}
                      onChange={(n) => setInputs((s) => ({ ...s, assessed_land_price: n }))}
                      step="1"
                    />
                  )}
                </div>
                {vars.structure && (data.predict_options.structure_group ?? []).length > 0 && (
                  <DummySelect
                    label="구조"
                    value={inputs.structure_group ?? ""}
                    options={data.predict_options.structure_group ?? []}
                    reference={data.reference_categories?.structure_group}
                    onChange={(g) => setInputs((s) => ({ ...s, structure_group: g }))}
                  />
                )}
                {vars.builder && (data.predict_options.builder_group ?? []).length > 0 && (
                  <DummySelect
                    label="시공사"
                    value={inputs.builder_group ?? ""}
                    options={data.predict_options.builder_group ?? []}
                    reference={data.reference_categories?.builder_group}
                    onChange={(g) => setInputs((s) => ({ ...s, builder_group: g }))}
                  />
                )}
                {vars.asset_type_dummy && (data.predict_options.asset_type ?? []).length > 0 && (
                  <DummySelect
                    label="유형"
                    value={inputs.asset_type ?? ""}
                    options={data.predict_options.asset_type ?? []}
                    reference={data.reference_categories?.asset_type}
                    optionLabel={(g) => ASSET_LABELS[g as keyof typeof ASSET_LABELS] ?? g}
                    onChange={(g) => setInputs((s) => ({ ...s, asset_type: g }))}
                  />
                )}
                <button
                  type="button"
                  className="btn"
                  disabled={predM.isPending}
                  onClick={() => predM.mutate()}
                >
                  {predM.isPending ? "계산 중…" : "이 값으로 예측"}
                </button>
                {predM.isError && (
                  <p className="text-red-600">
                    {(predM.error as { response?: { data?: { detail?: string } } })?.response?.data
                      ?.detail ?? "예측에 실패했습니다."}
                  </p>
                )}
                    {predM.data && (
                  <div className="rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600 p-3 space-y-2">
                    <div>
                      <span className="text-slate-500 dark:text-slate-400 text-[10px]">
                        {ESTIMATE_COPY.valueLabel}
                        {predM.data.model_type === "log" ? " · 로그" : " · 선형"}
                      </span>
                      <div className="text-lg font-bold text-slate-800 dark:text-slate-100 tabular-nums">
                        {fmt(predM.data.y_hat, 0)} {predM.data.unit}
                      </div>
                      <StatisticalEstimateCaption compact />
                    </div>
                    {predM.data.ci_lower != null && predM.data.ci_upper != null && (
                      <div className="text-[11px] space-y-1.5 text-slate-700 dark:text-slate-300">
                        <StatisticalEstimateRangeRow kind="mean" compact>
                          <span className="tabular-nums">
                            {fmt(predM.data.ci_lower, 0)} ~ {fmt(predM.data.ci_upper, 0)} {predM.data.unit}
                          </span>
                        </StatisticalEstimateRangeRow>
                        {predM.data.pi_lower != null && predM.data.pi_upper != null && (
                          <StatisticalEstimateRangeRow kind="individual" subject="단지" compact>
                            <span className="tabular-nums">
                              {fmt(predM.data.pi_lower, 0)} ~ {fmt(predM.data.pi_upper, 0)} {predM.data.unit}
                            </span>
                          </StatisticalEstimateRangeRow>
                        )}
                      </div>
                    )}
                    <StatisticalEstimateDisclaimer compact />
                    <p className="text-[10px] text-slate-500">
                      단일 정답이 아닙니다. 식을 바꿔 가며 비교하세요.
                    </p>
                    {vars.building_age && inputs.building_age != null && inputs.building_age <= 0 && (
                      <div className="text-[11px] text-slate-600 dark:text-slate-300 space-y-1 leading-snug">
                        <p>
                          연식 0은 기존 재고 식의 선형 연식을 연장한 값입니다. 신축 전용 모형이
                          아니며, 신축 시세가 아닙니다.
                        </p>
                        {data.newbuild_age0_gap ? (
                          <NewBuildAge0GapNote gap={data.newbuild_age0_gap} />
                        ) : (
                          <p>연식 변수가 이 식에 없어 격차율을 계산하지 않았습니다.</p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </DraggableModalShell>
  );
}

function LowSampleHint({
  n,
  vars,
  sample,
  minTx,
  pending,
  onTurnOffMissing,
}: {
  n: number;
  vars: RegionalRegressionVariables;
  sample: SampleBreakdown;
  minTx: MinTx;
  pending: boolean;
  onTurnOffMissing: (keys: Array<keyof RegionalRegressionVariables>) => void;
}) {
  const dropKeys = missingVarsStillOn(vars, sample);
  const dropLabels = dropKeys.map((k) => VAR_KEY_LABEL[k] ?? k);
  const thinN = funnelStep(sample, "thin_tx")?.n ?? 0;

  return (
    <div className="rounded-md border border-amber-200 bg-amber-50/70 px-2.5 py-2 text-[11px] text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200 space-y-1.5">
      <p>적합 단지가 {n.toLocaleString("ko-KR")}곳으로, 최소 20곳이 필요합니다. 같은 지역에서 먼저 표본을 늘려 보세요.</p>
      <ol className="list-decimal pl-4 space-y-1 leading-snug">
        <li>
          {dropKeys.length > 0 ? (
            <div className="space-y-1.5">
              <p>
                결측으로 단지가 빠진 연속변수({dropLabels.join("·")})를 끄고 다시 실행하세요. 식의 의미가
                바뀝니다.
              </p>
              <button
                type="button"
                className="btn btn-primary text-[11px] px-3 py-1.5"
                disabled={pending}
                onClick={() => onTurnOffMissing(dropKeys)}
              >
                {dropLabels.join("·")} 끄고 다시 실행
              </button>
            </div>
          ) : (
            <>결측으로 빠지는 연속변수가 없거나 이미 꺼져 있습니다.</>
          )}
        </li>
        <li>
          {thinN > 0 && minTx > 2
            ? `거래 ${minTx}건 미만으로 ${thinN.toLocaleString("ko-KR")}단지가 빠졌습니다. 위의 최소 거래수를 3 또는 2로 낮춘 뒤 다시 실행하세요. 낮추면 거래수 가중을 권합니다.`
            : minTx === 2
              ? "최소 거래수는 이미 2건입니다. 1건 단지는 창 중앙값이 아니라 그 거래 하나라서 넣지 않습니다."
              : "거래가 적은 단지를 더 넣으려면 위의 최소 거래수를 3 또는 2로 낮출 수 있습니다. 기본 5건은 유지하는 편이 안전합니다."}
        </li>
        <li>
          그래도 부족하면 이 창을 닫고 지도에서 같은 시군구의 인접 읍·면·동을 추가한 뒤 다시 실행하세요.
          3·5·7년 창과 선택한 유형은 그대로 유지됩니다.
        </li>
      </ol>
    </div>
  );
}

function SampleFunnel({ sample }: { sample: SampleBreakdown }) {
  const steps = sample.funnel ?? [];
  const [detailStep, setDetailStep] = useState<FunnelStep | null>(null);
  if (!steps.length) {
    return (
      <section className="space-y-1">
        <p className="text-xs font-semibold">4. 결과</p>
        <p className="text-[11px] text-slate-500">
          원본 {sample.n_pool} · 속성 연결 {sample.n_usable_tier} · 최종 {sample.n_fit}
          {sample.n_hold ? ` · Holdout ${sample.n_hold}` : ""}
        </p>
      </section>
    );
  }

  const byCode = new Map(steps.map((s) => [s.code, s]));
  const pool = byCode.get("pool");
  const usable = byCode.get("usable");
  const matchDrop = byCode.get("match_drop");
  const grouped = Boolean(pool && usable && matchDrop);
  const matchHeader = "매칭";
  const rest = grouped
    ? steps.filter((s) => s.code !== "pool" && s.code !== "usable" && s.code !== "match_drop")
    : steps;

  return (
    <section className="space-y-1.5">
      <p className="text-xs font-semibold">4. 결과</p>
      <div className="rounded-md border border-slate-200 dark:border-slate-600 overflow-hidden">
        <ul className="list-none divide-y divide-slate-100 dark:divide-slate-700">
          {grouped ? (
            <>
              <FunnelRow step={pool!} onOpenDetail={setDetailStep} />
              <li>
                <div className="px-2.5 py-1 text-[10px] font-medium text-slate-500 dark:text-slate-400">
                  {matchHeader}
                </div>
                <ul className="list-none">
                  <FunnelRow step={usable!} tree="branch" onOpenDetail={setDetailStep} />
                  <FunnelRow step={matchDrop!} tree="end" onOpenDetail={setDetailStep} />
                </ul>
              </li>
              {rest.map((step) => (
                <FunnelRow key={step.code} step={step} onOpenDetail={setDetailStep} />
              ))}
            </>
          ) : (
            steps.map((step) => (
              <FunnelRow key={step.code} step={step} onOpenDetail={setDetailStep} />
            ))
          )}
        </ul>
      </div>
      {detailStep && (
        <DraggableModalShell
          open
          onClose={() => setDetailStep(null)}
          titleId="sample-funnel-detail-title"
          title={`${detailStep.label} 상세`}
          subtitle="적합 표본에 들어가지 않은 단지의 첫 번째 탈락 사유"
          maxWidthClass="max-w-md"
          resizable
          defaultWidth={460}
          defaultHeight={360}
          minWidth={360}
          minHeight={240}
        >
          <div className="space-y-3 text-xs">
            <div className="rounded-md bg-slate-50 p-3 dark:bg-slate-800/60">
              <p className="text-slate-500 dark:text-slate-400">{detailStep.label}</p>
              <p className="mt-1 text-lg font-semibold tabular-nums">
                {detailStep.n.toLocaleString("ko-KR")}곳
              </p>
            </div>
            {detailStep.note && (
              <p className="text-[11px] text-slate-600 dark:text-slate-300">
                {detailStep.note}
              </p>
            )}
            <ul className="list-none divide-y divide-slate-100 rounded-md border border-slate-200 dark:divide-slate-700 dark:border-slate-600">
              {detailStep.reasons.map((reason) => (
                <li key={reason.code} className="flex justify-between gap-3 px-3 py-2">
                  <span>{reason.label}</span>
                  <span className="tabular-nums">{reason.n.toLocaleString("ko-KR")}곳</span>
                </li>
              ))}
            </ul>
            <p className="text-[10px] text-slate-400">
              한 단지가 여러 조건에 해당해도 깔때기에서는 첫 번째 사유 하나로만 집계합니다.
            </p>
          </div>
        </DraggableModalShell>
      )}
    </section>
  );
}

function FunnelRow({
  step,
  tree,
  onOpenDetail,
}: {
  step: FunnelStep;
  tree?: "branch" | "end";
  onOpenDetail: (step: FunnelStep) => void;
}) {
  const count = step.n.toLocaleString("ko-KR");
  const prefix = tree === "branch" ? "├─ " : tree === "end" ? "└─ " : "";
  const label = `${prefix}${step.label}`;
  const muted = (step.kind === "drop" || step.kind === "split") && step.n === 0;
  const rowClass = clsx(
    "flex items-center justify-between gap-3 px-2.5 py-1.5 text-[11px]",
    tree && "pl-4",
    step.kind === "split" && !tree && "pl-6 text-slate-600 dark:text-slate-300",
    muted && "text-slate-400",
  );

  if (step.kind === "drop" && step.n > 0 && step.reasons.length > 0) {
    return (
      <li>
        <button
          type="button"
          className={clsx(rowClass, "w-full cursor-pointer text-left")}
          onClick={() => onOpenDetail(step)}
        >
          <span>
            {label}
            <span className="ml-1 font-normal text-[10px] text-slate-400">상세 보기</span>
          </span>
          <span className="tabular-nums">{count}</span>
        </button>
      </li>
    );
  }

  return (
    <li className={rowClass}>
      <span className={clsx(step.kind === "remain" && !tree && "font-medium")}>{label}</span>
      <span className="tabular-nums">{count}</span>
    </li>
  );
}

function referenceRows(refs?: Record<string, string>) {
  if (!refs) return [];
  const order: Array<[string, string]> = [
    ["asset_type", "유형"],
    ["structure_group", "구조"],
    ["builder_group", "시공사"],
  ];
  return order
    .filter(([key]) => refs[key])
    .map(([key, kind]) => ({
      key,
      kind,
      label: `${kind} ${labelRef(refs[key])}`,
    }));
}

function ReferenceCategoriesLine({ refs }: { refs?: Record<string, string> }) {
  const parts = referenceRows(refs);
  if (!parts.length) return null;
  return (
    <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-snug">
      기준 범주: {parts.map((p) => `${p.kind}=${labelRef(refs?.[p.key])}`).join(" · ")}
      . 이 지역에서 표본이 가장 많은 군이며, 식의 유형·시공사·구조 계수는 이 값 대비입니다.
    </p>
  );
}

function labelRef(code?: string) {
  if (!code) return "";
  return ASSET_LABELS[code as keyof typeof ASSET_LABELS] ?? code;
}

function DummySelect({
  label,
  value,
  options,
  reference,
  optionLabel,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  reference?: string;
  optionLabel?: (g: string) => string;
  onChange: (g: string | null) => void;
}) {
  const current = value || reference || "";
  const text = optionLabel ?? ((g: string) => g);
  return (
    <label className="block space-y-1">
      <span className="text-slate-500">
        {label}
        {reference ? ` · 기준 ${text(reference)}` : ""}
      </span>
      <select
        className="input"
        value={current}
        onChange={(e) => onChange(e.target.value || null)}
      >
        {reference && (
          <option value={reference}>
            {text(reference)} (기준)
          </option>
        )}
        {options
          .filter((g) => g !== reference)
          .map((g) => (
            <option key={g} value={g}>
              {text(g)}
            </option>
          ))}
      </select>
    </label>
  );
}

function NumField({
  label,
  value,
  onChange,
  disabled,
  step = "1",
}: {
  label: string;
  value?: number | null;
  onChange: (n: number | undefined) => void;
  disabled?: boolean;
  step?: string;
}) {
  return (
    <label className={clsx("block space-y-0.5", disabled && "opacity-40")}>
      <span className="text-slate-500">{label}</span>
      <input
        className="input"
        type="number"
        step={step}
        disabled={disabled}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
      />
    </label>
  );
}
