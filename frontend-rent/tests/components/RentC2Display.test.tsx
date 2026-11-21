import { test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import DraggableModalShell from "../../src/components/DraggableModalShell";
import { PeerPicker } from "../../src/components/BuildingDetailModal";
import type { LeaseMetric, RentBuildingRow } from "../../src/types";

const metric = (n: number, median: number | null = null): LeaseMetric => ({
  n, mean: median, median, ci_lower: null, ci_upper: null,
});

function row(partial: Partial<RentBuildingRow> & Pick<RentBuildingRow, "display_name" | "building_key">): RentBuildingRow {
  return {
    asset_type: "apartment",
    jibun_address: "",
    road_address: "",
    building_year: 2021,
    jeonse: metric(10),
    mixed: { n: 0, deposit: metric(0), monthly: metric(0) },
    monthly: metric(0),
    jeonse_equiv: metric(0),
    monthly_equiv: metric(0),
    ...partial,
  };
}

test("인접 목록은 아파트 조각의 표시 이름을 쓰고 연립은 단지명만 쓴다", () => {
  const apt = row({
    building_key: "a".repeat(64),
    display_name: "다성이즈빌",
    display_label: "다성이즈빌 (2021년 준공)",
  });
  const villa = row({
    building_key: "b".repeat(64),
    asset_type: "rowhouse",
    display_name: "영재리치빌",
    display_label: null,
    building_year: 2023,
  });
  const html = renderToStaticMarkup(
    <PeerPicker peers={[apt, villa]} extraKeys={[]} onToggle={() => {}} />,
  );
  assert.ok(html.includes("다성이즈빌 (2021년 준공)"));
  assert.ok(html.includes("영재리치빌"));
  assert.equal(html.includes("영재리치빌 ("), false);
});

test("상세 제목은 표시 이름을 줄바꿈으로 보여 말줄임하지 않는다", () => {
  const html = renderToStaticMarkup(
    <DraggableModalShell
      open
      usePortal={false}
      titleWrap
      title="다성이즈빌 (2021년 준공)"
      titleId="rent-building-detail-title"
      onClose={() => {}}
    >
      <p>본문</p>
    </DraggableModalShell>,
  );
  assert.ok(html.includes("다성이즈빌 (2021년 준공)"));
  assert.ok(html.includes("whitespace-normal"));
  assert.equal(html.includes("truncate"), false);
});
