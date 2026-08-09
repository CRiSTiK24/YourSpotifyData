(function () {
  // /most-listened's Songs/Albums/Artists tabs (mobile) - same
  // show/hide-a-pre-rendered-panel pattern as the quick-search dropdown's
  // tabs (see quick-search.js), just for page content instead of chrome.
  // Delegated on document so it survives htmx swapping #content on
  // navigation, no re-init needed. On desktop all three .ml-column panels
  // are shown at once via CSS (see the min-width:700px block in
  // style.css), so this handler still runs there but is a harmless no-op
  // beyond the active-tab styling, since the tabs themselves are hidden.
  document.addEventListener("click", function (e) {
    var tab = e.target.closest(".ml-tab");
    if (!tab) return;
    var tabsWrap = tab.closest(".ml-tabs");
    var columnsWrap = tabsWrap && tabsWrap.nextElementSibling;
    if (!tabsWrap || !columnsWrap || !columnsWrap.classList.contains("ml-columns")) return;
    tabsWrap.querySelectorAll(".ml-tab").forEach(function (t) {
      t.classList.toggle("active", t === tab);
    });
    columnsWrap.querySelectorAll(".ml-column").forEach(function (c) {
      c.hidden = c.dataset.mlPanel !== tab.dataset.mlTab;
    });
  });
})();
