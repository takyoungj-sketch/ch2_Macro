// 컴포넌트 테스트 실행기 — 새 의존성 없이 이미 있는 esbuild(vite 의존성)로 tests/components/*.test.tsx 를 묶어
// Node 내장 테스트 실행기(node:test)로 돌린다. react-dom/server 로 정적 HTML 을 그려 확인한다.
//   node scripts/component-tests.mjs        (npm run test:components)
import { build } from "esbuild";
import { readdirSync, mkdirSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { run } from "node:test";
import { spec } from "node:test/reporters";

const root = resolve(import.meta.dirname, "..");
const dir = join(root, "tests", "components");
const files = readdirSync(dir).filter((f) => f.endsWith(".test.tsx")).map((f) => join(dir, f));
// 패키지는 묶지 않는다(react-dom 등 CommonJS) — 결과 파일을 앱 폴더 안에 둬서 node_modules 에서 찾게 하고, 끝나면 지운다
const out = join(root, ".component-tests-tmp");
rmSync(out, { recursive: true, force: true });
mkdirSync(out);
try {
  await build({
    entryPoints: files,
    bundle: true,
    platform: "node",
    format: "esm",
    outdir: out,
    jsx: "automatic",
    outExtension: { ".js": ".mjs" },
    packages: "external",
    // vite 의 import.meta.env 를 비운 값으로(테스트는 실험 모드·개발 모드 아님)
    define: { "import.meta.env": JSON.stringify({ DEV: false, PROD: true, MODE: "test" }) },
    logLevel: "warning",
  });
  const built = readdirSync(out).filter((f) => f.endsWith(".mjs")).map((f) => join(out, f));
  let failed = 0;
  const stream = run({ files: built });
  stream.on("test:fail", () => {
    failed += 1;
  });
  for await (const line of stream.compose(spec)) process.stdout.write(line);
  process.exitCode = failed ? 1 : 0;
} finally {
  rmSync(out, { recursive: true, force: true });
}
