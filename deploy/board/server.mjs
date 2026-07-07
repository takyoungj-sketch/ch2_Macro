import { createReadStream, existsSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  CATEGORIES,
  PRODUCTS,
  createComment,
  createPost,
  getPost,
  listPosts,
  updatePostStatus,
} from "./store.mjs";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)));
const publicDir = join(rootDir, "public");
const preferredPort = Number(process.env.PORT ?? 5180);

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
};

function tryLoadDotenvFile(filePath) {
  if (!existsSync(filePath)) {
    return;
  }
  try {
    const content = readFileSync(filePath, "utf8");
    for (const rawLine of content.split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) {
        continue;
      }
      const eq = line.indexOf("=");
      if (eq <= 0) {
        continue;
      }
      const key = line.slice(0, eq).trim();
      let value = line.slice(eq + 1).trim();
      if (!key || process.env[key] !== undefined) {
        continue;
      }
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      process.env[key] = value;
    }
  } catch {
    /* ignore */
  }
}

tryLoadDotenvFile(join(rootDir, "..", "..", "deploy", ".env.production"));
tryLoadDotenvFile(join(rootDir, ".env"));

function sendJson(res, status, payload) {
  const body = `${JSON.stringify(payload)}\n`;
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  res.end(body);
}

function sendText(res, status, message) {
  res.writeHead(status, { "Content-Type": "text/plain; charset=utf-8" });
  res.end(message);
}

function readJsonBody(req) {
  return new Promise((resolvePromise, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > 64 * 1024) {
        reject(new Error("payload_too_large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => {
      if (!chunks.length) {
        resolvePromise({});
        return;
      }
      try {
        resolvePromise(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      } catch {
        reject(new Error("invalid_json"));
      }
    });
    req.on("error", reject);
  });
}

function serveStatic(res, relativePath) {
  const safePath = normalize(relativePath).replace(/^(\.\.[/\\])+/, "");
  const filePath = join(publicDir, safePath);
  if (!filePath.startsWith(publicDir) || !existsSync(filePath)) {
    return false;
  }
  const ext = extname(filePath).toLowerCase();
  res.writeHead(200, {
    "Content-Type": contentTypes[ext] ?? "application/octet-stream",
    "Cache-Control": ext === ".html" ? "no-cache" : "public, max-age=300",
  });
  createReadStream(filePath).pipe(res);
  return true;
}

function mapStoreError(error) {
  const code = error instanceof Error ? error.message : "unknown";
  const clientErrors = new Set([
    "invalid_product",
    "invalid_category",
    "invalid_status",
    "title_required",
    "body_required",
    "author_required",
    "post_not_found",
    "invalid_json",
    "payload_too_large",
  ]);
  if (clientErrors.has(code)) {
    return { status: 400, code };
  }
  return { status: 500, code: "internal_error" };
}

async function handleApi(req, res, pathname, searchParams) {
  if (req.method === "GET" && pathname === "/api/board/meta") {
    return sendJson(res, 200, {
      products: [...PRODUCTS],
      categories: [...CATEGORIES],
      auth: {
        enabled: false,
        providers: ["google", "kakao"],
        note: "소셜 로그인은 추후 연동 예정입니다. 현재는 작성자 이름으로 글을 남깁니다.",
      },
    });
  }

  if (req.method === "GET" && pathname === "/api/board/posts") {
    const result = listPosts({
      product: searchParams.get("product") ?? undefined,
      category: searchParams.get("category") ?? undefined,
      page: searchParams.get("page") ?? 1,
      pageSize: searchParams.get("pageSize") ?? 20,
    });
    return sendJson(res, 200, result);
  }

  const postMatch = pathname.match(/^\/api\/board\/posts\/(\d+)$/);
  if (postMatch) {
    const postId = Number(postMatch[1]);
    if (req.method === "GET") {
      const result = getPost(postId);
      if (!result) {
        return sendJson(res, 404, { error: "post_not_found" });
      }
      return sendJson(res, 200, result);
    }
    if (req.method === "PATCH") {
      try {
        const body = await readJsonBody(req);
        const post = updatePostStatus(postId, body.status);
        return sendJson(res, 200, { post });
      } catch (error) {
        const mapped = mapStoreError(error);
        return sendJson(res, mapped.status, { error: mapped.code });
      }
    }
  }

  const commentMatch = pathname.match(/^\/api\/board\/posts\/(\d+)\/comments$/);
  if (commentMatch && req.method === "POST") {
    const postId = Number(commentMatch[1]);
    try {
      const body = await readJsonBody(req);
      const comment = createComment(postId, body);
      return sendJson(res, 201, { comment });
    } catch (error) {
      const mapped = mapStoreError(error);
      return sendJson(res, mapped.status, { error: mapped.code });
    }
  }

  if (req.method === "POST" && pathname === "/api/board/posts") {
    try {
      const body = await readJsonBody(req);
      const post = createPost(body);
      return sendJson(res, 201, { post });
    } catch (error) {
      const mapped = mapStoreError(error);
      return sendJson(res, mapped.status, { error: mapped.code });
    }
  }

  return sendJson(res, 404, { error: "not_found" });
}

function handleBoardPage(res, pathname) {
  if (pathname === "/board" || pathname === "/board/") {
    if (serveStatic(res, "index.html")) {
      return true;
    }
  }
  if (pathname.startsWith("/board/assets/")) {
    const assetPath = pathname.slice("/board".length);
    if (serveStatic(res, assetPath)) {
      return true;
    }
  }
  return false;
}

const server = createServer(async (req, res) => {
  try {
    const host = req.headers.host ?? "localhost";
    const url = new URL(req.url ?? "/", `http://${host}`);
    const pathname = decodeURIComponent(url.pathname);

    if (pathname === "/health") {
      return sendJson(res, 200, { ok: true, service: "ch2-board" });
    }

    if (pathname.startsWith("/api/board")) {
      return handleApi(req, res, pathname, url.searchParams);
    }

    if (handleBoardPage(res, pathname)) {
      return;
    }

    if (pathname === "/" || pathname === "/index.html") {
      if (serveStatic(res, "index.html")) {
        return;
      }
    }

    if (pathname.startsWith("/assets/") && serveStatic(res, pathname)) {
      return;
    }

    sendText(res, 404, "Not Found");
  } catch (error) {
    console.error(error);
    sendJson(res, 500, { error: "internal_error" });
  }
});

function listen(port) {
  return new Promise((resolvePromise, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => {
      server.off("error", reject);
      resolvePromise(port);
    });
  });
}

async function start() {
  let port = preferredPort;
  for (let attempt = 0; attempt < 20; attempt += 1) {
    try {
      port = await listen(port);
      console.log(`CH2 board listening on http://127.0.0.1:${port}`);
      console.log(`  board UI: http://127.0.0.1:${port}/board`);
      return;
    } catch (error) {
      if (error && error.code === "EADDRINUSE") {
        port += 1;
        continue;
      }
      throw error;
    }
  }
  throw new Error(`Could not bind port starting at ${preferredPort}`);
}

start().catch((error) => {
  console.error(error);
  process.exit(1);
});
