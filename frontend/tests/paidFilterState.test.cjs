const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");

const src = path.resolve(__dirname, "../src");
const code = "4377025626";

function setup() {
  const calls = [];
  const api = {
    fetchFreeStatsBulk: async () => { throw new Error("Unexpected bulk lookup"); },
    runPaidAnalysis: async (request) => {
      calls.push(request);
      return { request: structuredClone(request) };
    },
  };
  const loaded = new Map();
  function load(filename) {
    if (loaded.has(filename)) return loaded.get(filename).exports;
    const mod = new Module(filename, module);
    mod.filename = filename;
    mod.paths = module.paths;
    loaded.set(filename, mod);
    const nativeRequire = mod.require.bind(mod);
    mod.require = (id) => {
      if (id === "./api/client") return api;
      if (id === "@ch2/region-picker") {
        return load(path.resolve(src, "../../shared/region-picker/legalDongWithoutRi.ts"));
      }
      if (id.startsWith(".")) return load(path.resolve(path.dirname(filename), id + ".ts"));
      return nativeRequire(id);
    };
    mod._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        esModuleInterop: true,
      },
    }).outputText, filename);
    return mod.exports;
  }
  const { useAppStore } = load(path.join(src, "store.ts"));
  const { buildPaidMatrixCellRequest } = load(path.join(src, "utils/paidAnalysisPayload.ts"));
  return { state: useAppStore.getState, calls, api, buildPaidMatrixCellRequest };
}

test("기본통계 뒤 필터 분석은 현재 필터를 전송한다", async () => {
  const { state, calls } = setup();
  state().kickPaidBasicStatsAnalysis();
  state().commitStatsDisplayScope(code);
  state().setPaidRequest({ exclude_outlier: true, outlier_iqr_multiplier: 2 });
  await state().runPaidFilteredAnalysis([code]);
  assert.equal(calls[0].outlier_iqr_multiplier, 2);
  assert.equal(state().paidResultView, "filtered");
});

test("필터 설정 뒤 기본통계를 조회해도 현재 입력이 그대로 전송된다", async () => {
  const { state, calls } = setup();
  state().setPaidRequest({
    years: [2023, 2025], area_sqm_min: 40, exclude_partial: true,
    exclude_outlier: true, outlier_iqr_multiplier: 1.5,
  });
  state().togglePaidRoadExclude("25이상");
  state().togglePaidDealTypeExclude("직거래");
  state().setFreeStatsWindowYears(3);
  state().kickPaidBasicStatsAnalysis();
  state().commitStatsDisplayScope(code);
  state().syncPaidBasicStatsMeta({ beopjungri_code: code });
  await state().runPaidFilteredAnalysis([code]);
  assert.deepEqual(calls[0].years, [2023, 2025]);
  assert.equal(calls[0].area_sqm_min, 40);
  assert.equal(calls[0].exclude_partial, true);
  assert.equal(calls[0].exclude_outlier, true);
  assert.equal(calls[0].outlier_iqr_multiplier, 1.5);
  assert.ok(!calls[0].road_conditions.includes("25이상"));
  assert.deepEqual(calls[0].deal_types, ["중개거래"]);
});

test("필터 편집과 명시적 초기화 뒤에도 표와 칸 조회에 쓰는 성공 요청은 유지된다", async () => {
  const { state, buildPaidMatrixCellRequest } = setup();
  state().setPaidRequest({ years: [2025], exclude_outlier: true, outlier_iqr_multiplier: 1.5 });
  await state().runPaidFilteredAnalysis([code]);
  const applied = state().paidAnalysisResult.request;
  state().setPaidRequest({ years: [2024], outlier_iqr_multiplier: 2 });
  assert.deepEqual(state().paidRequest.years, [2024]);
  const cellRequest = buildPaidMatrixCellRequest(state().paidAnalysisResult.request, "농림", "임");
  assert.deepEqual(cellRequest.years, [2025]);
  assert.equal(cellRequest.outlier_iqr_multiplier, 1.5);
  assert.deepEqual(cellRequest.region_codes, [code]);
  assert.equal(cellRequest.land_category, "임");

  state().resetPaidFilters();
  assert.equal(state().paidRequest.exclude_outlier, false);
  assert.equal(state().paidRequest.outlier_iqr_multiplier, 3);
  assert.deepEqual(state().paidAnalysisResult.request, applied);
  state().kickPaidBasicStatsAnalysis();
  assert.deepEqual(state().paidAnalysisResult.request, applied);
});

test("기본통계로 돌아간 뒤 이전 필터 분석 응답이 도착해도 채택하지 않는다", async () => {
  const { state, api } = setup();
  let resolveAnalysis;
  api.runPaidAnalysis = () => new Promise((resolve) => { resolveAnalysis = resolve; });
  const running = state().runPaidFilteredAnalysis([code]);
  state().kickPaidBasicStatsAnalysis();
  resolveAnalysis({ request: { years: [2025] } });
  await running;
  assert.equal(state().paidResultView, "basic");
  assert.equal(state().paidAnalysisStatus, "idle");
  assert.equal(state().paidAnalysisResult, null);
});

test("복수 지역 선조회 중 편집한 필터는 다음 분석에만 반영된다", async () => {
  const { state, calls, api } = setup();
  const anotherCode = "4377025627";
  let resolveBulk;
  api.fetchFreeStatsBulk = () => new Promise((resolve) => { resolveBulk = resolve; });
  state().setPaidRequest({ exclude_outlier: true, outlier_iqr_multiplier: 1.5 });
  const running = state().runPaidFilteredAnalysis([code, anotherCode]);
  state().setPaidRequest({ outlier_iqr_multiplier: 2 });
  resolveBulk({ beopjungri_code: `${code},${anotherCode}` });
  await running;
  assert.equal(calls[0].outlier_iqr_multiplier, 1.5);
  await state().runPaidFilteredAnalysis([code, anotherCode]);
  assert.equal(calls[1].outlier_iqr_multiplier, 2);
});
