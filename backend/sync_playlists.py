"""Manually trigger a one-off library sync (playlists, liked songs/albums, followed artists).

Usage: run from backend/ with the same env/venv as the app: python sync_playlists.py
"""

from src.database import get_connection
from src.scrobbler import library_sync

if __name__ == "__main__":
    con = get_connection()
    try:
        library_sync.ensure_migrations(con)
        counts = library_sync.sync_once(con)
        print(counts)
    finally:
        con.close()
