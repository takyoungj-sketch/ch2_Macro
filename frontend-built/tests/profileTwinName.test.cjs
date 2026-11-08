const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.resolve(__dirname, '../src/utils/profileLink.ts');
const loaded = new Module(filename, module);
loaded._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020},
}).outputText, filename);
const { profileTwinFullName: fullName } = loaded.exports;

test('동 이름 앞에 시도와 시군구를 함께 표시한다', () => {
  assert.equal(fullName({twin_sido_name:'충청북도',twin_sigungu_name:'청주시 흥덕구',twin_eupmyeondong_name:'복대동'}), '충청북도 청주시 흥덕구 복대동');
});
test('이미 포함된 상위 지역명과 같은 동 이름을 중복하지 않는다', () => {
  assert.equal(fullName({twin_sido_name:'서울특별시',twin_sigungu_name:'서울특별시 중구',twin_eupmyeondong_name:'명동'}), '서울특별시 중구 명동');
  assert.equal(fullName({twin_sido_name:'충청북도',twin_sigungu_name:'청주시 흥덕구',twin_eupmyeondong_name:'복대동',twin_beopjungri_name:'복대동'}), '충청북도 청주시 흥덕구 복대동');
});
test('법정리의 제공된 전체 이름을 보존하고 빈 값은 생략한다', () => {
  assert.equal(fullName({twin_sido_name:' 충청북도 ',twin_sigungu_name:'청주시 청원구',twin_beopjungri_name:'오창읍 화산리'}), '충청북도 청주시 청원구 오창읍 화산리');
  assert.equal(fullName({twin_sido_name:'',twin_sigungu_name:'청주시',twin_eupmyeondong_name:null}), '청주시');
});
