(function () {
  function clearResults() {
    document.querySelectorAll(".quick-search-results").forEach(function (el) {
      el.innerHTML = "";
    });
  }

  function positionResults(resultsEl) {
    var input = resultsEl.previousElementSibling;
    if (!input) return;
    var r = input.getBoundingClientRect();
    var width = Math.max(r.width, 360);
    var left = Math.min(r.left, window.innerWidth - width - 8);
    resultsEl.style.position = "fixed";
    resultsEl.style.top = r.bottom + 4 + "px";
    resultsEl.style.left = Math.max(left, 8) + "px";
    resultsEl.style.right = "auto";
    resultsEl.style.width = width + "px";
  }

  document.addEventListener("click", function (e) {
    var tab = e.target.closest(".qs-tab");
    if (!tab) return;
    var tabsWrap = tab.closest(".qs-tabs");
    var resultsWrap = tab.closest(".quick-search-results");
    if (!tabsWrap || !resultsWrap) return;
    tabsWrap.querySelectorAll(".qs-tab").forEach(function (t) {
      t.classList.toggle("active", t === tab);
    });
    resultsWrap.querySelectorAll(".qs-column").forEach(function (p) {
      p.hidden = p.dataset.qsPanel !== tab.dataset.qsTab;
    });
  });

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".quick-search")) clearResults();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") clearResults();
  });

  document.body.addEventListener("htmx:afterSwap", function (e) {
    var target = e.detail.target;
    if (target && target.classList && target.classList.contains("quick-search-results")) {
      if (target.innerHTML.trim()) positionResults(target);
      return;
    }
    if (!target || target.id !== "content") return;
    clearResults();
    document.querySelectorAll(".quick-search-input").forEach(function (el) {
      el.value = "";
    });
  });
})();
