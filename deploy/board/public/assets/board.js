const API_BASE = "/api/board";
const AUTH_BASE = "/api/auth";

const PRODUCT_LABELS = {
  macro: "Macro",
  fieldnote: "FieldNote",
  viewer: "Viewer",
  general: "공용",
};

const CATEGORY_LABELS = {
  question: "질문",
  bug: "오류",
  feature: "기능개선",
};

const STATUS_LABELS = {
  open: "접수",
  checking: "확인중",
  answered: "답변완료",
  planned: "개선예정",
  done: "반영완료",
};

const state = {
  page: 1,
  totalPages: 1,
  currentPostId: null,
  mine: false,
  searchTimer: null,
  auth: {
    loggedIn: false,
    nickname: "",
    role: "member",
    userId: null,
    providers: { google: true, kakao: false },
  },
};

function $(id) {
  return document.getElementById(id);
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const yy = String(date.getFullYear()).slice(2);
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mi = String(date.getMinutes()).padStart(2, "0");
  return `${yy}.${mm}.${dd} ${hh}:${mi}`;
}

function excerpt(text, max = 80) {
  const normalized = String(text ?? "").replace(/\s+/g, " ").trim();
  if (normalized.length <= max) {
    return normalized;
  }
  return `${normalized.slice(0, max)}…`;
}

function badge(className, label) {
  return `<span class="badge ${className}">${escapeHtml(label)}</span>`;
}

function statusBadge(status, isPinned) {
  if (isPinned) {
    return badge("badge--pin", "공지");
  }
  const label = STATUS_LABELS[status] ?? status;
  return badge(`badge--status badge--status-${status}`, label);
}

function parseError(payload) {
  if (typeof payload.detail === "string") {
    return payload.detail;
  }
  if (payload.detail && typeof payload.detail.message === "string") {
    return payload.detail.message;
  }
  if (typeof payload.error === "string") {
    return payload.error;
  }
  return "request_failed";
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(payload));
  }
  return payload;
}

async function authApi(path, options = {}) {
  const response = await fetch(`${AUTH_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(payload));
  }
  return payload;
}

function setUserMenuOpen(open) {
  const drop = $("user-menu-drop");
  const btn = $("user-menu-btn");
  if (!drop || !btn) {
    return;
  }
  drop.hidden = !open;
  btn.setAttribute("aria-expanded", open ? "true" : "false");
}

function updateAuthBar() {
  const loginBtn = $("login-btn");
  const kakaoBtn = $("kakao-login-btn");
  const loginActions = $("login-actions");
  const userMenu = $("user-menu");
  const userLabel = $("auth-user");
  const pinField = $("pin-field");
  if (state.auth.loggedIn) {
    userLabel.textContent = state.auth.nickname || "사용자";
    if (loginActions) {
      loginActions.hidden = true;
    }
    loginBtn.hidden = true;
    if (kakaoBtn) {
      kakaoBtn.hidden = true;
    }
    userMenu.hidden = false;
  } else {
    if (loginActions) {
      loginActions.hidden = false;
    }
    loginBtn.hidden = !state.auth.providers.google;
    if (kakaoBtn) {
      kakaoBtn.hidden = !state.auth.providers.kakao;
    }
    userMenu.hidden = true;
    setUserMenuOpen(false);
    state.mine = false;
  }
  if (pinField) {
    pinField.hidden = !(state.auth.loggedIn && state.auth.role === "admin");
  }
  updateMineChip();
  toggleAuthorFields(!state.auth.loggedIn);
}

function updateMineChip() {
  const chip = $("mine-chip");
  if (!chip) {
    return;
  }
  chip.hidden = !state.mine;
}

const NICK_PROMPT_KEY = "ch2-board-nick-prompted";

function maybeShowNickPrompt() {
  const panel = $("nick-prompt");
  if (!panel) {
    return;
  }
  if (!state.auth.loggedIn) {
    panel.hidden = true;
    return;
  }
  if (window.localStorage.getItem(NICK_PROMPT_KEY) === "1") {
    return;
  }
  $("nick-input").value = state.auth.nickname || "";
  panel.hidden = false;
}

function toggleAuthorFields(show) {
  for (const field of document.querySelectorAll(".author-field")) {
    field.hidden = !show;
    const input = field.querySelector("input");
    if (input) {
      input.required = show;
    }
  }
}

async function refreshAuthStatus() {
  try {
    const status = await authApi("/status");
    state.auth.loggedIn = Boolean(status.logged_in);
    state.auth.nickname = status.nickname ?? "";
    state.auth.role = status.role ?? "member";
    state.auth.userId = status.id ?? null;
    if (status.providers) {
      state.auth.providers = status.providers;
    }
  } catch {
    state.auth.loggedIn = false;
    state.auth.nickname = "";
    state.auth.userId = null;
  }
  updateAuthBar();
  maybeShowNickPrompt();
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

function renderPostItem(post, { notice = false } = {}) {
  const li = document.createElement("li");
  li.className = notice ? "post-item post-item--notice" : "post-item";
  const bodyPreview = post.excerpt || excerpt(post.body || "");
  const comments = Number(post.comment_count || 0);
  li.innerHTML = `
    <a class="post-item__link" href="?post=${post.id}">
      <div class="post-item__head">
        ${badge("badge--product", PRODUCT_LABELS[post.product] ?? post.product)}
        ${badge(`badge--${post.category}`, CATEGORY_LABELS[post.category] ?? post.category)}
        ${statusBadge(post.status, post.is_pinned)}
        <h3 class="post-item__title">${escapeHtml(post.title)}</h3>
      </div>
      <p class="post-item__excerpt">${escapeHtml(bodyPreview)}</p>
      <p class="post-item__info">
        <span>${escapeHtml(post.author_name)} · ${formatDate(post.created_at)}</span>
        <span>댓글 ${comments}</span>
      </p>
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
  const status = $("filter-status").value;
  const q = ($("filter-q").value || "").trim();
  const params = new URLSearchParams({ page: String(state.page), pageSize: "20" });
  if (product) {
    params.set("product", product);
  }
  if (category) {
    params.set("category", category);
  }
  if (status) {
    params.set("status", status);
  }
  if (q) {
    params.set("q", q);
  }
  if (state.mine) {
    params.set("mine", "true");
  }

  $("list-meta").textContent = "불러오는 중…";
  const data = await api(`/posts?${params.toString()}`);
  const list = $("post-list");
  list.replaceChildren();

  const noticePanel = $("notice-panel");
  const noticeList = $("notice-list");
  noticeList.replaceChildren();
  const notices = data.notices || [];
  noticePanel.hidden = notices.length === 0;
  for (const post of notices) {
    noticeList.appendChild(renderPostItem(post, { notice: true }));
  }

  state.totalPages = data.totalPages;
  $("page-label").textContent = `${data.page} / ${data.totalPages}`;
  $("pager").hidden = data.totalPages <= 1;
  $("prev-page").disabled = data.page <= 1;
  $("next-page").disabled = data.page >= data.totalPages;
  $("empty-state").hidden = data.items.length > 0 || notices.length > 0;
  $("list-meta").textContent = `총 ${data.total}건`;

  for (const post of data.items) {
    list.appendChild(renderPostItem(post));
  }
}

function renderPostDetail(post, comments) {
  $("post-detail").innerHTML = `
    <div class="post-item__head">
      ${badge("badge--product", PRODUCT_LABELS[post.product] ?? post.product)}
      ${badge(`badge--${post.category}`, CATEGORY_LABELS[post.category] ?? post.category)}
      ${statusBadge(post.status, post.is_pinned)}
    </div>
    <h1 class="detail__title">${escapeHtml(post.title)}</h1>
    <div class="detail__body">${escapeHtml(post.body)}</div>
    <p class="detail__info">${escapeHtml(post.author_name)} · ${formatDate(post.created_at)}</p>
  `;

  const actions = $("post-actions");
  const adminWrap = $("status-admin-wrap");
  const statusSelect = $("status-select");
  const authorBtn = $("status-author-btn");
  const pinBtn = $("pin-btn");
  const isAdmin = state.auth.loggedIn && state.auth.role === "admin";
  const isAuthor =
    state.auth.loggedIn && Number(post.author_id) === Number(state.auth.userId);
  const showActions = isAdmin || isAuthor;
  actions.hidden = !showActions;

  if (isAdmin) {
    adminWrap.hidden = false;
    statusSelect.value = post.status;
    statusSelect.dataset.postId = String(post.id);
    pinBtn.hidden = false;
    pinBtn.dataset.postId = String(post.id);
    pinBtn.dataset.pinned = post.is_pinned ? "1" : "0";
    pinBtn.textContent = post.is_pinned ? "공지 해제" : "공지 고정";
  } else {
    adminWrap.hidden = true;
    pinBtn.hidden = true;
  }

  if (!isAdmin && isAuthor && (post.status === "open" || post.status === "answered")) {
    authorBtn.hidden = false;
    authorBtn.dataset.postId = String(post.id);
    authorBtn.dataset.status = post.status;
    authorBtn.textContent = post.status === "answered" ? "다시 접수로" : "답변완료로 표시";
  } else {
    authorBtn.hidden = true;
  }

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
  if (meta.auth && meta.auth.enabled) {
    notice.hidden = true;
  } else if (meta.auth) {
    notice.hidden = false;
    noticeText.textContent = meta.auth.note ?? "Google 로그인 설정 중입니다.";
  }
}

function scheduleSearch() {
  window.clearTimeout(state.searchTimer);
  state.searchTimer = window.setTimeout(() => {
    state.page = 1;
    loadPosts().catch(showError);
  }, 350);
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
  $("filter-status").addEventListener("change", () => {
    state.page = 1;
    loadPosts().catch(showError);
  });
  $("filter-q").addEventListener("input", scheduleSearch);
  $("filter-q").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      window.clearTimeout(state.searchTimer);
      state.page = 1;
      loadPosts().catch(showError);
    }
  });
  $("prev-page").addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    loadPosts().catch(showError);
  });
  $("next-page").addEventListener("click", () => {
    state.page = Math.min(state.totalPages, state.page + 1);
    loadPosts().catch(showError);
  });

  $("login-btn").addEventListener("click", () => {
    const next = encodeURIComponent(window.location.pathname + window.location.search || "/board/");
    window.location.href = `${AUTH_BASE}/google/login?next=${next}`;
  });
  const kakaoLogin = $("kakao-login-btn");
  if (kakaoLogin) {
    kakaoLogin.addEventListener("click", () => {
      const next = encodeURIComponent(window.location.pathname + window.location.search || "/board/");
      window.location.href = `${AUTH_BASE}/kakao/login?next=${next}`;
    });
  }

  $("user-menu-btn").addEventListener("click", (event) => {
    event.stopPropagation();
    const drop = $("user-menu-drop");
    setUserMenuOpen(drop.hidden);
  });
  document.addEventListener("click", (event) => {
    const menu = $("user-menu");
    if (menu && !menu.contains(event.target)) {
      setUserMenuOpen(false);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setUserMenuOpen(false);
    }
  });

  $("logout-btn").addEventListener("click", () => {
    setUserMenuOpen(false);
    authApi("/logout", { method: "POST" })
      .then(() => refreshAuthStatus())
      .then(() => loadPosts())
      .catch(showError);
  });

  $("mine-btn").addEventListener("click", () => {
    if (!state.auth.loggedIn) {
      return;
    }
    state.mine = true;
    state.page = 1;
    setUserMenuOpen(false);
    updateMineChip();
    showListView();
    loadPosts().catch(showError);
  });
  $("mine-chip").addEventListener("click", () => {
    state.mine = false;
    state.page = 1;
    updateMineChip();
    loadPosts().catch(showError);
  });

  const nickSave = $("nick-save");
  const nickSkip = $("nick-skip");
  const nickEdit = $("nick-edit-btn");
  if (nickSave) {
    nickSave.addEventListener("click", async () => {
      const nick = ($("nick-input").value || "").trim();
      if (nick.length < 2) {
        showError(new Error("닉네임은 2자 이상이어야 합니다."));
        return;
      }
      try {
        const result = await authApi("/me", {
          method: "PATCH",
          body: JSON.stringify({ nickname: nick }),
        });
        state.auth.nickname = result.nickname;
        window.localStorage.setItem(NICK_PROMPT_KEY, "1");
        $("nick-prompt").hidden = true;
        updateAuthBar();
      } catch (error) {
        showError(error);
      }
    });
  }
  if (nickSkip) {
    nickSkip.addEventListener("click", () => {
      window.localStorage.setItem(NICK_PROMPT_KEY, "1");
      $("nick-prompt").hidden = true;
    });
  }
  if (nickEdit) {
    nickEdit.addEventListener("click", () => {
      setUserMenuOpen(false);
      window.localStorage.removeItem(NICK_PROMPT_KEY);
      maybeShowNickPrompt();
    });
  }

  $("status-select").addEventListener("change", async (event) => {
    const select = event.currentTarget;
    const postId = select.dataset.postId;
    if (!postId) {
      return;
    }
    try {
      await api(`/posts/${postId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: select.value }),
      });
      await loadPost(Number(postId));
    } catch (error) {
      showError(error);
    }
  });
  $("status-author-btn").addEventListener("click", async () => {
    const btn = $("status-author-btn");
    const postId = btn.dataset.postId;
    const current = btn.dataset.status;
    if (!postId) {
      return;
    }
    const next = current === "answered" ? "open" : "answered";
    try {
      await api(`/posts/${postId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: next }),
      });
      await loadPost(Number(postId));
    } catch (error) {
      showError(error);
    }
  });
  $("pin-btn").addEventListener("click", async () => {
    const btn = $("pin-btn");
    const postId = btn.dataset.postId;
    if (!postId) {
      return;
    }
    const pinned = btn.dataset.pinned === "1";
    try {
      await api(`/posts/${postId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_pinned: !pinned }),
      });
      await loadPost(Number(postId));
    } catch (error) {
      showError(error);
    }
  });

  $("new-post-btn").addEventListener("click", () => {
    if (!state.auth.loggedIn) {
      window.alert("글쓰기는 로그인 후 이용할 수 있습니다.");
      return;
    }
    $("compose-panel").hidden = false;
  });
  $("compose-cancel").addEventListener("click", () => {
    $("compose-panel").hidden = true;
  });

  $("compose-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.auth.loggedIn) {
      showError(new Error("로그인이 필요합니다."));
      return;
    }
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    delete payload.author_name;
    payload.is_pinned = formData.get("is_pinned") === "true";
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
    if (!state.auth.loggedIn) {
      showError(new Error("로그인이 필요합니다."));
      return;
    }
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    delete payload.author_name;
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
  await refreshAuthStatus();
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
