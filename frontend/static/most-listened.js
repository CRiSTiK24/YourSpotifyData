(function () {
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
