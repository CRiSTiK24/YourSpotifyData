import os
from contextvars import ContextVar
from html import escape
from urllib.parse import quote

from fastapi.responses import HTMLResponse

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "static"
)

# Set by auth middleware for the duration of each request, so `page()` can
# render the right nav links without every route having to pass auth state
# through explicitly.
logged_in_var: ContextVar[bool] = ContextVar("logged_in", default=False)


def page(content: str) -> HTMLResponse:
    if logged_in_var.get():
        sidebar_bottom = """
    <div class="sidebar-bottom">
      <a href="/upload">Upload</a>
      <a href="/scrobbler">Scrobbler</a>
      <a href="/theme">Theme</a>
    </div>"""
    else:
        sidebar_bottom = """
    <div class="sidebar-bottom">
      <a href="/login">Login</a>
    </div>"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title></title>
  <link rel="stylesheet" href="/static/style.css">
  <script>
  (function () {{
    try {{
      var overrides = JSON.parse(localStorage.getItem("theme-overrides") || "{{}}");
      for (var key in overrides) document.documentElement.style.setProperty(key, overrides[key]);
    }} catch (e) {{}}
  }})();
  </script>
  <script src="https://unpkg.com/htmx.org@2.0.4" integrity="sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+" crossorigin="anonymous"></script>
</head>
<body hx-boost="true" hx-target="#content" hx-select="#content" hx-swap="outerHTML">
<div class="shell">
  <aside class="sidebar">
    <a class="brand" href="/">Home</a>
    <a href="/liked-songs">Liked Songs</a>
    <a href="/liked-albums">Liked Albums</a>
    <a href="/playlists">Playlists</a>
    <a href="/artists">Artists</a>{sidebar_bottom}
  </aside>
  <main class="content" id="content">
{content}
  </main>
</div>
</body>
</html>"""
    return HTMLResponse(html)


def link(label: str, href: str) -> str:
    return f"<a href='{escape(href)}'>{escape(label)}</a>"


def button(label: str, href: str, *, hx_boost: bool | None = None) -> str:
    boost_attr = f" hx-boost='{'true' if hx_boost else 'false'}'" if hx_boost is not None else ""
    return f"<a class='btn' href='{escape(href)}'{boost_attr}>{escape(label)}</a>"


def copy_list_button(lines: list[str], element_id: str, label: str = "Copy List") -> str:
    """Renders the given lines as a hidden <pre> block plus a button that
    copies its text to the clipboard - used on the liked songs/albums/
    playlists pages to let a user grab the full list as plain text (one
    "Title - Artist" per line) in one click. escape() handles the HTML
    escaping, so no extra escaping is needed for the <pre> body itself."""
    text = "\n".join(lines)
    id_esc = escape(element_id)
    label_esc = escape(label)
    return f"""
<pre id="{id_esc}" style="display:none">{escape(text)}</pre>
<button type="button" class="btn" onclick="navigator.clipboard.writeText(document.getElementById('{id_esc}').textContent).then(() => {{ this.textContent = 'Copied!'; setTimeout(() => {{ this.textContent = '{label_esc}'; }}, 1500); }})">{label_esc}</button>"""


def page_header(title: str, actions: str = "") -> str:
    return f"""
<div class="page-header">
  <h1>{escape(title)}</h1>
  {actions}
</div>"""


def search_form(
    action: str,
    placeholder: str,
    *,
    value: str = "",
    autofocus: bool = True,
    name: str = "query",
    hx_target: str = "#content",
    hx_select: str = "#content",
    hx_swap: str = "outerHTML",
    hx_push_url: bool = True,
) -> str:
    autofocus_attr = " autofocus" if autofocus else ""
    value_attr = f" value='{escape(value)}'" if value else ""
    action_esc = escape(action)
    push_url = "true" if hx_push_url else "false"
    return f"""
<form class="search-form" action="{action_esc}" method="get" autocomplete="off">
  <input id="live-search-input" name="{escape(name)}" type="text" autocomplete="off"{value_attr} placeholder="{escape(placeholder)}"{autofocus_attr}
    onkeydown="if(event.key==='Enter'){{event.preventDefault();}}"
    hx-get="{action_esc}" hx-trigger="input changed delay:300ms" hx-target="{escape(hx_target)}"
    hx-select="{escape(hx_select)}" hx-swap="{escape(hx_swap)}" hx-push-url="{push_url}" hx-preserve="true">
</form>"""


def _cover_src(image_url: str | None, size: int | None = None) -> str | None:
    """Every album/artist/playlist cover is served through /cover, which
    recolors it into the site's own palette rather than showing Spotify's
    original colors as-is - a single choke point so this applies uniformly
    everywhere a cover image renders. size requests a real server-side
    resize (roughly 2x the CSS display size, for retina) instead of
    shipping the source's full resolution for the browser to scale down."""
    if not image_url:
        return None
    src = f"/cover?src={quote(image_url, safe='')}"
    if size:
        src += f"&size={size}"
    return src


def row(
    primary_label: str,
    primary_href: str,
    secondary_label: str | None = None,
    secondary_href: str | None = None,
    note: str | None = None,
    *,
    image_url: str | None = None,
    bar_fraction: float | None = None,
) -> str:
    """bar_fraction (0.0-1.0) replaces the plain `note` text with a filled
    bar sized to that fraction, with `note` rendered as a label inside it -
    e.g. a track's play count relative to the most-played track in the same
    list, so the list itself reads as a mini bar chart."""
    cover_src = _cover_src(image_url, size=64)
    thumb = f"<img class='row-thumb' src='{escape(cover_src)}' loading='lazy'>" if cover_src else ""
    left = f"<a class='row-primary' href='{escape(primary_href)}'>{escape(primary_label)}</a>"
    if secondary_label and secondary_href:
        left += (
            f" <span class='sep'>—</span> "
            f"<a class='row-secondary' href='{escape(secondary_href)}'>{escape(secondary_label)}</a>"
        )
    if bar_fraction is not None:
        fill_pct = max(0.0, min(1.0, bar_fraction)) * 100
        label = f"<span class='row-bar-label'>{escape(note)}</span>" if note else ""
        right = (
            f"<div class='row-bar'><div class='row-bar-fill' style='width:{fill_pct:.1f}%'></div>"
            f"{label}</div>"
        )
    else:
        right = f"<span class='note'>{escape(note)}</span>" if note else ""
    return f"<div class='row'><div class='left'>{thumb}{left}</div>{right}</div>"


def card(
    primary_label: str,
    primary_href: str,
    secondary_label: str | None = None,
    secondary_href: str | None = None,
    note: str | None = None,
    *,
    image_url: str | None = None,
) -> str:
    """A grid tile: cover art with a title (and optional secondary link, or
    a plain-text note e.g. a play count) below it - the card/grid
    counterpart to row()'s list-item layout, used where cover art benefits
    from more room (liked songs/albums, playlists) than row()'s 32px
    thumbnail affords."""
    cover_src = _cover_src(image_url, size=320)
    thumb = (
        f"<img class='card-thumb' src='{escape(cover_src)}' loading='lazy'>"
        if cover_src
        else "<div class='card-thumb card-thumb-empty'></div>"
    )
    secondary = (
        f"<a class='card-secondary' href='{escape(secondary_href)}'>{escape(secondary_label)}</a>"
        if secondary_label and secondary_href
        else ""
    )
    note_html = f"<span class='card-note'>{escape(note)}</span>" if note else ""
    return f"""
<div class="card">
  <a class="card-cover" href="{escape(primary_href)}">{thumb}</a>
  <a class="card-title" href="{escape(primary_href)}">{escape(primary_label)}</a>
  {secondary}
  {note_html}
</div>"""


def grid(cards_html: str, *, compact: bool = False) -> str:
    """compact uses a smaller minimum tile size (see .grid-compact in
    style.css) - for grids inside a detail page's narrower side panel,
    where the full-size grid's minimum column width would collapse to a
    single oversized column instead of actually filling the space."""
    cls = "grid grid-compact" if compact else "grid"
    return f"<div class='{cls}'>{cards_html}</div>"


def hero_image(image_url: str | None) -> str:
    cover_src = _cover_src(image_url, size=320)
    if not cover_src:
        return ""
    return f"<img class='hero-image' src='{escape(cover_src)}' loading='lazy'>"


def detail_layout(
    header: str, heatmap: str, list_title: str, list_content: str, list_id: str = ""
) -> str:
    """Two-panel layout used by track/album/artist/playlist detail pages:
    header info + list on the left, heatmap on the right."""
    list_id_attr = f" id='{escape(list_id)}'" if list_id else ""
    return f"""
<div class="detail-layout">
  <div class="panel detail-header">
    {header}
    <hr class="divider">
    <h2>{escape(list_title)}</h2>
    <div{list_id_attr}>{list_content}</div>
  </div>
  <div class="panel detail-heatmap">{heatmap}</div>
</div>"""


def infinite_scroll_trigger(next_href: str) -> str:
    """A sentinel element that fetches the next batch when scrolled into
    view, replacing itself with the response (more rows + a fresh sentinel,
    or nothing once there's no more data).

    Uses "intersect once" (IntersectionObserver-backed) rather than
    "revealed", since "revealed" only listens for the window's own scroll
    event, so it never fires when the scrolling happens inside a nested
    `overflow: auto` panel (e.g. detail pages' capped-height panels) rather
    than the page itself. "intersect" doesn't care which element scrolled.

    hx-target/hx-select are pinned to itself and unset, since without this
    it inherits hx-target="#content" / hx-select="#content" from <body> (the
    nearest ancestor that sets them, since this sentinel isn't a descendant
    of the search input that overrides those), and since its own response
    has no #content element, that inherited select-and-swap wipes the
    entire page content out."""
    return (
        f"<div hx-get='{escape(next_href)}' hx-trigger='intersect once' hx-target='this' "
        f"hx-select='unset' hx-swap='outerHTML'></div>"
    )


def pagination_html(current_page: int, total_pages: int, base_href: str, param: str) -> str:
    if total_pages <= 1:
        return ""
    half = 4
    p_start = max(1, current_page - half)
    p_end = min(total_pages, p_start + 8)
    p_start = max(1, p_end - 8)
    sep = "&" if "?" in base_href else "?"
    links = []
    if current_page > 1:
        links.append(f"<a href='{base_href}{sep}{param}={current_page - 1}'>‹</a>")
    for p in range(p_start, p_end + 1):
        if p == current_page:
            links.append(f"<span class='current'>{p}</span>")
        else:
            links.append(f"<a href='{base_href}{sep}{param}={p}'>{p}</a>")
    if current_page < total_pages:
        links.append(f"<a href='{base_href}{sep}{param}={current_page + 1}'>›</a>")
    links.append(f"<span class='pg-info'>Page {current_page} of {total_pages}</span>")
    return f"<div class='pagination'>{''.join(links)}</div>"


def paginate(items: list, current_page: int, page_size: int = 25) -> tuple[list, int, int]:
    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    current_page = max(1, min(current_page, total_pages))
    start = (current_page - 1) * page_size
    return items[start : start + page_size], current_page, total_pages
