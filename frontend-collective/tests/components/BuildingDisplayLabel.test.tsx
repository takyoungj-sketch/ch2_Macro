import { test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import BuildingStatsTable, { buildingMatchesQuery } from "../../src/components/BuildingStatsTable";
import { buildingDisplayName, regressionAiName } from "../../src/utils/buildingName";
import { buildCollectiveListContext, buildOpenBuildingDetailContext } from "../../src/api/aiContext";
import type { BuildingStatsRow } from "../../src/types";

const base = {
  address: "",
  asset_type: "apartment",
  count: 40,
  mean: 900,
  median: 880,
  ci_lower: null,
  ci_upper: null,
  is_reliable: true,
} as unknown as BuildingStatsRow;
const FRAG = { ...base, building_key: "f".repeat(64), display_name: "주공", display_label: "주공 (1986년 준공)", building_year: 1986 };
const OTHER = { ...base, building_key: "x".repeat(64), display_name: "래미안", display_label: null, building_year: 2004 };

test("표시 이름: display_label 이 있으면 그것, 없으면 display_name", () => {
  assert.equal(buildingDisplayName(FRAG), "주공 (1986년 준공)");
  assert.equal(buildingDisplayName(OTHER), "래미안");
  assert.equal(buildingDisplayName({ display_name: "한빛" }), "한빛");
});

test("목록 표: 분할 아파트 조각은 「단지명 (YYYY년 준공)」, 나머지는 이름 그대로", () => {
  const html = renderToStaticMarkup(
    <BuildingStatsTable items={[FRAG, OTHER]} wide={true} highlightQuery="" onSelect={() => {}} />,
  );
  assert.ok(html.includes("주공 (1986년 준공)"));
  assert.ok(html.includes("래미안"));
  assert.ok(!html.includes("래미안 ("));
});

test("검색은 원래 이름·표시 이름 둘 다로 찾는다", () => {
  assert.ok(buildingMatchesQuery(FRAG, "주공"));
  assert.ok(buildingMatchesQuery(FRAG, "1986년 준공"));
});

test("AI 문맥 목록 행 이름도 표시 이름", () => {
  const ctx = buildCollectiveListContext({
    regionLabel: "부천시 소사구",
    assetType: "apartment",
    windowYears: 5,
    total: 2,
    first: FRAG,
    items: [FRAG, OTHER],
  } as never) as { facts: { visible_rows: { name: string }[]; first_row?: { name: string } } };
  assert.deepEqual(ctx.facts.visible_rows.map((r) => r.name), ["주공 (1986년 준공)", "래미안"]);
  assert.equal(ctx.facts.first_row?.name, "주공 (1986년 준공)");
});

test("AI 코호트 추이 문맥: 시리즈 이름도 표시 이름(labels → display_label → display_name)", async () => {
  const { buildCollectiveCohortRollingTrendContext } = await import("../../src/api/aiContext");
  const pt = { label: "2024", count: 1, mean: 1 };
  const items = [
    { building_key: FRAG.building_key, display_name: "주공", window_years: 5, points: [pt] },
    { building_key: OTHER.building_key, display_name: "래미안", display_label: null, window_years: 5, points: [pt] },
    { building_key: "z".repeat(64), display_name: "한빛", display_label: "한빛 (2001년 준공)", window_years: 5, points: [pt] },
  ];
  const ctx = buildCollectiveCohortRollingTrendContext(items as never, {
    regionLabel: "부천시", assetType: "apartment", labels: { [FRAG.building_key]: "주공 (1986년 준공)" },
  } as never) as { facts: { series: { label: string }[] } };
  assert.deepEqual(ctx.facts.series.map((s) => s.label), ["주공 (1986년 준공)", "래미안", "한빛 (2001년 준공)"]);
});

test("열린 단지 상세는 현재 탭 집계를 AI에 넘기고 거래 행은 넘기지 않는다", () => {
  const rolling = buildOpenBuildingDetailContext({
    panel: "trend",
    regionLabel: "주공 (1986년 준공)",
    assetType: "apartment",
    metric: "median",
    rolling: {
      building_key: "f".repeat(64),
      display_name: "주공",
      window_years: 5,
      points: [{ bucket_index: 1, period_start: "2024-01-01", period_end: "2024-12-31", label: "2024", count: 12, mean: 900, median: 880 }],
    },
  });
  assert.equal(rolling?.panel, "TrendCard");
  assert.equal(rolling?.scope.region_label, "주공 (1986년 준공)");
  assert.equal((rolling?.facts as { trend_metric?: string }).trend_metric, "median");
  assert.equal((rolling?.facts as { rows?: { median?: number }[] }).rows?.[0].median, 880);

  const hidden = buildOpenBuildingDetailContext({
    panel: "floor_index",
    regionLabel: "주공",
    assetType: "apartment",
    rolling: {
      building_key: "f".repeat(64),
      display_name: "주공",
      window_years: 5,
      points: [{ bucket_index: 1, period_start: "2024-01-01", period_end: "2024-12-31", label: "2024", count: 1, mean: 1 }],
    },
  });
  assert.equal(hidden, null);

  const tx = buildOpenBuildingDetailContext({
    panel: "transactions",
    regionLabel: "주공",
    assetType: "apartment",
    transactionTotal: 40,
    transactionLoaded: 20,
  });
  assert.equal(tx?.panel, "TransactionsPanel");
  assert.deepEqual(tx?.facts, { total: 40, loaded: 20 });

  const yearly = buildOpenBuildingDetailContext({
    panel: "long_term",
    regionLabel: "통합",
    assetType: "apartment",
    metric: "median",
    labels: { ["a".repeat(64)]: "주공 (1986년 준공)" },
    cohortYearly: [
      { building_key: "a".repeat(64), display_name: "주공", points: [{ year: 2020, count: 4, mean: 100, median: 90 }] },
      { building_key: "b".repeat(64), display_name: "래미안", points: [{ year: 2020, count: 5, mean: 200, median: 180 }] },
    ],
  });
  const series = (yearly?.facts as { cohort?: boolean; series?: { label: string; points: { median?: number }[] }[] }).series;
  assert.equal(yearly?.panel, "LongTermTrendPanel");
  assert.equal((yearly?.facts as { cohort?: boolean }).cohort, true);
  assert.deepEqual(series?.map((item) => item.label), ["주공 (1986년 준공)", "래미안"]);
  assert.equal(series?.[0].points[0].median, 90);

  const hist = buildOpenBuildingDetailContext({
    panel: "histogram",
    regionLabel: "통합",
    assetType: "apartment",
    histogram: { building_keys: ["a", "b"], bins: [{ lo: 1, hi: 2, count: 3 }], n: 8, data_source: "live" },
  });
  assert.equal(hist?.panel, "HistogramPanel");
  assert.equal((hist?.facts as { cohort?: boolean; n?: number }).cohort, true);
  assert.equal((hist?.facts as { n?: number }).n, 8);
  assert.equal("items" in (hist?.facts ?? {}), false);

  const cohortTx = buildOpenBuildingDetailContext({
    panel: "transactions",
    regionLabel: "통합",
    assetType: "apartment",
    transactionTotal: 12,
    transactionLoaded: 12,
  });
  assert.deepEqual(cohortTx?.facts, { total: 12, loaded: 12 });
});

test("AI 회귀 문맥 이름: 단지 하나면 표시 이름, 코호트·라벨 없음이면 응답 이름", () => {
  assert.equal(regressionAiName("주공 (1986년 준공)", "주공", false), "주공 (1986년 준공)");
  assert.equal(regressionAiName("주공 (1986년 준공)", "주공 외 2", true), "주공 외 2");
  assert.equal(regressionAiName(null, "래미안", false), "래미안");
});

test("코호트 추이 범례: rolling 응답의 display_label", async () => {
  const { rollingToTrendSeries } = await import("../../src/utils/cohortTrendSeries");
  const pts = [{ bucket_index: 0, label: "2024", count: 1, mean: 1 }];
  assert.equal(rollingToTrendSeries({ building_key: "f".repeat(64), display_name: "주공", display_label: "주공 (1986년 준공)", window_years: 5, points: pts } as never).label, "주공 (1986년 준공)");
  assert.equal(rollingToTrendSeries({ building_key: "x".repeat(64), display_name: "래미안", window_years: 5, points: pts } as never).label, "래미안");
});
