(function () {
  // Switching profiles should land you on the same kind of page you were
  // on (e.g. Playlists -> Playlists for the new user), not always reset to
  // /now - see _profile_switcher() in html.py, which renders each option's
  // value as a bare username ("" for the aggregate "All merged" option)
  // rather than a full href, so this can rebuild the target URL itself.
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
      // Switching to the aggregate view: only reuse the current sub-page
      // if it actually has a merged equivalent (see AGGREGATE_ROOT_SEGMENTS
      // in html.py) - a per-user-only page like a specific playlist has
      // nothing to land on there, so this falls back to /now instead.
      var firstRestSegment = rest.split("/").filter(Boolean)[0];
      newPath = aggregateSegments.indexOf(firstRestSegment) !== -1 ? rest : "/now";
    }
    window.location.href = newPath + window.location.search;
  });
})();
