import { test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import {
  CandidateSwitchStatus,
  candidateFilter,
  switchToCandidate,
  type CandidateSwitchState,
} from "../../src/components/candidateSwitch";
import { KEY_STATUS_UNKNOWN_TEXT, KeyStatusUnknownNotice, type KeySplitC2Candidate } from "../../src/components/KeySplitC2Notice";
import { rentGuardMode } from "../../src/components/RentKeySplitGuard";
import { rentKeyStatusFromError as keyStatusFromError } from "../../src/api/client";

type Row = { building_key: string; display_name: string; count: number; median: number };
const CUR: Row = { building_key: "a".repeat(64), display_name: "한빛", count: 120, median: 900 };
const CAND: KeySplitC2Candidate = { building_key: "b".repeat(64), display_name: "한빛", addr3: "상록구", addr4: "사동" };

function Selected({ row }: { row: Row }) {
  return <p>{`${row.display_name} · ${row.count}건 · 중앙값 ${row.median}`}</p>;
}

test("후보 클릭 → 후보 키 실제 행 재조회 → 새 수치로 상세 전환(기존 행 복사 아님)", async () => {
  const states: CandidateSwitchState[] = [];
  let selected: Row = CUR;
  const asked: unknown[] = [];
  const fetchRows = async (f: { addr3List: string[]; addr4List: string[] }) => {
    asked.push(f);
    // 조회하는 동안 로딩이 보인다
    assert.ok(renderToStaticMarkup(<CandidateSwitchStatus state={states[states.length - 1]} />).includes("불러오는 중"));
    return [
      { building_key: "c".repeat(64), display_name: "다른", count: 5, median: 1 },
      { building_key: CAND.building_key, display_name: "한빛", count: 31, median: 1234 },
    ];
  };
  await switchToCandidate<Row>(CAND.building_key, CAND, {
    label: "한빛",
    fetchRows,
    setSelected: (r) => {
      selected = r;
    },
    setState: (s) => states.push(s),
  });
  assert.deepEqual(asked, [{ addr3List: ["상록구"], addr4List: ["사동"] }]);   // 후보의 동으로 다시 조회
  assert.deepEqual(states.map((s) => s.status), ["loading", "idle"]);
  assert.equal(selected.building_key, CAND.building_key);
  const html = renderToStaticMarkup(<Selected row={selected} />);
  assert.ok(html.includes("31건") && html.includes("중앙값 1234"));            // 새 수치(현재 120건·900 이 아님)
  assert.ok(!html.includes("120건"));
});

test("재조회 실패·행 없음 → 안내(현재 상세 유지)", async () => {
  for (const [fetchRows, needle] of [
    [async () => Promise.reject(new Error("network")), "불러오지 못했습니다"],
    [async () => [{ building_key: "z".repeat(64), display_name: "x", count: 1, median: 1 }], "찾지 못했습니다"],
  ] as const) {
    const states: CandidateSwitchState[] = [];
    let selected: Row = CUR;
    await switchToCandidate<Row>(CAND.building_key, CAND, {
      label: "한빛",
      fetchRows: fetchRows as () => Promise<Row[]>,
      setSelected: (r) => {
        selected = r;
      },
      setState: (s) => states.push(s),
    });
    assert.equal(selected, CUR);
    const last = states[states.length - 1];
    assert.equal(last.status, "error");
    const html = renderToStaticMarkup(<CandidateSwitchStatus state={last} onDismiss={() => {}} />);
    assert.ok(html.includes(needle) && html.includes('role="alert"'), html);
  }
});

test("후보 동 필터: 구 없는 시는 addr3 만", () => {
  assert.deepEqual(candidateFilter({ ...CAND, addr3: "평택동", addr4: null }), { addr3List: ["평택동"], addr4List: [] });
});

test("/key-status 401·403·연결 실패 → 정상이 아니라 「확인 불가」, 409(C-01) → 안내 없음(임대는 그대로 연다)", () => {
  for (const status of [401, 403, 500]) {
    const s = keyStatusFromError({ response: { status } }, CUR.building_key);
    assert.equal(s.key_status, "unknown");
    assert.equal(rentGuardMode(s), "unknown");
    const html = renderToStaticMarkup(<KeyStatusUnknownNotice reason={s.key_status === "unknown" ? s.reason : ""} />);
    assert.ok(html.includes(KEY_STATUS_UNKNOWN_TEXT) && html.includes(`HTTP ${status}`));
  }
  assert.equal(keyStatusFromError(new Error("x"), CUR.building_key).key_status, "unknown");
  assert.equal(rentGuardMode(keyStatusFromError({ response: { status: 409 } }, CUR.building_key)), "none");
});
