import sqlite3
from urllib.parse import quote

from src.artists import service as artists_service
from src.html import (
    card,
    copy_list_button,
    grid,
    infinite_scroll_trigger,
    lazy_load_trigger,
    page_header,
    row,
)
from src.utils import format_month_param

from . import service

MOST_LISTENED_BATCH = 30


def _placeholder(period: int) -> str:
    """MM/YYYY, purely for the placeholder text - value/min/max on an
    <input type="month"> must stay "YYYY-MM" (the one format the element
    actually accepts; the browser renders its own locale-formatted month
    picker over that regardless of what we put here)."""
    year, month = divmod(period, 100)
    return f"{month:02d}/{year:04d}"


def date_filter_html(
    min_period: int, max_period: int, start_period: int, end_period: int, base_href: str
) -> str:
    """Two native <input type="month"> fields (From/To) scoping a
    most-listened ranking to a month range - replaced an earlier
    dual-thumb slider. Native month inputs give mobile an optimized
    touch/wheel picker and desktop a small calendar dropdown, both
    low-click, without needing any custom widget code to keep the two in
    visual sync (the actual goal was interaction comfort on both, not
    pixel-identical rendering). 0 on either end means unbounded on that
    side; left blank rather than defaulting to min/max, so 'All time' is
    just both inputs empty - no dedicated 'All time' control, clearing
    both fields (or just navigating away) gets you back there. The
    available range is shown as each field's own placeholder (MM/YYYY,
    see _placeholder) rather than as separate text elsewhere on the page.
    base_href is the page this filter lives on."""
    start_value = format_month_param(start_period) if start_period else ""
    end_value = format_month_param(end_period) if end_period else ""
    min_value = format_month_param(min_period)
    max_value = format_month_param(max_period)
    return f"""
<div class="date-filter">
  <label class="date-filter-field">
    <span>From</span>
    <input type="month" id="date-filter-start" min="{min_value}" max="{max_value}" value="{start_value}" placeholder="{_placeholder(min_period)}">
  </label>
  <label class="date-filter-field">
    <span>To</span>
    <input type="month" id="date-filter-end" min="{min_value}" max="{max_value}" value="{end_value}" placeholder="{_placeholder(max_period)}">
  </label>
</div>
<script>
(function () {{
  var baseHref = "{base_href}";
  var startInput = document.getElementById("date-filter-start");
  var endInput = document.getElementById("date-filter-end");

  function navigate() {{
    var params = [];
    if (startInput.value) {{ params.push("start_month=" + startInput.value); }}
    if (endInput.value) {{ params.push("end_month=" + endInput.value); }}
    window.location.href = baseHref + (params.length ? "?" + params.join("&") : "");
  }}

  startInput.addEventListener("change", navigate);
  endInput.addEventListener("change", navigate);
}})();
</script>"""


def most_listened_rows_html(
    con: sqlite3.Connection, offset: int, max_plays: int, start_period: int = 0, end_period: int = 0
) -> str:
    """Fetches one batch + a lookahead row (cheaper than a separate COUNT)
    to know whether to append another infinite-scroll trigger."""
    tracks = service.load_most_listened(con, MOST_LISTENED_BATCH + 1, offset, start_period, end_period)
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
            f"&max_plays={max_plays}&start_month={format_month_param(start_period) if start_period else ''}"
            f"&end_month={format_month_param(end_period) if end_period else ''}"
        )
        rows_html += infinite_scroll_trigger(next_href)
    return rows_html


def most_listened_albums_rows_html(
    con: sqlite3.Connection, offset: int, max_plays: int, start_period: int = 0, end_period: int = 0
) -> str:
    albums = service.load_most_listened_albums(
        con, MOST_LISTENED_BATCH + 1, offset, start_period, end_period
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
            f"&max_plays={max_plays}&start_month={format_month_param(start_period) if start_period else ''}"
            f"&end_month={format_month_param(end_period) if end_period else ''}"
        )
        rows_html += infinite_scroll_trigger(next_href)
    return rows_html


def most_listened_combined_content(
    con: sqlite3.Connection, start_period: int = 0, end_period: int = 0
) -> str:
    """Songs, Albums and Artists used to be three separate pages; merged
    into one so desktop (room to spare) can show all three as side-by-side
    scrollable columns while mobile switches between them with tabs - see
    .ml-tabs/.ml-columns in style.css and most-listened.js for the
    tab-switch behavior these three .ml-column sections rely on. One
    shared month-range filter applies to all three at once rather than
    each having its own.

    Only Songs' rows are fetched eagerly here - ranking Albums/Artists by
    play count is its own ~500-700ms full scan+sort each (no index can
    shortcut sorting by an aggregate COUNT(*)), and computing all three
    serially on every page load / filter change was the exact regression a
    single merged page risked over three separate ones, each previously
    paying for only its own ranking. lazy_load_trigger() defers those two
    so they load moments later via their own parallel requests instead of
    blocking the page's first paint. Stats stay eager (cheap enough, and
    the tab labels/column titles need the counts immediately)."""
    songs_total, songs_max = service.most_listened_stats(con, start_period, end_period)
    albums_total, albums_max = service.most_listened_albums_stats(con, start_period, end_period)
    artists_total, artists_max = artists_service.most_listened_artists_stats(
        con, start_period, end_period
    )
    min_period, max_period = service.most_listened_period_range(con)

    start_month = format_month_param(start_period) if start_period else ""
    end_month = format_month_param(end_period) if end_period else ""

    songs_rows = most_listened_rows_html(con, 0, songs_max, start_period, end_period)
    albums_rows = lazy_load_trigger(
        f"/most-listened-albums/more?offset=0&max_plays={albums_max}"
        f"&start_month={start_month}&end_month={end_month}",
        "Loading albums…",
    )
    artists_rows = lazy_load_trigger(
        f"/most-listened-artists/more?offset=0&max_plays={artists_max}"
        f"&start_month={start_month}&end_month={end_month}",
        "Loading artists…",
    )

    header = page_header(
        "My Most Listened",
        date_filter_html(min_period, max_period, start_period, end_period, "/most-listened"),
    )
    return f"""
{header}
<hr class="divider">
<div class="ml-tabs">
  <button type="button" class="ml-tab active" data-ml-tab="songs">Songs <span class="ml-tab-count">({songs_total})</span></button>
  <button type="button" class="ml-tab" data-ml-tab="albums">Albums <span class="ml-tab-count">({albums_total})</span></button>
  <button type="button" class="ml-tab" data-ml-tab="artists">Artists <span class="ml-tab-count">({artists_total})</span></button>
</div>
<div class="ml-columns">
  <div class="ml-column" data-ml-panel="songs">
    <h2 class="ml-column-title">Songs ({songs_total})</h2>
    <div id="most-listened-rows">{songs_rows}</div>
  </div>
  <div class="ml-column" data-ml-panel="albums" hidden>
    <h2 class="ml-column-title">Albums ({albums_total})</h2>
    <div id="most-listened-albums-rows">{albums_rows}</div>
  </div>
  <div class="ml-column" data-ml-panel="artists" hidden>
    <h2 class="ml-column-title">Artists ({artists_total})</h2>
    <div id="most-listened-artists-rows">{artists_rows}</div>
  </div>
</div>
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
