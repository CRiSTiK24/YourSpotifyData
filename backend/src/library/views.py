import sqlite3
from urllib.parse import quote

from src.artists import service as artists_service
from src.html import (
    card,
    copy_list_button,
    grid,
    lazy_load_trigger,
    page_header,
    paginated_fragment,
    row,
)
from src.utils import format_date_param_iso, most_listened_next_href

from . import play_counts, service

MOST_LISTENED_BATCH = 30


def date_filter_html(
    min_period: int, max_period: int, start_period: int, end_period: int, base_href: str
) -> str:
    start_value = format_date_param_iso(start_period)
    end_value = format_date_param_iso(end_period, end=True)
    min_value = format_date_param_iso(min_period)
    max_value = format_date_param_iso(max_period, end=True)
    return f"""
<div class="date-filter">
  <label class="date-filter-field">
    <span>From</span>
    <input type="date" id="date-filter-start" min="{min_value}" max="{max_value}" value="{start_value}">
  </label>
  <label class="date-filter-field">
    <span>To</span>
    <input type="date" id="date-filter-end" min="{min_value}" max="{max_value}" value="{end_value}">
  </label>
</div>
<script>
(function () {{
  var baseHref = "{base_href}";
  var startInput = document.getElementById("date-filter-start");
  var endInput = document.getElementById("date-filter-end");

  function navigate() {{
    var params = [];
    if (startInput.value) {{ params.push("start_month=" + encodeURIComponent(startInput.value)); }}
    if (endInput.value) {{ params.push("end_month=" + encodeURIComponent(endInput.value)); }}
    window.location.href = baseHref + (params.length ? "?" + params.join("&") : "");
  }}

  startInput.addEventListener("change", navigate);
  endInput.addEventListener("change", navigate);
}})();
</script>"""


def most_listened_rows_html(
    con: sqlite3.Connection, offset: int, max_plays: int, start_period: int = 0, end_period: int = 0
) -> str:
    tracks = play_counts.load_most_listened(
        con, MOST_LISTENED_BATCH + 1, offset, start_period, end_period
    )
    has_more = len(tracks) > MOST_LISTENED_BATCH
    tracks = tracks[:MOST_LISTENED_BATCH]
    rows_html = "".join(
        row(
            t["name"],
            f"/track/{quote(t['name'])}?artist={quote(t['singer'] or '')}",
            note=str(t["play_count"]),
            image_url=t["image_url"],
            preview_artist=t["singer"],
        )
        for t in tracks
    )
    next_href = most_listened_next_href(
        "/most-listened/more", offset + MOST_LISTENED_BATCH, max_plays, start_period, end_period
    )
    return paginated_fragment(
        rows_html,
        offset=offset,
        has_more=has_more,
        next_href=next_href,
        empty_message="<p class='info'>No plays yet.</p>",
    )


def most_listened_albums_rows_html(
    con: sqlite3.Connection, offset: int, max_plays: int, start_period: int = 0, end_period: int = 0
) -> str:
    albums = play_counts.load_most_listened_albums(
        con, MOST_LISTENED_BATCH + 1, offset, start_period, end_period
    )
    has_more = len(albums) > MOST_LISTENED_BATCH
    albums = albums[:MOST_LISTENED_BATCH]
    rows_html = "".join(
        row(
            a["album"],
            f"/album/{quote(a['album'])}?artist={quote(a['singer'])}",
            note=str(a["play_count"]),
            image_url=a["image_url"],
        )
        for a in albums
    )
    next_href = most_listened_next_href(
        "/most-listened-albums/more",
        offset + MOST_LISTENED_BATCH,
        max_plays,
        start_period,
        end_period,
    )
    return paginated_fragment(
        rows_html,
        offset=offset,
        has_more=has_more,
        next_href=next_href,
        empty_message="<p class='info'>No plays yet.</p>",
    )


def most_listened_combined_content(
    con: sqlite3.Connection, start_period: int = 0, end_period: int = 0
) -> str:
    songs_total, songs_max = play_counts.most_listened_stats(con, start_period, end_period)
    albums_total, albums_max = play_counts.most_listened_albums_stats(con, start_period, end_period)
    artists_total, artists_max = artists_service.most_listened_artists_stats(
        con, start_period, end_period
    )
    min_period, max_period = play_counts.most_listened_period_range(con)

    songs_rows = most_listened_rows_html(con, 0, songs_max, start_period, end_period)
    albums_rows = lazy_load_trigger(
        most_listened_next_href(
            "/most-listened-albums/more", 0, albums_max, start_period, end_period
        ),
        "Loading albums…",
    )
    artists_rows = lazy_load_trigger(
        most_listened_next_href(
            "/most-listened-artists/more", 0, artists_max, start_period, end_period
        ),
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
    <div class="ml-column-header"><span>Track</span><span>Plays</span></div>
    <div id="most-listened-rows">{songs_rows}</div>
  </div>
  <div class="ml-column" data-ml-panel="albums" hidden>
    <h2 class="ml-column-title">Albums ({albums_total})</h2>
    <div class="ml-column-header"><span>Album</span><span>Plays</span></div>
    <div id="most-listened-albums-rows">{albums_rows}</div>
  </div>
  <div class="ml-column" data-ml-panel="artists" hidden>
    <h2 class="ml-column-title">Artists ({artists_total})</h2>
    <div class="ml-column-header"><span>Artist</span><span>Plays</span></div>
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
