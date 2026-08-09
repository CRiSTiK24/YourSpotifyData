(function () {
  var btn = document.getElementById("hamburger-btn");
  var drawer = document.getElementById("mobile-drawer");
  var overlay = document.getElementById("drawer-overlay");
  if (!btn || !drawer || !overlay) return;

  // Opening the drawer pushes a throwaway history entry so the device's
  // back gesture/button closes the drawer first instead of leaving the
  // page - the same trick used for closing mobile nav menus/modals
  // elsewhere. Only pop it ourselves (closeDrawer(true)) when the drawer
  // is dismissed some other way (overlay tap, Escape, re-toggling); a
  // popstate-triggered close (the user actually went back) must not also
  // call history.back(), or it'll eat a second history entry.
  var DRAWER_STATE = "mobileDrawerOpen";

  function closeDrawer(fromPopstate) {
    if (!drawer.classList.contains("open")) return;
    drawer.classList.remove("open");
    overlay.classList.remove("open");
    btn.setAttribute("aria-expanded", "false");
    if (!fromPopstate && history.state && history.state[DRAWER_STATE]) {
      history.back();
    }
  }

  function openDrawer() {
    drawer.classList.add("open");
    overlay.classList.add("open");
    btn.setAttribute("aria-expanded", "true");
    history.pushState(Object.assign({}, history.state, { [DRAWER_STATE]: true }), "");
  }

  btn.addEventListener("click", function () {
    if (drawer.classList.contains("open")) closeDrawer();
    else openDrawer();
  });

  overlay.addEventListener("click", function () {
    closeDrawer();
  });
  drawer.addEventListener("click", function (e) {
    // A nav link inside the drawer already triggers its own navigation
    // (which will supersede our pushed dummy state), so just close
    // visually here rather than also popping history out from under it.
    if (e.target.tagName === "A") closeDrawer(true);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDrawer();
  });
  window.addEventListener("popstate", function () {
    if (drawer.classList.contains("open")) closeDrawer(true);
  });

  // htmx swaps #content only, but a boosted nav click still counts as
  // navigation from the user's perspective, so the drawer should close.
  document.body.addEventListener("htmx:afterSwap", function () {
    closeDrawer(true);
  });
})();
