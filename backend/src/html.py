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


_SITE_NAME = "Your Spotify Data"


def _quick_search_widget(id_prefix: str) -> str:
    """Persistent, chrome-embedded live search - the sidebar (desktop) and
    topbar (mobile) each get their own instance of this, since both exist
    in the DOM at once (CSS just hides whichever doesn't apply). Debounced
    hx-get renders results into a dropdown under the input with no page
    navigation; id_prefix keeps the two instances' ids from colliding.
    hx-select is pinned to unset - without it, this input inherits body's
    hx-select="#content", and since the /search fragment response has no
    #content element, that inherited select would silently swap in
    nothing (same failure mode documented on infinite_scroll_trigger)."""
    input_id = f"{id_prefix}-search-input"
    results_id = f"{id_prefix}-search-results"
    return f"""
    <div class="quick-search">
      <input id="{input_id}" class="quick-search-input" type="text" name="query" autocomplete="off"
        placeholder="Search…" aria-label="Search"
        hx-get="/search" hx-trigger="input changed delay:300ms" hx-target="#{results_id}"
        hx-select="unset" hx-swap="innerHTML">
      <div id="{results_id}" class="quick-search-results"></div>
    </div>"""


def page(content: str, title: str = "") -> HTMLResponse:
    # htmx scans the full response body for a <title> tag and applies it to
    # document.title on every boosted navigation, even though hx-select only
    # swaps #content - so this works for both full loads and boosted nav.
    page_title = f"{title} · {_SITE_NAME}" if title else _SITE_NAME
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
    nav_links = """
    <a href="/playlists">See my curated playlists!</a>
    <a href="/liked-albums">Albums I like</a>
    <hr class="sidebar-divider">
    <a href="/most-listened">My most listened</a>"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(page_title)}</title>
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
<body hx-boost="true" hx-target="#content" hx-select="#content" hx-swap="outerHTML transition:true">
<div class="shell">
  <aside class="sidebar">
    <a class="brand" href="/">Home</a>
    <hr class="sidebar-divider">{nav_links}{sidebar_bottom}
  </aside>

  <header class="mobile-topbar">
    <button type="button" class="hamburger-btn" id="hamburger-btn" aria-label="Open menu" aria-expanded="false" aria-controls="mobile-drawer">
      <span></span><span></span><span></span>
    </button>
    {_quick_search_widget("topbar")}
  </header>

  <div class="drawer-overlay" id="drawer-overlay"></div>
  <nav class="mobile-drawer" id="mobile-drawer" aria-label="Main menu">
    <a class="brand" href="/">Home</a>
    <hr class="sidebar-divider">{nav_links}{sidebar_bottom}
  </nav>

  <div class="content-column">
    <header class="desktop-topbar">
      {_quick_search_widget("desktop")}
    </header>
    <main class="content" id="content">
{content}
    </main>
  </div>
</div>
<script src="/static/mobile-nav.js"></script>
<script src="/static/tooltips.js"></script>
<script src="/static/quick-search.js"></script>
<script src="/static/most-listened.js"></script>
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


def _cover_src(image_url: str | None, size: int | None = None, *, raw: bool = False) -> str | None:
    """Every album/artist/playlist cover is served through /cover, which by
    default recolors it into the site's own palette rather than showing
    Spotify's original colors as-is - a single choke point so this applies
    uniformly everywhere a cover image renders. size requests a real
    server-side resize (roughly 2x the CSS display size, for retina)
    instead of shipping the source's full resolution for the browser to
    scale down. raw=True opts a cover out of the recolor (e.g. playlists),
    keeping the source's original colors."""
    if not image_url:
        return None
    src = f"/cover?src={quote(image_url, safe='')}"
    if size:
        src += f"&size={size}"
    if raw:
        src += "&raw=true"
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
    bar sized to that fraction, `note` rendered as a label after it (not
    overlaid on top - a label sitting on top of the fill made the actual
    bar length hard to perceive, since every bar reads at a glance as a
    same-sized pill regardless of fraction) - e.g. a track's play count
    relative to the most-played track in the same list, so the list itself
    reads as a mini bar chart."""
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
            f"<div class='row-bar-wrap'>"
            f"<div class='row-bar'><div class='row-bar-fill' style='width:{fill_pct:.1f}%'></div></div>"
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
    title: str | None = None,
    raw_cover: bool = False,
) -> str:
    """A grid tile: cover art with a title (and optional secondary link, or
    a plain-text note e.g. a play count) below it - the card/grid
    counterpart to row()'s list-item layout, used where cover art benefits
    from more room (liked songs/albums, playlists) than row()'s 32px
    thumbnail affords. `title`, when given, spawns a small tooltip bubble
    above the card on hover (e.g. a playlist's Spotify description) - a
    CSS ::after driven off data-tooltip rather than the native browser
    title attribute, since that one's slow to appear and unstyled. Hover
    never fires on touch, so a `card-info-btn` sibling (shown only on
    devices without hover, via the CSS `(hover: none)` query) toggles the
    same tooltip via a `tooltip-active` class instead - see tooltips.js.
    It's a sibling of card-cover rather than nested inside that anchor so
    tapping it doesn't also trigger the cover's navigation.
    `raw_cover` shows the source image's original colors instead of the
    site-palette recolor applied everywhere else."""
    cover_src = _cover_src(image_url, size=320, raw=raw_cover)
    thumb_class = "card-thumb card-thumb-raw" if raw_cover else "card-thumb"
    thumb = (
        f"<img class='{thumb_class}' src='{escape(cover_src)}' loading='lazy'>"
        if cover_src
        else "<div class='card-thumb card-thumb-empty'></div>"
    )
    secondary = (
        f"<a class='card-secondary' href='{escape(secondary_href)}'>{escape(secondary_label)}</a>"
        if secondary_label and secondary_href
        else ""
    )
    note_html = f"<span class='card-note'>{escape(note)}</span>" if note else ""
    tooltip_attr = f" data-tooltip='{escape(title)}'" if title else ""
    info_btn = (
        "<button type='button' class='card-info-btn' aria-label='Show description'>i</button>"
        if title
        else ""
    )
    return f"""
<div class="card"{tooltip_attr}>
  <a class="card-cover" href="{escape(primary_href)}">{thumb}</a>
  {info_btn}
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


def hero_image(image_url: str | None, *, raw: bool = False) -> str:
    cover_src = _cover_src(image_url, size=320, raw=raw)
    if not cover_src:
        return ""
    cls = "hero-image hero-image-raw" if raw else "hero-image"
    return f"<img class='{cls}' src='{escape(cover_src)}' loading='lazy'>"


def filter_clear_link(label: str, clear_href: str) -> str:
    """"· ‹period label› ×", meant to be appended inline into a detail
    page's existing play-count subtitle line (e.g. "184 total plays ·
    Aug 2026 ×") when a heatmap period is selected - not a separate
    element, so it can't end up positioned somewhere unexpected the way
    an earlier standalone pill/badge version did."""
    return (
        f" &nbsp;·&nbsp; <a class='detail-filter-clear' href='{escape(clear_href)}'>"
        f"{escape(label)} <span class='detail-filter-clear-x'>&times;</span></a>"
    )


def detail_header(title_html: str, meta_html: str, hero_html: str, heatmap_html: str) -> str:
    """Header for track/album/artist/playlist detail pages: title + meta
    (subtitle lines, description) span the full row width on their own
    line, then a second row holds the hero image (fixed size) beside the
    heatmap. Title used to share a row with the image and heatmap side by
    side (see the .detail-header-info column in earlier versions), which
    meant a long title had to negotiate width against the heatmap and
    could end up word-broken. Splitting them onto separate rows means the
    title always gets the full row to itself, and the heatmap - now next
    to only a fixed-width image, no text to negotiate with - can flex to
    fill essentially all the leftover width (see .detail-header-heatmap in
    style.css) instead of guessing a cqw ceiling against how much text
    might be beside it."""
    return f"""
<div class="detail-header-top">
  <div class="detail-header-title">
    {title_html}
    {meta_html}
  </div>
  <div class="detail-header-media">
    {hero_html}
    <div class="detail-header-heatmap">{heatmap_html}</div>
  </div>
</div>"""


def detail_layout(
    header: str,
    list_title: str,
    list_content: str,
    list_id: str = "",
    list_actions: str = "",
) -> str:
    """Single-panel layout used by track/album/artist/playlist detail
    pages: header info (image/title/heatmap drill-down - see
    .detail-header-top) followed by the track/tracks list. Used to be a
    two-panel layout with the heatmap in its own side panel, but the
    heatmap is compact enough now (see build_heatmap_html) to live
    embedded in the header instead of needing a dedicated panel."""
    list_id_attr = f" id='{escape(list_id)}'" if list_id else ""
    return f"""
<div class="detail-layout">
  <div class="panel detail-header">
    {header}
    <hr class="divider">
    <div class="list-title-row">
      <h2>{escape(list_title)}</h2>
      {list_actions}
    </div>
    <div{list_id_attr}>{list_content}</div>
  </div>
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


def lazy_load_trigger(href: str, label: str = "Loading…") -> str:
    """Like infinite_scroll_trigger, but fires immediately on insertion
    (hx-trigger='load') rather than on scroll-into-view - for a section
    that's expensive enough to compute that it shouldn't block the rest of
    the page's first paint. E.g. /most-listened's Albums/Artists columns:
    ranking by play count over 200k+ rows has no shortcut index (there's
    no way to index-sort by an aggregate COUNT(*)), so each one is a real
    ~500-700ms full scan+sort - rendering only the default-visible column
    eagerly and letting the other two turn up moments later via their own
    parallel requests keeps a year-filter change from serially paying for
    all three at once."""
    return (
        f"<p class='info' hx-get='{escape(href)}' hx-trigger='load' hx-target='this' "
        f"hx-select='unset' hx-swap='outerHTML'>{escape(label)}</p>"
    )
