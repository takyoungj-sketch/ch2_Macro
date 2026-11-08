const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.resolve(__dirname, '../src/utils/landTxDisplay.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const loaded = new Module(filename, module);
loaded._compile(compiled, filename);
const {formatTraitOfficialPrice: amount, formatTraitOfficialPriceYear: year} = loaded.exports;

test('공시지가가 없으면 사유와 관계없이 대시를 표시하고 연도는 숨긴다', () => {
  for (const r of [{}, {trait_link_status:'multiple_candidates'}, {trait_link_status:'exact',trait_price_status:'price_conflict'}, {trait_link_status:'exact',trait_price_status:'price_missing'}]) {
    assert.equal(amount(r), '—');
    assert.equal(year(r), null);
  }
});
test('거래연도와 전년도 공시지가의 금액과 실제 기준연도를 구분한다', () => {
  const r = {trait_link_status:'exact',trait_price_status:'same_year',official_price_won:68200,official_price_year:2026};
  assert.equal(amount(r), '68,200');
  assert.equal(year(r), '2026년');
  assert.equal(year({...r,trait_price_status:'previous_year',official_price_year:2025}), '2025년');
  assert.equal(amount({...r,trait_price_status:'previous_year'}), '68,200');
});
test('연도 누락·비정상 금액·미확정 필지의 잔여 값을 표시하지 않는다', () => {
  const r = {trait_link_status:'exact',trait_price_status:'same_year',official_price_won:0,official_price_year:2026};
  assert.equal(amount(r), '0');
  for (const invalid of [{...r,official_price_year:null},{...r,official_price_won:NaN},{...r,trait_link_status:'multiple_candidates'}]) {
    assert.equal(amount(invalid), '—');
    assert.equal(year(invalid), null);
  }
});
