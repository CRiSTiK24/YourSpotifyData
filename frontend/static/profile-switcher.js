(function () {
  document.addEventListener("change", function (e) {
    var select = e.target.closest(".profile-switcher");
    if (!select) return;

    var usernames = JSON.parse(select.dataset.usernames || "[]");
    var aggregateSegments = JSON.parse(select.dataset.aggregateSegments || "[]");
    var target = select.value;

    var segments = window.location.pathname.split("/").filter(Boolean);
    var onUsernamePage = segments.length > 0 && usernames.indexOf(segments[0]) !== -1;
    var rest = "/" + (onUsernamePage ? segments.slice(1) : segments).join("/");

    var newPath;
    if (target) {
      newPath = "/" + target + (rest === "/" ? "" : rest);
    } else {
      var firstRestSegment = rest.split("/").filter(Boolean)[0];
      newPath = aggregateSegments.indexOf(firstRestSegment) !== -1 ? rest : "/now";
    }
    window.location.href = newPath + window.location.search;
  });
})();
