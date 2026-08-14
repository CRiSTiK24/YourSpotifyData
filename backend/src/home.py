import random
import sqlite3
from html import escape
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.html import card, carousel, page, widget, widget_grid
from src.total_war_rome_ii_greetings import TotalWarRomeIIGreetings

router = APIRouter(tags=["home"])

RECENT_DISCOVERIES_DAYS = 7
RECENTLY_EXPLORED_ALBUMS_DAYS = 7
RECENTLY_EXPLORED_ALBUMS_MIN_TRACKS = 4


def _load_recent_discoveries(con: sqlite3.Connection, days: int) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT pt.track_name AS name, pt.artist_name AS singer, ai.image_url,
               MIN(th.time) AS first_played
        FROM playlist_tracks pt
        JOIN track_history th ON th.name = pt.track_name AND th.singer = pt.artist_name
        LEFT JOIN album_images ai ON ai.artist_name = pt.artist_name AND ai.album_name = th.album
        GROUP BY pt.track_name, pt.artist_name
        HAVING MIN(th.time) >= datetime('now', ?)
        ORDER BY first_played DESC
        """,
        (f"-{days} days",),
    ).fetchall()


def _load_recently_explored_albums(
    con: sqlite3.Connection, days: int, min_tracks: int
) -> list[sqlite3.Row]:
    # "Explored" = at least half of the album's tracks (distinct track
    # names ever played from it - there's no canonical tracklist/total-track
    # count anywhere in this schema, so a track's own play history is the
    # only available stand-in for "how big is this album") had their first
    # ever play within the window. recent_tracks*2 >= total_tracks instead
    # of a fixed count so it scales with album length rather than e.g.
    # always demanding 3 fresh tracks regardless of whether the album has
    # 4 tracks or 20.
    #
    # min_tracks guards against that same proxy at the low end: an album
    # you've only ever sampled 1-2 tracks from trivially clears a 50%
    # ratio the moment you replay just one of them, which reads as "I
    # explored this album" when really it's "I've barely touched it" -
    # requiring a handful of distinct tracks played (ever) before an album
    # is eligible at all keeps the ratio meaningful.
    #
    # group_key: Spotify sometimes reports a different album_name string
    # for the same release depending on which API path supplied it (see
    # albums/service.py's resolve_album_name_variants, which handles the
    # single-album-page version of this same problem) - without unifying
    # by the album_images-resolved spotify_album_id here too, a real
    # explored album could get its plays split across two name spellings
    # and never individually clear the ratio. Falls back to the literal
    # (singer, album) pair when no id was resolved (album_images covers
    # ~99.99% of this library, but not unconditionally all of it).
    window = f"-{days} days"
    return con.execute(
        """
        WITH track_first_play AS (
            SELECT th.album, th.singer, th.name, MIN(th.time) AS first_played,
                   COALESCE(ai.spotify_album_id, th.singer || '|' || th.album) AS group_key
            FROM track_history th
            LEFT JOIN album_images ai ON ai.artist_name = th.singer AND ai.album_name = th.album
            WHERE th.album IS NOT NULL AND th.album != ''
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
        (window, window, min_tracks),
    ).fetchall()


@router.get(
    "/", response_class=HTMLResponse, status_code=200, description="Home page"
)
def home(con: DBDep):
    greeting = random.choice(TotalWarRomeIIGreetings)
    widgets_html = widget("", f"<blockquote><em>{escape(greeting)}</em></blockquote>")

    discoveries = _load_recent_discoveries(con, RECENT_DISCOVERIES_DAYS)
    if discoveries:
        cards_html = "".join(
            card(
                t["name"],
                f"/track/{quote(t['name'])}?artist={quote(t['singer'])}",
                t["singer"],
                f"/artist/{quote(t['singer'])}",
                image_url=t["image_url"],
                preview_artist=t["singer"],
            )
            for t in discoveries
        )
        info_tooltip = (
            f"Tracks saved to one of my playlists that I listened to for "
            f"the first time in the last {RECENT_DISCOVERIES_DAYS} days."
        )
        widgets_html += widget(
            "New supercool tracks",
            carousel(cards_html, compact=True),
            info_tooltip=info_tooltip,
        )

    explored_albums = _load_recently_explored_albums(
        con, RECENTLY_EXPLORED_ALBUMS_DAYS, RECENTLY_EXPLORED_ALBUMS_MIN_TRACKS
    )
    if explored_albums:
        cards_html = "".join(
            card(
                a["album"],
                f"/album/{quote(a['album'])}?artist={quote(a['singer'])}",
                a["singer"],
                f"/artist/{quote(a['singer'])}",
                image_url=a["image_url"],
            )
            for a in explored_albums
        )
        info_tooltip = (
            f"Albums with at least {RECENTLY_EXPLORED_ALBUMS_MIN_TRACKS} tracks "
            f"in my play history, where at least half of those tracks "
            f"got their first-ever play in the last {RECENTLY_EXPLORED_ALBUMS_DAYS} "
            f"days."
        )
        widgets_html += widget(
            "Recently explored albums",
            carousel(cards_html, compact=True),
            info_tooltip=info_tooltip,
        )

    return page(widget_grid(widgets_html))
