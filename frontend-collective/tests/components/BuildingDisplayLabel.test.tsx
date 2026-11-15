import { test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import BuildingStatsTable, { buildingMatchesQuery } from "../../src/components/BuildingStatsTable";
import { buildingDisplayName } from "../../src/utils/buildingName";
import { buildCollectiveListContext } from "../../src/api/aiContext";
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
