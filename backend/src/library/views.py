import json
import sqlite3
from html import escape
from urllib.parse import quote

from src.artists import service as artists_service
from src.genres import load_top_genres_for_period
from src.html import (
    card,
    copy_list_button,
    grid,
    lazy_load_trigger,
    page_header,
    paginated_fragment,
    row,
    u,
    word_cloud,
)
from src.utils import format_month_param, most_listened_next_href

from . import play_counts, service

MOST_LISTENED_BATCH = 30


def _most_listened_href(start_period: int, end_period: int, genre: str) -> str:
    params = []
    if start_period:
        params.append(f"start_month={format_month_param(start_period)}")
    if end_period:
        params.append(f"end_month={format_month_param(end_period)}")
    if genre:
        params.append(f"genre={quote(genre)}")
    return u("/most-listened") + (f"?{'&'.join(params)}" if params else "")


def date_filter_html(
    min_period: int, max_period: int, start_period: int, end_period: int, genre: str
) -> str:
    start_value = format_month_param(start_period) if start_period else ""
    end_value = format_month_param(end_period) if end_period else ""
    min_value = format_month_param(min_period) if min_period else ""
    max_value = format_month_param(max_period) if max_period else ""
    # json.dumps (not html.escape) since this value lands inside a <script>
    # block, not HTML markup - <script> content isn't entity-decoded by the
    # browser, so an HTML-escaped quote would show up as literal text
    # (&quot;) in the JS source instead of closing the string, corrupting
    # the value read back on the next date/genre navigation. The <
    # replacement on top guards against a genre containing "</script>"
    # from breaking out of the block (json.dumps alone doesn't escape it).
    genre_js = json.dumps(genre).replace("<", "\\u003c")
    return f"""
<div class="date-filter">
  <label class="date-filter-field">
    <span>From</span>
    <input type="month" id="date-filter-start" min="{min_value}" max="{max_value}" value="{start_value}" placeholder="YYYY-MM">
  </label>
  <label class="date-filter-field">
    <span>To</span>
    <input type="month" id="date-filter-end" min="{min_value}" max="{max_value}" value="{end_value}" placeholder="YYYY-MM">
  </label>
</div>
<script>
(function () {{
  var baseHref = {json.dumps(u("/most-listened"))};
  var genre = {genre_js};
  var startInput = document.getElementById("date-filter-start");
  var endInput = document.getElementById("date-filter-end");

  function navigate() {{
    var params = [];
    if (startInput.value) {{ params.push("start_month=" + encodeURIComponent(startInput.value)); }}
    if (endInput.value) {{ params.push("end_month=" + encodeURIComponent(endInput.value)); }}
    if (genre) {{ params.push("genre=" + encodeURIComponent(genre)); }}
    window.location.href = baseHref + (params.length ? "?" + params.join("&") : "");
  }}

  startInput.addEventListener("change", navigate);
  endInput.addEventListener("change", navigate);
}})();
</script>"""


def most_listened_rows_html(
    con: sqlite3.Connection,
    user_id: int | None,
    offset: int,
    max_plays: int,
    start_period: int = 0,
    end_period: int = 0,
    genre: str = "",
) -> str:
    tracks = play_counts.load_most_listened(
        con, user_id, MOST_LISTENED_BATCH + 1, offset, start_period, end_period, genre
    )
    has_more = len(tracks) > MOST_LISTENED_BATCH
    tracks = tracks[:MOST_LISTENED_BATCH]
    rows_html = "".join(
        row(
            t["name"],
            u(f"/track/{quote(t['name'])}?artist={quote(t['singer'] or '')}"),
            note=str(t["play_count"]),
            image_url=t["image_url"],
            preview_artist=t["singer"],
        )
        for t in tracks
    )
    next_href = most_listened_next_href(
        u("/most-listened/more"),
        offset + MOST_LISTENED_BATCH,
        max_plays,
        start_period,
        end_period,
        genre,
    )
    return paginated_fragment(
        rows_html,
        offset=offset,
        has_more=has_more,
        next_href=next_href,
        empty_message="<p class='info'>No plays yet.</p>",
    )


def most_listened_albums_rows_html(
    con: sqlite3.Connection,
    user_id: int | None,
    offset: int,
    max_plays: int,
    start_period: int = 0,
    end_period: int = 0,
    genre: str = "",
) -> str:
    albums = play_counts.load_most_listened_albums(
        con, user_id, MOST_LISTENED_BATCH + 1, offset, start_period, end_period, genre
    )
    has_more = len(albums) > MOST_LISTENED_BATCH
    albums = albums[:MOST_LISTENED_BATCH]
    rows_html = "".join(
        row(
            a["album"],
            u(f"/album/{quote(a['album'])}?artist={quote(a['singer'])}"),
            note=str(a["play_count"]),
            image_url=a["image_url"],
        )
        for a in albums
    )
    next_href = most_listened_next_href(
        u("/most-listened-albums/more"),
        offset + MOST_LISTENED_BATCH,
        max_plays,
        start_period,
        end_period,
        genre,
    )
    return paginated_fragment(
        rows_html,
        offset=offset,
        has_more=has_more,
        next_href=next_href,
        empty_message="<p class='info'>No plays yet.</p>",
    )


def most_listened_combined_content(
    con: sqlite3.Connection,
    user_id: int | None,
    start_period: int = 0,
    end_period: int = 0,
    genre: str = "",
    oob: bool = False,
) -> str:
    songs_total, songs_max = play_counts.most_listened_stats(
        con, user_id, start_period, end_period, genre
    )
    albums_total, albums_max = play_counts.most_listened_albums_stats(
        con, user_id, start_period, end_period, genre
    )
    artists_total, artists_max = artists_service.most_listened_artists_stats(
        con, user_id, start_period, end_period, genre
    )
    min_period, max_period = play_counts.most_listened_period_range(con, user_id)

    songs_rows = most_listened_rows_html(
        con, user_id, 0, songs_max, start_period, end_period, genre
    )
    albums_rows = lazy_load_trigger(
        most_listened_next_href(
            u("/most-listened-albums/more"), 0, albums_max, start_period, end_period, genre
        ),
        "Loading albums…",
    )
    artists_rows = lazy_load_trigger(
        most_listened_next_href(
            u("/most-listened-artists/more"), 0, artists_max, start_period, end_period, genre
        ),
        "Loading artists…",
    )

    top_genres = load_top_genres_for_period(con, user_id, start_period, end_period)
    genre_cloud = ""
    if top_genres:
        period_desc = (
            "the selected date range" if start_period or end_period else "my whole history"
        )
        tooltip = (
            f"Genres of artists I've played in {period_desc}, sized by how many plays "
            f"they're behind - click one to filter Songs/Albums/Artists to it."
        )
        cloud_html = word_cloud(
            [(g["genre"], g["n"]) for g in top_genres],
            min_size=11,
            max_size=20,
            href_for=lambda name: _most_listened_href(
                start_period, end_period, "" if name == genre else name
            ),
            active={genre} if genre else None,
            extra_class="carousel",
            hx_swap_target="ml-results",
            container_id="ml-genre-tags",
            oob=oob,
        )
        genre_cloud = f"<div class='ml-genre-cloud tooltip-below' data-tooltip='{escape(tooltip)}'>{cloud_html}</div>"
    actions = (
        f"<div class='page-header-actions'>{genre_cloud}"
        f"{date_filter_html(min_period, max_period, start_period, end_period, genre)}"
        f"</div>"
    )
    header = page_header("My Most Listened", actions)
    return f"""
{header}
<hr class="divider">
<div id="ml-results">
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
</div>
"""


def liked_albums_content(con: sqlite3.Connection, user_id: int | None) -> str:
    albums = service.load_library_albums(con, user_id)
    cards_html = "".join(
        card(
            a["album_name"],
            u(f"/album/{quote(a['album_name'])}?artist={quote(a['artist_name'])}"),
            a["artist_name"],
            u(f"/artist/{quote(a['artist_name'])}"),
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
