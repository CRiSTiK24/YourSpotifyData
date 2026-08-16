import sqlite3
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.genres import load_top_genres_for_period
from src.html import card, carousel, page, u, widget, widget_grid, word_cloud
from src.users import service as users_service

router = APIRouter(tags=["home"])

RECENT_DISCOVERIES_DAYS = 7
RECENTLY_EXPLORED_ALBUMS_DAYS = 7
RECENTLY_EXPLORED_ALBUMS_MIN_TRACKS = 4


def _current_month_period() -> int:
    now = datetime.now(UTC)
    return now.year * 100 + now.month


def _load_recent_discoveries(
    con: sqlite3.Connection, user_id: int | None, days: int
) -> list[sqlite3.Row]:
    user_clause, user_params = ("pt.user_id = ?", [user_id]) if user_id is not None else ("1=1", [])
    return con.execute(
        f"""
        SELECT pt.track_name AS name, pt.artist_name AS singer, ai.image_url,
               MIN(th.time) AS first_played
        FROM playlist_tracks pt
        JOIN track_history th ON th.name = pt.track_name AND th.singer = pt.artist_name
            AND th.user_id = pt.user_id
        LEFT JOIN album_images ai ON ai.artist_name = pt.artist_name AND ai.album_name = th.album
        WHERE {user_clause}
        GROUP BY pt.track_name, pt.artist_name
        HAVING MIN(th.time) >= datetime('now', ?)
        ORDER BY first_played DESC
        """,
        (*user_params, f"-{days} days"),
    ).fetchall()


def _load_recently_explored_albums(
    con: sqlite3.Connection, user_id: int | None, days: int, min_tracks: int
) -> list[sqlite3.Row]:
    window = f"-{days} days"
    user_clause, user_params = ("th.user_id = ?", [user_id]) if user_id is not None else ("1=1", [])
    return con.execute(
        f"""
        WITH track_first_play AS (
            SELECT th.album, th.singer, th.name, MIN(th.time) AS first_played,
                   COALESCE(ai.spotify_album_id, th.singer || '|' || th.album) AS group_key
            FROM track_history th
            LEFT JOIN album_images ai ON ai.artist_name = th.singer AND ai.album_name = th.album
            WHERE {user_clause} AND th.album IS NOT NULL AND th.album != ''
              AND th.singer IS NOT NULL AND th.singer != ''
            GROUP BY th.album, th.singer, th.name
        ),
        album_stats AS (
            SELECT group_key,
                   MIN(album) AS album,
                   MIN(singer) AS singer,
                   COUNT(*) AS total_tracks,
                   SUM(CASE WHEN first_played >= datetime('now', ?) THEN 1 ELSE 0 END)
                       AS recent_tracks,
                   MAX(CASE WHEN first_played >= datetime('now', ?) THEN first_played END)
                       AS most_recent_first_play
            FROM track_first_play
            GROUP BY group_key
        )
        SELECT album_stats.album, album_stats.singer, album_stats.total_tracks,
               album_stats.recent_tracks, album_stats.most_recent_first_play, ai.image_url
        FROM album_stats
        LEFT JOIN album_images ai ON ai.artist_name = album_stats.singer
                                  AND ai.album_name = album_stats.album
        WHERE album_stats.recent_tracks > 0
          AND album_stats.total_tracks >= ?
          AND album_stats.recent_tracks * 2 >= album_stats.total_tracks
        ORDER BY album_stats.most_recent_first_play DESC
        """,
        (*user_params, window, window, min_tracks),
    ).fetchall()


def _most_listened_genre_href(genre: str) -> str:
    month = datetime.now(UTC).strftime("%Y-%m")
    return u(f"/most-listened?start_month={month}&end_month={month}&genre={quote(genre)}")


@router.get("/now", response_class=HTMLResponse, status_code=200, description="Now page")
def home(con: DBDep, viewed_user: users_service.ViewedUserDep):
    user_id = viewed_user["id"] if viewed_user else None
    possessive, subject_pronoun = ("our", "we") if user_id is None else ("my", "I")
    widgets_html = ""

    discoveries = _load_recent_discoveries(con, user_id, RECENT_DISCOVERIES_DAYS)
    if discoveries:
        cards_html = "".join(
            card(
                t["name"],
                u(f"/track/{quote(t['name'])}?artist={quote(t['singer'])}"),
                t["singer"],
                u(f"/artist/{quote(t['singer'])}"),
                image_url=t["image_url"],
                preview_artist=t["singer"],
            )
            for t in discoveries
        )
        info_tooltip = (
            f"Tracks saved to one of {possessive} playlists that {subject_pronoun} listened to for "
            f"the first time in the last {RECENT_DISCOVERIES_DAYS} days."
        )
        widgets_html += widget(
            "New supercool tracks",
            carousel(cards_html, compact=True),
            info_tooltip=info_tooltip,
            id="discoveries-widget",
        )

    explored_albums = _load_recently_explored_albums(
        con, user_id, RECENTLY_EXPLORED_ALBUMS_DAYS, RECENTLY_EXPLORED_ALBUMS_MIN_TRACKS
    )
    if explored_albums:
        cards_html = "".join(
            card(
                a["album"],
                u(f"/album/{quote(a['album'])}?artist={quote(a['singer'])}"),
                a["singer"],
                u(f"/artist/{quote(a['singer'])}"),
                image_url=a["image_url"],
            )
            for a in explored_albums
        )
        info_tooltip = (
            f"Albums with at least {RECENTLY_EXPLORED_ALBUMS_MIN_TRACKS} tracks "
            f"in {possessive} play history, where at least half of those tracks "
            f"got their first-ever play in the last {RECENTLY_EXPLORED_ALBUMS_DAYS} "
            f"days."
        )
        widgets_html += widget(
            "Recently explored albums",
            carousel(cards_html, compact=True),
            info_tooltip=info_tooltip,
            id="explored-albums-widget",
        )

    current_period = _current_month_period()
    top_genres = load_top_genres_for_period(con, user_id, current_period, current_period)
    if top_genres:
        info_tooltip = (
            f"Genres of artists {subject_pronoun}'ve played so far this month, "
            "sized by how many plays they're behind."
        )
        widgets_html += widget(
            "Most played genres this month",
            word_cloud(
                [(g["genre"], g["n"]) for g in top_genres],
                href_for=_most_listened_genre_href,
                extra_class="carousel",
            ),
            info_tooltip=info_tooltip,
            id="genre-widget",
        )

    return page(widget_grid(widgets_html))
