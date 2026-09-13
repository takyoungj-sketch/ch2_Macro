const API_BASE = "/api/board";
const AUTH_BASE = "/api/auth";

const PRODUCT_LABELS = {
  macro: "CH2 Macro",
  fieldnote: "CH2 FieldNote",
  viewer: "CH2 Viewer",
  general: "기타",
};

const CATEGORY_LABELS = {
  question: "사용 문의",
  bug: "오류 신고",
  feature: "기능 개선",
  data: "데이터",
  other: "기타",
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
  currentPost: null,
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

function formatDateShort(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const yy = String(date.getFullYear()).slice(2);
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  return `${yy}.${mm}.${dd}`;
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

function secretBadge(_isSecret) {
  return "";
}

function isAdmin() {
  return state.auth.loggedIn && state.auth.role === "admin";
}

function updateVoiceLayout() {
  const gate = $("login-gate");
  const compose = $("compose-panel");
  const toolbar = $("admin-toolbar");
  const heading = $("list-heading");
  if (gate) {
    gate.hidden = state.auth.loggedIn;
  }
  if (compose) {
    compose.hidden = !state.auth.loggedIn;
  }
  if (toolbar) {
    toolbar.hidden = !isAdmin();
  }
  if (heading) {
    heading.textContent = isAdmin() ? "접수 목록" : "내가 보낸 의견";
  }
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
  updateVoiceLayout();
  updateMineChip();
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
  state.currentPost = null;
  const editPanel = $("edit-post-panel");
  if (editPanel) {
    editPanel.hidden = true;
  }
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
  const comments = Number(post.comment_count || 0);
  li.innerHTML = `
    <a class="post-item__link" href="?post=${post.id}">
      <div class="post-item__main">
        ${badge("badge--product", PRODUCT_LABELS[post.product] ?? post.product)}
        ${badge(`badge--${post.category}`, CATEGORY_LABELS[post.category] ?? post.category)}
        ${statusBadge(post.status, post.is_pinned)}
        ${secretBadge(post.is_secret)}
        <h3 class="post-item__title">${escapeHtml(post.title)}</h3>
      </div>
      <span class="post-item__author">${escapeHtml(post.author_name)}</span>
      <span class="post-item__date">${escapeHtml(formatDateShort(post.created_at))}</span>
      <span class="post-item__cmt">${comments}</span>
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
  $("empty-state").hidden = !state.auth.loggedIn || data.items.length > 0 || notices.length > 0;
  $("list-meta").textContent = `총 ${data.total}건`;

  for (const post of data.items) {
    list.appendChild(renderPostItem(post));
  }
}

function renderPostDetail(post, comments) {
  const bodyHidden = Boolean(post.body_hidden);
  const bodyHtml = bodyHidden
    ? `<div class="detail__body detail__body--hidden">${escapeHtml("작성자와 관리자만 볼 수 있습니다.")}</div>`
    : `<div class="detail__body">${escapeHtml(post.body || "")}</div>`;
  $("post-detail").innerHTML = `
    <div class="post-item__head">
      ${badge("badge--product", PRODUCT_LABELS[post.product] ?? post.product)}
      ${badge(`badge--${post.category}`, CATEGORY_LABELS[post.category] ?? post.category)}
      ${statusBadge(post.status, post.is_pinned)}
      ${secretBadge(post.is_secret)}
    </div>
    <h1 class="detail__title">${escapeHtml(post.title)}</h1>
    ${bodyHtml}
    <p class="detail__info">${escapeHtml(post.author_name)} · ${formatDate(post.created_at)}</p>
  `;

  const actions = $("post-actions");
  const adminWrap = $("status-admin-wrap");
  const statusSelect = $("status-select");
  const authorBtn = $("status-author-btn");
  const pinBtn = $("pin-btn");
  const editBtn = $("edit-post-btn");
  const deleteBtn = $("delete-post-btn");
  const editPanel = $("edit-post-panel");
  if (editPanel) {
    editPanel.hidden = true;
  }
  const isAdmin = state.auth.loggedIn && state.auth.role === "admin";
  const isAuthor =
    state.auth.loggedIn && Number(post.author_id) === Number(state.auth.userId);
  const canDelete = Boolean(post.can_delete) || isAdmin || isAuthor;
  const canEdit = Boolean(post.can_edit) || isAdmin || isAuthor;
  const showActions = isAdmin || isAuthor || canDelete || canEdit;
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

  if (canEdit && !bodyHidden) {
    editBtn.hidden = false;
    editBtn.dataset.postId = String(post.id);
  } else {
    editBtn.hidden = true;
  }

  if (canDelete) {
    deleteBtn.hidden = false;
    deleteBtn.dataset.postId = String(post.id);
  } else {
    deleteBtn.hidden = true;
  }

  const commentForm = $("comment-form");
  const commentLocked = $("comment-locked");
  const canComment = !bodyHidden && post.can_comment !== false;
  commentForm.hidden = !canComment;
  if (commentLocked) {
    commentLocked.hidden = !bodyHidden;
  }

  const commentList = $("comment-list");
  commentList.replaceChildren();
  if (bodyHidden) {
    return;
  }
  if (!comments.length) {
    const empty = document.createElement("li");
    empty.className = "comment-item";
    empty.innerHTML = `<p class="comment-item__meta">아직 답변이 없습니다.</p>`;
    commentList.appendChild(empty);
    return;
  }

  for (const comment of comments) {
    const li = document.createElement("li");
    li.className = "comment-item";
    const canDeleteComment = Boolean(comment.can_delete);
    const canEditComment = Boolean(comment.can_edit);
    const actions = [];
    if (canEditComment) {
      actions.push(
        `<button type="button" class="btn btn--ghost btn--sm comment-edit" data-comment-id="${comment.id}">수정</button>`
      );
    }
    if (canDeleteComment) {
      actions.push(
        `<button type="button" class="btn btn--danger btn--sm comment-delete" data-comment-id="${comment.id}">삭제</button>`
      );
    }
    const actionsHtml = actions.length
      ? `<div class="comment-item__actions">${actions.join("")}</div>`
      : "";
    li.dataset.body = comment.body;
    li.innerHTML = `
      <div class="comment-item__head">
        <p class="comment-item__meta">${escapeHtml(comment.author_name)} · ${formatDate(comment.created_at)}</p>
        ${actionsHtml}
      </div>
      <div class="comment-item__body">${escapeHtml(comment.body)}</div>
    `;
    commentList.appendChild(li);
  }
}

async function loadPost(postId) {
  const data = await api(`/posts/${postId}`);
  state.currentPost = data.post;
  renderPostDetail(data.post, data.comments);
  renderNeighbors(data.neighbors);
  showDetailView(postId);
}

function renderNeighbors(neighbors) {
  const nav = $("post-nav");
  const newerLink = $("nav-newer");
  const olderLink = $("nav-older");
  if (!nav || !newerLink || !olderLink) {
    return;
  }
  const newer = neighbors && neighbors.newer;
  const older = neighbors && neighbors.older;
  nav.hidden = !newer && !older;
  newerLink.hidden = !newer;
  olderLink.hidden = !older;
  if (newer) {
    newerLink.href = `?post=${newer.id}`;
    newerLink.dataset.postId = String(newer.id);
    $("nav-newer-title").textContent = newer.title;
  }
  if (older) {
    olderLink.href = `?post=${older.id}`;
    olderLink.dataset.postId = String(older.id);
    $("nav-older-title").textContent = older.title;
  }
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

  $("delete-post-btn").addEventListener("click", async () => {
    const postId = $("delete-post-btn").dataset.postId;
    if (!postId) {
      return;
    }
    if (!window.confirm("이 글을 삭제할까요? 댓글도 함께 지워집니다.")) {
      return;
    }
    try {
      await api(`/posts/${postId}`, { method: "DELETE" });
      showListView();
      await loadPosts();
    } catch (error) {
      showError(error);
    }
  });

  $("edit-post-btn").addEventListener("click", () => {
    const post = state.currentPost;
    const panel = $("edit-post-panel");
    const form = $("edit-post-form");
    if (!post || !panel || !form) {
      return;
    }
    form.querySelector('[name="title"]').value = post.title || "";
    form.querySelector('[name="body"]').value = post.body || "";
    panel.hidden = false;
    panel.scrollIntoView({ block: "nearest" });
  });
  $("edit-post-cancel").addEventListener("click", () => {
    $("edit-post-panel").hidden = true;
  });
  $("edit-post-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const postId = state.currentPostId;
    if (!postId) {
      return;
    }
    const form = event.currentTarget;
    const formData = new FormData(form);
    try {
      await api(`/posts/${postId}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: String(formData.get("title") || "").trim(),
          body: String(formData.get("body") || "").trim(),
          is_secret: formData.get("is_secret") === "true",
        }),
      });
      $("edit-post-panel").hidden = true;
      await loadPost(postId);
    } catch (error) {
      showError(error);
    }
  });

  $("nav-newer").addEventListener("click", (event) => {
    event.preventDefault();
    const postId = $("nav-newer").dataset.postId;
    if (postId) {
      loadPost(Number(postId)).catch(showError);
    }
  });
  $("nav-older").addEventListener("click", (event) => {
    event.preventDefault();
    const postId = $("nav-older").dataset.postId;
    if (postId) {
      loadPost(Number(postId)).catch(showError);
    }
  });

  $("comment-list").addEventListener("click", async (event) => {
    const btn = event.target.closest("button");
    if (!btn || !state.currentPostId) {
      return;
    }
    const commentId = btn.dataset.commentId;
    if (btn.classList.contains("comment-delete")) {
      if (!commentId) {
        return;
      }
      if (!window.confirm("이 댓글을 삭제할까요?")) {
        return;
      }
      try {
        await api(`/posts/${state.currentPostId}/comments/${commentId}`, {
          method: "DELETE",
        });
        await loadPost(state.currentPostId);
      } catch (error) {
        showError(error);
      }
      return;
    }
    if (btn.classList.contains("comment-edit")) {
      const item = btn.closest(".comment-item");
      const bodyEl = item && item.querySelector(".comment-item__body");
      if (!item || !bodyEl || bodyEl.querySelector("textarea")) {
        return;
      }
      const ta = document.createElement("textarea");
      ta.className = "comment-edit-input";
      ta.maxLength = 8000;
      ta.value = item.dataset.body || "";
      const actions = document.createElement("div");
      actions.className = "form__actions";
      actions.innerHTML = `
        <button type="button" class="btn btn--ghost btn--sm comment-edit-cancel">취소</button>
        <button type="button" class="btn btn--primary btn--sm comment-edit-save" data-comment-id="${commentId}">저장</button>
      `;
      bodyEl.replaceChildren(ta, actions);
      ta.focus();
      return;
    }
    if (btn.classList.contains("comment-edit-cancel")) {
      await loadPost(state.currentPostId).catch(showError);
      return;
    }
    if (btn.classList.contains("comment-edit-save")) {
      if (!commentId) {
        return;
      }
      const item = btn.closest(".comment-item");
      const ta = item && item.querySelector(".comment-edit-input");
      const nextBody = ta ? ta.value.trim() : "";
      if (!nextBody) {
        showError(new Error("댓글 내용을 입력해 주세요."));
        return;
      }
      try {
        await api(`/posts/${state.currentPostId}/comments/${commentId}`, {
          method: "PATCH",
          body: JSON.stringify({ body: nextBody }),
        });
        await loadPost(state.currentPostId);
      } catch (error) {
        showError(error);
      }
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
    $("compose-form").reset();
  });

  $("compose-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.auth.loggedIn) {
      showError(new Error("로그인이 필요합니다."));
      return;
    }
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = {
      product: String(formData.get("product") || ""),
      category: String(formData.get("category") || ""),
      title: String(formData.get("title") || "").trim(),
      body: String(formData.get("body") || "").trim(),
      is_pinned: formData.get("is_pinned") === "true",
      is_secret: true,
      want_reply: formData.get("no_reply") !== "true",
    };
    try {
      const result = await api("/posts", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      form.reset();
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
