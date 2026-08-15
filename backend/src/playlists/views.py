import sqlite3
from html import escape, unescape
from urllib.parse import quote

from src.html import can_write_var, card, copy_list_button, grid, page_header, u

from . import service


def playlists_content(
    con: sqlite3.Connection, user_id: int | None, playlist_rules: str | None = None
) -> str:
    pls = service.load_playlists(con, user_id)
    cards_html = "".join(
        card(
            pl["name"],
            f"/{pl['owner_username']}/playlist/{pl['id']}?name={quote(pl['name'])}"
            if pl["owner_username"]
            else u(f"/playlist/{pl['id']}?name={quote(pl['name'])}"),
            f"by @{pl['owner_username']}" if pl["owner_username"] else None,
            f"/{pl['owner_username']}/playlists" if pl["owner_username"] else None,
            image_url=pl["image_url"],
            hover_tooltip=unescape(pl["description"]) if pl["description"] else None,
            raw_cover=True,
        )
        for pl in pls
    )
    export_lines = []
    for pl in pls:
        export_lines.append(pl["name"])
        if pl["description"]:
            export_lines.append(unescape(pl["description"]))
        for t in service.load_playlist_tracks(con, pl["user_id"], pl["id"]):
            export_lines.append(f"  * {t['track_name']} - {t['artist_name']}")
        export_lines.append("")
    header = page_header(
        f"Playlists ({len(pls)})",
        copy_list_button(export_lines, "playlists-list"),
    )
    rules_html = ""
    if user_id is not None and can_write_var.get():
        rules_html = f"""
<form class="description-form" action="{u("/playlists/rules")}" method="post">
  <textarea name="playlist_rules" class="description-input" maxlength="2000" rows="4"
    aria-label="Playlist curation rules"
    placeholder="Curation rules for this page (one per line)…">{escape(playlist_rules or "")}</textarea>
  <button type="submit" class="btn">Save rules</button>
</form>
"""
    elif playlist_rules:
        lines = "".join(f"<li>{escape(line)}</li>" for line in playlist_rules.splitlines() if line)
        rules_html = f'<ul class="subtitle">{lines}</ul>'
    return f"""
{header}
{rules_html}
<hr class="divider">
{grid(cards_html)}
"""
