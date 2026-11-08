const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const previous = Module._extensions['.ts'];
Module._extensions['.ts'] = (m, filename) => m._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020},
}).outputText, filename);
const cost = require('../src/utils/allocationCost.ts');
const aggregate = require('../src/utils/builtTxAggregate.ts');
if (previous) Module._extensions['.ts'] = previous;
else delete Module._extensions['.ts'];

const bands = {[cost.bandKey('단독','RC')]:{low:100,high:200,life:50,minResidual:.1}};
const row = {id:1,building_use:'단독',structure_group:'RC',contract_year:2025,building_year:2000,gross_area:100,land_area:200,price:100000};

test('건물가액 차감과 원가 상하한에 따른 토지단가 범위를 복원한다', () => {
  const out = cost.allocateRow(row,bands);
  assert.equal(out.ok,true);
  assert.equal(out.view.residual,.5);
  assert.equal(out.view.landLow,450);
  assert.equal(out.view.landHigh,475);
  assert.equal(out.view.landMid,462.5);
});
test('실거래 건축연도를 우선하고 없을 때 대장 사용승인연도를 쓴다', () => {
  assert.deepEqual(cost.allocationAge({...row,approve_year:2010}),{years:25,source:'실거래'});
  assert.deepEqual(cost.allocationAge({...row,building_year:null,approve_year:2010}),{years:15,source:'대장 사용승인'});
});
test('개별 거래 잔존연수 조정은 다른 거래와 원가표를 바꾸지 않는다', () => {
  const out = cost.allocateRow(row,bands,{remainingYears:0});
  assert.equal(out.view.residual,0);
  assert.equal(out.view.landLow,500);
  assert.equal(cost.allocateRow(row,bands).view.landLow,450);
  assert.equal(bands[cost.bandKey('단독','RC')].life,50);
});
test('음수 단가는 보존하고 면적이 없는 거래는 계산하지 않는다', () => {
  const out = cost.allocateRow({...row,price:100},bands);
  assert.equal(out.ok,true);
  assert.ok(out.view.landHigh<0);
  assert.equal(cost.allocateRow({...row,land_area:0},bands).ok,false);
});
test('집계는 목록과 같은 배분단가를 쓰고 계산 불가 거래는 범위에서만 뺀다', () => {
  const rows = [row,{...row,id:2,price:80000},{...row,id:3,land_area:null}];
  const result = aggregate.aggregateBuiltTransactions(rows,'building_use',r=>aggregate.allocationAggregateEnds(r,bands))[0];
  assert.equal(result.count,3);
  assert.equal(result.alloc.n,2);
  assert.equal(result.alloc.lowMedian,400);
  assert.equal(result.alloc.highMedian,425);
  assert.equal(result.alloc.lowMean,400);
  assert.equal(result.alloc.highMean,425);
});
test('실거래 연도가 없을 때 사용승인연도는 대체 표식을 가진다', () => {
  const display = require.cache[require.resolve('../src/utils/builtTxDisplay.ts')].exports;
  assert.deepEqual(display.builtTxDisplayedYear({...row,building_year:null,approve_year:2010}),{year:2010,substituted:true});
});
