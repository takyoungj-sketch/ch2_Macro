import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const source = await readFile(new URL("../src/utils/twinPool.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { checkedTwinsAddRegion } = await import(
  "data:text/javascript;base64," + Buffer.from(outputText).toString("base64")
);

const anchor = "충청북도|청주시|강서동";
const other = "충청북도|청주시|복대동";
const outside = "서울특별시|강남구|역삼동";

test("a twin already in the selection does not widen the fit", () => {
  assert.equal(checkedTwinsAddRegion([anchor, other], anchor, [other]), false);
});

test("a twin outside the selection widens the fit", () => {
  assert.equal(checkedTwinsAddRegion([anchor, other], anchor, [other, outside]), true);
});

test("with no eup selected, a checked twin widens the one anchor", () => {
  assert.equal(checkedTwinsAddRegion([], anchor, [outside]), true);
  assert.equal(checkedTwinsAddRegion([], anchor, [anchor]), false);
});
