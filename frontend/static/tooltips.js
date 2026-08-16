(function () {
  var TOOLTIP_MAX_WIDTH = 220;
  var TOOLTIP_MARGIN = 8;

  function positionTooltip(host) {
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
