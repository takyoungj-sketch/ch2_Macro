const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
function load(relative) {
  const filename = path.resolve(__dirname, relative);
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const result = new Module(filename, module);
  result.filename = filename;
  result._compile(compiled, filename);
  return result.exports;
}
const { interpretCoefficient, formatCoefValue } = load('../src/utils/regressionFormat.ts');
const { formatProbability, formatStatistic } = load('../../shared/regression-ui/format.ts');
const { contentSignature } = load('../../shared/regression-ui/signature.ts');
const { clampModalBox, centeredModalBox, fullscreenModalBox } = load('../../shared/ui-window/modalViewport.ts');
const { reconcileListedInputs } = load('../../shared/regression-ui/inputs.ts');
const { analysisPhase } = load('../../shared/regression-ui/phase.ts');
const { validationCaption } = load('../../shared/regression-ui/validation.ts');
const { createRequestGate } = load('../../shared/regression-ui/requestGate.ts');
const interpret = (name, estimate, scale='loglog') => interpretCoefficient({ name, estimate }, scale);

test('로그 면적과 공시지가의 1% 효과를 정확히 변환한다', () => {
  assert.match(interpret('gross_area', 1.112), /1% 증가.*1\.11%/);
  assert.match(interpret('assessed_land_price', .8978, 'log'), /1% 증가.*0\.90%/);
  assert.match(interpret('assessed_land_price', 1000, 'linear'), /1% 증가.*10만원/);
});
test('범주와 원변수 효과는 로그 종속변수에서 퍼센트로 표시한다', () => {
  assert.match(interpret('loc_test', Math.log(1.1)), /10\.0%/);
  assert.match(interpret('building_age', Math.log(.9)), /10\.0%/);
  assert.match(interpret('const', 0), /로그 금액 상수/);
});
test('작은 값과 미제공을 0으로 표시하지 않는다', () => {
  assert.equal(formatProbability(1e-9), '<0.001');
  assert.equal(formatProbability(0), '<0.001');
  assert.equal(formatProbability(null), '—');
  assert.equal(formatProbability(.1), '0.100');
  assert.notEqual(formatStatistic(.000001), '0');
  assert.notEqual(formatCoefValue(.000001), '0');
  assert.doesNotMatch(interpret('assessed_land_price', .001, 'linear'), /\+0만원/);
  assert.doesNotMatch(interpret('assessed_land_price', .00001), /\+0\.00%/);
});

test('객체 속성 순서만 바뀌면 결과를 무효화하지 않고 입력 변경은 구분한다', () => {
  assert.equal(contentSignature({ inputs: { area: 100, year: 2024 }, scope: ['a', 'b'] }),
    contentSignature({ scope: ['a', 'b'], inputs: { year: 2024, area: 100 } }));
  assert.notEqual(contentSignature({ area: 100 }), contentSignature({ area: 101 }));
});

test('작은 화면에서도 모달 제목과 닫기 경계를 헤더 아래에 남긴다', () => {
  const view = { width: 280, height: 320, headerHeight: 70 };
  const assertInside = box => {
    assert.ok(box.x >= 8 && box.y >= 78);
    assert.ok(box.x + box.w <= 272 && box.y + box.h <= 312);
  };
  assertInside(clampModalBox({ x: -50, y: -50, w: 900, h: 900 }, 480, 400, view));
  assertInside(centeredModalBox(900, 900, 480, 400, view));
  assertInside(fullscreenModalBox(480, 400, view));
  const saved = centeredModalBox(900, 700, 480, 400, { width: 1400, height: 1000, headerHeight: 70 });
  assertInside(clampModalBox(saved, 480, 400, view));
});

test('재적합 때 수치 입력을 보존하고 새 모형에 없는 범주는 새 기준으로 바꾼다', () => {
  assert.deepEqual(reconcileListedInputs({ area: '', region: 'b', period: '2025H1' },
    { area: '101', region: 'a', period: '2024H2' },
    { region: ['b', 'c'], period: ['2024H2', '2025H1'] }),
    { area: '101', region: 'b', period: '2024H2' });
});

test('이전 결과가 남아도 재요청 중이나 실패를 완료로 표시하지 않는다', () => {
  assert.equal(analysisPhase({ hasResult: true, pending: true }), 'running');
  assert.equal(analysisPhase({ hasResult: true, failed: true }), 'failed');
  assert.equal(analysisPhase({ hasResult: true, changed: true }), 'previous');
  assert.equal(analysisPhase({ hasResult: true }), 'ready');
  assert.equal(analysisPhase({ unavailable: true }), 'unavailable');
  assert.equal(analysisPhase({}), 'idle');
});

test('일부 분할의 정상 예측을 전체 교차검증 완료로 표현하지 않는다', () => {
  const report = { status: 'unavailable', requested_folds: 5, completed_folds: 4,
    eligible_n: 80, evaluated_n: 64, reason: '전체 교차검증 오차는 제공하지 않습니다.' };
  assert.match(validationCaption(report), /미제공.*4\/5.*64\/80/);
  assert.match(validationCaption({ ...report, status: 'not_run', reason: '대상 아님' }), /미실행.*대상 아님/);
  assert.match(validationCaption({ ...report, method: 'random_holdout', observation_unit: 'complex' }), /분리 검증.*64\/80곳/);
  assert.match(validationCaption({ ...report, method: 'rolling_year', status: 'partial' }), /연도별 검증 일부 제공.*4\/5연도/);
});

test('느린 이전 성공·실패 응답이 최신 성공 결과와 로딩 상태를 덮지 않는다', async () => {
  for (const rejected of [false, true]) {
    const gate = createRequestGate();
    let oldResolve, oldReject, latestResolve;
    let view, error = null, loading = false;
    const apply = async response => {
      const ticket = gate.start(); loading = true;
      try {
        const value = await response;
        if (gate.isCurrent(ticket)) { view = value; error = null; }
      } catch (failure) {
        if (gate.isCurrent(ticket)) { view = null; error = failure.message; }
      } finally {
        if (gate.isCurrent(ticket)) loading = false;
      }
    };
    const old = apply(new Promise((resolve, reject) => { oldResolve = resolve; oldReject = reject; }));
    gate.invalidate();
    const latest = apply(new Promise(resolve => { latestResolve = resolve; }));
    if (rejected) oldReject(new Error('이전 오류')); else oldResolve('이전 결과');
    await old;
    assert.equal(loading, true);
    assert.equal(error, null);
    latestResolve('새 결과'); await latest;
    assert.equal(view, '새 결과');
    assert.equal(loading, false);
    assert.equal(error, null);
    const ticket = gate.start(); gate.invalidate();
    assert.equal(gate.isCurrent(ticket), false);
    await apply(Promise.reject(new Error('현재 오류')));
    assert.equal(error, '현재 오류');
    await apply(Promise.resolve('재시도 성공'));
    assert.equal(view, '재시도 성공');
    assert.equal(error, null);
  }
});


test('입력 변경으로 해제한 mutation의 늦은 오류가 새 mutation에 전파되지 않는다', async () => {
  const { QueryClient, MutationObserver } = require('@tanstack/query-core');
  const client = new QueryClient();
  const observer = new MutationObserver(client, { mutationFn: pending => pending });
  const unsubscribe = observer.subscribe(() => {});
  let rejectOld, resolveNew;
  const old = observer.mutate(new Promise((_, reject) => { rejectOld = reject; })).catch(() => {});
  observer.reset();
  assert.equal(observer.getCurrentResult().status, 'idle');
  const latest = observer.mutate(new Promise(resolve => { resolveNew = resolve; }));
  resolveNew('새 입력 결과'); await latest;
  rejectOld(new Error('이전 입력 오류')); await old;
  assert.equal(observer.getCurrentResult().status, 'success');
  assert.equal(observer.getCurrentResult().data, '새 입력 결과');
  assert.equal(observer.getCurrentResult().error, null);
  unsubscribe(); client.clear();
});
