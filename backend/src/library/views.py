import sqlite3
from urllib.parse import quote

from src.html import card, copy_list_button, grid, infinite_scroll_trigger, page_header, row

from . import service

MOST_LISTENED_BATCH = 30


def year_filter_html(
    min_year: int, max_year: int, start_year: int, end_year: int, base_href: str
) -> str:
    """A two-handle drag bar (two overlaid range inputs, the classic
    vanilla-JS/CSS dual-slider trick) scoping a most-listened ranking to a
    year range. 0 on either end means unbounded on that side, so the bar
    reflects that immediately (thumb pinned to the min/max edge) rather
    than needing a separate 'all time' state. base_href is the page this
    filter lives on (songs vs albums), so both can reuse this one bar."""
    start_value = start_year or min_year
    end_value = end_year or max_year
    span = max_year - min_year or 1
    start_pct = (start_value - min_year) / span * 100
    end_pct = (end_value - min_year) / span * 100
    label = (
        "All time"
        if not start_year and not end_year
        else f"{start_value}–{end_value}"
    )
    return f"""
<div class="year-filter">
  <span class="year-filter-label" id="year-filter-label">{label}</span>
  <div class="year-range" data-min="{min_year}" data-max="{max_year}">
    <div class="year-range-track"></div>
    <div class="year-range-fill" id="year-range-fill"
         style="left:{start_pct:.2f}%;right:{100 - end_pct:.2f}%"></div>
    <input type="range" class="year-thumb year-thumb-start" id="year-thumb-start"
           min="{min_year}" max="{max_year}" step="1" value="{start_value}">
    <input type="range" class="year-thumb year-thumb-end" id="year-thumb-end"
           min="{min_year}" max="{max_year}" step="1" value="{end_value}">
  </div>
  <a class="btn" href="{base_href}">All time</a>
</div>
<script>
(function () {{
  var minYear = {min_year}, maxYear = {max_year};
  var baseHref = "{base_href}";
  var startInput = document.getElementById("year-thumb-start");
  var endInput = document.getElementById("year-thumb-end");
  var fill = document.getElementById("year-range-fill");
  var label = document.getElementById("year-filter-label");
  var span = (maxYear - minYear) || 1;

  function render() {{
    var s = parseInt(startInput.value, 10), e = parseInt(endInput.value, 10);
    fill.style.left = ((s - minYear) / span * 100) + "%";
    fill.style.right = (100 - (e - minYear) / span * 100) + "%";
    label.textContent = (s === minYear && e === maxYear) ? "All time" : s + "–" + e;
  }}

  function onDrag(moved) {{
    var s = parseInt(startInput.value, 10), e = parseInt(endInput.value, 10);
    if (s > e) {{
      if (moved === startInput) {{ endInput.value = s; }} else {{ startInput.value = e; }}
    }}
    render();
  }}

  function navigate() {{
    window.location.href = baseHref + "?start_year=" + startInput.value
      + "&end_year=" + endInput.value;
  }}

  startInput.addEventListener("input", function () {{ onDrag(startInput); }});
  endInput.addEventListener("input", function () {{ onDrag(endInput); }});
  startInput.addEventListener("change", navigate);
  endInput.addEventListener("change", navigate);
}})();
</script>"""


def most_listened_rows_html(
    con: sqlite3.Connection, offset: int, max_plays: int, start_year: int = 0, end_year: int = 0
) -> str:
    """Fetches one batch + a lookahead row (cheaper than a separate COUNT)
    to know whether to append another infinite-scroll trigger."""
    tracks = service.load_most_listened(con, MOST_LISTENED_BATCH + 1, offset, start_year, end_year)
    has_more = len(tracks) > MOST_LISTENED_BATCH
    tracks = tracks[:MOST_LISTENED_BATCH]
    rows_html = "".join(
        row(
            t["name"],
            f"/track/{quote(t['name'])}?artist={quote(t['singer'] or '')}",
            t["singer"],
            f"/artist/{quote(t['singer'])}" if t["singer"] else None,
            note=f"×{t['play_count']}",
            image_url=t["image_url"],
            bar_fraction=(t["play_count"] / max_plays) if max_plays else 0,
        )
        for t in tracks
    )
    if not rows_html:
        return "<p class='info'>No plays yet.</p>" if offset == 0 else ""
    if has_more:
        next_href = (
            f"/most-listened/more?offset={offset + MOST_LISTENED_BATCH}"
            f"&max_plays={max_plays}&start_year={start_year}&end_year={end_year}"
        )
        rows_html += infinite_scroll_trigger(next_href)
    return rows_html


def most_listened_content(con: sqlite3.Connection, start_year: int = 0, end_year: int = 0) -> str:
    total, max_plays = service.most_listened_stats(con, start_year, end_year)
    min_year, max_year = service.most_listened_year_range(con)
    header = page_header(
        f"My Most Listened Songs ({total})",
        year_filter_html(min_year, max_year, start_year, end_year, "/most-listened"),
    )
    return f"""
{header}
<hr class="divider">
<div id="most-listened-rows">{most_listened_rows_html(con, 0, max_plays, start_year, end_year)}</div>
"""


def most_listened_albums_rows_html(
    con: sqlite3.Connection, offset: int, max_plays: int, start_year: int = 0, end_year: int = 0
) -> str:
    albums = service.load_most_listened_albums(
        con, MOST_LISTENED_BATCH + 1, offset, start_year, end_year
    )
    has_more = len(albums) > MOST_LISTENED_BATCH
    albums = albums[:MOST_LISTENED_BATCH]
    rows_html = "".join(
        row(
            a["album"],
            f"/album/{quote(a['album'])}?artist={quote(a['singer'])}",
            a["singer"],
            f"/artist/{quote(a['singer'])}",
            note=f"×{a['play_count']}",
            image_url=a["image_url"],
            bar_fraction=(a["play_count"] / max_plays) if max_plays else 0,
        )
        for a in albums
    )
    if not rows_html:
        return "<p class='info'>No plays yet.</p>" if offset == 0 else ""
    if has_more:
        next_href = (
            f"/most-listened-albums/more?offset={offset + MOST_LISTENED_BATCH}"
            f"&max_plays={max_plays}&start_year={start_year}&end_year={end_year}"
        )
        rows_html += infinite_scroll_trigger(next_href)
    return rows_html


def most_listened_albums_content(
    con: sqlite3.Connection, start_year: int = 0, end_year: int = 0
) -> str:
    total, max_plays = service.most_listened_albums_stats(con, start_year, end_year)
    min_year, max_year = service.most_listened_year_range(con)
    header = page_header(
        f"My Most Listened Albums ({total})",
        year_filter_html(min_year, max_year, start_year, end_year, "/most-listened-albums"),
    )
    rows = most_listened_albums_rows_html(con, 0, max_plays, start_year, end_year)
    return f"""
{header}
<hr class="divider">
<div id="most-listened-albums-rows">{rows}</div>
"""


def liked_albums_content(con: sqlite3.Connection) -> str:
    albums = service.load_library_albums(con)
    cards_html = "".join(
        card(
            a["album_name"],
            f"/album/{quote(a['album_name'])}?artist={quote(a['artist_name'])}",
            a["artist_name"],
            f"/artist/{quote(a['artist_name'])}",
            image_url=a["image_url"],
        )
        for a in albums
    )
    export_lines = [f"{a['album_name']} - {a['artist_name']}" for a in albums]
    header = page_header(
        f"Liked Albums ({len(albums)})",
        copy_list_button(export_lines, "liked-albums-list"),
    )
    return f"""
{header}
<hr class="divider">
{grid(cards_html)}
"""
