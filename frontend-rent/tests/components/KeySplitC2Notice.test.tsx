import { test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import KeySplitC2Notice, {
  C2_NOTICE_TEXT,
  c2CandidateLabel,
  hasC2Siblings,
  type KeySplitC2Note,
} from "../../src/components/KeySplitC2Notice";

const NOTE: KeySplitC2Note = {
  status: "has_split_siblings",
  message: "서버 안내",
  building_key: "a".repeat(64),
  new_keys: ["b".repeat(64), "c".repeat(64)],
  candidates: [
    { building_key: "b".repeat(64), split_part: 1, n_tx: 1234, display_name: "가동빌라", addr4: "우암동" },
    { building_key: "c".repeat(64), split_part: 2, n_tx: 7 },
  ],
};

test("C-2 안내: 가장 큰 단지 문구와 분리된 단지 링크", () => {
  const html = renderToStaticMarkup(<KeySplitC2Notice note={NOTE} displayName="한빛" onOpenKey={() => {}} />);
  assert.ok(html.includes(C2_NOTICE_TEXT));
  assert.equal(C2_NOTICE_TEXT, "같은 이름의 단지 중 가장 큰 단지를 보고 있습니다.");
  assert.ok(html.includes("가동빌라 · 우암동 · 1,234건"));
  assert.ok(html.includes("한빛 · 7건"));                       // 이름 없는 후보는 현재 단지 이름
  assert.equal((html.match(/<button/g) || []).length, 2);       // 링크(버튼) 2개
  const plain = renderToStaticMarkup(<KeySplitC2Notice note={NOTE} />);
  assert.equal((plain.match(/<button/g) || []).length, 0);      // 여는 함수가 없으면 글자만
});

test("후보 라벨·안내 여부", () => {
  assert.equal(c2CandidateLabel({ building_key: "x", split_part: 1, n_tx: 3, addr3: "청주시", addr4: "복대동" }), "단지 · 청주시 복대동 · 3건");
  assert.equal(hasC2Siblings(NOTE), true);
  assert.equal(hasC2Siblings({ ...NOTE, candidates: [] }), false);
  assert.equal(hasC2Siblings(null), false);
});

test("임대 가드: 같은 안내 컴포넌트를 쓴다(집합과 문구·모양 같음)", async () => {
  const mod = await import("../../src/components/RentKeySplitGuard");
  assert.equal(typeof mod.default, "function");
});
