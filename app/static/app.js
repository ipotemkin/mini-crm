(function () {
  function getCookie(name) {
    const m = document.cookie.match(
      new RegExp("(?:^|; )" + name + "=([^;]*)")
    );
    return m ? decodeURIComponent(m[1]) : "";
  }

  document.body.addEventListener("htmx:configRequest", function (e) {
    const token = getCookie("csrf_token");
    if (token) {
      e.detail.headers["X-CSRF-Token"] = token;
    }
  });

  document.addEventListener("keydown", function (e) {
    if (
      e.key === "/" &&
      document.activeElement &&
      document.activeElement.tagName !== "INPUT" &&
      document.activeElement.tagName !== "TEXTAREA"
    ) {
      const box = document.getElementById("global-search");
      if (box) {
        e.preventDefault();
        box.focus();
      }
    }
  });

  setInterval(function () {
    const el = document.getElementById("reminders-badge");
    if (!el) return;
    fetch("/api/v1/reminders/summary", { credentials: "same-origin" })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (!data) return;
        el.textContent = data.overdue + " / " + data.today;
        el.classList.toggle("has-overdue", data.overdue > 0);
      })
      .catch(function () {});
  }, 60000);
})();
