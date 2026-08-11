import logging
from html import escape, unescape
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.service import require_auth
from src.database import DBDep
from src.heatmap import build_heatmap_html, resolve_period_filter
from src.html import (
    card,
    copy_list_button,
    detail_header,
    detail_layout,
    grid,
    hero_image,
    logged_in_var,
    page,
)
from src.scrobbler import library_sync as library_sync_service
from src.scrobbler.exceptions import NotConnected
from src.utils import aggregate_plays, pluralize

from . import service
from .exceptions import PlaylistNotFound
from .views import playlists_content

router = APIRouter(tags=["playlists"])
logger = logging.getLogger("playlists")


@router.get("/playlists", response_class=HTMLResponse, status_code=200, description="All playlists")
def playlists(con: DBDep):
    return page(playlists_content(con), title="Playlists")


@router.post(
    "/playlist/{playlist_id}/description",
    status_code=302,
    description="Edit a playlist's description and push it to Spotify (logged-in only)",
    dependencies=[Depends(require_auth)],
)
def update_description(playlist_id: int, con: DBDep, description: str = Form(""), name: str = ""):
    playlist = service.get_playlist(con, playlist_id)
    if playlist is None:
        raise PlaylistNotFound(playlist_id)

    description = description.strip()
    if playlist["spotify_playlist_id"]:
        try:
            library_sync_service.set_playlist_description_via_spotify_api(
                con, playlist["spotify_playlist_id"], description
            )
            saved = "ok"
        except NotConnected:
            saved = "not_connected"
        except Exception:
            logger.exception("failed pushing playlist %s description to Spotify", playlist_id)
            saved = "error"
    else:
        saved = "unlinked"
    service.set_local_description(con, playlist_id, description)
    return RedirectResponse(
        url=f"/playlist/{playlist_id}?name={quote(name)}&saved={saved}", status_code=302
    )


@router.get(
    "/playlist/{playlist_id}",
    response_class=HTMLResponse,
    status_code=200,
    description="Playlist detail with play history",
)
def playlist_detail(
    playlist_id: int, request: Request, con: DBDep, name: str = "", saved: str = ""
):
    playlist = service.get_playlist(con, playlist_id)
    if playlist is None:
        raise PlaylistNotFound(playlist_id)

    tracks = service.load_playlist_tracks(con, playlist_id)
    history = service.load_playlist_history_with_album_for_cover_lookup(con, playlist_id)

    heatmap_html, result, base_href = build_heatmap_html(
        history, f"playlist_{playlist_id}", request
    )

    plays, play_count, filter_clear_html = resolve_period_filter(history, result, base_href)
    if result:
        aggregated = aggregate_plays(plays)
        album_by_name: dict[str, tuple[str, str]] = {}
        for p in plays:
            if p.get("album") and p.get("singer"):
                album_by_name.setdefault(p["name"], (p["singer"], p["album"]))
        images = service.cover_images_for_artist_album_pairs(con, set(album_by_name.values()))
        tracks_html = grid(
            "".join(
                card(
                    n,
                    f"/track/{quote(n)}?artist={quote(s or '')}",
                    s,
                    f"/artist/{quote(s)}" if s else None,
                    note=str(c),
                    image_url=images.get(album_by_name.get(n)),
                    preview_artist=s,
                )
                for n, s, c in aggregated
            ),
            compact=True,
        )
    else:
        tracks_html = grid(
            "".join(
                card(
                    t["track_name"],
                    f"/track/{quote(t['track_name'])}?artist={quote(t['artist_name'])}",
                    t["artist_name"],
                    f"/artist/{quote(t['artist_name'])}",
                    image_url=t["image_url"],
                    preview_artist=t["artist_name"],
                )
                for t in tracks
            ),
            compact=True,
        )

    save_notes = {
        "ok": "Saved to Spotify.",
        "not_connected": "Saved locally, but Spotify isn't connected — connect it on the Scrobbler page to sync edits.",
        "unlinked": "Saved locally — this playlist has no linked Spotify ID (imported from a GDPR export, not the live API sync), so it can't be pushed.",
        "error": "Saved locally, but pushing to Spotify failed — check server logs.",
    }
    save_note_html = (
        f"<p class='subtitle'>{escape(save_notes[saved])}</p>" if saved in save_notes else ""
    )
    description_line = unescape(playlist["description"]) if playlist["description"] else ""
    if logged_in_var.get():
        description_html = f"""
<form class="description-form" action="/playlist/{playlist_id}/description?name={quote(name)}" method="post">
  <textarea name="description" class="description-input" maxlength="300"
            placeholder="Add a description…">{escape(description_line)}</textarea>
  <button type="submit" class="btn">Save description</button>
</form>
{save_note_html}
"""
    else:
        description_html = (
            f"<p class='subtitle'>{escape(description_line)}</p>" if description_line else ""
        )

    export_lines = (
        [name]
        + ([description_line] if description_line else [])
        + [""]
        + [f"* {t['track_name']} - {t['artist_name']}" for t in tracks]
    )
    spotify_link_html = (
        f"<a class='btn' style='margin-left:auto' "
        f"href='https://open.spotify.com/playlist/{escape(playlist['spotify_playlist_id'])}' "
        "target='_blank' rel='noopener noreferrer'>Open in Spotify</a>"
        if playlist["spotify_playlist_id"]
        else ""
    )
    title_html = f"<h1>{escape(name)}</h1>"
    tracks_actions_html = (
        copy_list_button(export_lines, f"playlist-{playlist_id}-list") + spotify_link_html
    )

    meta_html = (
        f"{description_html}"
        f"<p class='subtitle'>{pluralize(len(tracks), 'track')} "
        f"&nbsp;·&nbsp; {pluralize(play_count, 'play')}{filter_clear_html}</p>"
    )
    header = detail_header(
        title_html,
        meta_html,
        hero_image(playlist["image_url"], raw=True),
        heatmap_html,
    )
    return page(
        detail_layout(header, "Tracks", tracks_html, list_actions=tracks_actions_html),
        title=name,
    )
