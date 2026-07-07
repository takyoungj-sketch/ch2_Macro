const API_BASE = "/api/board";

const PRODUCT_LABELS = {
  macro: "Macro",
  fieldnote: "FieldNote",
  viewer: "Viewer",
  general: "공통",
};

const CATEGORY_LABELS = {
  question: "질문",
  bug: "오류 보고",
  feature: "기능 개선",
};

const state = {
  page: 1,
  totalPages: 1,
  currentPostId: null,
};

function $(id) {
  return document.getElementById(id);
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function excerpt(text, max = 120) {
  const normalized = String(text ?? "").replace(/\s+/g, " ").trim();
  if (normalized.length <= max) {
    return normalized;
  }
  return `${normalized.slice(0, max)}…`;
}

function badge(className, label) {
  return `<span class="badge ${className}">${label}</span>`;
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.error ?? "request_failed";
    throw new Error(message);
  }
  return payload;
}

function showListView() {
  $("list-view").hidden = false;
  $("detail-view").hidden = true;
  state.currentPostId = null;
  const url = new URL(window.location.href);
  url.searchParams.delete("post");
  window.history.replaceState({}, "", url);
}

function showDetailView(postId) {
  $("list-view").hidden = true;
  $("detail-view").hidden = false;
  state.currentPostId = postId;
  const url = new URL(window.location.href);
  url.searchParams.set("post", String(postId));
  window.history.replaceState({}, "", url);
}

function renderPostItem(post) {
  const li = document.createElement("li");
  li.className = "post-item";
  li.innerHTML = `
    <a class="post-item__link" href="?post=${post.id}">
      <div class="post-item__meta">
        ${badge("badge--product", PRODUCT_LABELS[post.product] ?? post.product)}
        ${badge(`badge--${post.category}`, CATEGORY_LABELS[post.category] ?? post.category)}
        ${post.status === "resolved" ? badge("badge--status", "해결됨") : ""}
      </div>
      <h3 class="post-item__title">${escapeHtml(post.title)}</h3>
      <p class="post-item__excerpt">${escapeHtml(excerpt(post.body))}</p>
      <p class="post-item__info">${escapeHtml(post.author_name)} · ${formatDate(post.created_at)}</p>
    </a>
  `;
  li.querySelector("a").addEventListener("click", (event) => {
    event.preventDefault();
    loadPost(post.id);
  });
  return li;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function loadPosts() {
  const product = $("filter-product").value;
  const category = $("filter-category").value;
  const params = new URLSearchParams({ page: String(state.page), pageSize: "20" });
  if (product) {
    params.set("product", product);
  }
  if (category) {
    params.set("category", category);
  }

  $("list-meta").textContent = "불러오는 중…";
  const data = await api(`/posts?${params.toString()}`);
  const list = $("post-list");
  list.replaceChildren();

  state.totalPages = data.totalPages;
  $("page-label").textContent = `${data.page} / ${data.totalPages}`;
  $("pager").hidden = data.totalPages <= 1;
  $("prev-page").disabled = data.page <= 1;
  $("next-page").disabled = data.page >= data.totalPages;
  $("empty-state").hidden = data.items.length > 0;
  $("list-meta").textContent = `총 ${data.total}건`;

  for (const post of data.items) {
    list.appendChild(renderPostItem(post));
  }
}

function renderPostDetail(post, comments) {
  $("post-detail").innerHTML = `
    <div class="post-item__meta">
      ${badge("badge--product", PRODUCT_LABELS[post.product] ?? post.product)}
      ${badge(`badge--${post.category}`, CATEGORY_LABELS[post.category] ?? post.category)}
      ${post.status === "resolved" ? badge("badge--status", "해결됨") : ""}
    </div>
    <h1 class="detail__title">${escapeHtml(post.title)}</h1>
    <div class="detail__body">${escapeHtml(post.body)}</div>
    <p class="detail__info">${escapeHtml(post.author_name)} · ${formatDate(post.created_at)}</p>
  `;

  const commentList = $("comment-list");
  commentList.replaceChildren();
  if (!comments.length) {
    const empty = document.createElement("li");
    empty.className = "comment-item";
    empty.innerHTML = `<p class="comment-item__meta">아직 댓글이 없습니다.</p>`;
    commentList.appendChild(empty);
    return;
  }

  for (const comment of comments) {
    const li = document.createElement("li");
    li.className = "comment-item";
    li.innerHTML = `
      <p class="comment-item__meta">${escapeHtml(comment.author_name)} · ${formatDate(comment.created_at)}</p>
      <div class="comment-item__body">${escapeHtml(comment.body)}</div>
    `;
    commentList.appendChild(li);
  }
}

async function loadPost(postId) {
  const data = await api(`/posts/${postId}`);
  renderPostDetail(data.post, data.comments);
  showDetailView(postId);
}

async function loadMeta() {
  const meta = await api("/meta");
  const notice = $("auth-notice");
  const noticeText = $("auth-notice-text");
  if (meta.auth && !meta.auth.enabled) {
    notice.hidden = false;
    noticeText.textContent = meta.auth.note ?? "";
  }
}

function bindEvents() {
  $("filter-product").addEventListener("change", () => {
    state.page = 1;
    loadPosts().catch(showError);
  });
  $("filter-category").addEventListener("change", () => {
    state.page = 1;
    loadPosts().catch(showError);
  });
  $("refresh-btn").addEventListener("click", () => loadPosts().catch(showError));
  $("prev-page").addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    loadPosts().catch(showError);
  });
  $("next-page").addEventListener("click", () => {
    state.page = Math.min(state.totalPages, state.page + 1);
    loadPosts().catch(showError);
  });

  $("new-post-btn").addEventListener("click", () => {
    $("compose-panel").hidden = false;
  });
  $("compose-cancel").addEventListener("click", () => {
    $("compose-panel").hidden = true;
  });

  $("compose-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    try {
      const result = await api("/posts", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      form.reset();
      $("compose-panel").hidden = true;
      await loadPosts();
      await loadPost(result.post.id);
    } catch (error) {
      showError(error);
    }
  });

  $("comment-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.currentPostId) {
      return;
    }
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    try {
      await api(`/posts/${state.currentPostId}/comments`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      form.reset();
      await loadPost(state.currentPostId);
    } catch (error) {
      showError(error);
    }
  });

  $("back-to-list").addEventListener("click", () => {
    showListView();
    loadPosts().catch(showError);
  });
}

function showError(error) {
  const message =
    error instanceof Error && error.message
      ? error.message
      : "요청 처리 중 오류가 발생했습니다.";
  window.alert(message);
}

async function boot() {
  bindEvents();
  await loadMeta();
  const postId = new URL(window.location.href).searchParams.get("post");
  if (postId) {
    await loadPost(Number(postId));
    return;
  }
  showListView();
  await loadPosts();
}

boot().catch(showError);
