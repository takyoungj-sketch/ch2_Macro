const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.resolve(__dirname, '../src/utils/landRegressionFormat.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const formatter = new Module(filename, module);
formatter.filename = filename;
formatter._compile(compiled, filename);
const interpret = (name, coef, type='log') => formatter.exports.interpretLandCoefficient({name,coef},type);

test('공시지가 1%의 로그-로그 탄력성을 1 로그 단위 변화로 과장하지 않는다', () => {
  assert.match(interpret('log_assessed_land_price', 0.8978), /1% 증가.*\+0\.90%/);
  assert.match(interpret('log_assessed_land_price', 1), /\+1\.00%/);
  assert.doesNotMatch(interpret('log_assessed_land_price', 0.8978), /145/);
});
test('선형 단가에서도 로그 공시지가를 1% 변화로 설명한다', () => {
  assert.match(interpret('log_assessed_land_price', 1000, 'linear'), /1% 증가.*\+10만원/);
});
test('로그 단가의 원면적 계수를 금액 차이로 표시하지 않는다', () => {
  assert.match(interpret('area_sqm', Math.log(1.1)), /1㎡ 증가.*\+10\.0%/);
});
test('상수를 반올림한 0만원 단가로 설명하지 않는다', () => {
  assert.match(interpret('const', -7.9), /로그 단가 상수/);
  assert.doesNotMatch(interpret('const', -7.9), /0만원/);
});

test('작은 단가 계수와 작은 로그 효과를 0으로 표시하지 않는다', () => {
  assert.doesNotMatch(interpret('area_sqm', .00001, 'linear'), /\+0만원/);
  assert.doesNotMatch(interpret('log_assessed_land_price', .00001), /\+0\.00%/);
  assert.notEqual(formatter.exports.formatCoefValue(.000001), '0');
});
