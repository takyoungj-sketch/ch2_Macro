/* Apply before paint; storage may be unavailable in private browsing. */
(function () {
  const key = "ch2-learn-theme";
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";
  try { preference = localStorage.getItem(key) || "system"; } catch (_) {}
  if (!["system", "light", "dark"].includes(preference)) preference = "system";
  function apply() {
    const theme = preference === "system" ? (media.matches ? "dark" : "light") : preference;
    document.documentElement.dataset.learnTheme = theme;
    window.dispatchEvent(new CustomEvent("learn-theme-change", { detail: preference }));
  }
  window.learnTheme = {
    get: () => preference,
    set(value) {
      if (!["system", "light", "dark"].includes(value)) return;
      preference = value;
      try { localStorage.setItem(key, value); } catch (_) {}
      apply();
    }
  };
  media.addEventListener("change", apply);
  window.addEventListener("storage", (event) => {
    if (event.key !== key) return;
    preference = ["light", "dark"].includes(event.newValue) ? event.newValue : "system";
    apply();
  });
  apply();
})();
