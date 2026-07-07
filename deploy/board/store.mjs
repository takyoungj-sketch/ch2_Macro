import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = dirname(fileURLToPath(import.meta.url));
const dataDir = join(rootDir, "data");
const dataFile = join(dataDir, "board.json");

const PRODUCTS = new Set(["macro", "fieldnote", "viewer", "general"]);
const CATEGORIES = new Set(["question", "bug", "feature"]);
const STATUSES = new Set(["open", "resolved"]);

function emptyDb() {
  return {
    nextPostId: 1,
    nextCommentId: 1,
    posts: [],
    comments: [],
  };
}

function ensureDataDir() {
  if (!existsSync(dataDir)) {
    mkdirSync(dataDir, { recursive: true });
  }
}

function readDb() {
  ensureDataDir();
  if (!existsSync(dataFile)) {
    const db = emptyDb();
    writeDb(db);
    return db;
  }
  try {
    const parsed = JSON.parse(readFileSync(dataFile, "utf8"));
    return {
      nextPostId: Number(parsed.nextPostId) || 1,
      nextCommentId: Number(parsed.nextCommentId) || 1,
      posts: Array.isArray(parsed.posts) ? parsed.posts : [],
      comments: Array.isArray(parsed.comments) ? parsed.comments : [],
    };
  } catch {
    const backup = `${dataFile}.corrupt-${Date.now()}`;
    try {
      renameSync(dataFile, backup);
    } catch {
      /* ignore */
    }
    const db = emptyDb();
    writeDb(db);
    return db;
  }
}

function writeDb(db) {
  ensureDataDir();
  const tmp = `${dataFile}.tmp`;
  writeFileSync(tmp, `${JSON.stringify(db, null, 2)}\n`, "utf8");
  renameSync(tmp, dataFile);
}

function nowIso() {
  return new Date().toISOString();
}

function trimText(value, maxLen) {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) {
    return "";
  }
  return text.length > maxLen ? text.slice(0, maxLen) : text;
}

export function listPosts({ product, category, page = 1, pageSize = 20 } = {}) {
  const db = readDb();
  let items = [...db.posts].sort((a, b) => b.created_at.localeCompare(a.created_at));

  if (product && PRODUCTS.has(product)) {
    items = items.filter((post) => post.product === product);
  }
  if (category && CATEGORIES.has(category)) {
    items = items.filter((post) => post.category === category);
  }

  const total = items.length;
  const safePage = Math.max(1, Number(page) || 1);
  const safeSize = Math.min(50, Math.max(1, Number(pageSize) || 20));
  const offset = (safePage - 1) * safeSize;

  return {
    items: items.slice(offset, offset + safeSize),
    total,
    page: safePage,
    pageSize: safeSize,
    totalPages: Math.max(1, Math.ceil(total / safeSize)),
  };
}

export function getPost(id) {
  const db = readDb();
  const post = db.posts.find((item) => item.id === id);
  if (!post) {
    return null;
  }
  const comments = db.comments
    .filter((item) => item.post_id === id)
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  return { post, comments };
}

export function createPost(input) {
  const product = trimText(input.product, 32).toLowerCase();
  const category = trimText(input.category, 32).toLowerCase();
  const title = trimText(input.title, 200);
  const body = trimText(input.body, 12000);
  const authorName = trimText(input.author_name, 80);

  if (!PRODUCTS.has(product)) {
    throw new Error("invalid_product");
  }
  if (!CATEGORIES.has(category)) {
    throw new Error("invalid_category");
  }
  if (!title) {
    throw new Error("title_required");
  }
  if (!body) {
    throw new Error("body_required");
  }
  if (!authorName) {
    throw new Error("author_required");
  }

  const db = readDb();
  const createdAt = nowIso();
  const post = {
    id: db.nextPostId++,
    product,
    category,
    title,
    body,
    author_name: authorName,
    author_id: input.author_id ?? null,
    auth_provider: input.auth_provider ?? null,
    status: "open",
    created_at: createdAt,
    updated_at: createdAt,
  };

  db.posts.push(post);
  writeDb(db);
  return post;
}

export function createComment(postId, input) {
  const body = trimText(input.body, 8000);
  const authorName = trimText(input.author_name, 80);

  if (!body) {
    throw new Error("body_required");
  }
  if (!authorName) {
    throw new Error("author_required");
  }

  const db = readDb();
  const post = db.posts.find((item) => item.id === postId);
  if (!post) {
    throw new Error("post_not_found");
  }

  const comment = {
    id: db.nextCommentId++,
    post_id: postId,
    body,
    author_name: authorName,
    author_id: input.author_id ?? null,
    auth_provider: input.auth_provider ?? null,
    created_at: nowIso(),
  };

  db.comments.push(comment);
  post.updated_at = comment.created_at;
  writeDb(db);
  return comment;
}

export function updatePostStatus(postId, status) {
  if (!STATUSES.has(status)) {
    throw new Error("invalid_status");
  }
  const db = readDb();
  const post = db.posts.find((item) => item.id === postId);
  if (!post) {
    throw new Error("post_not_found");
  }
  post.status = status;
  post.updated_at = nowIso();
  writeDb(db);
  return post;
}

export { PRODUCTS, CATEGORIES, STATUSES };
