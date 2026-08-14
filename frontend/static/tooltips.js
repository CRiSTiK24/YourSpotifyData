(function () {
  // Touch fallback for the hover-only description tooltip used by card()
  // and standalone .info-btn elements - see the card-info-btn/.info-btn
  // CSS/docstring in html.py for why. Delegated on document so it keeps
  // working after htmx swaps #content, no re-init needed.

  // The tooltip bubble is centered on its host element (see [data-tooltip]::after
  // in style.css), which overflows the viewport for elements near a screen
  // edge - this nudges it back in via a --tooltip-shift custom property the
  // CSS transform reads, so the bubble stays fully visible while the arrow
  // keeps pointing at the host itself.
  var TOOLTIP_MAX_WIDTH = 220;
  var TOOLTIP_MARGIN = 8;

  function positionTooltip(host) {
    // .grid clips overflow-x (see style.css - it stops every card's
    // inactive tooltip pseudo-element from inflating the page's
    // scrollable width), so that's the real boundary the bubble has to
    // stay inside, not just the viewport - the viewport is only ever the
    // *looser* of the two. Falls back to the viewport alone if this host
    // isn't inside a clipping .grid.
    var container = host.closest(".grid");
    var containerRect = container ? container.getBoundingClientRect() : null;
    var minX = TOOLTIP_MARGIN;
    var maxX = window.innerWidth - TOOLTIP_MARGIN;
    if (containerRect) {
      minX = Math.max(minX, containerRect.left + TOOLTIP_MARGIN);
      maxX = Math.min(maxX, containerRect.right - TOOLTIP_MARGIN);
    }
    var rect = host.getBoundingClientRect();
    var centerX = rect.left + rect.width / 2;
    var halfWidth = TOOLTIP_MAX_WIDTH / 2;
    var leftEdge = centerX - halfWidth;
    var rightEdge = centerX + halfWidth;
    var shift = 0;
    if (leftEdge < minX) {
      shift = minX - leftEdge;
    } else if (rightEdge > maxX) {
      shift = maxX - rightEdge;
    }
    host.style.setProperty("--tooltip-shift", shift + "px");
  }

  // mouseover (bubbles, unlike mouseenter) + a relatedTarget check so this
  // only fires once when the pointer actually enters a new host, not on
  // every internal mouse move - matches when CSS :hover would activate.
  document.addEventListener("mouseover", function (e) {
    var host = e.target.closest("[data-tooltip]");
    if (!host || host.contains(e.relatedTarget)) return;
    positionTooltip(host);
  });

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".card-info-btn, .info-btn");
    if (btn) {
      var host = btn.closest("[data-tooltip]") || btn;
      var wasActive = host.classList.contains("tooltip-active");
      document.querySelectorAll(".tooltip-active").forEach(function (c) {
        c.classList.remove("tooltip-active");
      });
      if (!wasActive) {
        positionTooltip(host);
        host.classList.add("tooltip-active");
      }
      return;
    }
    if (!e.target.closest("[data-tooltip]")) {
      document.querySelectorAll(".tooltip-active").forEach(function (c) {
        c.classList.remove("tooltip-active");
      });
    }
  });
})();
