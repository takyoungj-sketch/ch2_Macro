import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  COLLECTIVE_EXPERIMENT_MODE,
  downloadBuildingTransactionsCsv,
  downloadCohortTransactionsCsv,
  fetchAllBuildingTransactions,
  fetchAllCohortTransactions,
  fetchBuildingHistogram,
  fetchBuildingRollingStats,
  fetchBuildingYearlyStats,
  fetchDanjiAttributes,
  fetchRelatedPresaleAnnual,
  fetchCohortHistogram,
  type BuildingStatsRow,
} from "../api/client";
import type {
  AssetSelectorType,
  AssetType,
  DanjiAttributesResponse,
  DanjiQualityFlag,
} from "../types";
import { assetTypeLabel } from "../types";
import BuildingRegressionPanel from "./BuildingRegressionPanel";
import CohortTrendPanel from "./CohortTrendPanel";
import CollectiveTransactionTable from "./CollectiveTransactionTable";
import DraggableModalShell from "./DraggableModalShell";
import FloorIndexPanel from "./FloorIndexPanel";
import HistogramChart from "./HistogramChart";
import type { CohortTrendMetric } from "./MultiBuildingTrendChart";
import RollingTrendChart from "./RollingTrendChart";
import YearlyTrendChart, { yearlyPointPrice } from "./YearlyTrendChart";
import LongTermMetricToggle, { longTermPriceLabel, type LongTermPriceMetric } from "./LongTermMetricToggle";
import type { StatsWindowYears } from "./StatsWindowToggle";
import { buildAnalysisPeriodParams, formatPeriodLabel, type AnalysisPeriodParams } from "../utils/analysisPeriod";
import { rollingToTrendSeries, yearlyResponseToTrendSeries } from "../utils/cohortTrendSeries";

type PanelMode =
  | "trend"
  | "long_term"
  | "histogram"
  | "transactions"
  | "floor_index"
  | "regression"
  | "danji";

const MAX_COHORT_BUILDINGS = 10;

function defaultBuildingDetailSize(): { width: number; height: number } {
  if (typeof window === "undefined") return { width: 896, height: 640 };
  return {
    width: Math.min(896, window.innerWidth - 32),
    height: Math.min(Math.round(window.innerHeight * 0.85), Math.max(520, window.innerHeight - 48)),
  };
}

const TABS: { id: PanelMode; label: string | ((assetType: AssetType) => string) }[] = [
  { id: "trend", label: "롤링 구간" },
  { id: "histogram", label: "단가 분포" },
  { id: "transactions", label: "거래 목록" },
  { id: "floor_index", label: (t) => (t === "presale" ? "층·권리·면적 효용지수" : "층·동·면적 효용지수") },
  { id: "regression", label: "회귀 분석" },
  { id: "long_term", label: "장기 추세" },
];

/** K-apt 단지 속성 — 실험 단계에서만 노출 */
const DANJI_TAB: { id: PanelMode; label: string } = { id: "danji", label: "단지 정보" };

function fmtPrice(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

const DANJI_SECTION_TITLE = "text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-3 pt-3 pb-1";
const DANJI_TH = "border px-2 py-1.5 text-left font-medium w-[38%]";
const DANJI_TD = "border px-2 py-1 text-slate-800 dark:text-slate-100";

function danjiText(v: string | null | undefined) {
  return v == null || v === "" ? "—" : v;
}

function danjiNumber(v: number | null | undefined, maximumFractionDigits = 0) {
  if (v == null) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits });
}

/** 품질 플래그가 지목한 필드는 값 옆에 경고를 붙여 회귀 결측 처리를 알린다. */
function DanjiFieldWarning({ flags }: { flags: DanjiQualityFlag[] }) {
  if (flags.length === 0) return null;
  const detail = flags.map((f) => (f.detail ? `${f.label}: ${f.detail}` : f.label)).join(" / ");
  return (
    <span
      className="ml-1 text-[10px] font-semibold text-amber-600 dark:text-amber-400"
      title={`${detail} — 이 값은 회귀에서 결측으로 처리됩니다.`}
    >
      ⚠ 결측
    </span>
  );
}

function DanjiBadge({ label, tone }: { label: string; tone: "slate" | "amber" }) {
  return (
    <span
      className={clsx(
        "ml-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border",
        tone === "amber"
          ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/50 dark:bg-amber-500/10 dark:text-amber-300"
          : "border-slate-300 bg-slate-50 text-slate-600 dark:border-slate-500 dark:bg-slate-700/50 dark:text-slate-200",
      )}
    >
      {label}
    </span>
  );
}

function DanjiNotes({ notes }: { notes: string[] }) {
  if (notes.length === 0) return null;
  return (
    <ul className="space-y-0.5 text-[10px] text-slate-500 dark:text-slate-400">
      {notes.map((n) => (
        <li key={n}>· {n}</li>
      ))}
    </ul>
  );
}

function DanjiAttributesPanel({ data }: { data: DanjiAttributesResponse }) {
  const { match, builder, brand, scale, structure, classification } = data;
  const risky = !match.usable_for_regression;
  const flagsByField = new Map<string, DanjiQualityFlag[]>();
  for (const flag of data.quality_flags) {
    for (const field of flag.affected_fields ?? []) {
      flagsByField.set(field, [...(flagsByField.get(field) ?? []), flag]);
    }
  }
  const fieldFlags = (field: string) => flagsByField.get(field) ?? [];

  const banner = (
    <div
      className={clsx(
        "rounded border px-2 py-1.5 text-[10px] space-y-0.5",
        risky
          ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/50 dark:bg-amber-500/10 dark:text-amber-300"
          : "border-slate-200 bg-slate-50/80 text-slate-600 dark:border-slate-600 dark:bg-slate-800/40 dark:text-slate-300",
      )}
    >
      <p>
        <span className="font-semibold">{data.source_label}</span>
        <span> · 매칭 {match.tier_label}</span>
        <span>
          {" "}
          (tier {match.tier}/{match.rule})
        </span>
        <span> · 신뢰도 {match.reliability}</span>
        {data.dictionary_version && <span> · 사전 {data.dictionary_version}</span>}
      </p>
      {data.matched && (
        <p>
          K-apt 단지 {danjiText(match.danji_name)}
          {match.danji_code ? ` (${match.danji_code})` : ""} · 사용승인{" "}
          {danjiNumber(match.approved_year)}년 · 실거래 건축 {danjiNumber(match.building_year)}년
          {match.year_diff != null ? ` (차이 ${match.year_diff}년)` : ""}
        </p>
      )}
      {match.note && <p>{match.note}</p>}
    </div>
  );

  if (!data.matched) {
    return (
      <div className="space-y-3">
        {banner}
        <div className="modal-card px-3 py-3 space-y-1.5">
          <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-200">
            연결된 K-apt 단지 정보가 없습니다
          </p>
          <p className="text-[11px] text-slate-600 dark:text-slate-300">
            {match.note ?? match.tier_label}
          </p>
          {brand?.name && (
            <p className="text-[11px] text-slate-700 dark:text-slate-200">
              브랜드 <span className="font-semibold">{brand.name}</span>
              {brand.confidence && (
                <DanjiBadge
                  label={`신뢰도 ${brand.confidence}`}
                  tone={brand.confidence === "low" ? "amber" : "slate"}
                />
              )}
              {brand.detected_from ? ` · 출처 ${brand.detected_from}` : ""}
            </p>
          )}
          <DanjiNotes notes={data.notes} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {banner}

      {data.quality_flags.length > 0 && (
        <div className="rounded border border-amber-300 bg-amber-50 px-2 py-1.5 dark:border-amber-500/50 dark:bg-amber-500/10">
          <p className="text-[10px] font-semibold text-amber-800 dark:text-amber-300">
            K-apt 원본 이상값 {data.quality_flags.length}건 — 값은 원본 그대로 표시합니다
          </p>
          <ul className="mt-1 space-y-0.5 text-[10px] text-amber-800 dark:text-amber-200">
            {data.quality_flags.map((flag) => (
              <li key={flag.code}>
                <span className="font-semibold">{flag.label}</span>
                {flag.detail ? ` — ${flag.detail}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="modal-table-wrap">
        <p className={DANJI_SECTION_TITLE}>
          시공사·브랜드
          {builder?.is_joint && <DanjiBadge label="공동시공" tone="amber" />}
          {(builder?.is_public || brand?.is_public) && <DanjiBadge label="공공 공급주체" tone="amber" />}
        </p>
        <table className="w-full text-xs border-collapse modal-inner-table">
          <tbody>
            <tr>
              <th className={DANJI_TH}>시공사 원문 (K-apt)</th>
              <td className={DANJI_TD}>{danjiText(builder?.raw)}</td>
            </tr>
            <tr>
              <th className={DANJI_TH}>시공사 표기 정규화</th>
              <td className={DANJI_TD}>{danjiText(builder?.norm)}</td>
            </tr>
            <tr>
              <th className={DANJI_TH}>시공사 기업집단 (분석 단위)</th>
              <td className={DANJI_TD}>{danjiText(builder?.group)}</td>
            </tr>
            <tr>
              <th className={DANJI_TH}>시행사 원문 (K-apt)</th>
              <td className={DANJI_TD}>{danjiText(builder?.developer_raw)}</td>
            </tr>
            <tr>
              <th className={DANJI_TH}>브랜드</th>
              <td className={DANJI_TD}>
                {danjiText(brand?.name)}
                {brand?.confidence && <DanjiBadge label={`신뢰도 ${brand.confidence}`} tone={brand.confidence === "low" ? "amber" : "slate"} />}
              </td>
            </tr>
            <tr>
              <th className={DANJI_TH}>브랜드 검출 출처</th>
              <td className={DANJI_TD}>{danjiText(brand?.detected_from)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="modal-table-wrap">
        <p className={DANJI_SECTION_TITLE}>규모·구조</p>
        <table className="w-full text-xs border-collapse modal-inner-table">
          <tbody>
            <tr>
              <th className={DANJI_TH}>세대수</th>
              <td className={clsx(DANJI_TD, "tabular-nums")}>
                {danjiNumber(scale?.households)}
                <DanjiFieldWarning flags={fieldFlags("households")} />
              </td>
            </tr>
            <tr>
              <th className={DANJI_TH}>분양 세대수</th>
              <td className={clsx(DANJI_TD, "tabular-nums")}>{danjiNumber(scale?.households_sale)}</td>
            </tr>
            <tr>
              <th className={DANJI_TH}>임대 세대수</th>
              <td className={clsx(DANJI_TD, "tabular-nums")}>{danjiNumber(scale?.households_rent)}</td>
            </tr>
            <tr>
              <th className={DANJI_TH}>동수</th>
              <td className={clsx(DANJI_TD, "tabular-nums")}>
                {danjiNumber(scale?.dong_count)}
                <DanjiFieldWarning flags={fieldFlags("dong_count")} />
              </td>
            </tr>
            <tr>
              <th className={DANJI_TH}>최고층수</th>
              <td className={clsx(DANJI_TD, "tabular-nums")}>
                {danjiNumber(scale?.max_floor)}
                <DanjiFieldWarning flags={fieldFlags("max_floor")} />
              </td>
            </tr>
            <tr>
              <th className={DANJI_TH}>총 주차대수</th>
              <td className={clsx(DANJI_TD, "tabular-nums")}>
                {danjiNumber(scale?.parking_total)}
                <DanjiFieldWarning flags={fieldFlags("parking_total")} />
              </td>
            </tr>
            <tr>
              <th className={DANJI_TH}>세대당 주차</th>
              <td className={clsx(DANJI_TD, "tabular-nums")}>
                {danjiNumber(scale?.parking_per_household, 3)}
                <DanjiFieldWarning flags={fieldFlags("parking_per_household")} />
              </td>
            </tr>
            <tr>
              <th className={DANJI_TH}>구조</th>
              <td className={DANJI_TD}>
                {danjiText(structure?.raw)}
                {structure?.group && <DanjiBadge label={structure.group} tone="slate" />}
              </td>
            </tr>
            <tr>
              <th className={DANJI_TH}>단지분류</th>
              <td className={DANJI_TD}>{danjiText(classification?.danji_class)}</td>
            </tr>
            <tr>
              <th className={DANJI_TH}>공급형태</th>
              <td className={DANJI_TD}>{danjiText(classification?.supply_type)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <DanjiNotes notes={data.notes} />
    </div>
  );
}

async function txExportErrorMessage(err: unknown): Promise<string> {
  const ax = err as { response?: { data?: Blob | { detail?: string } } };
  const data = ax.response?.data;
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text()) as { detail?: string };
      if (parsed.detail) return String(parsed.detail);
    } catch {
      /* ignore */
    }
  } else if (data && typeof data === "object" && "detail" in data && data.detail) {
    return String(data.detail);
  }
  return "CSV 내보내기에 실패했습니다.";
}

export default function BuildingDetailModal({
  row,
  assetType,
  windowYears = 5,
  yearFrom,
  yearTo,
  periodStart,
  periodEnd,
  statsAsOfLabel,
  peerBuildings = [],
  onClose,
}: {
  row: BuildingStatsRow;
  assetType: AssetSelectorType;
  windowYears?: StatsWindowYears;
  yearFrom?: number;
  yearTo?: number;
  periodStart?: string | null;
  periodEnd?: string | null;
  statsAsOfLabel?: string | null;
  peerBuildings?: BuildingStatsRow[];
  onClose: () => void;
}) {
  const effectiveAssetType = (
    assetType === "all" || assetType.includes(",") ? row.asset_type : assetType
  ) as AssetType;
  const analysisPeriod: AnalysisPeriodParams = useMemo(
    () => buildAnalysisPeriodParams(yearFrom, yearTo, periodStart, periodEnd),
    [yearFrom, yearTo, periodStart, periodEnd],
  );
  const periodLabel = formatPeriodLabel(periodStart, periodEnd);
  const usesMartPeriod = Boolean(analysisPeriod.contract_date_from && analysisPeriod.contract_date_to);
  const [panel, setPanel] = useState<PanelMode>("trend");
  const [cohortExtra, setCohortExtra] = useState<string[]>([]);
  const [cohortRunKeys, setCohortRunKeys] = useState<string[]>([]);
  const [cohortRunByPanel, setCohortRunByPanel] = useState<Partial<Record<PanelMode, number>>>({});
  const [histScope, setHistScope] = useState<"all" | "single">("all");
  const [histYear, setHistYear] = useState<number | null>(null);
  const [txExportLoading, setTxExportLoading] = useState(false);
  const [txExportError, setTxExportError] = useState<string | null>(null);
  const [cohortChartMetric, setCohortChartMetric] = useState<CohortTrendMetric>("mean");
  const [longTermMetric, setLongTermMetric] = useState<LongTermPriceMetric>("mean");
  const [defaultSize] = useState(defaultBuildingDetailSize);
  const [presaleOverlay, setPresaleOverlay] = useState<{ key: string; name: string }[]>([]);
  const [showPresalePicker, setShowPresalePicker] = useState(false);
  const experiment = COLLECTIVE_EXPERIMENT_MODE;
  /** 준공 거주유형(아파트·연립·오피스텔) — 분양권 본인 모달에는 불필요 */
  const canAttachPresaleAnnual = effectiveAssetType !== "presale";

  const cohortKeys = useMemo(
    () => [row.building_key, ...cohortExtra.filter((k) => k !== row.building_key)].slice(0, MAX_COHORT_BUILDINGS),
    [row.building_key, cohortExtra],
  );
  const cohortStale =
    Object.keys(cohortRunByPanel).length > 0 &&
    (cohortRunKeys.length !== cohortKeys.length || cohortRunKeys.some((k, i) => k !== cohortKeys[i]));
  const canRunCohort = cohortKeys.length > 1;
  const cohortRunForPanel = (p: PanelMode) => (cohortStale ? 0 : cohortRunByPanel[p] ?? 0);

  const cohortBody = useMemo(
    () => ({
      building_keys: cohortRunKeys,
      asset_type: assetType === "all" || assetType.includes(",") ? undefined : effectiveAssetType,
      experiment,
      ...analysisPeriod,
    }),
    [cohortRunKeys, assetType, effectiveAssetType, experiment, analysisPeriod],
  );
  const peerOptions = useMemo(
    () => peerBuildings.filter((b) => b.building_key !== row.building_key && !cohortExtra.includes(b.building_key)),
    [peerBuildings, row.building_key, cohortExtra],
  );

  const rollingQ = useQuery({
    queryKey: ["b-rolling", row.building_key, windowYears],
    queryFn: () => fetchBuildingRollingStats(row.building_key, windowYears),
    enabled: cohortRunForPanel("trend") === 0 && panel === "trend",
  });

  const longTermYearQ = useQuery({
    queryKey: ["b-year-long", row.building_key],
    queryFn: () => fetchBuildingYearlyStats(row.building_key),
    enabled: cohortRunForPanel("long_term") === 0 && panel === "long_term",
  });

  const windowYearQ = useQuery({
    queryKey: ["b-year-window", row.building_key, analysisPeriod],
    queryFn: () =>
      fetchBuildingYearlyStats(row.building_key, {
        contract_date_from: analysisPeriod.contract_date_from,
        contract_date_to: analysisPeriod.contract_date_to,
      }),
    enabled: cohortRunForPanel("histogram") === 0 && panel === "histogram",
  });

  const histYears = useMemo(
    () => [...(windowYearQ.data?.points ?? [])].sort((a, b) => a.year - b.year),
    [windowYearQ.data?.points],
  );

  const longTermYears = useMemo(
    () => [...(longTermYearQ.data?.points ?? [])].sort((a, b) => a.year - b.year),
    [longTermYearQ.data?.points],
  );

  useEffect(() => {
    if (histYears.length && histYear == null) {
      setHistYear(histYears[histYears.length - 1].year);
    }
  }, [histYears, histYear]);

  const histQ = useQuery({
    queryKey: ["b-hist", row.building_key, histScope, histScope === "single" ? histYear : null, analysisPeriod],
    queryFn: () =>
      fetchBuildingHistogram(row.building_key, {
        contract_year: histScope === "single" && histYear != null ? histYear : undefined,
        ...analysisPeriod,
      }),
    enabled: cohortRunForPanel("histogram") === 0,
  });

  const txQ = useQuery({
    queryKey: ["b-tx-all", row.building_key, analysisPeriod],
    queryFn: () => fetchAllBuildingTransactions(row.building_key, analysisPeriod),
    enabled: cohortRunForPanel("transactions") === 0 && panel === "transactions",
  });

  const cohortTxQ = useQuery({
    queryKey: ["cohort-tx-all", cohortRunKeys, cohortRunForPanel("transactions"), analysisPeriod],
    queryFn: () => fetchAllCohortTransactions(cohortBody),
    enabled:
      cohortRunForPanel("transactions") > 0 && cohortRunKeys.length > 1 && panel === "transactions",
  });

  const cohortRollingQ = useQuery({
    queryKey: ["cohort-rolling", cohortRunKeys, windowYears, cohortRunForPanel("trend")],
    queryFn: async () => Promise.all(cohortRunKeys.map((k) => fetchBuildingRollingStats(k, windowYears))),
    enabled: cohortRunForPanel("trend") > 0 && cohortRunKeys.length > 1 && panel === "trend",
  });

  const cohortLongTermQ = useQuery({
    queryKey: ["cohort-year-long", cohortRunKeys, cohortRunForPanel("long_term")],
    queryFn: async () => Promise.all(cohortRunKeys.map((k) => fetchBuildingYearlyStats(k))),
    enabled: cohortRunForPanel("long_term") > 0 && cohortRunKeys.length > 1 && panel === "long_term",
  });

  const danjiQ = useQuery({
    queryKey: ["b-danji-attrs", row.building_key],
    queryFn: () => fetchDanjiAttributes(row.building_key),
    enabled: experiment && panel === "danji",
  });

  const relatedPresaleQ = useQuery({
    queryKey: ["related-presale", row.building_key],
    queryFn: () => fetchRelatedPresaleAnnual(row.building_key),
    enabled: showPresalePicker && canAttachPresaleAnnual && panel === "long_term",
  });

  const presaleOverlayQ = useQuery({
    queryKey: ["presale-overlay-year", row.building_key, presaleOverlay.map((p) => p.key)],
    queryFn: async () =>
      Promise.all(
        presaleOverlay.map(async (p) => {
          const data = await fetchBuildingYearlyStats(p.key);
          return { ...data, display_name: `분양권 · ${p.name || data.display_name}` };
        }),
      ),
    enabled:
      cohortRunForPanel("long_term") === 0 &&
      presaleOverlay.length > 0 &&
      panel === "long_term",
  });

  const overlayLongTermSeries = useMemo(() => {
    if (!longTermYearQ.data || !presaleOverlayQ.data?.length) return null;
    return [
      yearlyResponseToTrendSeries(longTermYearQ.data),
      ...presaleOverlayQ.data.map(yearlyResponseToTrendSeries),
    ];
  }, [longTermYearQ.data, presaleOverlayQ.data]);

  const cohortHistQ = useQuery({
    queryKey: [
      "cohort-hist",
      cohortRunKeys,
      cohortRunForPanel("histogram"),
      histScope,
      histScope === "single" ? histYear : null,
      analysisPeriod,
    ],
    queryFn: () =>
      fetchCohortHistogram(cohortBody, {
        contract_year: histScope === "single" && histYear != null ? histYear : undefined,
      }),
    enabled: cohortRunForPanel("histogram") > 0 && cohortRunKeys.length > 1,
  });

  useEffect(() => {
    setPanel("trend");
    setTxExportError(null);
    setHistScope("all");
    setCohortExtra([]);
    setCohortRunKeys([]);
    setCohortRunByPanel({});
    setCohortChartMetric("mean");
    setPresaleOverlay([]);
    setShowPresalePicker(false);
  }, [row.building_key]);

  const runCohortAnalysis = () => {
    if (!canRunCohort) return;
    setCohortRunKeys([...cohortKeys]);
    setCohortRunByPanel((prev) => ({ ...prev, [panel]: (prev[panel] ?? 0) + 1 }));
  };

  const addToCohort = (buildingKey: string) => {
    if (cohortKeys.length >= MAX_COHORT_BUILDINGS) return;
    setCohortExtra((prev) => (prev.includes(buildingKey) ? prev : [...prev, buildingKey]));
  };


  const analysis = row.analysis ?? {
    floor_index: row.count >= 50,
    regression: row.count >= 30,
    count_total: row.count,
    count_recent: 0,
    messages: [],
  };
  const gateTip =
    analysis.messages.join(" ") ||
    "선택 연도 구간 거래건수가 부족하여 통계 분석을 제공하지 않습니다.";

  const trendCohortActive = cohortRunForPanel("trend") > 0;
  const longTermCohortActive = cohortRunForPanel("long_term") > 0;
  const histCohortActive = cohortRunForPanel("histogram") > 0;
  const txCohortActive = cohortRunForPanel("transactions") > 0;

  const handleTxExport = async () => {
    setTxExportLoading(true);
    setTxExportError(null);
    try {
      if (txCohortActive && cohortRunKeys.length > 1) {
        await downloadCohortTransactionsCsv(cohortBody);
      } else {
        await downloadBuildingTransactionsCsv(row.building_key, analysisPeriod);
      }
    } catch (err) {
      setTxExportError(await txExportErrorMessage(err));
    } finally {
      setTxExportLoading(false);
    }
  };

  const txExportButton = (
    <button
      type="button"
      disabled={txExportLoading}
      onClick={() => void handleTxExport()}
      className="shrink-0 px-2.5 py-1 rounded border border-slate-200 text-[11px] font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
    >
      {txExportLoading ? "내보내는 중…" : "CSV 내보내기"}
    </button>
  );

  return (
    <DraggableModalShell
      open={true}
      onClose={onClose}
      titleId="building-detail-modal-title"
      title={row.display_name}
      subtitle={
        <>
          {assetTypeLabel(effectiveAssetType)} · n={row.count.toLocaleString("ko-KR")} · 평균 {fmtPrice(row.mean)}{" "}
          만원/㎡
          {usesMartPeriod && periodLabel && (
            <span className="ml-1.5 text-indigo-600 dark:text-indigo-400">
              · 분석 {periodLabel}
              {statsAsOfLabel ? ` (${statsAsOfLabel})` : ""}
            </span>
          )}
          {(yearFrom != null || yearTo != null) && (
            <span className="ml-1.5 text-indigo-600 dark:text-indigo-400">
              · 연도 {yearFrom ?? "…"}–{yearTo ?? "…"}
            </span>
          )}
          {experiment && <span className="ml-1.5 text-indigo-600 font-medium">· 실험 모드</span>}
        </>
      }
      headerExtra={
        <>
          <div
            className="flex flex-wrap gap-0.5 rounded-md border modal-tab-bar p-0.5"
            role="tablist"
          >
            {[...TABS, ...(experiment ? [DANJI_TAB] : [])].map(({ id, label }) => {
              const tabLabel = typeof label === "function" ? label(effectiveAssetType) : label;
              const needsGate = id === "floor_index" || id === "regression";
              const eligible =
                id === "floor_index" ? analysis.floor_index : id === "regression" ? analysis.regression : true;
              const showWarn = needsGate && !eligible && !experiment;
              return (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={panel === id}
                  title={showWarn ? gateTip : undefined}
                  className={clsx(
                    "px-2 py-1 text-[11px] font-medium rounded transition-colors whitespace-nowrap",
                    panel === id
                      ? "modal-tab-active"
                      : "modal-tab-idle",
                    showWarn && panel !== id && "text-amber-700",
                  )}
                  onClick={() => setPanel(id)}
                >
                  {tabLabel}
                  {showWarn && <span className="ml-0.5 text-[9px]">*</span>}
                </button>
              );
            })}
          </div>
          {peerBuildings.length > 0 && (
            <div className="mt-2 rounded border border-indigo-100 bg-indigo-50/50 px-2 py-1.5 text-[10px]">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-indigo-800">분석 코호트</span>
                <span className="text-slate-600">
                  {cohortKeys.length === 1 ? "단일 단지" : `${cohortKeys.length}개 단지`}
                </span>
                {canRunCohort && (
                  <button
                    type="button"
                    className="ml-auto px-2 py-0.5 rounded bg-indigo-700 text-white text-[10px] font-semibold hover:bg-indigo-800 disabled:opacity-50"
                    title="현재 탭 기준 실시간 통합 분석"
                    onClick={runCohortAnalysis}
                  >
                    통합분석
                  </button>
                )}
              </div>
              {cohortStale && (
                <p className="mt-1 text-amber-700">코호트가 변경되었습니다. 「통합분석」을 다시 실행하세요.</p>
              )}
              {cohortKeys.length >= MAX_COHORT_BUILDINGS && (
                <p className="mt-1 text-slate-500">최대 {MAX_COHORT_BUILDINGS}개 단지까지 포함할 수 있습니다.</p>
              )}
              {cohortExtra.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {cohortExtra.map((k) => {
                    const label = peerBuildings.find((b) => b.building_key === k)?.display_name ?? k.slice(0, 8);
                    return (
                      <button
                        key={k}
                        type="button"
                        className="px-1.5 py-0.5 rounded bg-white border border-indigo-200 text-indigo-700"
                        onClick={() => setCohortExtra((prev) => prev.filter((x) => x !== k))}
                        title="코호트에서 제거"
                      >
                        {label} ×
                      </button>
                    );
                  })}
                </div>
              )}
              {peerOptions.length > 0 && (
                <label className="mt-1 flex items-center gap-1 text-slate-600">
                  <span>+ 단지 추가</span>
                  <select
                    className="text-[10px] border border-slate-200 rounded px-1 py-0.5 max-w-[180px]"
                    defaultValue=""
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v) addToCohort(v);
                      e.target.value = "";
                    }}
                    disabled={cohortKeys.length >= MAX_COHORT_BUILDINGS}
                  >
                    <option value="">선택…</option>
                    {peerOptions.slice(0, 80).map((b) => (
                      <option key={b.building_key} value={b.building_key}>
                        {b.display_name} (n={b.count})
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          )}
        </>
      }
      resizable
      zClassName="z-[100]"
      backdropClassName="bg-black/35"
      defaultWidth={defaultSize.width}
      defaultHeight={defaultSize.height}
      maxWidthClass="max-w-4xl"
      minWidth={480}
      minHeight={360}
      bodyClassName="flex-1 min-h-0 overflow-auto px-4 py-3 space-y-4"
    >
          {panel === "trend" && (
            <>
              {trendCohortActive && cohortRollingQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">코호트 롤링 구간 집계 중…</p>
              )}
              {trendCohortActive && cohortRollingQ.isError && (
                <p className="text-xs text-amber-700 text-center py-6">
                  {String(
                    (cohortRollingQ.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                      "통합 롤링 추세를 불러오지 못했습니다.",
                  )}
                </p>
              )}
              {trendCohortActive && cohortRollingQ.data && (
                <CohortTrendPanel
                  series={cohortRollingQ.data.map(rollingToTrendSeries)}
                  metric={cohortChartMetric}
                  onMetricChange={setCohortChartMetric}
                  buildingCount={cohortRunKeys.length}
                  chartTitle="12개월 롤링 버킷 추이 (꺾은선)"
                  note={
                    cohortRollingQ.data[0]?.stats_as_of_label
                      ? `${cohortRollingQ.data[0].stats_as_of_label}${cohortRollingQ.data[0].window_years ? ` · ${cohortRollingQ.data[0].window_years}년 창` : ""}`
                      : undefined
                  }
                />
              )}
              {!trendCohortActive && panel === "trend" && rollingQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">롤링 구간 집계 중…</p>
              )}
              {!trendCohortActive && panel === "trend" && rollingQ.isError && (
                <p className="text-xs text-amber-700 dark:text-amber-400 text-center py-6">롤링 추세를 불러오지 못했습니다.</p>
              )}
              {!trendCohortActive && panel === "trend" && rollingQ.data && rollingQ.data.points.length > 0 && (
                <>
                  {rollingQ.data.stats_as_of_label && (
                    <p className="text-[10px] text-indigo-600 dark:text-indigo-400 mb-1">
                      {rollingQ.data.stats_as_of_label}
                      {rollingQ.data.window_years ? ` · ${rollingQ.data.window_years}년 창` : ""}
                    </p>
                  )}
                  <div className="modal-card px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-1 mb-2">12개월 롤링 버킷 추이</p>
                    <RollingTrendChart points={rollingQ.data.points} />
                  </div>
                  <div className="modal-table-wrap">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-3 pt-3 pb-1">구간별 수치</p>
                    <table className="w-full text-xs border-collapse modal-inner-table">
                      <thead>
                        <tr>
                          <th className="border px-2 py-1.5 text-left font-medium">구간</th>
                          <th className="border px-2 py-1.5 text-right font-medium">건수</th>
                          <th className="border px-2 py-1.5 text-right font-bold text-blue-700 dark:text-blue-400">
                            평균(만원/㎡)
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...rollingQ.data.points].sort((a, b) => a.bucket_index - b.bucket_index).map((p) => (
                          <tr key={p.bucket_index}>
                            <td className="border px-2 py-1 tabular-nums">{p.label}</td>
                            <td className="border px-2 py-1 text-right tabular-nums">
                              {p.count.toLocaleString("ko-KR")}
                            </td>
                            <td className="border px-2 py-1 text-right tabular-nums text-blue-600 dark:text-blue-400 font-bold">
                              {p.mean != null ? fmtPrice(p.mean) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {!trendCohortActive && panel === "trend" && rollingQ.data && rollingQ.data.points.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-6">표시할 롤링 데이터가 없습니다.</p>
              )}
            </>
          )}

          {panel === "long_term" && (
            <>
              {canAttachPresaleAnnual && !longTermCohortActive && (
                <div className="mb-2 rounded border border-slate-200 dark:border-slate-600 bg-slate-50/80 dark:bg-slate-800/40 px-2 py-1.5 text-[10px]">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-700 dark:text-slate-200">과거 분양권 추세</span>
                    <span className="text-slate-500">
                      아파트·연립·오피스텔에서 관련 분양권 annual을 겹쳐 봅니다 (자동 병합 없음)
                    </span>
                    <button
                      type="button"
                      className="ml-auto px-2 py-0.5 rounded border border-slate-300 dark:border-slate-500 text-slate-700 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-700"
                      onClick={() => setShowPresalePicker((v) => !v)}
                    >
                      {showPresalePicker ? "후보 닫기" : "후보 찾기"}
                    </button>
                  </div>
                  {presaleOverlay.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {presaleOverlay.map((p) => (
                        <button
                          key={p.key}
                          type="button"
                          className="px-1.5 py-0.5 rounded bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-500 text-slate-700 dark:text-slate-200"
                          onClick={() => setPresaleOverlay((prev) => prev.filter((x) => x.key !== p.key))}
                          title="제거"
                        >
                          분양권 · {p.name} ×
                        </button>
                      ))}
                    </div>
                  )}
                  {showPresalePicker && relatedPresaleQ.isLoading && (
                    <p className="mt-1 text-slate-400">후보 검색 중…</p>
                  )}
                  {showPresalePicker && relatedPresaleQ.isError && (
                    <p className="mt-1 text-amber-700">관련 분양권을 불러오지 못했습니다.</p>
                  )}
                  {showPresalePicker && relatedPresaleQ.data && (
                    <div className="mt-1 max-h-36 overflow-y-auto space-y-0.5">
                      {relatedPresaleQ.data.candidates.length === 0 ? (
                        <p className="text-slate-400">같은 시군구에서 이름 유사 분양권 annual이 없습니다.</p>
                      ) : (
                        relatedPresaleQ.data.candidates.map((c) => {
                          const added = presaleOverlay.some((p) => p.key === c.building_key);
                          return (
                            <button
                              key={c.building_key}
                              type="button"
                              disabled={added || (presaleOverlay.length + 1 >= MAX_COHORT_BUILDINGS)}
                              className="w-full text-left px-1.5 py-1 rounded hover:bg-white dark:hover:bg-slate-700 disabled:opacity-40"
                              onClick={() =>
                                setPresaleOverlay((prev) =>
                                  prev.some((p) => p.key === c.building_key)
                                    ? prev
                                    : [...prev, { key: c.building_key, name: c.display_name }],
                                )
                              }
                            >
                              <span className="font-medium text-slate-800 dark:text-slate-100">{c.display_name}</span>
                              <span className="ml-1 text-slate-500">
                                {c.year_from}–{c.year_to} · n={c.total_count.toLocaleString("ko-KR")}
                                {c.addr3 ? ` · ${c.addr3}` : ""}
                              </span>
                            </button>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              )}
              {longTermCohortActive && cohortLongTermQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">코호트 연도별 집계 중…</p>
              )}
              {longTermCohortActive && cohortLongTermQ.isError && (
                <p className="text-xs text-amber-700 text-center py-6">
                  {String(
                    (cohortLongTermQ.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                      "통합 장기 추세를 불러오지 못했습니다.",
                  )}
                </p>
              )}
              {longTermCohortActive && cohortLongTermQ.data && (
                <CohortTrendPanel
                  series={cohortLongTermQ.data.map(yearlyResponseToTrendSeries)}
                  metric={cohortChartMetric}
                  onMetricChange={setCohortChartMetric}
                  buildingCount={cohortRunKeys.length}
                  chartTitle="연도별 추이 (꺾은선)"
                  note="만년력 · 롤링 통계 창과 기간·표본이 다를 수 있음"
                  variant="longTerm"
                  priceMetric={longTermMetric}
                  onPriceMetricChange={setLongTermMetric}
                />
              )}
              {!longTermCohortActive && overlayLongTermSeries && (
                <CohortTrendPanel
                  series={overlayLongTermSeries}
                  metric={cohortChartMetric}
                  onMetricChange={setCohortChartMetric}
                  buildingCount={overlayLongTermSeries.length}
                  chartTitle="연도별 추이 (본단지 + 분양권)"
                  note="분양권은 annual mart(2010–) · 키는 분리된 sibling 비교"
                  variant="longTerm"
                  priceMetric={longTermMetric}
                  onPriceMetricChange={setLongTermMetric}
                />
              )}
              {!longTermCohortActive &&
                !overlayLongTermSeries &&
                presaleOverlay.length > 0 &&
                (longTermYearQ.isLoading || presaleOverlayQ.isLoading) && (
                <p className="text-xs text-slate-400 text-center py-6">본단지·분양권 연도별 집계 중…</p>
              )}
              {!longTermCohortActive && !overlayLongTermSeries && !presaleOverlay.length && longTermYearQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">연도별 집계 중…</p>
              )}
              {!longTermCohortActive && !overlayLongTermSeries && !presaleOverlay.length && !longTermYearQ.isLoading && longTermYears.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-6">표시할 연도별 데이터가 없습니다.</p>
              )}
              {!longTermCohortActive && !overlayLongTermSeries && !presaleOverlay.length && longTermYears.length > 0 && (
                <>
                  {longTermYears.some((p) => p.year < 2021) && (
                    <p className="text-[10px] text-indigo-600 dark:text-indigo-400 mb-1">
                      2010–2020 구간 포함 · {longTermYearQ.data?.data_source === "mart" ? "annual mart" : "실시간 집계"}
                    </p>
                  )}
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <p className="text-[10px] text-slate-500 dark:text-slate-400">
                      만년력 연도별 추이 · 롤링 통계 창({periodLabel ?? "5년"})과 기간·표본이 다릅니다.
                    </p>
                    <LongTermMetricToggle metric={longTermMetric} onChange={setLongTermMetric} />
                  </div>
                  <div className="modal-card px-2 py-3">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-1 mb-2">추이 (꺾은선)</p>
                    <YearlyTrendChart points={longTermYears} metric={longTermMetric} />
                  </div>
                  <div className="modal-table-wrap">
                    <p className="text-[10px] font-semibold text-slate-600 dark:text-slate-300 px-3 pt-3 pb-1">연도별 수치</p>
                    <table className="w-full text-xs border-collapse modal-inner-table">
                      <thead>
                        <tr>
                          <th className="border px-2 py-1.5 text-left font-medium">연도</th>
                          <th className="border px-2 py-1.5 text-right font-medium">건수</th>
                          <th className="border px-2 py-1.5 text-right font-bold text-blue-700 dark:text-blue-400">
                            {longTermPriceLabel(longTermMetric)}(만원/㎡)
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {longTermYears.map((p) => (
                          <tr key={p.year}>
                            <td className="border px-2 py-1 tabular-nums">{p.year}</td>
                            <td className="border px-2 py-1 text-right tabular-nums">
                              {p.count.toLocaleString("ko-KR")}
                            </td>
                            <td className="border px-2 py-1 text-right tabular-nums text-blue-600 dark:text-blue-400 font-bold">
                              {yearlyPointPrice(p, longTermMetric) != null ? fmtPrice(yearlyPointPrice(p, longTermMetric)!) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </>
          )}

          {panel === "histogram" && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="text-slate-500">표본 범위</span>
                <select
                  value={histScope}
                  onChange={(e) => setHistScope(e.target.value === "single" ? "single" : "all")}
                  className="modal-select"
                >
                  <option value="all">{usesMartPeriod ? "분석 구간 전체" : "전체 연도"}</option>
                  <option value="single">특정 연도만</option>
                </select>
                {histScope === "single" && (
                  <select
                    value={histYear ?? ""}
                    onChange={(e) => setHistYear(Number(e.target.value))}
                    className="modal-select"
                  >
                    {histYears.map((p) => (
                      <option key={p.year} value={p.year}>
                        {p.year} ({p.count.toLocaleString("ko-KR")}건)
                      </option>
                    ))}
                  </select>
                )}
              </div>
              {histCohortActive && cohortHistQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">코호트 분포 계산 중…</p>
              )}
              {histCohortActive && cohortHistQ.isError && (
                <p className="text-xs text-amber-700 text-center py-4">통합 분포를 불러오지 못했습니다.</p>
              )}
              {histCohortActive && cohortHistQ.data && (
                <>
                  <p className="text-[10px] text-indigo-700 bg-indigo-50 border border-indigo-100 rounded px-2 py-1">
                    {cohortRunKeys.length}개 단지 통합 · 실시간 · n={cohortHistQ.data.n.toLocaleString("ko-KR")}건
                  </p>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-2">
                    <HistogramChart bins={cohortHistQ.data.bins} />
                  </div>
                </>
              )}
              {!histCohortActive && histQ.isLoading && <p className="text-xs text-slate-400 text-center py-4">분포 계산 중…</p>}
              {!histCohortActive && histQ.isError && <p className="text-xs text-red-500 text-center py-4">분포를 불러오지 못했습니다.</p>}
              {!histCohortActive && histQ.data && (
                <>
                  <p className="text-[10px] text-slate-500">
                    표본 수 <strong className="text-slate-700">{histQ.data.n.toLocaleString("ko-KR")}</strong>건
                    {histScope === "single" && histYear != null && (
                      <>
                        {" "}
                        · 대상 연도 <strong className="text-slate-700">{histYear}</strong>
                      </>
                    )}
                    {histScope === "all" && usesMartPeriod && periodLabel && (
                      <span> · 분석 {periodLabel}</span>
                    )}
                  </p>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-2 py-2">
                    <HistogramChart bins={histQ.data.bins} />
                  </div>
                </>
              )}
            </div>
          )}

          {panel === "transactions" && (
            <div className="space-y-2 flex flex-col min-h-[360px]">
              {txCohortActive && cohortTxQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">코호트 목록 불러오는 중…</p>
              )}
              {txCohortActive && cohortTxQ.isError && (
                <p className="text-xs text-amber-700 text-center py-4">통합 거래 목록을 불러오지 못했습니다.</p>
              )}
              {txCohortActive && cohortTxQ.data && (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2 shrink-0">
                    <p className="text-[10px] text-indigo-700 bg-indigo-50 border border-indigo-100 rounded px-2 py-1">
                      {cohortRunKeys.length}개 단지 통합 · 실시간 · 전체 {cohortTxQ.data.total.toLocaleString("ko-KR")}건
                      {yearFrom != null || yearTo != null ? (
                        <span>
                          {" "}
                          · 연도 {yearFrom ?? "…"}–{yearTo ?? "…"}
                        </span>
                      ) : usesMartPeriod && periodLabel ? (
                        <span> · 분석 {periodLabel}</span>
                      ) : null}
                    </p>
                    {txExportButton}
                  </div>
                  {txExportError && <p className="text-[10px] text-red-500">{txExportError}</p>}
                  <CollectiveTransactionTable
                    items={cohortTxQ.data.items}
                    assetType={effectiveAssetType}
                    showBuilding
                    truncated={cohortTxQ.data.truncated}
                  />
                </>
              )}
              {!txCohortActive && txQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-4">목록 불러오는 중…</p>
              )}
              {!txCohortActive && txQ.isError && (
                <p className="text-xs text-red-500 text-center py-4">목록을 불러오지 못했습니다.</p>
              )}
              {!txCohortActive && txQ.data && (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2 shrink-0">
                    <p className="text-[10px] text-slate-500 dark:text-slate-400">
                      전체 <strong className="text-slate-700 dark:text-slate-200">{txQ.data.total.toLocaleString("ko-KR")}</strong>건
                      {yearFrom != null || yearTo != null ? (
                        <span>
                          {" "}
                          · 연도 {yearFrom ?? "…"}–{yearTo ?? "…"}
                        </span>
                      ) : usesMartPeriod && periodLabel ? (
                        <span> · 분석 {periodLabel}</span>
                      ) : (
                        " (전체 연도)"
                      )}
                    </p>
                    {txExportButton}
                  </div>
                  {txExportError && <p className="text-[10px] text-red-500">{txExportError}</p>}
                  <CollectiveTransactionTable
                    items={txQ.data.items}
                    assetType={effectiveAssetType}
                    truncated={txQ.data.truncated}
                  />
                </>
              )}
            </div>
          )}

          {panel === "floor_index" && (
            <FloorIndexPanel
              buildingKey={row.building_key}
              cohortKeys={cohortRunKeys}
              cohortRunId={cohortRunForPanel("floor_index")}
              assetType={effectiveAssetType}
              yearFrom={yearFrom}
              yearTo={yearTo}
              periodStart={periodStart ?? undefined}
              periodEnd={periodEnd ?? undefined}
              experiment={experiment}
              floorIndexEligible={analysis.floor_index}
              gateTip={gateTip}
            />
          )}

          {panel === "danji" && (
            <>
              {danjiQ.isLoading && (
                <p className="text-xs text-slate-400 text-center py-6">단지 정보 불러오는 중…</p>
              )}
              {danjiQ.isError && (
                <p className="text-xs text-amber-700 dark:text-amber-400 text-center py-6">
                  단지 정보를 불러오지 못했습니다.
                </p>
              )}
              {danjiQ.data && <DanjiAttributesPanel data={danjiQ.data} />}
            </>
          )}

          {panel === "regression" && (
            <BuildingRegressionPanel
              buildingKey={row.building_key}
              cohortKeys={cohortRunKeys}
              cohortRunId={cohortRunForPanel("regression")}
              assetType={effectiveAssetType}
              yearFrom={yearFrom}
              yearTo={yearTo}
              periodStart={periodStart ?? undefined}
              periodEnd={periodEnd ?? undefined}
              experiment={experiment}
              regressionEligible={analysis.regression}
              gateTip={gateTip}
            />
          )}
    </DraggableModalShell>
  );
}
