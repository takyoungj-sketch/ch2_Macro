(function () {
  fetch("/api/ops/event", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product: "hub",
      event_name: "page_view",
      path: window.location.pathname || "/",
    }),
  }).catch(function () {});
})();
