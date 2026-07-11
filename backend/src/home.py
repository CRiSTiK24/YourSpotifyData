import sqlite3

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.database import DBDep
from src.html import page

router = APIRouter(tags=["home"])


def home_page(con: sqlite3.Connection) -> HTMLResponse:
    n_tracks = con.execute("SELECT COUNT(*) FROM library_tracks").fetchone()[0]
    n_albums = con.execute("SELECT COUNT(*) FROM library_albums").fetchone()[0]
    n_playlists = con.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
    n_artists = con.execute(
        "SELECT COUNT(DISTINCT singer) FROM track_history WHERE singer IS NOT NULL AND singer != ''"
    ).fetchone()[0]

    content = f"""
<h1>🎵 Your Spotify Data</h1>
<form class="search-form" action="/search" method="get">
  <input name="query" type="text" placeholder="Search for a song or artist…" autofocus>
  <button type="submit">Search</button>
</form>
<hr class="divider">
<div class="grid-4">
  <div class="card">
    <h2>💚 Liked Songs</h2>
    <p class="count">{n_tracks} tracks</p>
    <a class="btn" href="/liked-songs">View Liked Songs</a>
  </div>
  <div class="card">
    <h2>💿 Liked Albums</h2>
    <p class="count">{n_albums} albums</p>
    <a class="btn" href="/liked-albums">View Liked Albums</a>
  </div>
  <div class="card">
    <h2>📋 Playlists</h2>
    <p class="count">{n_playlists} playlists</p>
    <a class="btn" href="/playlists">View Playlists</a>
  </div>
  <div class="card">
    <h2>🎤 Artists</h2>
    <p class="count">{n_artists} artists</p>
    <a class="btn" href="/artists">View Artists</a>
  </div>
</div>
"""
    return page(content)


@router.get(
    "/", response_class=HTMLResponse, status_code=200, description="Home page with stats overview"
)
def home(con: DBDep):
    return home_page(con)
