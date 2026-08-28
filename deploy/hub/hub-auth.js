(function () {
  const AUTH = "/api/auth";

  function $(id) {
    return document.getElementById(id);
  }

  function applyAuth(data) {
    const loggedIn = Boolean(data && data.logged_in);
    const providers = (data && data.providers) || {};
    const loginActions = $("login-actions");
    const userActions = $("user-actions");
    const googleBtn = $("google-login");
    const kakaoBtn = $("kakao-login");
    const nameEl = $("auth-name");

    if (loginActions) {
      loginActions.hidden = loggedIn;
    }
    if (userActions) {
      userActions.hidden = !loggedIn;
    }
    if (nameEl) {
      nameEl.textContent = loggedIn ? data.nickname || "사용자" : "";
    }
    if (googleBtn) {
      googleBtn.hidden = loggedIn || providers.google === false;
    }
    if (kakaoBtn) {
      kakaoBtn.hidden = loggedIn || !providers.kakao;
    }
  }

  async function refresh() {
    try {
      const res = await fetch(`${AUTH}/status`, { credentials: "include" });
      applyAuth(await res.json());
    } catch (_err) {
      applyAuth({ logged_in: false, providers: { google: true, kakao: false } });
    }
  }

  const googleBtn = $("google-login");
  if (googleBtn) {
    googleBtn.addEventListener("click", () => {
      window.location.href = `${AUTH}/google/login?next=${encodeURIComponent("/")}`;
    });
  }
  const kakaoBtn = $("kakao-login");
  if (kakaoBtn) {
    kakaoBtn.addEventListener("click", () => {
      window.location.href = `${AUTH}/kakao/login?next=${encodeURIComponent("/")}`;
    });
  }
  const logoutBtn = $("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      await fetch(`${AUTH}/logout`, { method: "POST", credentials: "include" });
      await refresh();
    });
  }

  refresh();
})();
