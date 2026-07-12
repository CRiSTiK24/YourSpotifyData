import sqlite3

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.html import page, search_form, stat_card

router = APIRouter(tags=["home"])


def home_page(con: sqlite3.Connection) -> HTMLResponse:
    n_tracks = con.execute("SELECT COUNT(*) FROM library_tracks").fetchone()[0]
    n_albums = con.execute("SELECT COUNT(*) FROM library_albums").fetchone()[0]
    n_playlists = con.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
    n_artists = con.execute(
        "SELECT COUNT(DISTINCT singer) FROM track_history WHERE singer IS NOT NULL AND singer != ''"
    ).fetchone()[0]

    cards = "".join(
        [
            stat_card("Liked Songs", f"{n_tracks} tracks"),
            stat_card("Liked Albums", f"{n_albums} albums"),
            stat_card("Playlists", f"{n_playlists} playlists"),
            stat_card("Artists", f"{n_artists} artists"),
        ]
    )
    content = f"""
{search_form("/search", "Search for a song or artist…")}
<hr class="divider">
<div class="grid-4">{cards}
</div>
"""
    return page(content)


@router.get(
    "/", response_class=HTMLResponse, status_code=200, description="Home page with stats overview"
)
def home(con: DBDep):
    return home_page(con)
