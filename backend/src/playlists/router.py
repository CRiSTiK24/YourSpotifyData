import logging
from html import escape, unescape
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.service import require_auth
from src.database import DBDep
from src.heatmap import build_heatmap_html, period_label
from src.html import (
    card,
    copy_list_button,
    detail_header,
    detail_layout,
    filter_clear_link,
    grid,
    hero_image,
    logged_in_var,
    page,
)
from src.scrobbler import service as scrobbler_service
from src.scrobbler.exceptions import NotConnected
from src.utils import aggregate_plays

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
    if not service.playlist_exists(con, playlist_id):
        raise PlaylistNotFound(playlist_id)

    playlist = service.get_playlist(con, playlist_id)
    description = description.strip()
    if playlist and playlist["spotify_playlist_id"]:
        try:
            scrobbler_service.update_playlist_description(
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
    service.set_description(con, playlist_id, description)
    return RedirectResponse(
        url=f"/playlist/{playlist_id}?name={quote(name)}&saved={saved}", status_code=302
    )


@router.get(
    "/playlist/{playlist_id}",
    response_class=HTMLResponse,
    status_code=200,
    description="Playlist detail with play history",
)
def playlist_detail(playlist_id: int, request: Request, con: DBDep, name: str = "", saved: str = ""):
    if not service.playlist_exists(con, playlist_id):
        raise PlaylistNotFound(playlist_id)

    tracks = service.load_playlist_tracks(con, playlist_id)
    history = service.load_playlist_history(con, playlist_id)

    heatmap_html, result, base_href = build_heatmap_html(
        history, f"playlist_{playlist_id}", request
    )

    filter_clear_html = ""
    if result:
        _, _, _, plays = result
        label = period_label(result)
        aggregated = aggregate_plays(plays)
        filter_clear_html = filter_clear_link(label, base_href)
        play_count = len(plays)
        # Same card-grid layout as the unfiltered view below (not row()'s
        # plain-text list) - picking a period should narrow which tracks
        # show, not change how they're displayed. Cover art needs its own
        # lookup here since plays isn't pre-joined against album_images.
        album_by_name: dict[str, tuple[str, str]] = {}
        for p in plays:
            if p.get("album") and p.get("singer"):
                album_by_name.setdefault(p["name"], (p["singer"], p["album"]))
        images = service.images_for_tracks(con, set(album_by_name.values()))
        tracks_html = grid(
            "".join(
                card(
                    n,
                    f"/track/{quote(n)}?artist={quote(s or '')}",
                    s,
                    f"/artist/{quote(s)}" if s else None,
                    note=f"×{c}",
                    image_url=images.get(album_by_name.get(n)),
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
                )
                for t in tracks
            ),
            compact=True,
        )
        play_count = len(history)

    playlist = service.get_playlist(con, playlist_id)
    save_notes = {
        "ok": "Saved to Spotify.",
        "not_connected": "Saved locally, but Spotify isn't connected — connect it on the Scrobbler page to sync edits.",
        "unlinked": "Saved locally — this playlist has no linked Spotify ID (imported from a GDPR export, not the live API sync), so it can't be pushed.",
        "error": "Saved locally, but pushing to Spotify failed — check server logs.",
    }
    save_note_html = (
        f"<p class='subtitle'>{escape(save_notes[saved])}</p>" if saved in save_notes else ""
    )
    if logged_in_var.get():
        description_html = f"""
<form class="description-form" action="/playlist/{playlist_id}/description?name={quote(name)}" method="post">
  <textarea name="description" class="description-input" maxlength="300"
            placeholder="Add a description…">{escape(unescape(playlist["description"] or "")) if playlist else ""}</textarea>
  <button type="submit" class="btn">Save description</button>
</form>
{save_note_html}
"""
    else:
        description_html = (
            f"<p class='subtitle'>{escape(unescape(playlist['description']))}</p>"
            if playlist and playlist["description"]
            else ""
        )

    description_line = (
        unescape(playlist["description"]) if playlist and playlist["description"] else ""
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
        if playlist and playlist["spotify_playlist_id"]
        else ""
    )
    title_html = f"<h1>{escape(name)}</h1>"
    tracks_actions_html = copy_list_button(export_lines, f"playlist-{playlist_id}-list") + spotify_link_html

    meta_html = (
        f"{description_html}"
        f"<p class='subtitle'>{len(tracks)} track{'s' if len(tracks) != 1 else ''} "
        f"&nbsp;·&nbsp; {play_count} play{'s' if play_count != 1 else ''}{filter_clear_html}</p>"
    )
    header = detail_header(
        title_html,
        meta_html,
        hero_image(playlist["image_url"] if playlist else None, raw=True),
        heatmap_html,
    )
    return page(
        detail_layout(header, "Tracks", tracks_html, list_actions=tracks_actions_html),
        title=name,
    )
