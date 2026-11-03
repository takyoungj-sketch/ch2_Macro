import { useEffect, useMemo, useRef, useState } from "react";
import AnalysisSummary, { primaryCaution } from "../../../shared/regression-ui/AnalysisSummary";
import { DetailAnalysis } from "../../../shared/regression-ui/ReadingLayout";
import ValidationStatus from "../../../shared/regression-ui/ValidationStatus";
import { contentSignature } from "../../../shared/regression-ui/signature";
import { formatProbability } from "../../../shared/regression-ui/format";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { buildRegionalRegressionContext } from "../api/aiContext";
import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchAptTwins,
  predictRegionalRegression,
  runRegionalRegression,
  type AptTwinPlace,
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
import { EffectsTable } from "./CollectiveRegressionResults";
import CollectiveModelRecommend from "./CollectiveModelRecommend";
import DraggableModalShell from "./DraggableModalShell";
import {
  MetricWithHelp,
  StatsGlossaryHelp,
  StatisticalEstimateRangeRow,
} from "@ch2/stats-glossary";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { ASSET_LABELS } from "../types";
import { parseResidentialAssetKinds } from "../utils/residentialAssetTypes";
import { countSignificantCoefficients, structureGroupLabel } from "../utils/collectiveRegressionFormat";
import { APT_TWIN_REGION_HELP, RESIDENTIAL_REGIONAL_REGRESSION_HELP, RESIDENTIAL_REGIONAL_ESTIMATE_HELP, REGIONAL_SETTINGS_HELP } from "../utils/residentialAnalysisHelp";
import { FLAT_SIDO_ADDR2_TOKEN } from "../utils/flatSidoRegion";
import { regionalPredictionCategories } from "../utils/regionalPredictionCategories";
import { regionalTwinNotice } from "../utils/regionalTwinNotice";

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

const REGIONAL_RESULT_HELP = {
  spec_id: "regional.result.reading", spec_version: "1", title: "지역회귀 결과 읽기",
  summary: "선택한 단지 자료에서 계산한 적합도와 검증 오차입니다.",
  interpretation: ["결정계수와 조정 R²는 현재 모형의 척도에서 표시합니다. 로그 모형에서는 로그 단가 기준입니다.", "학습 MAPE는 적합 단지에서 계산합니다. 분리 검증 MAPE는 학습에서 제외한 단지의 오차이며, 교차검증 CV-MAPE와 다릅니다.", "회귀식은 절편과 p<0.1인 항을 표시합니다. 전체보기에서는 유의하지 않은 항도 확인할 수 있습니다. 추정값은 전체 적합 모형으로 계산합니다.", "단가만 로그를 적용하며 세대수·연식 등 설명변수는 원래 단위를 유지합니다. 범주형 계수는 표시한 기준 범주와 비교합니다. 가상단지는 표시된 기준 지역을 적용합니다."],
  limitations: ["산출되지 않은 지표는 —로 표시합니다. 검증 상태와 현재 표본의 해석 제한을 함께 확인해 주세요."],
};

const REGIONAL_COEFFICIENT_ORDER = ["households", "max_floor", "building_age", "parking_per_household", "assessed_land_price", "atype_", "struct_", "builder_", "region_"];
const REGIONAL_VAR_LABELS: Record<string, string> = { households: "세대수", max_floor: "최고층", building_age: "연식", parking: "세대당 주차", structure: "구조", builder: "시공사", asset_type_dummy: "유형", assessed_land_price: "개별공시지가", region_dummy: "지역" };

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
    region_group: row.region_group ?? undefined,
  };
}

const CORE_VARS: Array<[keyof RegionalRegressionVariables, string]> = [
  ["households", "세대수"],
  ["max_floor", "최고층"],
  ["building_age", "연식"],
  ["parking", "세대당 주차"],
  ["assessed_land_price", "개별공시지가"],
  ["asset_type_dummy", "유형별 차이"],
];
const ADDITIONAL_VARS: Array<[keyof RegionalRegressionVariables, string, string]> = [
  ["structure", "구조", "단지의 구조·시공사에 따른 단가 차이를 분석합니다. 효과는 지역과 표본에 따라 다를 수 있습니다."],
  ["builder", "시공사", "단지의 구조·시공사에 따른 단가 차이를 분석합니다. 효과는 지역과 표본에 따라 다를 수 있습니다."],
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

function fmtFixed(n: number | null | undefined, digits = 5) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
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

type AnchorChoice = { key: string; code?: string; label: string };

function anchorChoices(p: Props): AnchorChoice[] {
  const addrs = (p.regionAddrs ?? []).map((s) => s.trim()).filter(Boolean);
  const codes = p.regionCodes ?? [];
  if (addrs.length) {
    return addrs.map((key, i) => ({
      key,
      code: codes.length === addrs.length ? codes[i] : undefined,
      label: key
        .split("|")
        .map((part) => part.trim())
        .filter((part) => part && part !== FLAT_SIDO_ADDR2_TOKEN)
        .join(" "),
    }));
  }
  if (p.leafList.length) {
    return p.leafList.map((leaf) => ({
      key: `${p.addr1}|${p.addr2}|${leaf}`,
      label: [p.addr2 === FLAT_SIDO_ADDR2_TOKEN ? p.addr1 : p.addr2, leaf].filter(Boolean).join(" "),
    }));
  }
  return [];
}

function josaEun(word: string): "은" | "는" {
  const last = [...word].pop() ?? "";
  const code = last.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) return (code - 0xac00) % 28 === 0 ? "는" : "은";
  return "은";
}

function splitAddrKey(key: string): { addr1: string; addr2: string; addr4: string } | null {
  const parts = key.split("|").map((s) => s.trim());
  if (parts.length < 3 || !parts[0] || !parts[2]) return null;
  return { addr1: parts[0], addr2: parts[1] ?? "", addr4: parts[2] };
}

/** 고른 지역과 체크한 쌍둥이를 중복 없이 붙인다. 순위만의 상위 읍·면은 식에 넣지 않는다. */
export function twinPoolRegionAddrs(selected: string[], anchor: string, twins: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  const push = (raw: string) => {
    const key = raw.trim();
    if (!key || seen.has(key)) return;
    seen.add(key);
    out.push(key);
  };
  const selectedKeys = selected.map((key) => key.trim()).filter(Boolean);
  const anchorKey = anchor.trim();
  if (selectedKeys.length === 0 || selectedKeys.includes(anchorKey)) push(anchorKey);
  for (const key of selectedKeys) push(key);
  for (const key of twins) push(key);
  return out;
}

function TwinRegionPanel(props: {
  windowYears: number;
  extraTypeLabel: string;
  choices: AnchorChoice[];
  anchorKey: string;
  onAnchorKey: (key: string) => void;
  scopeAnchors: AptTwinPlace[];
  scopeKey: string;
  onScopeKey: (key: string) => void;
  scopeLoading: boolean;
  scopeError: string | null;
  listLoading: boolean;
  listError: string | null;
  asOfLabel: string;
  anchorLabel: string;
  twins: AptTwinPlace[];
  checked: string[];
  onToggle: (regionAddr: string) => void;
  regionDummy: boolean;
  onRegionDummy: (on: boolean) => void;
  rankScopeNote: string;
  onAddNeighbors: () => void;
  onRetry: () => void;
}) {
  const notice = regionalTwinNotice({
    loading: props.scopeLoading || props.listLoading,
    error: props.scopeError || props.listError,
    scopeEmpty: props.choices.length === 0 && props.scopeAnchors.length === 0,
    hasAnchor: Boolean(props.anchorLabel),
    hasTwins: props.twins.length > 0,
  });
  return (
    <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-2">
      <div className="flex flex-wrap items-center gap-1">
        <p className="text-xs font-semibold">쌍둥이 지역</p>
        <AnalysisHelpPanel explain={APT_TWIN_REGION_HELP} />
      </div>
      <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-snug">
        기준 읍면동의 아파트 재고 구성과 가격분포를 비교해 최대 5곳을 제시합니다.
        {props.asOfLabel ? ` 목록 기준은 ${props.asOfLabel}의 3년 창입니다.` : " 목록은 최근 3년 창입니다."}
        {props.windowYears === 3
          ? " 식의 통계 창도 3년입니다."
          : ` 식은 이 화면의 ${props.windowYears}년 창으로 맞춥니다.`}
        {" "}
        변수, 모형, 최소 거래수는 기본회귀 탭과 같습니다.
      </p>
      {props.extraTypeLabel && (
        <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-snug">
          {`${props.extraTypeLabel}${josaEun(props.extraTypeLabel)} 순위에 쓰지 않았습니다. 통합회귀를 실행하면 고른 지역의 ${props.extraTypeLabel} 단지도 같은 식에 들어갑니다.`}
        </p>
      )}
      <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-snug">
        이 식은 이미 고른 읍면동 전부와 체크한 쌍둥이 지역의 단지를 한 식으로 합칩니다. 쌍둥이 순위만 기준
        읍면동으로 고릅니다. 미래 가격의 정답을 보장하지 않습니다. 그 지역만의 식은 기본회귀 탭에 있습니다.
      </p>

      {props.choices.length > 1 && (
        <label className="block space-y-1">
          <span className="text-[11px] text-slate-500">기준 읍면동</span>
          <select
            className="input"
            value={props.anchorKey}
            onChange={(e) => props.onAnchorKey(e.target.value)}
          >
            {props.choices.map((choice) => (
              <option key={choice.key} value={choice.key}>
                {choice.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {props.choices.length === 0 && (
        <label className="block space-y-1">
          <span className="text-[11px] text-slate-500">기준 읍면동</span>
          <select
            className="input"
            value={props.scopeKey}
            onChange={(e) => props.onScopeKey(e.target.value)}
            disabled={props.scopeLoading || props.scopeAnchors.length === 0}
          >
            {props.scopeAnchors.length === 0 && <option value="">{props.scopeLoading ? "읍면동을 찾는 중…" : "선택 가능한 기준 지역이 없습니다"}</option>}
            {props.scopeAnchors.map((row) => (
              <option key={row.region_addr} value={row.region_addr}>
                {row.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {notice && <div role={notice.kind === "error" ? "alert" : "status"} className="rounded-lg border border-amber-300 bg-amber-50 p-3 space-y-2 text-sm text-slate-800 dark:border-amber-700 dark:bg-amber-950/30 dark:text-slate-100">
        <p className="font-semibold">{notice.title}</p>
        <p className="leading-relaxed">{notice.reason}</p>
        {notice.kind === "insufficient" ? <>
          <p className="leading-relaxed">지도에서 인접지역을 추가하고 통계분석을 다시 실행한 뒤, 지역회귀의 기본회귀 탭에서 분석해 보세요. 실제 분석 단지 수와 검증 오차를 함께 확인해 주세요.</p>
          <p className="text-xs text-slate-600 dark:text-slate-300">쌍둥이 선정은 3년·거래 5건 이상과 필수 특성 정보 기준을 사용합니다. 위 회귀의 기간·변수·최소 거래수를 바꿔도 선정 기준은 달라지지 않습니다.</p>
          <button type="button" className="btn btn-primary" onClick={props.onAddNeighbors}>지도로 돌아가 인접지역 추가</button>
          {props.listError && <details className="text-xs text-slate-600 dark:text-slate-300"><summary className="cursor-pointer">상세 사유</summary><p className="mt-1">{props.listError}</p></details>}
        </> : <button type="button" className="btn" onClick={props.onRetry}>다시 불러오기</button>}
      </div>}
      {props.listLoading && (
        <p className="text-[11px] text-slate-500">전국 아파트 단지를 읽어 순위를 계산하고 있습니다.</p>
      )}
      {!props.listLoading && props.anchorLabel && (
        <p className="text-[11px] text-slate-500">기준: {props.anchorLabel}</p>
      )}
      {!props.listLoading && !props.listError && props.twins.length > 0 && (
        <div className="modal-table-wrap">
          <table className="data w-full text-[11px]">
            <thead>
              <tr>
                <th className="text-left w-8">선택</th>
                <th className="text-right">순위</th>
                <th className="text-left">지역</th>
                <th className="text-right" title="순위 계산에 쓴 아파트 적격 단지 수">
                  아파트 단지 수
                </th>
              </tr>
            </thead>
            <tbody>
              {props.twins.map((row) => (
                <tr key={row.region_addr}>
                  <td>
                    <input
                      type="checkbox"
                      checked={props.checked.includes(row.region_addr)}
                      onChange={() => props.onToggle(row.region_addr)}
                      aria-label={`${row.rank}위 ${row.label}`}
                    />
                  </td>
                  <td className="text-right tabular-nums">{row.rank}</td>
                  <td>{row.label}</td>
                  <td className="text-right tabular-nums">{row.n_complexes.toLocaleString("ko-KR")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <label className="flex items-start gap-1.5">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={props.regionDummy}
          onChange={(e) => props.onRegionDummy(e.target.checked)}
        />
        <span>
          지역 더미
          <span className="block text-[10px] text-slate-500 leading-snug">
            기울기는 지역이 공유하고, 절편만 지역마다 나눕니다. 기준은 이 읍면동입니다. 가상단지 예측도 그
            절편을 씁니다. 기본은 꺼져 있습니다.
          </span>
        </span>
      </label>
      {props.rankScopeNote && (
        <p className="text-xs text-amber-800 dark:text-amber-300 leading-snug">{props.rankScopeNote}</p>
      )}
    </section>
  );
}

export default function RegionalRegressionModal(props: Props) {
  const resultSummaryRef = useRef<HTMLElement>(null);
  const kinds = regressionKinds(props.assetType);
  const [vars, setVars] = useState<RegionalRegressionVariables>({
    households: true,
    max_floor: true,
    building_age: true,
    parking: true,
    structure: false,
    builder: false,
    asset_type_dummy: true,
    assessed_land_price: true,
  });
  const [modelType, setModelType] = useState<"linear" | "log">("log");
  const [weightMode, setWeightMode] = useState<"equal" | "tx">("equal");
  const [minTx, setMinTx] = useState<MinTx>(5);
  const [categoricalMissing, setCategoricalMissing] = useState<"keep_unknown" | "drop">("keep_unknown");
  const selectedBlocks = useMemo(
    () => (Object.keys(vars) as (keyof RegionalRegressionVariables)[]).filter((key) => Boolean(vars[key])),
    [vars],
  );
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
      categorical_missing: categoricalMissing,
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
      categoricalMissing,
      weightMode,
      minTx,
    ],
  );

  const showTwin = kinds.includes("apartment");
  const [tab, setTab] = useState<"local" | "twin">("local");
  const effectiveTab = showTwin && tab === "twin" ? "twin" : "local";
  const choices = useMemo(
    () => anchorChoices(props),
    [props.addr1, props.addr2, props.leafList, props.regionAddrs, props.regionCodes],
  );
  const choiceKey = choices.map((c) => `${c.key}\t${c.code ?? ""}`).join("\n");
  const [anchorKey, setAnchorKey] = useState("");
  const [scopeKey, setScopeKey] = useState("");
  const [checked, setChecked] = useState<string[]>([]);
  const [regionDummy, setRegionDummy] = useState(false);
  useEffect(() => {
    setAnchorKey(choices[0]?.key ?? "");
    setChecked([]);
  }, [choiceKey]);

  const explicit = choices.find((c) => c.key === anchorKey) ?? choices[0];
  const explicitParts = explicit ? splitAddrKey(explicit.key) : null;
  const scopeQ = useQuery({
    queryKey: ["apt-twin-scope", props.addr1, props.addr2],
    queryFn: () => fetchAptTwins({ addr1: props.addr1, addr2: props.addr2 }),
    enabled: showTwin && effectiveTab === "twin" && choices.length === 0,
    staleTime: 10 * 60 * 1000,
  });
  const scopeAnchors = scopeQ.data?.scope_anchors ?? [];
  useEffect(() => {
    const first = scopeQ.data?.scope_anchors?.[0]?.region_addr;
    if (choices.length > 0 || !first) return;
    setScopeKey((cur) => cur || first);
  }, [choices.length, scopeQ.data]);
  const scopePlace = scopeAnchors.find((row) => row.region_addr === scopeKey) ?? null;
  const twinQueryArgs = explicitParts
    ? {
        addr1: explicitParts.addr1,
        addr2: explicitParts.addr2,
        addr4: explicitParts.addr4,
        region_code: explicit?.code,
      }
    : scopePlace
      ? { addr1: scopePlace.addr1, addr2: scopePlace.addr2, addr4: scopePlace.addr4 }
      : null;
  const twinQ = useQuery({
    queryKey: ["apt-twin-list", twinQueryArgs],
    queryFn: () => fetchAptTwins(twinQueryArgs!),
    enabled: showTwin && effectiveTab === "twin" && twinQueryArgs != null && !!twinQueryArgs.addr4,
    staleTime: 10 * 60 * 1000,
  });
  const anchorAddr = twinQ.data?.anchor?.region_addr ?? "";
  const selectedRegionKeys = choices.map((choice) => choice.key);
  const rankScopeNote =
    anchorAddr && selectedRegionKeys.length > 0 && !selectedRegionKeys.includes(anchorAddr)
      ? `쌍둥이 순위는 ${twinQ.data?.anchor?.label || "상위 읍·면"} 기준입니다. 식에는 선택한 지역과 체크한 쌍둥이만 들어갑니다.`
      : "";
  useEffect(() => {
    setChecked([]);
  }, [anchorAddr]);

  const twinRequest = useMemo<RegionalRegressionRunRequest | null>(() => {
    const anchor = twinQ.data?.anchor;
    const pickedTwins = (twinQ.data?.twins ?? []).filter((row) => checked.includes(row.region_addr));
    if (!anchor || pickedTwins.length === 0) return null;
    return {
      addr1: anchor.addr1,
      addr2: anchor.addr2,
      window_years: props.windowYears,
      asset_type: props.assetType,
      variables: vars,
      model_type: modelType,
      categorical_missing: categoricalMissing,
      weight_mode: weightMode,
      min_tx: minTx,
      region_dummy: regionDummy,
      evaluation_region_addrs: choices.length ? choices.map(choice => choice.key) : [anchor.region_addr],
      region_addrs: twinPoolRegionAddrs(
        choices.map((choice) => choice.key),
        anchor.region_addr,
        pickedTwins.map((row) => row.region_addr),
      ),
    };
  }, [twinQ.data, checked, choices, regionDummy, props.windowYears, props.assetType, vars, modelType, categoricalMissing, weightMode, minTx]);

  const runM = useMutation({
    mutationFn: async (req: RegionalRegressionRunRequest) => ({
      ...await runRegionalRegression(req), requestSignature: contentSignature(req),
    }),
  });
  const twinRun = useMutation({
    mutationFn: async (req: RegionalRegressionRunRequest) => ({
      ...await runRegionalRegression(req), requestSignature: contentSignature(req),
    }),
  });
  const runShown = effectiveTab === "twin" ? twinRun : runM;
  const currentRequest = effectiveTab === "twin" ? twinRequest : body;
  const data = runShown.data;
  const conditionsChanged = Boolean(data && data.requestSignature !== contentSignature(currentRequest));
  const modelInputs = useMemo(() => regionalPredictionCategories(inputs, data?.predict_options), [inputs, data?.predict_options]);
  const predictionSignature = contentSignature({ request: currentRequest, inputs: modelInputs, model: data?.analysis?.model_signature });
  const predM = useMutation({
    mutationFn: async (req: RegionalRegressionRunRequest) => {
      if (conditionsChanged) throw new Error("분석 조건이 바뀌었습니다. 아래 결과는 이전 조건으로 계산했습니다.");
      const signature = predictionSignature;
      return { ...await predictRegionalRegression({ ...req, inputs: modelInputs, expected_model_signature: data?.analysis?.model_signature }), inputSignature: signature };
    },
  });
  // 입력·적합 모형이 바뀌면 이전 요청의 오류와 진행 상태도 무효화한다.
  const resetPrediction = predM.reset;
  useEffect(() => { resetPrediction(); }, [predictionSignature, resetPrediction]);
  const currentPrediction = !conditionsChanged && !runShown.isPending
    && predM.data?.inputSignature === predictionSignature ? predM.data : undefined;
  const picked = pickKey !== VIRTUAL_KEY ? data?.fitted.find((r) => fittedKey(r) === pickKey) : undefined;
  const loadedInputs = picked ? regionalPredictionCategories(inputsFromFitted(picked), data?.predict_options) : undefined;
  const editedLabels = loadedInputs ? ([
    ["households", "세대수"], ["max_floor", "최고층"], ["building_age", "연식"], ["parking_per_household", "세대당 주차"],
    ["assessed_land_price", "개별공시지가"], ["structure_group", "구조"], ["builder_group", "시공사"], ["asset_type", "유형"],
  ] as const).filter(([key]) => (modelInputs[key] ?? null) !== (loadedInputs[key] ?? null)).map(([, label]) => label) : [];
  const regionalAiContext = useMemo(() => {
    const regionLabel = data?.scope_label ?? [props.addr1, props.addr2].filter(Boolean).join(" ");
    if (!data) {
      return {
        app: "collective" as const,
        panel: "RegionalRegressionModal",
        purpose: "statistics" as const,
        scope: { region_label: regionLabel, asset_type: props.assetType },
        facts: {
          screen: "regional_regression",
          ran: false,
          tab: effectiveTab,
          window_years: props.windowYears,
        },
      };
    }
    const context = buildRegionalRegressionContext(data, {
      regionLabel,
      assetType: props.assetType,
      tab: effectiveTab,
      prediction: currentPrediction ?? null,
    });
    context.facts = { ...context.facts, conditions_changed: conditionsChanged,
      result_state: conditionsChanged ? "previous_conditions" : "current" };
    return context;
  }, [data, effectiveTab, props.addr1, props.addr2, props.assetType, props.windowYears, currentPrediction, conditionsChanged]);

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
    setInputs(regionalPredictionCategories(inputsFromFitted(row), data?.predict_options));
    predM.reset();
  }

  return (
    <DraggableModalShell
      open
      onClose={props.onClose}
      titleId="regional-regression-title"
      title="지역회귀(신규예측)"
      headerActions={<AnalysisHelpPanel explain={RESIDENTIAL_REGIONAL_REGRESSION_HELP} />}
      subtitle={`단지별 중앙단가 분석 · 최소 거래 ${minTx}건`}
      allowFullscreen
      allowFontScale
      resizable
      defaultWidth={920}
      defaultHeight={700}
      minWidth={640}
      minHeight={480}
    >
      <div className="text-xs text-slate-700 dark:text-slate-200 space-y-3">
        <PublishAiContext context={regionalAiContext} />
        {conditionsChanged && <p className="text-xs text-amber-700 dark:text-amber-300" role="status">
          분석 조건이 바뀌었습니다. 아래 결과는 이전 조건으로 계산했습니다.
        </p>}
        <div className="flex items-start justify-between gap-2">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {data?.scope_label ?? `${props.addr1} · ${props.addr2} · ${props.windowYears}년 창`}
          {data?.as_of_month ? ` · 기준 ${data.as_of_month.slice(0, 7)}` : ""}
        </p>
        </div>

        {showTwin && (
          <div className="flex flex-wrap gap-0.5 rounded-md border modal-tab-bar p-0.5" role="tablist">
            {(
              [
                ["local", "기본회귀"],
                ["twin", "쌍둥이 확장"],
              ] as const
            ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={effectiveTab === id}
              className={clsx(
                "px-3 py-1.5 text-sm font-medium rounded transition-colors whitespace-nowrap",
                effectiveTab === id ? "modal-tab-active" : "modal-tab-idle",
              )}
              onClick={() => {
                setTab(id);
                setPickKey(VIRTUAL_KEY);
                setInputs(emptyPredictInputs());
                predM.reset();
              }}
            >
              {label}
            </button>
            ))}
          </div>
        )}

        {effectiveTab === "twin" && (
          <TwinRegionPanel
            windowYears={props.windowYears}
            extraTypeLabel={kinds
              .filter((k) => k !== "apartment")
              .map((k) => ASSET_LABELS[k] ?? k)
              .join("·")}
            choices={choices}
            anchorKey={anchorKey}
            onAnchorKey={(key) => {
              setAnchorKey(key);
              setChecked([]);
            }}
            scopeAnchors={scopeAnchors}
            scopeKey={scopeKey}
            onScopeKey={(key) => {
              setScopeKey(key);
              setChecked([]);
            }}
            scopeLoading={scopeQ.isFetching}
            scopeError={
              scopeQ.isError
                ? ((scopeQ.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                  "기준 읍면동을 불러오지 못했습니다.")
                : null
            }
            listLoading={twinQ.isFetching}
            listError={
              twinQ.isError
                ? ((twinQ.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                  "쌍둥이 지역을 계산하지 못했습니다.")
                : null
            }
            asOfLabel={twinQ.data?.as_of_label ?? ""}
            anchorLabel={twinQ.data?.anchor?.label ?? ""}
            twins={twinQ.data?.twins ?? []}
            checked={checked}
            onToggle={(regionAddr) =>
              setChecked((cur) =>
                cur.includes(regionAddr) ? cur.filter((k) => k !== regionAddr) : [...cur, regionAddr],
              )
            }
            regionDummy={regionDummy}
            onRegionDummy={setRegionDummy}
            rankScopeNote={rankScopeNote}
            onAddNeighbors={props.onClose}
            onRetry={() => {
              if (choices.length === 0) void scopeQ.refetch();
              if (twinQueryArgs) void twinQ.refetch();
            }}
          />
        )}

        <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-2">
          <div className="flex items-center gap-2"><p className="text-sm font-semibold">1. 변수 선택</p><AnalysisHelpPanel explain={REGIONAL_SETTINGS_HELP.variables} /></div>
          <div className="flex flex-wrap gap-x-3 gap-y-1.5">
            {CORE_VARS.map(([key, label]) => (
              <label
                key={key}
                className="flex items-center gap-1"
                title={
                  key === "parking"
                    ? "주차 정보가 없는 단지는 이 변수를 선택하면 제외될 수 있습니다."
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
            {ADDITIONAL_VARS.map(([key, label, hint]) => (
              <label key={key} className="flex items-center gap-1" title={hint}>
                <input
                  type="checkbox"
                  checked={vars[key]}
                  onChange={(e) => setVars((v) => ({ ...v, [key]: e.target.checked }))}
                />
                {label}
              </label>
            ))}
            <AnalysisHelpPanel explain={REGIONAL_SETTINGS_HELP.structureBuilder} />
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-1.5">
          <div className="flex items-center gap-2"><p className="text-sm font-semibold">2. 회귀모형 선택</p><AnalysisHelpPanel explain={REGIONAL_SETTINGS_HELP.model} /></div>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={modelType === "linear"} onChange={() => setModelType("linear")} />
            선형회귀
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={modelType === "log"} onChange={() => setModelType("log")} />
            로그회귀 (log)
            
          </label>
        </section>

        <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-1.5">
          <div className="flex items-center gap-2"><p className="text-sm font-semibold">3. 결측치 처리</p><AnalysisHelpPanel explain={REGIONAL_SETTINGS_HELP.missing} /></div>
          
          <label className="flex items-center gap-1.5">
            <input
              type="radio"
              checked={categoricalMissing === "keep_unknown"}
              onChange={() => setCategoricalMissing("keep_unknown")}
            />
            미상 범주 유지 (기본값)
          </label>
          <label className="flex items-center gap-1.5">
            <input
              type="radio"
              checked={categoricalMissing === "drop"}
              onChange={() => setCategoricalMissing("drop")}
            />
            결측 단지 제외
          </label>
        </section>

        <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-1.5">
          <div className="flex items-center gap-2"><p className="text-sm font-semibold">4. 표본 및 가중치</p><AnalysisHelpPanel explain={REGIONAL_SETTINGS_HELP.sample} /></div>
          <p className="font-medium">단지별 최소 거래 수</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {MIN_TX_OPTIONS.map((n) => (
              <label key={n} className="flex items-center gap-1.5">
                <input type="radio" checked={minTx === n} onChange={() => setMinTx(n)} />
                {n}건 미만 제외{n === 5 ? " (기본)" : ""}
              </label>
            ))}
          </div>
          {minTx < 5 && (
            <p className="text-xs text-amber-800 dark:text-amber-300 leading-snug">
              거래가 {minTx}건인 단지까지 포함합니다. 중앙단가가 불안정할 수 있어 거래수 가중을 권합니다.
            </p>
          )}
          <p className="pt-1 font-medium">가중치</p>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={weightMode === "equal"} onChange={() => setWeightMode("equal")} />
            단지 균등
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" checked={weightMode === "tx"} onChange={() => setWeightMode("tx")} />
            거래수 가중
          </label>

        </section>

        {effectiveTab === "local" && (
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
        )}

        {effectiveTab === "twin" && (
          <button type="button" className="btn btn-primary" disabled={!twinRequest || twinRun.isPending}
            onClick={() => {
              if (!twinRequest) return;
              setPickKey(VIRTUAL_KEY);
              setInputs(emptyPredictInputs());
              predM.reset();
              twinRun.mutate(twinRequest);
            }}>
            {twinRun.isPending ? "적합 중…" : "통합회귀 실행"}
          </button>
        )}

        {runShown.isError && (
          <p className="text-red-600">
            {(runShown.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
              "지역회귀를 실행하지 못했습니다."}
          </p>
        )}

        {data && (
          <>


            {data.n < 20 && (
              <LowSampleHint
                n={data.n}
                vars={vars}
                sample={data.sample}
                minTx={minTx}
                pending={runShown.isPending}
                onTurnOffMissing={(keys) => {
                  const nextVars = turnOffVars(vars, keys);
                  const base = effectiveTab === "twin" ? twinRequest : body;
                  if (!base) return;
                  setVars(nextVars);
                  setPickKey(VIRTUAL_KEY);
                  setInputs(emptyPredictInputs());
                  predM.reset();
                  runShown.mutate({ ...base, variables: nextVars });
                }}
              />
            )}

            <section ref={resultSummaryRef} tabIndex={-1} className="card space-y-3" aria-label="결과 요약">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">결과 요약</h3>
                <span className="flex items-center gap-1 text-sm font-medium">학습·적합 {data.n.toLocaleString("ko-KR")}곳 <StatsGlossaryHelp termId="fit_n" size="xs" /></span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">단지 중앙단가(만원/㎡) · 분석 대상 {(data.sample.n_analysis?.toLocaleString("ko-KR") ?? "—")}곳 · 학습 {data.sample.n_fit.toLocaleString("ko-KR")}곳 · 검증 {data.sample.n_hold > 0 ? `${data.sample.n_hold.toLocaleString("ko-KR")}곳` : "미제공"}</p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: data.model_type === "log" ? "결정계수 R² (로그)" : "결정계수 R²", term: "r_squared", value: fmtFixed(data.r_squared, 3) },
                  { label: data.model_type === "log" ? "조정 R² (로그)" : "조정 R²", term: "adj_r_squared", value: fmtFixed(data.model_adj_r_squared, 3) },
                  { label: "학습 MAPE", term: "mape", value: data.mape != null ? `${fmtFixed(data.mape, 2)}%` : "—" },
                  { label: "분리 검증 MAPE", term: "hold", value: data.hold_mape != null ? `${fmtFixed(data.hold_mape, 2)}%` : "—" },
                ].map(metric => <div key={metric.term} className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-3 dark:border-slate-700 dark:bg-slate-900/40">
                  <div className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300">{metric.label}{metric.term === "hold" ? <AnalysisHelpPanel explain={REGIONAL_RESULT_HELP} /> : <StatsGlossaryHelp termId={metric.term} size="xs" />}</div>
                  <p className="mt-2 text-xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">{metric.value}</p>
                </div>)}
              </div>
              <ValidationStatus report={data.analysis?.metrics.find(metric => metric.role !== "training")?.validation} />
            {(data.equation || data.coefficients.length > 0) && (
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-sm font-semibold">회귀식 <AnalysisHelpPanel explain={REGIONAL_RESULT_HELP} /></div>
                <CollectiveRegressionEquation
                  targetLabel="단지 중앙단가" targetUnit="만원/㎡"
                  coefficients={data.coefficients}
                  modelType={data.model_type}
                  equation={data.equation ?? undefined}
                  prominent coefficientOrder={REGIONAL_COEFFICIENT_ORDER} showTechnicalNote={false}
                />
                <p className="text-xs text-slate-500">
                  적합: {data.weight_mode === "tx" ? "거래수 가중" : "단지 균등"}
                  {data.model_type === "log" ? " · log 단가" : " · 선형 단가"}
                </p>
                <ReferenceCategoriesLine refs={data.reference_categories} />
              </div>
            )}
              {primaryCaution(data.analysis) && <p role="status" className="border-l-2 border-amber-500 pl-3 text-xs leading-relaxed text-amber-800 dark:text-amber-200">{primaryCaution(data.analysis)}</p>}
              {data.warnings.length > 0 && <div className="space-y-1 border-l-2 border-amber-500 pl-3 text-xs leading-relaxed text-amber-800 dark:text-amber-200">{[...new Set(data.warnings)].filter(w => w !== primaryCaution(data.analysis)).map(w => <p key={w}>{w}</p>)}</div>}
            </section>

            <DetailAnalysis>
            {data.coefficients.length > 0 && <section className="space-y-2" aria-label="회귀계수 상세">
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                <h4 className="text-sm font-semibold">회귀계수</h4>
                <span className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300">유의 계수 {countSignificantCoefficients(data.coefficients)}개 <AnalysisHelpPanel explain={REGIONAL_RESULT_HELP} /></span>
              </div>
              {data.analysis && <div className="space-y-1 text-sm text-slate-600 dark:text-slate-300">
                <p>실제 반영: {data.analysis.variables.filter(v => v.state === "included").map(v => REGIONAL_VAR_LABELS[v.name] ?? "추가 변수").join(" · ") || "없음"}</p>
                {data.analysis.variables.some(v => v.state !== "included") && <p className="text-amber-800 dark:text-amber-300">선택했으나 제외: {data.analysis.variables.filter(v => v.state !== "included").map(v => `${REGIONAL_VAR_LABELS[v.name] ?? "추가 변수"} (${({ not_in_model: "모형에 미포함", constant: "값이 일정함", no_data: "자료 없음", missing_after_filter: "필터 후 자료 없음", not_identifiable: "효과 구분 어려움" } as Record<string, string>)[v.state] ?? "제외"})`).join(" · ")}</p>}
              </div>}
              <EffectsTable coefficients={data.coefficients} coefficientOrder={REGIONAL_COEFFICIENT_ORDER} />
            </section>}

            <details className="text-xs">
              <summary className="cursor-pointer py-1 font-medium text-slate-600 dark:text-slate-300">분석에 사용한 자료와 표본</summary>
              <div className="mt-2 space-y-3">
                <SampleFunnel sample={data.sample} />
                <AnalysisSummary analysis={data.analysis} />
                {data.missing_treatment_label && <p>{data.missing_treatment_label}</p>}
              </div>
            </details>
            {data.extension_comparison && <section className="rounded border border-slate-200 dark:border-slate-600 p-3 space-y-1 text-xs">
              <p className="font-semibold">기존 지역의 같은 단지로 확장 전후 비교</p>
              {data.extension_comparison.status === "available" || data.extension_comparison.status === "partial" ? <>
                <p>검증 {data.extension_comparison.evaluation_n}곳 · 확장 전 학습 {data.extension_comparison.fit_before_n}곳 · 확장 후 학습 {data.extension_comparison.fit_after_n}곳</p>
                <p>선정용 검증 MAPE: 확장 전 {fmt(data.extension_comparison.mape_before, 1)}% → 확장 후 {fmt(data.extension_comparison.mape_after, 1)}%</p>
                {data.extension_comparison.status === "partial" && data.extension_comparison.reason && (
                  <p className="text-amber-800 dark:text-amber-300">{data.extension_comparison.reason}</p>
                )}
                <p className="text-slate-500 dark:text-slate-400">양쪽 모두 같은 검증 단지를 학습에서 제외한 별도 비교입니다. 아래 전체 범위 모형의 분할과 다르며, 확장 선택에 참고하는 수치로 독립 확인 결과는 아닙니다.</p>
              </> : <p>{data.extension_comparison.reason ?? "동일 대상 비교를 제공하지 않습니다."}</p>}
            </section>}
            {data.blocks.length > 0 && (
              <details className="rounded border border-slate-200 px-3 py-2 dark:border-slate-600">
                <summary className="cursor-pointer text-xs font-medium">추가 변수 비교</summary>
                <div className="mt-2 overflow-auto">
                <table className="data w-full text-[11px]">
                  <thead>
                    <tr>
                      <th className="text-left">블록</th>
                      <th className="text-right">분리 검증 MAPE</th>
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
              </div></details>
            )}





            {data.fitted.length > 0 && <details className="rounded border border-slate-200 dark:border-slate-600 p-2.5 text-xs">
              <summary className="cursor-pointer font-semibold">학습 단지별 거래수·적합 결과 ({data.fitted.length}/{data.n}곳 표시)</summary>
              <p className="my-2 text-slate-600 dark:text-slate-300">학습에 사용한 단지입니다. 별도 평가 단지는 포함하지 않습니다. 거래수는 단지 중앙단가를 계산한 거래 건수이며 회귀 관측 수와 다릅니다. 표시 한도를 넘은 단지는 생략됩니다.</p>
              <div className="max-h-64 overflow-auto" tabIndex={0} aria-label="학습 단지별 결과 표">
                <table className="w-full text-left tabular-nums">
                  <thead><tr><th className="p-1">단지</th><th className="p-1 text-right">거래수</th><th className="p-1 text-right">중앙단가</th><th className="p-1 text-right">적합 단가</th></tr></thead>
                  <tbody>{data.fitted.map(r => <tr key={fittedKey(r)} className="border-t border-slate-200 dark:border-slate-700">
                    <td className="p-1">{r.display_name}{(r.address || r.region_group) && <span className="block text-slate-600 dark:text-slate-300">{r.address || r.region_group}</span>}</td>
                    <td className="p-1 text-right">{r.transaction_n ?? "—"}건</td>
                    <td className="p-1 text-right">{fmt(r.y, 1)}</td><td className="p-1 text-right">{fmt(r.y_hat, 1)}</td>
                  </tr>)}</tbody>
                </table>
              </div>
              <p className="mt-1">단가 단위: 만원/㎡. 적합값과의 차이는 학습 오차이며 검증 오차가 아닙니다.</p>
            </details>}
            <details className="text-xs text-slate-600 dark:text-slate-300">
              <summary className="cursor-pointer py-1">추가 통계정보</summary>
              <p className="mt-2">F 검정 p값: {formatProbability(data.f_p_value)} <StatsGlossaryHelp termId="f_p_value" size="xs" /></p>
              {data.weight_mode === "tx" && data.n_effective != null && <p className="mt-2">거래수 가중 · 유효 단지 {fmt(data.n_effective, 1)}곳</p>}
            </details>
            </DetailAnalysis>
            {data.n >= 20 && (
              <section className="rounded-lg border border-slate-200 dark:border-slate-600 p-2.5 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold">조건별 추정 · 단지 중앙단가 (만원/㎡)</p>
                  <AnalysisHelpPanel explain={RESIDENTIAL_REGIONAL_ESTIMATE_HELP} />
                </div>
                {data.fitted.length > 0 && (
                  <label className="block space-y-1">
                    <span className="text-slate-500">예측 대상 · 단지 정보 불러오기</span>
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
                          (기간 중앙단가 {fmt(r.y, 0)}
                          {r.ape != null ? ` · 오차 ${fmt(r.ape, 1)}%` : ""})
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {pickKey === VIRTUAL_KEY && (
                  <p className="text-sm text-slate-500">직접 입력한 조건으로 추정합니다.</p>
                )}
                {picked && (
                  <div className="space-y-1 rounded-md bg-slate-100 p-3 text-sm dark:bg-slate-800">
                    <p>선택 기간의 거래 중앙단가 <strong className="tabular-nums">{fmt(picked.y, 0)}</strong> · 원래 조건의 모형 적합값 <strong className="tabular-nums">{fmt(picked.y_hat, 0)}</strong> 만원/㎡</p>
                    <p className="text-slate-600 dark:text-slate-300">단지에서 불러온 값입니다. 아래 조건을 수정해 비교할 수 있습니다.</p>
                    <p className={editedLabels.length ? "text-indigo-700 dark:text-indigo-300" : "text-slate-500"}>{editedLabels.length ? `직접 수정: ${editedLabels.join(" · ")}` : "직접 수정한 항목 없음"}</p>
                  </div>
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
                    value={modelInputs.structure_group ?? ""}
                    options={data.predict_options.structure_group ?? []}
                    reference={data.reference_categories?.structure_group}
                    optionLabel={structureGroupLabel}
                    onChange={(g) => setInputs((s) => ({ ...s, structure_group: g }))}
                  />
                )}
                {vars.builder && (data.predict_options.builder_group ?? []).length > 0 && (
                  <DummySelect
                    label="시공사"
                    value={modelInputs.builder_group ?? ""}
                    options={data.predict_options.builder_group ?? []}
                    reference={data.reference_categories?.builder_group}
                    onChange={(g) => setInputs((s) => ({ ...s, builder_group: g }))}
                    note={data.predict_options.builder_group?.length === 1 && data.predict_options.builder_group[0] === "기타" ? "표본이 적은 시공사를 묶어 분석하므로 ‘기타’만 선택할 수 있습니다." : undefined}
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
                  disabled={predM.isPending || runShown.isPending || conditionsChanged || (effectiveTab === "twin" && !twinRequest)}
                  onClick={() => predM.mutate(effectiveTab === "twin" && twinRequest ? twinRequest : body)}
                >
                  {predM.isPending ? "계산 중…" : "추정값 계산"}
                </button>
                {predM.isError && (
                  <p className="text-red-600">
                    {(predM.error as { response?: { data?: { detail?: string } } })?.response?.data
                      ?.detail ?? "예측에 실패했습니다."}
                  </p>
                )}
                    {currentPrediction && (
                  <div className="rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-600 p-3 space-y-2">
                    <div>
                      <span className="text-slate-500 dark:text-slate-400 text-xs">
                        현재 입력 조건의 추정 중앙단가
                        {currentPrediction.model_type === "log" ? " · 로그" : " · 선형"}
                      </span>
                      <div className="text-3xl font-bold text-indigo-700 dark:text-indigo-300 tabular-nums">
                        {fmt(currentPrediction.y_hat, 0)} {currentPrediction.unit}
                      </div>
                      {pickKey === VIRTUAL_KEY && data.reference_categories?.region && (
                        <p className="text-[11px] text-slate-600 dark:text-slate-300">
                          적용 지역: {data.reference_categories.region}. 지역 더미의 기준 절편입니다.
                        </p>
                      )}

                    </div>
                    {currentPrediction.ci_lower != null && currentPrediction.ci_upper != null && (
                      <div className="text-sm font-semibold space-y-1.5 text-slate-700 dark:text-slate-200">
                        <StatisticalEstimateRangeRow kind="mean">
                          <span className="tabular-nums">
                            {fmt(currentPrediction.ci_lower, 0)} ~ {fmt(currentPrediction.ci_upper, 0)} {currentPrediction.unit}
                          </span>
                        </StatisticalEstimateRangeRow>
                        {currentPrediction.pi_lower != null && currentPrediction.pi_upper != null && (
                          <details className="pt-2 text-xs"><summary className="cursor-pointer text-slate-500 dark:text-slate-400">단지 중앙단가 예측범위 보기</summary><div className="pt-2"><StatisticalEstimateRangeRow kind="individual" subject="단지" compact>
                            <span className="tabular-nums">
                              {fmt(currentPrediction.pi_lower, 0)} ~ {fmt(currentPrediction.pi_upper, 0)} {currentPrediction.unit}
                            </span>
                          </StatisticalEstimateRangeRow></div></details>
                        )}
                      </div>
                    )}
                    <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">이 결과는 AVM에 의한 가격평가가 아닌, 회귀모형의 통계적 참고값입니다.</p>

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

            {data.model_candidates && data.model_candidates.length > 0 && (
              <details className="rounded border border-slate-200 px-3 py-2 dark:border-slate-700">
                <summary className="cursor-pointer text-sm font-medium">다른 변수 조합 비교 · 모형 추천</summary>
                <div className="mt-3"><CollectiveModelRecommend
                  candidates={data.model_candidates}
                  selectedType={modelType}
                  selectedBlocks={selectedBlocks}
                  datasetNote={
                    effectiveTab === "twin"
                      ? "고른 읍면동과 체크한 쌍둥이 지역의 단지를 사용합니다."
                      : "지금 고른 읍면동의 단지를 사용합니다."
                  }
                  samplePhrase="고른 지역의 단지에서"
                  outcomeNoun="단가"
                  applyRunsRegression
                  applyPending={runShown.isPending}
                  applyDisabled={effectiveTab === "twin" && !twinRequest}
                  applyNote="후보를 선택한 뒤 ‘후보 설정 반영’을 누르면 설정을 바꾸고 회귀를 실행합니다. 완료 후 결과 요약에서 회귀식과 계수를 확인할 수 있습니다. 후보 비교와 재적합 결과는 사용 표본이 달라 수치가 달라질 수 있습니다."
                  blockLabels={{
                    households: "세대수",
                    max_floor: "최고층",
                    parking: "세대당 주차",
                    builder: "시공사",
                    assessed_land_price: "개별공시지가",
                    asset_type_dummy: "유형",
                  }}
                  onAdopt={(pick) => {
                    if (runShown.isPending || !currentRequest) return;
                    const nextVars = { ...vars };
                    (Object.keys(nextVars) as (keyof RegionalRegressionVariables)[]).forEach(key => {
                      nextVars[key] = pick.blocks.includes(key);
                    });
                    const nextRequest = { ...currentRequest, model_type: pick.modelType, variables: nextVars };
                    setModelType(pick.modelType);
                    setVars(nextVars);
                    setPickKey(VIRTUAL_KEY);
                    setInputs(emptyPredictInputs());
                    predM.reset();
                    runShown.mutate(nextRequest, { onSuccess: () => requestAnimationFrame(() => {
                      resultSummaryRef.current?.focus({ preventScroll: true });
                      resultSummaryRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
                    }) });
                  }}
                />
                </div>
              </details>
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
          그래도 부족하면 이 창을 닫고 지도에서 같은 시군구의 인접 읍·면·동을 추가한 뒤 다시
          실행하거나, 쌍둥이 확장 탭에서 지역을 고르고 통합회귀를 실행해 보세요. 3·5·7년 창과
          선택한 유형은 그대로 유지됩니다.
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
        <p className="text-xs font-semibold">회귀분석 표본 구성</p>
        <p className="text-[11px] text-slate-500">
          원본 {sample.n_pool} · 속성 연결 {sample.n_usable_tier} · 최종 {sample.n_fit}
          {sample.n_hold ? ` · 분리 검증 ${sample.n_hold}곳` : ""}
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
      <p className="text-xs font-semibold">회귀분석 표본 구성</p>
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
    ["region", "지역"],
    ["asset_type", "유형"],
    ["structure_group", "구조"],
    ["builder_group", "시공사"],
  ];
  return order
    .filter(([key]) => refs[key])
    .map(([key, kind]) => ({
      key,
      kind,
      label: `${kind} ${key === "structure_group" ? structureGroupLabel(refs[key]) : labelRef(refs[key])}`,
    }));
}

function ReferenceCategoriesLine({ refs }: { refs?: Record<string, string> }) {
  const parts = referenceRows(refs);
  if (!parts.length) return null;
  return (
    <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
      기준 범주: {parts.map((p) => `${p.kind}=${p.key === "structure_group" ? structureGroupLabel(refs?.[p.key]) : labelRef(refs?.[p.key])}`).join(" · ")}.

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
  note,
}: {
  label: string;
  value: string;
  options: string[];
  reference?: string;
  optionLabel?: (g: string) => string;
  onChange: (g: string | null) => void;
  note?: string;
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
      {note && <span className="block text-xs text-slate-500 dark:text-slate-400">{note}</span>}
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
