(function () {
  // Persistent chrome search (mobile-topbar, at every width - see
  // _quick_search_widget() in html.py). Delegated on document so it keeps
  // working after htmx swaps #content, no re-init needed.
  function clearResults() {
    document.querySelectorAll(".quick-search-results").forEach(function (el) {
      el.innerHTML = "";
    });
  }

  // position:absolute can't escape an ancestor's clipping (e.g. a
  // scrollable container converting its overflow-x to auto), so this
  // positions the dropdown with position:fixed instead (anchored to the
  // input's real screen coordinates), which does.
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

  // All three tabs' results are already in the DOM (see
  // _quick_results_html in search/router.py) - switching tabs is just a
  // local show/hide, no request (desktop shows all three .qs-column at
  // once via CSS instead, so this handler is a no-op there beyond the
  // active-state styling). e.target.closest(".quick-search") already
  // covers tab clicks for the outside-click-closes handler below, so this
  // only needs to stop the click from also being treated as "navigate
  // away".
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
    // A result is a plain <a> row, boosted by htmx like any other link -
    // once it navigates, clear both the stale results dropdown and the
    // typed query so the next search starts fresh. htmx:afterSwap also
    // fires for the quick-search's own dropdown-filling swap above (any
    // htmx swap anywhere on the page, not just page navigation) - checking
    // the target is #content is what tells the two apart.
    if (!target || target.id !== "content") return;
    clearResults();
    document.querySelectorAll(".quick-search-input").forEach(function (el) {
      el.value = "";
    });
  });
})();
