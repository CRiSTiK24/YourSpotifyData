(function () {
  var btn = document.getElementById("hamburger-btn");
  var drawer = document.getElementById("mobile-drawer");
  var overlay = document.getElementById("drawer-overlay");
  if (!btn || !drawer || !overlay) return;

  var DRAWER_STATE_KEY = "mobileDrawerOpen";

  function closeDrawer(fromPopstate) {
    if (!drawer.classList.contains("open")) return;
    drawer.classList.remove("open");
    overlay.classList.remove("open");
    btn.setAttribute("aria-expanded", "false");
    if (!fromPopstate && history.state && history.state[DRAWER_STATE_KEY]) {
      history.back();
    }
  }

  function openDrawer() {
    drawer.classList.add("open");
    overlay.classList.add("open");
    btn.setAttribute("aria-expanded", "true");
    history.pushState(Object.assign({}, history.state, { [DRAWER_STATE_KEY]: true }), "");
  }

  btn.addEventListener("click", function () {
    if (drawer.classList.contains("open")) closeDrawer();
    else openDrawer();
  });

  overlay.addEventListener("click", function () {
    closeDrawer();
  });
  drawer.addEventListener("click", function (e) {
    if (e.target.tagName === "A") closeDrawer(true);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDrawer();
  });
  window.addEventListener("popstate", function () {
    if (drawer.classList.contains("open")) closeDrawer(true);
  });

  document.body.addEventListener("htmx:afterSwap", function () {
    closeDrawer(true);
  });
})();
