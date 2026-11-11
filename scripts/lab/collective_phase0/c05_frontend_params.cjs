// C-05 6-1 — 프론트 API 호출의 경로·보내는 파라미터 이름 추출 (TypeScript 타입 해석).
// 사용: node c05_frontend_params.cjs <typescript 모듈 경로> <repo 루트> > out.json
// axios 인스턴스(baseURL)별 api.get/post/put/delete 호출의 path, params 타입(또는 body 타입) 속성 이름을 모은다.
const path = require("path");
const fs = require("fs");
const ts = require(process.argv[2]);
const ROOT = process.argv[3];
const APPS = ["frontend", "frontend-built", "frontend-collective", "frontend-rent", "frontend-profile"];

function walk(dir, out) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (e.name !== "node_modules") walk(p, out); }
    else if (/\.(ts|tsx)$/.test(e.name) && !/\.test\./.test(e.name)) out.push(p);
  }
  return out;
}

const results = [];
for (const app of APPS) {
  const src = path.join(ROOT, app, "src");
  if (!fs.existsSync(src)) continue;
  const files = walk(src, []);
  const program = ts.createProgram(files, { jsx: ts.JsxEmit.ReactJSX, allowJs: false, strict: false, skipLibCheck: true, noEmit: true,
    target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler });
  const checker = program.getTypeChecker();
  for (const sf of program.getSourceFiles()) {
    if (!sf.fileName.replace(/\\/g, "/").includes(`/${app}/src/`)) continue;
    // axios.create baseURL 수집 (파일 단위)
    const bases = {};
    ts.forEachChild(sf, function visit(node) {
      if (ts.isVariableDeclaration(node) && node.initializer && ts.isCallExpression(node.initializer)
          && node.initializer.expression.getText(sf).endsWith("axios.create")) {
        const arg = node.initializer.arguments[0];
        if (arg && ts.isObjectLiteralExpression(arg)) {
          for (const pr of arg.properties) {
            if (pr.name && pr.name.getText(sf) === "baseURL" && pr.initializer) bases[node.name.getText(sf)] = pr.initializer.getText(sf).replace(/["'`]/g, "");
          }
        }
      }
      ts.forEachChild(node, visit);
    });
    const fnStack = [];
    function visit(node) {
      const named = (ts.isFunctionDeclaration(node) && node.name) ? node.name.text
        : (ts.isVariableDeclaration(node) && node.initializer && (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer))) ? node.name.getText(sf) : null;
      if (named) fnStack.push(named);
      if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
        const method = node.expression.name.text;
        const obj = node.expression.expression.getText(sf);
        if (["get", "post", "put", "delete", "patch"].includes(method) && (bases[obj] !== undefined || /(api|apiClient|Api)$/.test(obj)) && node.arguments.length) {
          const a0 = node.arguments[0];
          let p = a0.getText(sf).replace(/^[`"']|[`"']$/g, "").replace(/\$\{[^}]+\}/g, "{x}");
          const props = new Set();
          let kind = "";
          const cfgIdx = (method === "get" || method === "delete") ? 1 : 2;
          const cfg = node.arguments[cfgIdx];
          if (cfg) {
            const t = checker.getTypeAtLocation(cfg);
            const prm = t.getProperty && t.getProperty("params");
            if (prm) {
              const pt = checker.getTypeOfSymbolAtLocation(prm, cfg);
              for (const s of checker.getPropertiesOfType(checker.getNonNullableType(pt))) props.add(s.name);
              kind = "query";
            }
          }
          if (method !== "get" && method !== "delete" && node.arguments[1]) {
            const bt = checker.getTypeAtLocation(node.arguments[1]);
            const bodyProps = checker.getPropertiesOfType(checker.getNonNullableType(bt)).map((s) => s.name);
            results.push({ app, file: path.relative(ROOT, sf.fileName).replace(/\\/g, "/"), fn: fnStack[fnStack.length - 1] || "", method, base: bases[obj] ?? `?${obj}`, path: p, kind: "body", props: bodyProps });
          }
          if (kind || method === "get") {
            results.push({ app, file: path.relative(ROOT, sf.fileName).replace(/\\/g, "/"), fn: fnStack[fnStack.length - 1] || "", method, base: bases[obj] ?? `?${obj}`, path: p, kind: kind || "query", props: [...props] });
          }
        }
      }
      ts.forEachChild(node, visit);
      if (named) fnStack.pop();
    }
    visit(sf);
  }
}
process.stdout.write(JSON.stringify(results, null, 1));
