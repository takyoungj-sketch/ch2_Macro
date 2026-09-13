const AUTH_BASE = "/api/auth";
const BOARD_BASE = "/api/board";
const OPS_BASE = "/api/ops";

const PRODUCT_LABELS = {
  macro: "Macro",
  fieldnote: "FieldNote",
  viewer: "Viewer",
  general: "기타",
};

const CATEGORY_LABELS = {
  question: "문의",
  bug: "오류",
  feature: "제안",
  data: "데이터",
  other: "기타",
};

const STATUS_LABELS = {
  open: "신규",
  checking: "확인중",
  answered: "답변완료",
  planned: "개선예정",
  done: "처리완료",
};

const state = {
  auth: { loggedIn: false, role: "member", nickname: "", userId: null },
  page: 1,
  totalPages: 1,
  currentId: null,
  searchTimer: null,
};

function $(id) {
  return document.getElementById(id);
}

function ticketNo(id) {
  return `#${String(id).padStart(4, "0")}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
}

function formatDateShort(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" });
}

function parseError(payload) {
  if (typeof payload.detail === "string") {
    return payload.detail;
  }
  return "요청에 실패했습니다.";
}

async function api(base, path, options = {}) {
  const response = await fetch(`${base}${path}`, {
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

function parseHash() {
  const raw = (window.location.hash || "#/").replace(/^#/, "") || "/";
  const [path, query] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  const params = new URLSearchParams(query || "");
  if (parts[0] === "tickets" && parts[1]) {
    return { view: "detail", id: Number(parts[1]), status: params.get("status") || "" };
  }
  if (parts[0] === "tickets") {
    return { view: "tickets", id: null, status: params.get("status") || "" };
  }
  return { view: "dash", id: null, status: "" };
}

function isAdmin() {
  return state.auth.loggedIn && state.auth.role === "admin";
}

function showLogin(errorText) {
  $("login-view").hidden = false;
  $("app-view").hidden = true;
  const err = $("staff-login-error");
  if (errorText) {
    err.hidden = false;
    err.textContent = errorText;
  } else {
    err.hidden = true;
    err.textContent = "";
  }
}

function showApp() {
  $("login-view").hidden = true;
  $("app-view").hidden = false;
  $("admin-user").textContent = state.auth.nickname || "관리자";
}

function setNav(view) {
  $("nav-dash").classList.toggle("is-active", view === "dash");
  $("nav-tickets").classList.toggle("is-active", view === "tickets" || view === "detail");
}

async function refreshAuth() {
  const status = await api(AUTH_BASE, "/status");
  state.auth.loggedIn = Boolean(status.logged_in);
  state.auth.nickname = status.nickname || "";
  state.auth.role = status.role || "member";
  state.auth.userId = status.id ?? null;
  if (!isAdmin()) {
    showLogin(state.auth.loggedIn ? "관리 권한이 없습니다. 운영 비밀번호로 다시 들어가 주세요." : "");
    return false;
  }
  showApp();
  return true;
}

function formatCount(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return "0";
  }
  return n.toLocaleString("ko-KR");
}

async function loadDash() {
  const data = await api(OPS_BASE, "/dashboard");
  const tickets = data.tickets || {};
  $("stat-open").textContent = formatCount(tickets.open);
  $("stat-checking").textContent = formatCount(tickets.checking);
  $("stat-today").textContent = formatCount(tickets.today);
  const traffic = data.traffic || {};
  const today = traffic.today || {};
  const yesterday = traffic.yesterday || {};
  const total = traffic.total || {};
  $("tr-visitors-today").textContent = formatCount(today.visitors);
  $("tr-visitors-yesterday").textContent = formatCount(yesterday.visitors);
  $("tr-visitors-total").textContent = formatCount(total.visitors);
  $("tr-pv-today").textContent = formatCount(today.page_views);
  $("tr-pv-yesterday").textContent = formatCount(yesterday.page_views);
  $("tr-pv-total").textContent = formatCount(total.page_views);
  $("tr-dl-today").textContent = formatCount(today.downloads);
  $("tr-dl-yesterday").textContent = formatCount(yesterday.downloads);
  $("tr-dl-total").textContent = formatCount(total.downloads);
  $("tr-tk-today").textContent = formatCount(today.tickets);
  $("tr-tk-yesterday").textContent = formatCount(yesterday.tickets);
  $("tr-tk-total").textContent = formatCount(total.tickets);
  const body = $("recent-body");
  body.replaceChildren();
  const rows = tickets.recent || [];
  $("recent-empty").hidden = rows.length > 0;
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(STATUS_LABELS[row.status] || row.status)}</td>
      <td>${escapeHtml(PRODUCT_LABELS[row.product] || row.product)}</td>
      <td>${escapeHtml(CATEGORY_LABELS[row.category] || row.category)}</td>
      <td><a href="#/tickets/${row.id}">${escapeHtml(row.ticket_no || ticketNo(row.id))} ${escapeHtml(row.title)}</a></td>
      <td>${escapeHtml(formatDateShort(row.created_at))}</td>
    `;
    body.appendChild(tr);
  }
}

async function loadTickets() {
  const status = $("filter-status").value;
  const product = $("filter-product").value;
  const q = ($("filter-q").value || "").trim();
  const params = new URLSearchParams({ page: String(state.page), pageSize: "20" });
  if (status) {
    params.set("status", status);
  }
  if (product) {
    params.set("product", product);
  }
  if (q) {
    params.set("q", q);
  }
  $("list-meta").textContent = "불러오는 중…";
  const data = await api(BOARD_BASE, `/posts?${params.toString()}`);
  const list = $("ticket-list");
  list.replaceChildren();
  state.totalPages = data.totalPages;
  $("page-label").textContent = `${data.page} / ${data.totalPages}`;
  $("pager").hidden = data.totalPages <= 1;
  $("prev-page").disabled = data.page <= 1;
  $("next-page").disabled = data.page >= data.totalPages;
  $("list-empty").hidden = data.items.length > 0;
  $("list-meta").textContent = `총 ${data.total}건`;
  for (const post of data.items) {
    const li = document.createElement("li");
    li.className = "post-item";
    li.innerHTML = `
      <a class="post-item__link" href="#/tickets/${post.id}">
        <div class="post-item__main">
          <span class="ticket-no">${escapeHtml(post.ticket_no || ticketNo(post.id))}</span>
          <span class="badge badge--product">${escapeHtml(PRODUCT_LABELS[post.product] || post.product)}</span>
          <span class="badge badge--${post.category}">${escapeHtml(CATEGORY_LABELS[post.category] || post.category)}</span>
          <span class="badge badge--status badge--status-${post.status}">${escapeHtml(STATUS_LABELS[post.status] || post.status)}</span>
          <h3 class="post-item__title">${escapeHtml(post.title)}</h3>
        </div>
        <span class="post-item__author">${escapeHtml(post.author_name)}</span>
        <span class="post-item__date">${escapeHtml(formatDateShort(post.created_at))}</span>
      </a>
    `;
    list.appendChild(li);
  }
}

async function loadDetail(id) {
  const data = await api(BOARD_BASE, `/posts/${id}`);
  const post = data.post;
  state.currentId = post.id;
  $("status-select").value = post.status;
  $("ticket-detail").innerHTML = `
    <p class="ticket-no">${escapeHtml(post.ticket_no || ticketNo(post.id))}</p>
    <h1 class="detail__title">${escapeHtml(post.title)}</h1>
    <p class="detail__info">
      제품 ${escapeHtml(PRODUCT_LABELS[post.product] || post.product)}
      · 유형 ${escapeHtml(CATEGORY_LABELS[post.category] || post.category)}
      · 접수자 ${escapeHtml(post.author_name)}
      · ${escapeHtml(formatDate(post.created_at))}
    </p>
    <div class="detail__body">${escapeHtml(post.body || "")}</div>
  `;
  const comments = data.comments || [];
  const list = $("comment-list");
  list.replaceChildren();
  if (!comments.length) {
    const empty = document.createElement("li");
    empty.className = "comment-item";
    empty.innerHTML = `<p class="comment-item__meta">아직 답변이 없습니다.</p>`;
    list.appendChild(empty);
  } else {
    for (const comment of comments) {
      const li = document.createElement("li");
      li.className = "comment-item";
      li.innerHTML = `
        <p class="comment-item__meta">${escapeHtml(comment.author_name)} · ${escapeHtml(formatDate(comment.created_at))}</p>
        <div class="comment-item__body">${escapeHtml(comment.body)}</div>
      `;
      list.appendChild(li);
    }
  }
}

function showViews(view) {
  $("dash-view").hidden = view !== "dash";
  $("tickets-view").hidden = view !== "tickets";
  $("detail-view").hidden = view !== "detail";
  setNav(view);
}

async function route() {
  if (!(await refreshAuth())) {
    return;
  }
  const loc = parseHash();
  if (loc.view === "detail") {
    showViews("detail");
    await loadDetail(loc.id);
    return;
  }
  if (loc.view === "tickets") {
    showViews("tickets");
    if (loc.status) {
      $("filter-status").value = loc.status;
    }
    state.page = 1;
    await loadTickets();
    return;
  }
  showViews("dash");
  await loadDash();
}

function bind() {
  $("staff-login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = $("staff-password").value;
    try {
      await api(AUTH_BASE, "/staff-login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      $("staff-password").value = "";
      window.location.hash = "#/";
      await route();
    } catch (error) {
      showLogin(error.message || "로그인에 실패했습니다.");
    }
  });
  $("logout-btn").addEventListener("click", async () => {
    await api(AUTH_BASE, "/logout", { method: "POST" });
    showLogin("");
  });
  $("filter-status").addEventListener("change", () => {
    state.page = 1;
    loadTickets().catch((error) => window.alert(error.message));
  });
  $("filter-product").addEventListener("change", () => {
    state.page = 1;
    loadTickets().catch((error) => window.alert(error.message));
  });
  $("filter-q").addEventListener("input", () => {
    window.clearTimeout(state.searchTimer);
    state.searchTimer = window.setTimeout(() => {
      state.page = 1;
      loadTickets().catch((error) => window.alert(error.message));
    }, 350);
  });
  $("prev-page").addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    loadTickets().catch((error) => window.alert(error.message));
  });
  $("next-page").addEventListener("click", () => {
    state.page += 1;
    loadTickets().catch((error) => window.alert(error.message));
  });
  $("back-to-list").addEventListener("click", () => {
    window.location.hash = "#/tickets";
  });
  $("status-select").addEventListener("change", async (event) => {
    if (!state.currentId) {
      return;
    }
    try {
      await api(BOARD_BASE, `/posts/${state.currentId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: event.target.value }),
      });
      await loadDetail(state.currentId);
    } catch (error) {
      window.alert(error.message);
    }
  });
  $("reply-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.currentId) {
      return;
    }
    const form = event.currentTarget;
    const body = String(new FormData(form).get("body") || "").trim();
    if (!body) {
      return;
    }
    try {
      await api(BOARD_BASE, `/posts/${state.currentId}/comments`, {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      form.reset();
      await loadDetail(state.currentId);
    } catch (error) {
      window.alert(error.message);
    }
  });
  window.addEventListener("hashchange", () => {
    route().catch((error) => window.alert(error.message));
  });
}

bind();
route().catch((error) => {
  showLogin(error.message || "관리자 화면을 불러오지 못했습니다.");
});
